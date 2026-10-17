"""Bounded self-test of a passive TB monitor, never a Pro DUT execution."""
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

SOFT = Path(__file__).resolve().parent
ROOT = SOFT.parents[4]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017"
TB = ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017"
TOOLS = Path("E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy")
JOB = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
TARGETS = {1:"REQUEST_NOT_HELD",2:"REQUEST_NOT_HELD",3:"RESULT_ID",4:"RESULT_NOT_HELD",
           5:"DUPLICATE_LANE",6:"RESULT_BEFORE_FOUR_LANES",7:"RESULT_WITHOUT_REQUEST",
           8:"RESULT_WITHOUT_REQUEST",9:"REQUEST_DEADLINE",10:"FRAME_INTERVAL",
           11:"FRAME_AVERAGE_DRIFT",12:"PA_BEFORE_SAFE",13:"PA_BEFORE_SAFE",
           14:"PA_DURING_RESET",15:"END_UNCLOSED",16:"COMMIT_ID_PCM_CLIP",
           17:"DUPLICATE_RESULT_TRANSFER",18:"DUPLICATE_REQUEST_ID",19:"LANE_OWNER",
           20:"RESULT_UNKNOWN",21:"REQUEST_DEADLINE",22:"REQUEST_DEADLINE"}


def identity(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--round", type=int, required=True, choices=(1,2,3))
    args=parser.parse_args()
    repair = DOC/f"REPAIR_{args.round:02d}.md"
    if any(json.loads(p.read_text(encoding="utf-8")).get("passed")
           for p in DOC.glob("ROUND_*/RECEIPT.json")) and not (args.round>1 and repair.is_file()):
        raise SystemExit("Prior success: stop; a new concrete defect requires a repair note")
    if args.round>1 and not repair.is_file():
        raise SystemExit("Concrete repair note required")
    out=DOC/f"ROUND_{args.round:02d}";out.mkdir(exist_ok=False)
    stage=out/"stage";stage.mkdir()
    sources=[TB/"pro_frame_monitor.sv",TB/"tb_pro_frame_monitor.sv",SOFT/"run.py",JOB,DOC/"WORK_PLAN.md"]
    source_before=[identity(p) for p in sources]
    tool_paths=[p for p in TOOLS.rglob("*") if p.is_file()]
    pyroot=Path(sys.executable).parent
    tool_paths += [Path(sys.executable),pyroot/"Lib/subprocess.py",pyroot/"DLLs/_ctypes.pyd"]
    tool_paths += list(pyroot.glob("python*.dll"))+list(pyroot.glob("vcruntime*.dll"))
    tools_before=[identity(p) for p in sorted(set(tool_paths))]
    freeze=out/"sources";freeze.mkdir()
    for p in sources:shutil.copyfile(p,freeze/p.name)
    for p in sources[:2]:shutil.copyfile(p,stage/p.name)
    save(out/"BEFORE.json",{"source":source_before,"tools":tools_before})
    spec=importlib.util.spec_from_file_location("pro_owned_job",JOB)
    jobmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(jobmod)
    env=dict(os.environ);env["PYTHONDONTWRITEBYTECODE"]="1"
    env["IVERILOG_ROOT"]=str(TOOLS/"lib/ivl")
    pathkey=next((k for k in env if k.upper()=="PATH"),"PATH")
    env[pathkey]=str(TOOLS/"bin")+os.pathsep+str(TOOLS/"lib")+os.pathsep+env.get(pathkey,"")
    save(out/"ENVIRONMENT.json",{k:env[k] for k in (pathkey,"IVERILOG_ROOT","PYTHONDONTWRITEBYTECODE","SystemRoot") if k in env})
    began=time.monotonic();calls=[];error=None;positive=None
    start=datetime.now(timezone.utc).isoformat()
    def call(label, argv, expected):
        remaining=240-(time.monotonic()-began)
        if remaining<=0:raise ValueError("GROUP_DEADLINE")
        rec={"label":label,"argv":list(map(str,argv)),"cwd":str(stage),"start_utc":datetime.now(timezone.utc).isoformat(),
             "timeout_s":remaining,"expected_exit":expected,"exit_code":None,"timeout":False}
        save(out/(label+".launch.json"),rec)
        timer=time.monotonic();job=jobmod.WindowsJob()
        try:
            with (out/(label+".stdout.bin")).open("xb") as stdout,(out/(label+".stderr.bin")).open("xb") as stderr:
                if label=="compile":save(out/"CONSUMED.json",{"new_monitor_round":args.round,"old_package_quotas_changed":False})
                proc=subprocess.Popen(list(map(str,argv)),cwd=stage,env=env,stdin=subprocess.DEVNULL,
                                      stdout=stdout,stderr=stderr,creationflags=0x00000004)
                rec["pid"]=proc.pid;job.attach_and_resume(proc)
                try:rec["exit_code"]=proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    rec["timeout"]=True;job.terminate();rec["exit_code"]=proc.wait(timeout=5)
        finally:
            job.close();rec["seconds"]=time.monotonic()-timer
            rec["end_utc"]=datetime.now(timezone.utc).isoformat()
            rec["stdout"]=identity(out/(label+".stdout.bin"));rec["stderr"]=identity(out/(label+".stderr.bin"))
            calls.append(rec);save(out/(label+".receipt.json"),rec)
        if rec["timeout"] or rec["exit_code"]!=expected:raise ValueError("PROCESS_EXIT:"+label)
        return Path(rec["stdout"]["path"]).read_bytes().decode("utf-8",errors="strict")
    try:
        call("python_version",[sys.executable,"--version"],0)
        call("iverilog_version",[TOOLS/"bin/iverilog.exe","-V"],0)
        call("vvp_version",[TOOLS/"bin/vvp.exe","-V"],0)
        binary=stage/"monitor.vvp"
        call("compile",[TOOLS/"bin/iverilog.exe","-g2012","-Wall","-s","tb_pro_frame_monitor","-o",binary,
                        stage/"pro_frame_monitor.sv",stage/"tb_pro_frame_monitor.sv"],0)
        for fault in [0,23,24,*TARGETS]:
            capture=out/f"case_{fault:02d}.csv"
            text=call(f"case_{fault:02d}",[TOOLS/"bin/vvp.exe",binary,f"+FAULT={fault}","+TRACE="+str(capture)],0 if fault in (0,23,24) else 1)
            if fault==0:
                assert text.count("PASS PRO_MONITOR_SELFTEST_ONLY")==1 and "FIRST_REJECT" not in text
                assert "MONITOR_END accepts=8 commits=6 cancels=2" in text
                with capture.open(encoding="utf-8",newline="") as stream: rows=list(csv.DictReader(stream))
                assert all(int(row["cycle"])==i+1 for i,row in enumerate(rows))
                accepted=[r for r in rows if r["rst_n"]=="1" and r["cancel"]=="0" and r["req_valid"]==r["req_ready"]=="1"]
                committed=[r for r in rows if r["commit"]=="1"]
                assert len(accepted)==8 and len(committed)==6
                assert [(int(r["epoch"]),r["req_id"]) for r in accepted]==[(0,"fffffffe"),(0,"ffffffff"),(0,"00000000"),(0,"00000001"),(0,"00000002"),(0,"00000003"),(1,"00000000"),(1,"00000001")]
                positive={"raw_rows":len(rows),"accepted":8,"committed":6,"canceled":2,"epochs":2,
                          "capture":identity(capture),"scope":"SYNTHETIC_MONITOR_SELFTEST_NOT_PRO_DUT"}
            elif fault in (23,24):
                assert text.count("PASS PRO_MONITOR_BOUNDARY_SELFTEST_ONLY")==1 and "FIRST_REJECT" not in text
                with capture.open(encoding="utf-8",newline="") as stream: rows=list(csv.DictReader(stream))
                accepted=next(r for r in rows if r["req_valid"]==r["req_ready"]=="1")
                cleanup=next(r for r in rows if int(r["cycle"])>int(accepted["cycle"]) and
                             (r["cancel"]=="1" if fault==23 else r["rst_n"]=="0"))
                assert int(cleanup["cycle"])-int(accepted["cycle"])==832
            else:
                assert re.findall(r"^FIRST_REJECT (\w+) ",text,re.M)==[TARGETS[fault]]
                assert "PRO_FRAME_MONITOR_REJECT" in text and "FAULT_ESCAPED" not in text and "SELFTEST_TIMEOUT" not in text
                with capture.open(encoding="utf-8",newline="") as stream: rows=list(csv.DictReader(stream))
                rejected_cycle=int(re.search(r"^FIRST_REJECT \w+ cycle=(\d+)",text,re.M)[1])
                assert all(int(row["cycle"])==i+1 for i,row in enumerate(rows))
                assert int(rows[-1]["cycle"])==rejected_cycle
        passed=True
    except Exception as exc:
        passed=False;error=repr(exc)
    source_after=[identity(p) for p in sources]
    tools_after=[identity(p) for p in sorted(set(tool_paths))]
    stable=source_after==source_before and tools_after==tools_before
    passed=passed and stable
    receipt={"passed":passed,"error":error,"identity_stable":stable,"round":args.round,"new_round_limit":3,
             "start_utc":start,"end_utc":datetime.now(timezone.utc).isoformat(),"seconds":time.monotonic()-began,
             "machine":platform.node(),"python_version":sys.version,"calls":calls,"positive":positive,
             "negative_targets":TARGETS,"source_before":source_before,"source_after":source_after,
             "tool_file_count":len(tools_before),"tools_after_same":tools_after==tools_before,
             "actual_level":"L2_MONITOR_SELFTEST_ONLY" if passed else "PARTIAL",
             "pro_dut_pass":False,"board_release_allowed":False,"ModelSim_Gowin_device_calls":0}
    save(out/"RECEIPT.json",receipt)
    print(json.dumps({k:receipt[k] for k in ("passed","error","round","seconds","identity_stable","positive")},ensure_ascii=False))
    return 0 if passed else 1


if __name__=="__main__":raise SystemExit(main())
