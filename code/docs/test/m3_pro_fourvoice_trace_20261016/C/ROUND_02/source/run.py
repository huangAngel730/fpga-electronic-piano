"""One <=90s Python-only round with immutable source, inputs and raw streams."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time

from calendar import default_plan, build, encode
from cases import cases, hand_anchors, expected_failure_index

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/C"


def identity(path):
    p = Path(path).resolve()
    raw = p.read_bytes()
    return {"path":str(p),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def write(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.write("\n")


def invoke(argv, cwd, folder, tag, deadline):
    started = time.monotonic()
    utc = datetime.now(timezone.utc).isoformat()
    out, err = folder/(tag+".stdout"), folder/(tag+".stderr")
    timeout = False
    with out.open("xb") as so, err.open("xb") as se:
        proc = subprocess.Popen(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=so,stderr=se)
        try:
            proc.wait(timeout=max(0.01,min(90,deadline-started)))
        except subprocess.TimeoutExpired:
            timeout = True
            proc.kill()
            proc.wait()
    return {"argv":argv,"cwd":str(cwd),"pid":proc.pid,"started_utc":utc,
            "ended_utc":datetime.now(timezone.utc).isoformat(),
            "elapsed_s":time.monotonic()-started,"exit_code":proc.returncode,"timeout":timeout,
            "stdin":"NUL_EOF","children":"NONE_BY_INSPECTED_PYTHON_CHECKER_NO_SUBPROCESS",
            "stdout":identity(out),"stderr":identity(err)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--round",type=int,required=True)
    args = p.parse_args()
    if not 1 <= args.round <= 6 or len(list(DOC.glob("ROUND_*_CONSUMED.json"))) >= 6:
        raise ValueError("ROUND_BUDGET_EXHAUSTED")
    for old in DOC.glob("ROUND_*/RUN_RECEIPT.json"):
        if json.loads(old.read_text(encoding="utf-8")).get("status") == "FIXTURE_SOFTWARE_PASS":
            raise ValueError("SUCCESS_ALREADY_RECORDED_STOP")
    target = DOC / f"ROUND_{args.round:02d}"
    target.mkdir(exist_ok=False,parents=True)
    start = time.monotonic()
    deadline = start + 90
    source = {str(x.relative_to(ROOT)):identity(x) for x in HERE.glob("*.py")}
    snapshot = target/"source"
    snapshot.mkdir()
    for info in source.values():
        destination = snapshot/Path(info["path"]).name
        destination.write_bytes(Path(info["path"]).read_bytes())
    write(DOC/f"ROUND_{args.round:02d}_CONSUMED.json",{"round":args.round,"pid":os.getpid(),"created_utc":datetime.now(timezone.utc).isoformat(),"source_before":source,"budget_s":90,"authorization":"D/coordinator/NIGHT_PLAN_20261017.md","scope":"PYTHON_SOFTWARE_FIXTURE_ONLY"})
    input_dir = target/"inputs"
    logs = target/"logs"
    input_dir.mkdir()
    logs.mkdir()
    receipt = {"status":"RUNNING","round":args.round,"machine":socket.gethostname(),"platform":platform.platform(),"python_version":sys.version,"python_executable":identity(sys.executable),"source_before":source,"calls":[],"results":[],"board_release_allowed":False,
               "contract_before":identity(DOC/"CALENDAR_CONTRACT.json")}
    dependencies = {str(Path(x.__file__).resolve()):identity(x.__file__) for x in list(sys.modules.values()) if getattr(x,"__file__",None) and Path(x.__file__).is_file() and Path(x.__file__).suffix in (".py",".pyd")}
    for file in Path(sys.executable).parent.glob("*.dll"):
        if file.name.lower().startswith(("python","vcruntime","ucrtbase")):
            dependencies[str(file.resolve())] = identity(file)
    receipt["runtime_dependencies"] = dependencies
    success = True
    try:
        version = invoke([sys.executable,"--version"],ROOT,logs,"python_version",deadline)
        receipt["calls"].append(version)
        assert version["exit_code"] == 0 and not version["timeout"]
        plan = input_dir/"stimulus.json"
        write(plan,default_plan())
        fixture = input_dir/"calendar_expected.jsonl"
        fixture.write_bytes(encode(build(default_plan())))
        receipt["hand_anchors"] = hand_anchors(build(default_plan()))
        receipt["fixed_plan"] = identity(plan)
        receipt["frozen_calendar"] = identity(fixture)
        for name,rows,code,exitcode in cases():
            actual = input_dir/(name+".jsonl")
            actual.write_bytes(encode(rows))
            expected_index = expected_failure_index(name, rows)
            call = invoke([sys.executable,"-X","utf8",str(HERE/"check_calendar.py"),"--plan",str(plan),"--actual",str(actual)],ROOT,logs,name,deadline)
            receipt["calls"].append(call)
            result = json.loads(Path(call["stdout"]["path"]).read_text(encoding="utf-8"))
            matched = not call["timeout"] and call["exit_code"] == exitcode and (result.get("code") or result.get("status")) == code and (expected_index is None or result.get("record_index") == expected_index)
            receipt["results"].append({"name":name,"input":identity(actual),"expected_code":code,"expected_exit":exitcode,"expected_first_index":expected_index,"matched":matched,"actual":result,"call_index":len(receipt["calls"])-1})
            if not matched:
                success = False
                receipt["first_unexpected_failure"] = receipt["results"][-1]
                break
        receipt["status"] = "FIXTURE_SOFTWARE_PASS" if success else "FAILED_STOP_ORIGINALS_PRESERVED"
    except Exception as exc:
        success = False
        receipt.update(status="FAILED_STOP_ORIGINALS_PRESERVED",error=repr(exc))
    receipt["source_after"] = {k:identity(v["path"]) for k,v in source.items()}
    receipt["contract_after"] = identity(DOC/"CALENDAR_CONTRACT.json")
    receipt["runtime_dependencies_after"] = {k:identity(v["path"]) for k,v in dependencies.items()}
    if receipt["source_before"] != receipt["source_after"] or receipt["contract_before"] != receipt["contract_after"] or receipt["runtime_dependencies"] != receipt["runtime_dependencies_after"]:
        success = False
        receipt.update(status="IDENTITY_CHANGED")
    receipt["elapsed_s"] = time.monotonic()-start
    receipt["exit_code"] = 0 if success else 1
    write(target/"RUN_RECEIPT.json",receipt)
    print(json.dumps({"status":receipt["status"],"round":args.round,"elapsed_s":receipt["elapsed_s"],"cases":len(receipt["results"]),"first_failure":receipt.get("first_unexpected_failure"),"receipt":identity(target/"RUN_RECEIPT.json")},ensure_ascii=False))
    return receipt["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
