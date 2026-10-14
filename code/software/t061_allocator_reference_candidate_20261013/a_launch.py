"""SHA-pinned launcher and parent observation for the frozen N32-A plan.

Invoke the reviewed capsule copy, after an external raw-byte SHA check. All
project imports below are from that capsule, never the active worktree.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time


def launch(plan_path, plan_sha, bootstrap_sha, parent_output):
    started = time.monotonic()
    plan_path = Path(plan_path).resolve()
    raw = plan_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != plan_sha:
        raise ValueError("LAUNCH_PLAN_SHA")
    plan = json.loads(raw)
    capsule = Path(plan["capsule_root"]).resolve()
    bootstrap_path = capsule / plan["bootstrap"]
    bootstrap_raw = bootstrap_path.read_bytes()
    if hashlib.sha256(bootstrap_raw).hexdigest() != bootstrap_sha:
        raise ValueError("LAUNCH_BOOTSTRAP_SHA")
    namespace = {"__name__": "verified_bootstrap", "__file__": str(bootstrap_path)}
    exec(compile(bootstrap_raw, str(bootstrap_path), "exec"), namespace)
    namespace["bootstrap"](plan_path, plan_sha, invoke=False)
    child_cwd = Path(plan["launch"]["cwd"]).resolve()
    if child_cwd != capsule:
        raise ValueError("LAUNCH_CWD")
    launcher_relative = "code/software/t061_allocator_reference_candidate_20261013/a_launch.py"
    if Path(__file__).resolve() != capsule / launcher_relative:
        raise ValueError("LAUNCHER_NOT_FROM_CAPSULE")
    helpers = capsule / "code/software/t052_runner_acceptance_candidate_20261012"
    sys.path.insert(0, str(helpers))
    spec = importlib.util.spec_from_file_location("frozen_supervisor", helpers / "supervisor_20261013.py")
    supervisor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(supervisor)
    original_budget = supervisor.runner.Budget

    class LaunchBudget(original_budget):
        """Charge validation, imports and parent completion to the same 900s."""
        def __init__(self, seconds):
            super().__init__(seconds)
            self.started = started

    supervisor.runner.Budget = LaunchBudget
    sources = {str(plan_path): {"bytes": len(raw), "sha256": plan_sha}}
    sources.update({str(capsule / relative): {key: item[key] for key in ("bytes", "sha256")}
                    for relative, item in plan["capsule_files"].items()})
    argv = plan["launch"]["argv_prefix"] + [plan_sha]
    receipt_path = Path(plan["execution_output"]) / "receipt.json"
    result = supervisor.observe_run(parent_output, argv, child_cwd, receipt_path,
                                    sources, total_seconds=900, step_seconds=900)
    return {"status": result["status"], "exit_code": result["exit_code"],
            "failure": result["failure"], "elapsed_seconds": result["elapsed_seconds"],
            "actual_receipt": str(receipt_path), "plan_sha256": plan_sha}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha", required=True)
    parser.add_argument("--bootstrap-sha", required=True)
    parser.add_argument("--parent-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = launch(args.plan, args.plan_sha, args.bootstrap_sha, args.parent_output)
        print(json.dumps(result))
        raise SystemExit(result["exit_code"])
    except Exception as error:
        print(json.dumps({"status": "FAIL_PARTIAL", "exit_code": 1,
                          "failure": type(error).__name__ + ":" + str(error)}))
        raise SystemExit(1)
