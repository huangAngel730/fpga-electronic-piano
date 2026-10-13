"""Minimal receipt-tail successor; frozen runner.py remains unchanged.

A PASS receipt is valid only together with this invocation's zero exit.
elapsed_seconds is sampled immediately before the last receipt write; the
post-write budget gate controls the returned exit. Failure persistence is
best effort and may exceed the work budget, but can never restore success.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_spec = importlib.util.spec_from_file_location("t052_frozen_runner", HERE / "runner.py")
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
Budget = legacy.Budget
_run_process = legacy._run_process
identity = legacy.identity
write_json = legacy.write_json
load_json = legacy.load_json
require = legacy.require
safe_member = legacy.safe_member


def _fail(receipt, diagnostic):
    receipt["status"] = "FAIL_PARTIAL"
    receipt["exit_code"] = 1
    old = receipt.get("failure")
    receipt["failure"] = (old + "; " if old else "") + diagnostic


def finalize_receipt(path, receipt, budget, *, writer=None):
    """Write once, then gate the return on elapsed time including that write.

The destination must be new. Only this call's own receipt may be replaced by
a failure correction; old evidence is never overwritten. No retry of work
or artifact collection occurs in the failure path. writer is a software
test seam with the same (path, value, exclusive=bool) contract as write_json.
"""
    path = Path(path)
    require(not path.exists(), "RECEIPT_EXISTS_REFUSE_OVERWRITE")
    writer = write_json if writer is None else writer
    receipt["elapsed_seconds"] = budget.elapsed()
    if receipt["elapsed_seconds"] >= budget.seconds:
        _fail(receipt, "TOTAL_BUDGET_EXHAUSTED_BEFORE_RECEIPT")
    try:
        writer(path, receipt)
    except Exception as error:
        _fail(receipt, "RECEIPT_WRITE:" + type(error).__name__ + ":" + str(error))
        receipt["elapsed_seconds"] = budget.elapsed()
        try:
            writer(path, receipt, exclusive=not path.exists())
        except Exception as repair_error:
            _fail(receipt, "FAILURE_RECEIPT_WRITE:" + str(repair_error))
        return receipt
    after_write = budget.elapsed()
    if after_write >= budget.seconds:
        _fail(receipt, "TOTAL_BUDGET_EXHAUSTED_AFTER_RECEIPT")
        receipt["elapsed_seconds"] = after_write
        try:
            writer(path, receipt, exclusive=False)
        except Exception as error:
            _fail(receipt, "FAILURE_RECEIPT_WRITE:" + str(error))
    return receipt


def run(config_path, output):
    """Frozen v1 execution contract with the new finalization boundary only."""
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    require(not output.exists(), "OUTPUT_EXISTS_REFUSE_OVERWRITE")
    output.mkdir(parents=True)
    receipt = {
        "schema": legacy.SCHEMA, "status": "FAIL_PARTIAL", "exit_code": 1,
        "failure": None, "steps": [], "automatic_retries": 0,
        "runtime_scope": "SOFTWARE_RUNNER; TOOLS_DEFINED_BY_EXACT_CONFIG",
        "T052_complete": False, "RTL_verified_by_this_delivery": False,
        "EDA_runs_by_qualification": 0,
    }
    budget = None
    work = output / "work"
    try:
        require(config_path.is_file(), "CONFIG_MISSING")
        config_identity = identity(config_path)
        config = load_json(config_path)
        legacy._validate_profile(config)
        budget = Budget(config["total_seconds"])
        receipt.update(config=config_identity, total_seconds=config["total_seconds"])
        input_root, inputs_before = legacy._snapshot_inputs(config, config_path, budget)
        tools_before = legacy._snapshot_tools(config, budget)
        receipt.update(input_root=str(input_root), inputs_before=inputs_before,
                       tools_before=tools_before)
        work.mkdir()
        for relative, expected in inputs_before.items():
            target = safe_member(work, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(safe_member(input_root, relative).read_bytes())
            require(identity(target) == {k: expected[k] for k in ("bytes", "sha256")},
                    "SNAPSHOT_COPY_IDENTITY:" + relative)
        for critical in legacy.CRITICAL_NAMES:
            require(not safe_member(work, critical).exists(),
                    "STALE_CRITICAL_ARTIFACT:" + critical)
        for name, tool in tools_before.items():
            version = _run_process(output, "tool_version_" + name,
                                   [tool["path"], *tool["version_args"]], work, 60, budget)
            receipt["steps"].append(version)
            require(not version["timed_out"] and version["launch_error"] is None
                    and version["exit_code"] == 0, "TOOL_VERSION_FAILED:" + name)
        produced_by = {}
        for item in config["steps"]:
            require(item["tool"] in tools_before, "STEP_TOOL_UNKNOWN:" + item["tool"])
            paths = [safe_member(work, name) for name in item["expected_artifacts"]]
            for path in paths:
                require(not path.exists(), "PREEXISTING_STEP_ARTIFACT:" + path.name)
            step = _run_process(output, item["label"],
                                [tools_before[item["tool"]]["path"], *item["args"]],
                                work, item["timeout_seconds"], budget)
            receipt["steps"].append(step)
            raw = ((output / (item["label"] + ".stdout.bin")).read_bytes()
                   + (output / (item["label"] + ".stderr.bin")).read_bytes())
            require(not step["timed_out"] and step["launch_error"] is None,
                    "STEP_TIMEOUT_OR_LAUNCH:" + item["label"])
            require(step["exit_code"] == 0, "STEP_EXIT_NONZERO:" + item["label"])
            marker = item["required_marker"]
            require(marker is None or marker.encode("utf-8") in raw,
                    "STEP_MARKER_MISSING:" + item["label"])
            for relative, path in zip(item["expected_artifacts"], paths):
                require(path.is_file(), "STEP_ARTIFACT_MISSING:" + relative)
                produced_by[relative] = {"step": item["label"], **identity(path)}
            budget.remaining(60)
        for critical in legacy.CRITICAL_NAMES:
            require(critical in produced_by, "CRITICAL_ARTIFACT_NOT_THIS_RUN:" + critical)
        after_root, inputs_after = legacy._snapshot_inputs(config, config_path, budget)
        tools_after = legacy._snapshot_tools(config, budget)
        require(after_root == input_root and inputs_after == inputs_before, "INPUT_DRIFT")
        require(tools_after == tools_before, "TOOL_DRIFT")
        require(identity(config_path) == config_identity, "CONFIG_DRIFT")
        receipt.update(status="JOINT_COMPILE_SIMULATE_CHECK_PASS", exit_code=0,
                       produced_by=produced_by, inputs_after=inputs_after,
                       tools_after=tools_after)
    except Exception as error:
        _fail(receipt, type(error).__name__ + ":" + str(error))
    if budget is None:
        budget = Budget(1800)
    try:
        receipt["visible_artifacts"] = legacy._collect_artifacts(work, budget)
    except Exception as error:
        _fail(receipt, "ARTIFACT_COLLECTION:" + str(error))
    return finalize_receipt(output / "receipt.json", receipt, budget)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.config, args.output)
    print(json.dumps({key: result[key] for key in ("status", "exit_code", "failure")}))
    raise SystemExit(result["exit_code"])
