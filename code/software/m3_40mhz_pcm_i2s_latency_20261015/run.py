"""Bounded NEW module fixture only. Never runs R05 top or ModelSim/EDA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DOC=ROOT/"code/docs/test/m3_40mhz_pcm_i2s_latency_20261015"
TB=ROOT/"code/tb/audio_out/m3_40mhz_pcm_i2s_latency_20261015/tb_public_serial.sv"
TOOLS=Path("E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy")
R05=ROOT/"code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R05_XSAFE_ModelSim输入_20261015.zip"
R05_SHA="dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identities():
    paths=list(HERE.glob("*.py"))+[TB,R05,Path(sys.executable),ROOT/"code/rtl/common/sample_tick_gen.sv"]
    paths+=list((TOOLS/"bin").glob("*"))+list((TOOLS/"lib/ivl").glob("*"))
    return {str(p):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in paths if p.is_file()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    out=args.output.resolve()
    if out.parent!=DOC.resolve():
        raise SystemExit("OUTPUT_OUTSIDE_EXCLUSIVE_WRITE_SET")
    out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic(); calls=[]
    before=identities()
    receipt={"schema":"C_MODULE_RUN_V1","machine":platform.node(),"python":sys.version,"cwd":str(ROOT),"budget_seconds":300,"per_tool_seconds":90,"before":before,"calls":calls,"real_r05_modelsim_invocations":0,"gowin_invocations":0,"board_release_allowed":False,"evidence_kind":"NEW_MODULE_RTL_FIXTURE"}
    env=os.environ.copy()
    env["PATH"]=str(TOOLS/"bin")+os.pathsep+str(TOOLS/"lib/ivl")+os.pathsep+env.get("PATH","")
    env["TMP"]=env["TEMP"]=str(out)
    def call(name,argv,cwd,expected=0):
        remaining=300-(time.monotonic()-start)
        if remaining<=0:
            raise RuntimeError("TOTAL_BUDGET")
        stamp=time.monotonic(); timeout=False
        proc=subprocess.Popen(list(map(str,argv)),cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            stdout,stderr=proc.communicate(timeout=min(90,remaining))
        except subprocess.TimeoutExpired:
            timeout=True
            kill=subprocess.run(["taskkill","/PID",str(proc.pid),"/T","/F"],capture_output=True,timeout=15)
            (out/f"{name}.kill.stdout").write_bytes(kill.stdout)
            (out/f"{name}.kill.stderr").write_bytes(kill.stderr)
            stdout,stderr=proc.communicate(timeout=15)
        (out/f"{name}.stdout").write_bytes(stdout)
        (out/f"{name}.stderr").write_bytes(stderr)
        item={"name":name,"argv":list(map(str,argv)),"cwd":str(cwd),"exit_code":proc.returncode,"expected_exit":expected,"timeout":timeout,"elapsed_seconds":time.monotonic()-stamp,"stdout_sha256":hashlib.sha256(stdout).hexdigest(),"stderr_sha256":hashlib.sha256(stderr).hexdigest()}
        calls.append(item)
        if timeout or proc.returncode!=expected:
            raise RuntimeError("CHILD_FAILED:"+name)
        return stdout
    status=1
    try:
        if sha(R05)!=R05_SHA:
            raise RuntimeError("R05_IDENTITY")
        stage=out/"stage"; stage.mkdir()
        with zipfile.ZipFile(R05) as z:
            for name in ("i2s_tx.sv","pcm_frame_buffer.sv"):
                (stage/name).write_bytes(z.read("inputs/sources/"+name))
            for name in ("MANIFEST.json","PREPARATION_RECEIPT.json","inputs/compile.f"):
                (stage/Path(name).name).write_bytes(z.read(name))
        (stage/"sample_tick_gen.sv").write_bytes((ROOT/"code/rtl/common/sample_tick_gen.sv").read_bytes())
        (stage/TB.name).write_bytes(TB.read_bytes())
        receipt["stage_sha"]={p.name:sha(p) for p in stage.iterdir()}
        call("iverilog_version",[TOOLS/"bin/iverilog.exe","-V"],out)
        call("vvp_version",[TOOLS/"bin/vvp.exe","-V"],out)
        for variant in ("normal","wrong_stereo"):
            work=out/variant; work.mkdir()
            binary=work/"sim.vvp"
            argv=[TOOLS/"bin/iverilog.exe","-g2012","-s","tb_public_serial","-o",binary]
            if variant=="wrong_stereo": argv+=["-DWRONG_STEREO"]
            argv += [stage/name for name in ("sample_tick_gen.sv","pcm_frame_buffer.sv","i2s_tx.sv",TB.name)]
            call(variant+"_compile",argv,work)
            call(variant+"_simulate",[TOOLS/"bin/vvp.exe",binary],work)
            call(variant+"_check",[sys.executable,"-B","-X","utf8",HERE/"check_capture.py",work/"capture.csv","--output",work/"CHECK.json"],work,0 if variant=="normal" else 1)
        call("software_tests",[sys.executable,"-B","-X","utf8",HERE/"test_capture.py","--capture",out/"normal/capture.csv","--output",out/"software_cases"],out)
        status=0
    except Exception as exc:
        receipt["failure"]=repr(exc)
    finally:
        receipt["after"]=identities()
        receipt["inputs_stable"]=receipt["after"]==before
        receipt["elapsed_seconds"]=time.monotonic()-start
        receipt["passed"]=status==0 and receipt["inputs_stable"] and receipt["elapsed_seconds"]<=300
        receipt["actual_child_invocations"]=len(calls)
        receipt["exit_code"]=0 if receipt["passed"] else 1
        (out/"RUN_RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in receipt.items() if k not in ("before","after","calls")}))
    return receipt["exit_code"]


if __name__=="__main__":
    raise SystemExit(main())
