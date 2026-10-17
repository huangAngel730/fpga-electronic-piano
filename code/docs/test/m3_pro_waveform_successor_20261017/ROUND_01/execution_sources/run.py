"""E2 exclusive bounded runner. No legacy test, EDA, hardware or Git write."""
import argparse
from datetime import datetime, timezone
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

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TOOLS = Path("E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy")
JOB = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
AUTH = Path("E:/FPGA/GAOYUNFPGA/night_task/10.17/M3_四项完整拓展主责任务单_2026-10-17 (1).md")
RTL = ROOT / "code/rtl/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017/m3_pro_fixed_left_waveform.sv"
TB = ROOT / "code/tb/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017/tb_pro_fixed_left_waveform.sv"
ORIGINALS = ["code/rtl/common/reset_sync.sv", "code/rtl/common/visual_mailbox_cdc.sv",
    "code/rtl/common/pcm_waveform_observer_candidate/pcm_frame_observer.sv",
    "code/rtl/common/pcm_waveform_observer_candidate/pcm_waveform_observer_bridge.sv",
    "code/rtl/input/pcm_waveform_candidate/pcm_waveform_candidate.sv"]
EXPECTED = {1:"PIXEL_REFERENCE",2:"WINDOW_FRAME_TEAR",3:"SAMPLE_SEQ_GAP",
            4:"RESET_TRACE_STALE",5:"AUDIO_DISPLAY_BACKPRESSURE"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities(paths):
    return {str(p): {"bytes": p.stat().st_size,"sha256": sha(p)} for p in sorted(set(paths))}


def write(path, value):
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(value,stream,indent=2)
        stream.write("\n")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--preflight",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve()
    if out.parent!=HERE or not out.name.startswith("PREFLIGHT_" if args.preflight else "ROUND_"):
        parser.error("EXCLUSIVE_NEW_OUTPUT_REQUIRED")
    previous=list(HERE.glob("ROUND_*/CONSUMED.json"))
    candidate=identities([RTL,TB,HERE/"prepare.py",HERE/"check_capture.py",Path(__file__).resolve()])
    if not args.preflight:
        if len(previous)>=6 or any(json.loads(p.read_text(encoding="utf-8"))["candidate"]==candidate for p in previous):
            parser.error("SIX_ROUND_LIMIT_OR_IDENTICAL_SOURCE_RETRY")
        if any(json.loads(p.read_text(encoding="utf-8")).get("passed") for p in HERE.glob("ROUND_*/RUN_RECEIPT.json")):
            parser.error("SUCCESS_ALREADY_REACHED_STOP")
    out.mkdir(exist_ok=False)
    sources=[ROOT/p for p in ORIGINALS]+[RTL,TB]
    pyroot=Path(sys.executable).parent
    dependencies=list(pyroot.glob("python*.dll"))+list(pyroot.glob("vcruntime*.dll"))
    dependencies+=list((pyroot/"Lib/ctypes").glob("*.py"))
    dependencies+=[pyroot/"DLLs/_ctypes.pyd",pyroot/"Lib/subprocess.py"]
    tool_files=[p for p in TOOLS.rglob("*") if p.is_file()]+[Path(sys.executable)]+dependencies
    inputs=sources+[JOB,AUTH,Path(__file__).resolve(),HERE/"START.md",HERE/"prepare.py",HERE/"check_capture.py",
        ROOT/"code/tb/input/pcm_waveform_candidate/reference.py",ROOT/"code/tb/input/pcm_waveform_candidate/tb_waveform.sv",
        ROOT/"code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence/raw_manifest.json",
        ROOT/"code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence/normal_capture.b64",
        ROOT/"code/docs/M3_HDMI真实PCM波形_接口与独立任务单_2026-10-07.md",
        ROOT/"code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/NIGHT_PLAN_20261017_TASK2.md"]
    if not args.preflight:
        inputs += [HERE/n for n in ("catalogue.mem","golden.mem","INPUT_IDENTITY.json","normal_capture.original.txt")]
    before={"inputs":identities(inputs),"tools":identities(tool_files)}
    write(out/"before.json",before)
    if sha(AUTH)!="b8e6372b7cd9261f276247754a8f2f9bc8841c31344edc3116a78827d964ed0e":
        raise RuntimeError("AUTH_IDENTITY_CHANGED")
    if not args.preflight:
        preflight=json.loads((HERE/"PREFLIGHT_01/RUN_RECEIPT.json").read_text(encoding="utf-8"))
        if not preflight["passed"] or preflight["before"]["tools"]!=before["tools"]:
            raise RuntimeError("PREFLIGHT_TOOL_IDENTITY_DRIFT")
    work=out/"stage";work.mkdir()
    frozen=out/"execution_sources";frozen.mkdir()
    staged=[]
    for n,path in enumerate(sources):
        target=work/f"s{n:02d}.sv";shutil.copyfile(path,target)
        assert sha(path)==sha(target)
        staged.append(target)
    for path in inputs:
        target=frozen/path.name
        if target.exists():
            raise RuntimeError("FREEZE_FILENAME_COLLISION")
        shutil.copyfile(path,target)
    if not args.preflight:
        for name in ("catalogue.mem","golden.mem"):
            shutil.copyfile(HERE/name,work/name)
    env={k:os.environ[k] for k in ("SystemRoot","WINDIR","COMSPEC","OS","PROCESSOR_ARCHITECTURE",
        "NUMBER_OF_PROCESSORS","USERPROFILE","HOMEDRIVE","HOMEPATH") if k in os.environ}
    env.update(PATH=os.pathsep.join([str(TOOLS/"bin"),str(TOOLS/"lib"),str(Path(os.environ["SystemRoot"])/"System32"),os.environ["SystemRoot"]]),
        IVERILOG_ROOT=str(TOOLS/"lib/ivl"),TEMP=str(out),TMP=str(out),PYTHONDONTWRITEBYTECODE="1")
    write(out/"environment.json",env)
    spec=importlib.util.spec_from_file_location("owned_job",JOB)
    jobmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(jobmod)
    began=time.monotonic();calls=[];results=[];error=None
    metadata={"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        "origin_develop_visible":subprocess.check_output(["git","rev-parse","origin/develop"],cwd=ROOT,text=True).strip(),
        "machine":platform.node(),"platform":platform.platform(),"python_executable":sys.executable,
        "python_version":sys.version,"authorization":str(AUTH),"round_number":0 if args.preflight else len(previous)+1,
        "round_limit":6,"total_round_limit_seconds":600,"python_limit_seconds":90,
        "global_deadline_utc":"2026-10-16T20:51:00+00:00","board_release_allowed":False,
        "expected_negative_diagnostics":EXPECTED,"old_allowances_restored":False}
    write(out/"METADATA.json",metadata)

    def run(label,argv,expected=0,python_step=False):
        remaining=(datetime.fromisoformat(metadata["global_deadline_utc"])-datetime.now(timezone.utc)).total_seconds()
        budget=min(90 if args.preflight or python_step else 600,600-(time.monotonic()-began),remaining)
        if budget<=0:raise RuntimeError("GLOBAL_OR_ROUND_DEADLINE")
        call={"label":label,"argv":list(map(str,argv)),"cwd":str(work),"timeout_seconds":budget,
            "expected_exit":expected,"exit_code":None,"process_created":False,"timeout":False,
            "start_utc":datetime.now(timezone.utc).isoformat()}
        write(out/(label+".launch.json"),call)
        started=time.monotonic();job=jobmod.WindowsJob()
        try:
            with (out/(label+".stdout")).open("xb") as stdout,(out/(label+".stderr")).open("xb") as stderr:
                if not args.preflight and not (out/"CONSUMED.json").exists():
                    write(out/"CONSUMED.json",{"candidate":candidate,"round_number":len(previous)+1,
                        "reserved_before_process_create":True,"old_allowances_restored":False})
                proc=subprocess.Popen(list(map(str,argv)),cwd=work,env=env,stdin=subprocess.DEVNULL,
                    stdout=stdout,stderr=stderr,creationflags=0x00000004)
                call.update(process_created=True,pid=proc.pid)
                job.attach_and_resume(proc)
                try:call["exit_code"]=proc.wait(timeout=budget)
                except subprocess.TimeoutExpired:
                    call["timeout"]=True;job.terminate();call["exit_code"]=proc.wait(timeout=5)
        finally:
            job.close();call["elapsed_seconds"]=time.monotonic()-started
            call["end_utc"]=datetime.now(timezone.utc).isoformat()
            call["stdout_sha256"]=sha(out/(label+".stdout"));call["stderr_sha256"]=sha(out/(label+".stderr"))
            write(out/(label+".receipt.json"),call);calls.append(call)
        if call["timeout"] or call["exit_code"]!=expected:raise RuntimeError("CALL_FAILED:"+label)
        return (out/(label+".stdout")).read_text(encoding="utf-8")

    try:
        if args.preflight:
            run("python_version",[sys.executable,"--version"])
            run("iverilog_version",[TOOLS/"bin/iverilog.exe","-V"])
            run("vvp_version",[TOOLS/"bin/vvp.exe","-V"])
            run("prepare",[sys.executable,"-B",HERE/"prepare.py"],python_step=True)
        else:
            binary=work/"waveform.vvp"
            run("compile",[TOOLS/"bin/iverilog.exe","-g2012","-Wall","-s","tb_pro_fixed_left_waveform","-o",binary]+staged)
            text=run("positive",[TOOLS/"bin/vvp.exe",binary,"+FAULT=0"])
            if len(re.findall(r"^PASS E2 .+$",text,re.M))!=1 or "FIRST_REJECT" in text or "FATAL" in text:
                raise RuntimeError("POSITIVE_NOT_COMPLETE")
            checked=run("check_capture",[sys.executable,"-B",HERE/"check_capture.py",out/"positive.stdout",HERE/"catalogue.mem"],python_step=True)
            results.append(json.loads(checked))
            for fault,target in EXPECTED.items():
                text=run(f"negative_{fault}",[TOOLS/"bin/vvp.exe",binary,f"+FAULT={fault}"],expected=1)
                rejects=re.findall(r"^FIRST_REJECT ([A-Z0-9_]+) ",text,re.M)
                if rejects!=[target] or "PASS E2" in text:raise RuntimeError(f"WRONG_FIRST_REJECT:{fault}:{rejects}")
                results.append({"fault":fault,"actual_first_difference":target,"expected_rejection":True})
    except Exception as exc:error=repr(exc)
    after={"inputs":identities(inputs),"tools":identities(tool_files)}
    write(out/"after.json",after)
    passed=error is None and before==after
    receipt={**metadata,"passed":passed,"error":error,"identity_stable":before==after,
        "elapsed_seconds":time.monotonic()-began,"calls":calls,"results":results,
        "before":before,"after":after,"preflight_only":args.preflight,
        "level":"L0_TOOL_INPUT_PREFLIGHT" if args.preflight else "L2_ISOLATED_REPLAY" if passed else "PARTIAL",
        "Pro_actual_source_ROM_top_trace":"NOT_AVAILABLE_NOT_TESTED","formal_CDC_STA_board":"NOT_RUN",
        "git_writes":0,"Gowin_ModelSim_hardware_invocations":0}
    write(out/"RUN_RECEIPT.json",receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ("before","after","calls")},indent=2))
    return 0 if passed else 1


if __name__=="__main__":
    raise SystemExit(main())
