"""Persist bounded incremental prefix proof; never rerun HDL or long math."""
import argparse
import json
from pathlib import Path
import shutil
import socket
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(HERE))
from c_process import identity, run_step, write_json


def execute(output, full_math=False):
    output = output.resolve()
    base = (ROOT/"code/output").resolve()
    if output.exists() or output == base or not output.is_relative_to(base):
        raise ValueError("C_PREFIX_FRESH_OUTPUT_REQUIRED")
    output.mkdir()
    original = ROOT/"code/output/n32cr05"
    prepared = ROOT/"code/output/n32cp05"
    math_report = ROOT/"code/output/n32c_prefix_v6_r01.json"
    executed_source = ROOT/"code/output/n32c_prefix_checker_executed_r01.py"
    checker = ROOT/"code/software/t061_n32_stress_plan_candidate_20261013/check_prefix_v6.py"
    sources = [p for p in checker.parent.glob("*.py")]
    sources += [HERE/"c_prefix_evidence.py", HERE/"c_process.py", math_report, executed_source,
                original/"receipt.json", original/"simulate.stdout.bin", prepared/"plan.json",
                prepared/"snapshot/assets/plan_v4.jsonl", prepared/"snapshot/assets/expected_v4.jsonl"]
    frozen_plan = json.loads((prepared/"plan.json").read_text(encoding="utf-8"))
    for row in frozen_plan["inputs"]:
        rel = Path(row["snapshot"])
        if rel.suffix == ".py" and ("polyphony_scaling_candidate" in rel.parts or "audio_math_acceptance_candidate" in rel.parts):
            source = ROOT/rel
            if identity(source) != {k: row[k] for k in ("bytes", "sha256")}:
                raise ValueError("C_PREFIX_FROZEN_MATH_DRIFT:"+str(rel))
            sources.append(source)
    before = {str(p): identity(p) for p in dict.fromkeys(sources)}
    started = time.monotonic()
    common = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(checker),
              "--input", str(original/"simulate.stdout.bin"),
              "--plan", str(prepared/"snapshot/assets/plan_v4.jsonl"),
              "--expected", str(prepared/"snapshot/assets/expected_v4.jsonl")]
    steps = [
        {"name": "prefix_boundary_reused_math", "argv": [*common,
            "--reuse-math-report", str(math_report), "--reuse-report-sha256", identity(math_report)["sha256"],
            "--reuse-executed-source", str(executed_source), "--reuse-source-sha256", identity(executed_source)["sha256"],
            "--output", str(output/"prefix_report.json")], "timeout_seconds": 300, "cwd": str(ROOT)},
        {"name": "prefix_wrong_steal", "argv": [*common, "--mutations-only",
            "--output", str(output/"prefix_mutation_report.json")], "timeout_seconds": 300, "cwd": str(ROOT)},
    ]
    if full_math:
        steps[0] = {"name": "prefix_full_clocked_math", "argv": [*common,
            "--output", str(output/"prefix_report.json")], "timeout_seconds": 300, "cwd": str(ROOT)}
    receipt = {"schema": "C_PREFIX_INCREMENTAL_EVIDENCE_V6", "status": "FAIL_PARTIAL", "exit_code": 1,
               "machine": socket.gethostname(), "sources_before": before,
               "python_before": identity(sys.executable), "steps": [], "RTL_calls": 0,
               "math_replay": ("NEW_FULL_SOFTWARE_PROOF_WITH_PRE_POST_CLOSURE" if full_math
                               else "REUSED_COMPLETED_ORIGINAL_PREFIX_PROOF"), "automatic_retries": 0}
    write_json(output/"attempt.json", receipt)
    try:
        for step in steps:
            result = run_step(step, output, {}, ROOT/"code/software/t052_runner_acceptance_candidate_20261012",
                              lambda: 900-(time.monotonic()-started))
            receipt["steps"].append(result)
            if result["exit_code"] != 0 or result["timeout"] or result["failure"]:
                raise ValueError("C_PREFIX_INCREMENT_FAILED:"+step["name"])
        receipt["sources_after"] = {path: identity(path) for path in before}
        receipt["python_after"] = identity(sys.executable)
        if receipt["sources_after"] != before:
            raise ValueError("C_PREFIX_INPUT_DRIFT")
        if receipt["python_after"] != receipt["python_before"]:
            raise ValueError("C_PREFIX_PYTHON_DRIFT")
        for name, source in (("reused_math_report.json", math_report), ("reused_executed_checker.py", executed_source),
                             ("increment_checker.py", checker), ("prefix_evidence_runner.py", Path(__file__))):
            shutil.copyfile(source, output/name)
        receipt.update(status="C_PREFIX_INCREMENTAL_EVIDENCE_PASS", exit_code=0)
    except Exception as error:
        receipt["failure"] = type(error).__name__+":"+str(error)
    receipt["elapsed_seconds"] = time.monotonic()-started
    if receipt["elapsed_seconds"] >= 900:
        receipt.update(status="FAIL_PARTIAL", exit_code=1, failure="C_PREFIX_TOTAL_BUDGET")
    write_json(output/"receipt.json", receipt)
    if time.monotonic()-started >= 900:
        receipt.update(status="FAIL_PARTIAL", exit_code=1, failure="C_PREFIX_TOTAL_BUDGET_AFTER_RECEIPT")
        write_json(output/"receipt.json", receipt, exclusive=False)
    print(json.dumps({k: receipt[k] for k in ("status", "exit_code", "elapsed_seconds")}))
    return receipt["exit_code"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full-math", action="store_true")
    args = parser.parse_args()
    raise SystemExit(execute(args.output, args.full_math))
