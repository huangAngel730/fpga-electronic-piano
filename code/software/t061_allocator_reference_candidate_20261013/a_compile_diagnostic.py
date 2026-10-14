"""One new compile-only diagnostic with explicit suite loader environment.

No VVP, lower, EDA, version query, retry, installation or tool replacement.
Execute only the frozen capsule copy after same-version plan review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def check(condition, message):
    if not condition:
        raise ValueError(message)


class DiagnosticBudget:
    """One worker budget beginning before the first input validation."""

    def __init__(self, seconds=300, clock=None):
        self.seconds = float(seconds)
        self.clock = time.monotonic if clock is None else clock
        self.started = self.clock()

    def elapsed(self):
        return self.clock() - self.started

    def remaining(self, cap):
        left = self.seconds - self.elapsed()
        check(left > 0, "TOTAL_BUDGET_EXHAUSTED")
        check(type(cap) in (int, float) and cap > 0, "STEP_BUDGET_INVALID")
        return min(float(cap), left)


def load_bound_json(path, expected, budget, diagnostic):
    """Hash and parse exactly the same single read, never a second live read."""
    budget.remaining(90)
    raw = Path(path).read_bytes()
    observed = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    check(observed == expected if isinstance(expected, dict)
          else observed["sha256"] == expected, diagnostic)
    budget.remaining(90)
    return json.loads(raw), observed


def validate_dll_inventory(plan, budget):
    """Independently bind the actual top-level suite loader DLL closure."""
    suite = Path(plan["tools"]["compile"]).resolve().parent.parent
    folders = {suite / "bin", suite / "lib"}
    actual = set()
    for folder in folders:
        budget.remaining(90)
        for path in folder.glob("*"):
            budget.remaining(90)
            if path.is_file() and path.suffix.lower() == ".dll":
                actual.add(path.resolve())
    expected = set()
    for name in plan["tool_files"]:
        budget.remaining(90)
        path = Path(name).resolve()
        if path.parent in folders and path.suffix.lower() == ".dll":
            expected.add(path)
    check(actual == expected, "SUITE_DLL_MEMBERS")


def validate_inputs(plan, budget, phase="BEFORE"):
    """The real diagnostic's pre/post validator, also used by new guards."""
    capsule = Path(plan["capsule_root"]).resolve()
    actual = set()
    for path in capsule.rglob("*"):
        budget.remaining(90)
        if path.is_file():
            actual.add(path.relative_to(capsule).as_posix())
    check(actual == set(plan["capsule_files"]), "CAPSULE_MEMBERS:" + phase)
    source = {}
    for relative, expected in plan["capsule_files"].items():
        budget.remaining(90)
        path = (capsule / relative).resolve()
        check(path.is_relative_to(capsule) and path != capsule, "SOURCE_ESCAPE")
        observed = identity(path)
        budget.remaining(90)
        check(observed == {key: expected[key] for key in ("bytes", "sha256")},
              "SOURCE_DRIFT:" + phase + ":" + relative)
        source[relative] = observed
    validate_dll_inventory(plan, budget)
    tools = {}
    for path, expected in plan["tool_files"].items():
        budget.remaining(90)
        observed = identity(path)
        budget.remaining(90)
        check(observed == expected, "TOOL_DRIFT:" + phase + ":" + path)
        tools[path] = observed
    budget.remaining(90)
    return source, tools


def prepare(plan_path, config_path, output):
    plan_path, config_path, output = map(lambda p: Path(p).resolve(),
                                        (plan_path, config_path, output))
    plan = json.loads(plan_path.read_bytes())
    check(not config_path.exists() and not output.exists(), "OUTPUT_EXISTS")
    check(output.is_relative_to(Path(plan["repo"]) / "code/output"), "OUTPUT_SCOPE")
    step = {**plan["steps"][0], "label": "N4_environment_compile_only",
            "cwd": str(output / "work"), "timeout_seconds": 90}
    check(step["kind"] == "compile", "NOT_COMPILE")
    config = {"schema": "T061_N32_A_COMPILE_DIAGNOSTIC_V1",
              "hostname": plan["hostname"], "plan_path": str(plan_path),
              "plan": identity(plan_path), "execution_output": str(output),
              "step": step, "environment": plan["environment"],
              "total_seconds": 300, "step_seconds": 90, "calls": 1,
              "automatic_retries": 0, "simulate_calls": 0, "EDA_calls": 0,
              "reason": "New user-authorized diagnostic; add bound suite bin/lib loader environment; not retry old plan10",
              "old_failure_plan_sha": "414f836520d7dc8e1e0063a516e642cbf7094bb4cdcea5240f9d8b06e7e4f40b"}
    with config_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(config, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return {"status": "PREPARED_COMPILE_ONLY_NOT_RUN", "config": identity(config_path)}


def execute(config_path, expected_sha):
    budget = DiagnosticBudget(300)
    config_path = Path(config_path).resolve()
    config, config_identity = load_bound_json(config_path, expected_sha, budget, "CONFIG_SHA")
    check(config["schema"] == "T061_N32_A_COMPILE_DIAGNOSTIC_V1"
          and config["hostname"] == socket.gethostname(), "CONFIG_MACHINE")
    check(config["total_seconds"] == 300 and config["step_seconds"] == 90
          and config["calls"] == 1 and config["simulate_calls"] == 0, "CONFIG_LIMITS")
    plan_path = Path(config["plan_path"])
    plan, plan_identity = load_bound_json(plan_path, config["plan"], budget, "PLAN_SHA")
    capsule = Path(plan["capsule_root"])
    check(Path(sys.executable).resolve() == Path(plan["tools"]["python"]).resolve(),
          "PYTHON_IDENTITY")
    check(Path(__file__).resolve() == capsule / "code/software/t061_allocator_reference_candidate_20261013/a_compile_diagnostic.py",
          "DIAGNOSTIC_NOT_FROZEN")
    validate_inputs(plan, budget)
    check(config["environment"] == plan["environment"], "ENVIRONMENT_DRIFT")
    output = Path(config["execution_output"])
    step = config["step"]
    check(step["argv"] == plan["steps"][0]["argv"] and step["kind"] == "compile"
          and step["timeout_seconds"] == 90 and step["calls"] == 1, "STEP_SCOPE")
    check(Path(step["cwd"]) == output / "work", "STEP_CWD")
    helpers = capsule / "code/software/t052_runner_acceptance_candidate_20261012"
    sys.path.insert(0, str(helpers))
    budget.remaining(90)
    from runner_tail_20261013 import _run_process, finalize_receipt, write_json
    check(not output.exists(), "ATTEMPT_EXISTS")
    output.mkdir()
    (output / "work").mkdir()
    write_json(output / "attempt.json", {"config": config_identity, "automatic_retries": 0})
    receipt = {"status": "FAIL_PARTIAL", "exit_code": 1, "failure": None,
               "config": config_identity, "plan": plan_identity, "steps": [],
               "environment": config["environment"], "simulate_calls": 0,
               "automatic_retries": 0, "T061_complete": False}
    saved = {key: os.environ.get(key) for key in config["environment"]}
    try:
        check(budget.remaining(90) == 90, "INSUFFICIENT_COMPILE_BUDGET")
        os.environ.update(config["environment"])
        result = _run_process(output, step["label"], step["argv"], output / "work", 90, budget)
        receipt["steps"].append(result)
        check(result["exit_code"] == 0 and result["timed_out"] is False
              and result["launch_error"] is None, "COMPILE_FAILED")
        artifact = output / "work/sim.vvp"
        check(artifact.is_file() and artifact.stat().st_size > 0, "COMPILE_ARTIFACT_MISSING")
        receipt["artifact"] = identity(artifact)
        receipt.update(status="COMPILE_ONLY_PASS_NOT_SIMULATED", exit_code=0)
    except Exception as error:
        receipt["failure"] = type(error).__name__ + ":" + str(error)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            source_after, tool_after = validate_inputs(plan, budget, "AFTER")
            load_bound_json(config_path, config_identity, budget, "CONFIG_AFTER_DRIFT")
            load_bound_json(plan_path, plan_identity, budget, "PLAN_AFTER_DRIFT")
            budget.remaining(90)
            receipt.update(source_after=source_after, tools_after=tool_after,
                           config_after=config_identity, plan_after=plan_identity)
        except Exception as error:
            receipt.update(status="FAIL_PARTIAL", exit_code=1,
                           failure=str(receipt["failure"]) + ";POSTCHECK:" + str(error))
    return finalize_receipt(output / "receipt.json", receipt, budget)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("execute")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--config-sha", required=True)
    args = parser.parse_args()
    result = prepare(args.plan, args.config, args.output) if args.mode == "prepare" else execute(args.config, args.config_sha)
    print(json.dumps({key: value for key, value in result.items() if key != "tools_after"}))
    raise SystemExit(result.get("exit_code", 0))
