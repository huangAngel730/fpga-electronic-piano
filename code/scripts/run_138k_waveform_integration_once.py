"""One exactT058Gowin complete build, bounded, no auto retry/programming."""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"code/scripts"))
import prepare_138k_waveform_integration as prepare
import check_138k_waveform_integration_build as acceptance
TOOL=Path("D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe")


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--simulation-receipts",type=Path,nargs='+',required=True)
    p.add_argument("--tool",type=Path,default=TOOL)
    p.add_argument("--timeout-seconds",type=int,default=1800)
    args=p.parse_args()
    if not 1<=args.timeout_seconds<=1800 or not args.tool.is_file() or args.tool.name.lower()!="gw_sh.exe":
        p.error("require actualgw_sh andtimeout1..1800")
    cases={}
    qualified_sources={}
    for path in args.simulation_receipts:
        record=json.loads(path.read_text(encoding="utf-8"))
        if not record.get("passed") or record.get("elapsed_seconds",999999)>1800 or any(v.get("timed_out") for v in record["steps"].values()):p.error("simulation not passed or timing contract exceeded")
        if not record.get("compiled_inputs_sha256") or not record.get("source_sha256"):
            p.error("simulation input provenance missing")
        for rel,digest in record["source_sha256"].items():
            source=Path(rel) if Path(rel).is_absolute() else ROOT/rel
            # Historical runner versions are bound by their originalhash;
            # every synthesized input, ROM and module must still match live.
            if source.name=="run_138k_waveform_integration_sim.py":continue
            if not source.is_file() or sha(source)!=digest:p.error("simulated source changed "+rel)
            qualified_sources[str(source.resolve())]=digest
        for filename,digest in record["compiled_inputs_sha256"].items():
            if not Path(filename).is_file() or sha(Path(filename))!=digest:
                p.error("compiled staging/source snapshot changed "+filename)
        for mode,res in record["modes"].items():
            if not res.get("passed"):p.error("case did not pass")
            if mode.startswith("negative_") and (res.get("compile_exit")!=0 or res.get("run_exit")!=0 or res.get("check_exit")!=1):p.error("negative case not a compiled specified semantic rejection")
            if mode in cases:p.error("duplicated simulation mode")
            cases[mode]=dict(receipt=str(path.resolve()),sha256=sha(path),result=res)
    if set(cases)!={"0","1","2","display_0","vendor_0","vendor_1","vendor_2","negative_audio_pcm","negative_video_alignment"}:p.error("require3shorttops,longraster,3vendor startups and2specified negative assertions before Gowin")
    run=args.output.resolve()
    run.relative_to((prepare.BUILD_ROOT/"runs").resolve())
    if run.exists() or run==(prepare.BUILD_ROOT/"runs").resolve():p.error("refuse overwrite/root")
    run.mkdir(parents=True)
    project=run/"project"
    frozen=prepare.prepare(project)
    record=dict(date="2026-10-08",attempt_count=1,state="running",programmed=False,timed_out=False,
                started=datetime.now().astimezone().isoformat(),timeout_seconds=args.timeout_seconds,
                simulation_modes=cases,qualified_simulation_sources=qualified_sources,frozen_sha256_before=sha(project/"frozen_receipt.json"),
                command=[str(args.tool),"run.tcl"],tools_and_sources_sha256={str(path.resolve()):sha(path) for path in [args.tool,Path(__file__),Path(acceptance.__file__),Path(prepare.__file__)]})
    dump(run/"build_receipt.json",record)
    start=time.monotonic()
    with (run/"build.log").open("wb") as log:
        proc=subprocess.Popen(record["command"],cwd=project,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        record["pid"]=proc.pid;dump(run/"build_receipt.json",record)
        try:proc.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            record["timed_out"]=True
            subprocess.run(["taskkill","/PID",str(proc.pid),"/T","/F"],capture_output=True,timeout=20)
            proc.wait(timeout=20)
    record.update(state="finished" if proc.returncode==0 and not record["timed_out"] else "failed",exit_code=proc.returncode,
                  finished=datetime.now().astimezone().isoformat(),elapsed_seconds=round(time.monotonic()-start,3),
                  log_sha256=sha(run/"build.log"),frozen_sha256_after=sha(project/"frozen_receipt.json"))
    dump(run/"build_receipt.json",record)
    if proc.returncode or record["timed_out"]:
        print(json.dumps(record,indent=2));return 1
    result=acceptance.review(run);dump(run/"assessment.json",result)
    record["assessment_passed"]=result["passed"];dump(run/"build_receipt.json",record)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
