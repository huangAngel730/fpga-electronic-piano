"""One exact reset-hold-v3 T058 complete build, bounded, no auto retry/programming."""
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
import prepare_138k_waveform_integration_v3 as prepare
import check_138k_waveform_integration_build_v3 as acceptance
TOOL=Path("D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe")


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--preflight-receipt",type=Path,required=True)
    p.add_argument("--reset-contract-receipt",type=Path,required=True)
    p.add_argument("--simulation-receipts",type=Path,nargs='+',required=True)
    p.add_argument("--tool",type=Path,default=TOOL)
    p.add_argument("--timeout-seconds",type=int,default=1800)
    args=p.parse_args()
    if not 1<=args.timeout_seconds<=1800 or not args.tool.is_file() or args.tool.name.lower()!="gw_sh.exe":
        p.error("require actualgw_sh andtimeout1..1800")
    preflight=json.loads(args.preflight_receipt.read_bytes())
    if not preflight.get("passed") or not all(c.get("pass") is True for c in preflight["checks"]):
        p.error("require successful exactscope/resource/oldreport refusal preflight")
    for relative,digest in preflight["source_sha256"].items():
        # This one-shot runner receives the preflight before its own final binding;
        # all actual revision prepare/gate/reset sources must stay exact.
        if Path(relative).name=="run_138k_waveform_integration_once_v3.py":
            continue
        if sha(ROOT/relative)!=digest:
            p.error("preflight source identity changed "+relative)
    contract=json.loads(args.reset_contract_receipt.read_bytes())
    if not contract.get("passed") or contract.get("coverage_END",[])[4:7] != [64,1,2]:
        p.error("require new reset phase/stopped-clock contract")
    for relative,digest in contract["source_sha256"].items():
        if not (ROOT/relative).is_file() or sha(ROOT/relative)!=digest:
            p.error("reset proof source identity changed "+relative)
    if any(v["exit"]!= (1 if k in ("run_early_release","run_ignore_display_reset") else 0)
           for k,v in contract["steps"].items()):
        p.error("reset contract positive/behavior negative failed")
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
    record=dict(date="2026-10-09",reset_contract_receipt=str(args.reset_contract_receipt.resolve()),reset_contract_sha256=sha(args.reset_contract_receipt),preflight_sha256=sha(args.preflight_receipt),version="reset_hold_v3",logical_RTL_simulations_reused_without_logic_change=True,attempt_count=1,state="running",programmed=False,timed_out=False,
                started=datetime.now().astimezone().isoformat(),timeout_seconds=args.timeout_seconds,
                simulation_modes=cases,qualified_simulation_sources=qualified_sources,frozen_sha256_before=sha(project/"frozen_receipt.json"),
                command=[str(args.tool),"run.tcl"],tools_and_sources_sha256={str(path.resolve()):sha(path) for path in [args.tool,Path(__file__),Path(acceptance.__file__),Path(prepare.__file__),Path(prepare.parent.__file__),Path(prepare.parent.parent.__file__),prepare.SCOPE/"revision_manifest.json",prepare.SCOPE/"audio_visual_hold055.sdc",prepare.parent.SCOPE/"waveform_payload_preserve.gsc",args.preflight_receipt,args.reset_contract_receipt,ROOT/"code/scripts/run_138k_waveform_reset_contract_v3.py"]})
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
