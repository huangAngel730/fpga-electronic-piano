"""Bounded isolated transport TB and two compiled behavior counterexamples.

No N32 backend, waveform math, Gowin or production connection is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
SUITE=Path("D:/Gowin/oss-cad-suite")
SOURCES=[ROOT/p for p in (
    "code/rtl/audio_out/pcm_result_hold.sv",
    "code/rtl/audio_out/pcm_frame_buffer.sv",
    "code/rtl/common/pcm_clip_counter.sv",
    "code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv",
    "code/tb/audio_out/m2_polyphony_frame_candidate_20261012/tb_premixed_frame_adapter.sv")]


def identities():
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output",required=True,type=Path)
    a=cli.parse_args();out=a.output.resolve();root=(ROOT/"code/output").resolve()
    if out==root or not out.is_relative_to(root) or out.exists():raise ValueError("REFUSE_OUTPUT_SCOPE_OR_EXISTS")
    out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();before=identities();steps=[];err=None
    env=os.environ.copy();env["YOSYSHQ_ROOT"]=str(SUITE)+os.sep
    env["PATH"]=str(SUITE/"bin")+os.pathsep+str(SUITE/"lib")+os.pathsep+env.get("PATH","")
    def run(label,cmd,expected,diagnostic=None):
        remaining=180-(time.monotonic()-start)
        if remaining<=0:raise ValueError("TOTAL180_TIMEOUT")
        t=time.monotonic();p=subprocess.run(cmd,cwd=out,env=env,capture_output=True,timeout=min(30,remaining))
        for stream,raw in (("stdout",p.stdout),("stderr",p.stderr)):(out/(label+"."+stream+".bin")).write_bytes(raw)
        steps.append(dict(label=label,command=cmd,exit=p.returncode,expected=expected,seconds=time.monotonic()-t,
                          stdout_sha256=hashlib.sha256(p.stdout).hexdigest(),stderr_sha256=hashlib.sha256(p.stderr).hexdigest()))
        if p.returncode!=expected:raise ValueError("UNEXPECTED_EXIT:"+label+":"+str(p.returncode))
        if diagnostic and diagnostic.encode() not in p.stdout+p.stderr:raise ValueError("TARGET_DIAGNOSTIC_MISSING:"+label)
    try:
        for label,macro,expected,diagnostic in (("normal",None,0,"PASS PREMIXED_TRANSPORT"),
                ("bad_frame","M2_FRAME_MUTANT_ACCEPT_FRAME",1,"FRAME_EDGE_HANDSHAKE_FORBIDDEN"),
                ("bad_clip","M2_FRAME_MUTANT_CLIP_EVERY_VALID",1,"COMMIT_CLIP_EXACTLY_ONCE_LEDGER")):
            image=out/(label+".vvp")
            cmd=[str(SUITE/"bin/iverilog.exe"),"-g2012","-s","tb_premixed_frame_adapter","-o",str(image)]
            if macro:cmd += ["-D"+macro]
            run(label+"_compile",cmd+[str(p) for p in SOURCES],0)
            run(label+"_simulate",[str(SUITE/"bin/vvp.exe"),str(image)],expected,diagnostic)
    except (ValueError,OSError,subprocess.SubprocessError) as e:err=str(e)
    after=identities()
    if before!=after:err="SOURCE_DRIFT"
    receipt=dict(status="ISOLATED_TRANSPORT_PASS" if err is None else "FAIL",exit_code=0 if err is None else 1,
                 error=err,steps=steps,source_before=before,source_after=after,
                 tool_identity={n:hashlib.sha256((SUITE/"bin"/n).read_bytes()).hexdigest() for n in ("iverilog.exe","vvp.exe")},
                 seconds=time.monotonic()-start,total_bound=180,step_bound=30,synthetic_result_port_only=True,
                 actual_N32_sound_run=False,math_reference=False,physical_STA=False,Gowin=False,production_connected=False)
    (out/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:receipt[k] for k in ("status","exit_code","error","seconds")},ensure_ascii=False))
    return receipt["exit_code"]


if __name__=="__main__":raise SystemExit(main())
