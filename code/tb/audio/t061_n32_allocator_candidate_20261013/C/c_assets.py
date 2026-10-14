"""Build C stimuli and independent expectations before HDL execution."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(HERE))
from c_process import identity, run_step, write_json


def build(output, profile="v4"):
    output = output.absolute()
    base = (ROOT/"code/output").resolve()
    if output.exists() or output == base or not output.is_relative_to(base):
        raise ValueError("C_ASSET_NEW_DIRECTORY_REQUIRED")
    output.mkdir()
    software = ROOT/"code/software/t061_n32_stress_plan_candidate_20261013"
    bplan = json.loads((ROOT/"code/output/n32b03/plan.json").read_text(encoding="utf-8"))
    sealed = json.loads((ROOT/"code/tb/audio/t061_n32_allocator_candidate_20261013/B/SEALED_RESULT_R01/MANIFEST.json").read_text(encoding="utf-8"))
    if identity(ROOT/"code/output/n32b03/plan.json") != sealed["files"]["prepared/plan.json"]:
        raise ValueError("C_ASSET_B_PLAN_IDENTITY")
    def mathematical_dependency(row):
        path = Path(row["origin"])
        return (path.suffix == ".mem" or (path.suffix == ".py" and
                any(name in path.parts for name in ("audio_math_acceptance_candidate",
                                                    "polyphony_scaling_candidate"))))
    for row in bplan["inputs"]:
        if mathematical_dependency(row):
            if identity(row["origin"]) != {k: row[k] for k in ("bytes", "sha256")}:
                raise ValueError("C_ASSET_FROZEN_DEPENDENCY_DRIFT:"+row["origin"])
    dependencies = [Path(row["origin"]) for row in bplan["inputs"]
                    if mathematical_dependency(row)]
    sources = [p for p in software.glob("*.py")] + list(HERE.glob("*.py")) + dependencies
    sources = list(dict.fromkeys(sources))
    before = {str(p): identity(p) for p in sources}
    tool_before = identity(sys.executable)
    started = time.monotonic()
    data = output/"data"
    version = "v6" if profile in ("suffix-v6", "full-v6") else "v4"
    steps = [
        {"name": "operation_guard_tests", "argv": [sys.executable, "-I", "-S", "-B",
             str(HERE/"test_operation_progress.py")], "cwd": str(ROOT), "timeout_seconds": 90},
        {"name": "expected_generate", "argv": [sys.executable, "-I", "-S", "-B", "-X", "utf8",
             str(software/("generate_"+version+".py")), "--output", str(data)],
         "cwd": str(ROOT), "timeout_seconds": 300},
        {"name": "stimulus_generate", "argv": [sys.executable, "-I", "-S", "-B", "-X", "utf8",
             str(HERE/"generate_tb_v4.py"), "--plan", str(data/("plan_"+version+".jsonl")),
             "--output", str(data/("c_plan_"+version+".svh"))], "cwd": str(ROOT), "timeout_seconds": 300},
    ]
    if profile == "full-v6":
        steps[1]["argv"] += ["--segment", "FULL"]
        steps.insert(1, {"name": "full_identity_tests", "argv": [sys.executable,
            "-I", "-S", "-B", "-X", "utf8", str(HERE/"test_full_closure.py")],
            "cwd": str(ROOT), "timeout_seconds": 90})
        steps[2:2] = [{"name": name, "argv": [sys.executable, "-I", "-S", "-B", "-X", "utf8",
            str(HERE/file)], "cwd": str(ROOT), "timeout_seconds": 90} for name, file in (
                ("full_steal_tests", "test_full_steal_successor.py"),
                ("full_reuse_guard_tests", "test_full_reuse_guard.py"))]
    receipt = {"schema": "T061_N32_C_ASSET_BUILD_V4", "status": "FAIL_PARTIAL",
               "profile": profile,
               "sources_before": before, "tool_before": tool_before,
               "steps": [], "source": "INPUT_ONLY_FROZEN_MATH_BEFORE_RTL"}
    write_json(output/"asset_started.json", receipt)
    for step in steps:
        result = run_step(step, output, {}, ROOT/"code/software/t052_runner_acceptance_candidate_20261012",
                          lambda: 900-(time.monotonic()-started))
        receipt["steps"].append(result)
        if result["exit_code"] != 0 or result["timeout"] or result["failure"]:
            write_json(output/"asset_failure.json", receipt)
            raise ValueError("C_ASSET_BUILD_FAILED:"+step["name"])
    receipt["sources_after"] = {str(p): identity(p) for p in sources}
    receipt["tool_after"] = identity(sys.executable)
    if receipt["sources_after"] != before or receipt["tool_after"] != tool_before:
        raise ValueError("C_ASSET_BUILD_IDENTITY_DRIFT")
    receipt["artifacts"] = {p.name: identity(p) for p in data.iterdir() if p.is_file()}
    evidence = data/"build_evidence"
    evidence.mkdir()
    for p in output.iterdir():
        if p.is_file():
            shutil.copyfile(p, evidence/p.name)
    receipt["elapsed_seconds"] = time.monotonic()-started
    if receipt["elapsed_seconds"] >= 900:
        raise ValueError("C_ASSET_TOTAL_BUDGET_BEFORE_RECEIPT")
    receipt["status"] = "PASS_INDEPENDENT_EXPECTED_BEFORE_RTL"
    write_json(data/"asset_build_receipt.json", receipt)
    if time.monotonic()-started >= 900:
        receipt.update(status="FAIL_PARTIAL", failure="C_ASSET_TOTAL_BUDGET_AFTER_RECEIPT")
        write_json(data/"asset_build_receipt.json", receipt, exclusive=False)
        raise ValueError(receipt["failure"])
    return {"status": receipt["status"], "assets": str(data), "elapsed_seconds": receipt["elapsed_seconds"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("v4", "suffix-v6", "full-v6"), default="v4")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output, args.profile)))
    except Exception as error:
        failure = {"status": "FAIL_PARTIAL", "failure": type(error).__name__+":"+str(error)}
        if args.output.is_dir() and not (args.output/"asset_failure.json").exists():
            write_json(args.output/"asset_failure.json", failure)
        print(json.dumps(failure))
        raise SystemExit(1)
