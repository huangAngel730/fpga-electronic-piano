"""Execute one frozen verbose Icarus compile, never simulation or EDA.

The module performs no sibling import at import time. The frozen base worker
is first read, authenticated against the plan, and only then compiled from the
same verified bytes.
"""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import time
import types


SCHEMA = "T061_N32_A_VERBOSE_COMPILE_PLAN_V1"
CONFIG_SCHEMA = "T061_N32_A_VERBOSE_COMPILE_CONFIG_V1"
RELATIVE = (
    "code/software/t061_allocator_reference_candidate_20261013/"
    "a_verbose_compile_diagnostic.py"
)
BASE_RELATIVE = (
    "code/software/t061_allocator_reference_candidate_20261013/"
    "a_compile_diagnostic.py"
)


def identity_bytes(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def check(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def read_bound_json(path, expected, diagnostic):
    raw = Path(path).read_bytes()
    observed = identity_bytes(raw)
    check(observed == expected if isinstance(expected, dict)
          else observed["sha256"] == expected, diagnostic)
    return json.loads(raw), observed


def load_verified_base(plan, capsule):
    """Authenticate exact base-worker bytes before compiling/executing them."""
    path = (capsule / BASE_RELATIVE).resolve()
    check(path.is_relative_to(capsule) and path.is_file(), "BASE_SOURCE_PATH")
    expected = plan["capsule_files"][BASE_RELATIVE]
    raw = path.read_bytes()
    check(identity_bytes(raw)
          == {key: expected[key] for key in ("bytes", "sha256")},
          "BASE_SOURCE_SHA")
    module = types.ModuleType("t061_n32_a_compile_base")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def load_verified_runner_tail(plan, capsule):
    """Load runner_tail and its nested imports from one verified raw snapshot."""
    helpers = capsule / Path(plan["runner_tail"]).parent
    names = ("runner.py", "runner_tail_20261013.py", "windows_job.py")
    raw_helpers = {}
    for name in names:
        path = (helpers / name).resolve()
        relative = path.relative_to(capsule).as_posix()
        expected = plan["capsule_files"][relative]
        raw = path.read_bytes()
        check(identity_bytes(raw)
              == {key: expected[key] for key in ("bytes", "sha256")},
              "CHILD_HELPER_SHA:" + name)
        raw_helpers[path] = raw

    class RawLoader(importlib.abc.Loader):
        def __init__(self, path):
            self.path = path

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            module.__file__ = str(self.path)
            exec(compile(raw_helpers[self.path], str(self.path), "exec"),
                 module.__dict__)

    def raw_spec(name, path):
        spec = importlib.util.spec_from_loader(name, RawLoader(path),
                                               origin=str(path))
        spec.has_location = True
        return spec

    class RawFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            source = helpers / (fullname + ".py")
            return raw_spec(fullname, source) if source in raw_helpers else None

    original = importlib.util.spec_from_file_location

    def pinned_file_spec(name, location, *args, **kwargs):
        path = Path(location).resolve()
        return raw_spec(name, path) if path in raw_helpers \
            else original(name, location, *args, **kwargs)

    finder = RawFinder()
    for path in raw_helpers:
        sys.modules.pop(path.stem, None)
    sys.meta_path.insert(0, finder)
    importlib.util.spec_from_file_location = pinned_file_spec
    try:
        path = helpers / "runner_tail_20261013.py"
        spec = raw_spec("frozen_verbose_runner_tail", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.meta_path.remove(finder)
        importlib.util.spec_from_file_location = original


def expected_verbose_argv(plan):
    non_verbose = plan["non_verbose_argv"]
    expected = [non_verbose[0], "-v", *non_verbose[1:]]
    check(plan["delta"] == {"added_tokens": ["-v"],
                            "removed_tokens": []}, "DELTA_SCOPE")
    check(plan["steps"][0]["argv"] == expected, "PLAN_VERBOSE_ARGV")
    check(expected.count("-v") == 1, "VERBOSE_COUNT")
    check(expected[0] == plan["tools"]["compile"], "COMPILE_TOOL")
    return expected


def execute(config_path, expected_sha):
    started = time.monotonic()
    config_path = Path(config_path).resolve()
    config, config_identity = read_bound_json(config_path, expected_sha,
                                               "CONFIG_SHA")
    check(config["schema"] == CONFIG_SCHEMA, "CONFIG_SCHEMA")
    check(config["hostname"] == socket.gethostname(), "CONFIG_MACHINE")
    check(config["total_seconds"] == 300
          and config["step_seconds"] == 90
          and config["calls"] == 1
          and config["automatic_retries"] == 0
          and config["simulate_calls"] == 0
          and config["EDA_calls"] == 0, "CONFIG_LIMITS")
    plan_path = Path(config["plan_path"])
    plan, plan_identity = read_bound_json(plan_path, config["plan"],
                                           "PLAN_SHA")
    check(plan["schema"] == SCHEMA, "PLAN_SCHEMA")
    capsule = Path(plan["capsule_root"]).resolve()
    check(Path(__file__).resolve() == capsule / RELATIVE,
          "DIAGNOSTIC_NOT_FROZEN")
    check(identity_bytes(Path(__file__).read_bytes()) == config["worker"],
          "WORKER_IDENTITY")
    base = load_verified_base(plan, capsule)
    budget = base.DiagnosticBudget(300)
    budget.started = started
    base.check(Path(sys.executable).resolve()
               == Path(plan["tools"]["python"]).resolve(),
               "PYTHON_IDENTITY")
    source_before, tools_before = base.validate_inputs(plan, budget)
    base.check(config["environment"] == plan["environment"],
               "ENVIRONMENT_DRIFT")
    expected_argv = expected_verbose_argv(plan)
    step = config["step"]
    base.check(len(plan["steps"]) == 1 and step == plan["steps"][0],
               "STEP_BINDING")
    base.check(step["argv"] == expected_argv
               and step["kind"] == "compile"
               and step["timeout_seconds"] == 90
               and step["calls"] == 1, "STEP_SCOPE")
    output = Path(config["execution_output"]).resolve()
    base.check(Path(step["cwd"]).resolve() == output / "work", "STEP_CWD")

    budget.remaining(90)
    runner_tail = load_verified_runner_tail(plan, capsule)
    _run_process = runner_tail._run_process
    finalize_receipt = runner_tail.finalize_receipt
    write_json = runner_tail.write_json

    base.check(not output.exists(), "ATTEMPT_EXISTS")
    output.mkdir()
    (output / "work").mkdir()
    write_json(output / "attempt.json", {
        "config": config_identity,
        "automatic_retries": 0,
        "simulate_calls": 0,
    })
    receipt = {
        "status": "FAIL_PARTIAL",
        "exit_code": 1,
        "failure": None,
        "config": config_identity,
        "plan": plan_identity,
        "steps": [],
        "environment": config["environment"],
        "source_before": source_before,
        "tools_before": tools_before,
        "simulate_calls": 0,
        "automatic_retries": 0,
        "T061_complete": False,
        "verbose_only_delta": ["-v"],
    }
    saved = {key: os.environ.get(key) for key in config["environment"]}
    try:
        base.check(budget.remaining(90) == 90,
                   "INSUFFICIENT_COMPILE_BUDGET")
        os.environ.update(config["environment"])
        result = _run_process(output, step["label"], step["argv"],
                              output / "work", 90, budget)
        receipt["steps"].append(result)
        base.check(result["exit_code"] == 0
                   and result["timed_out"] is False
                   and result["launch_error"] is None, "COMPILE_FAILED")
        artifact = output / "work/sim.vvp"
        base.check(artifact.is_file() and artifact.stat().st_size > 0,
                   "COMPILE_ARTIFACT_MISSING")
        receipt["artifact"] = base.identity(artifact)
        receipt.update(status="VERBOSE_COMPILE_ONLY_PASS_NOT_SIMULATED",
                       exit_code=0)
    except Exception as error:
        receipt["failure"] = type(error).__name__ + ":" + str(error)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            source_after, tool_after = base.validate_inputs(
                plan, budget, "AFTER")
            base.load_bound_json(config_path, config_identity, budget,
                                 "CONFIG_AFTER_DRIFT")
            base.load_bound_json(plan_path, plan_identity, budget,
                                 "PLAN_AFTER_DRIFT")
            budget.remaining(90)
            receipt.update(source_after=source_after, tools_after=tool_after,
                           config_after=config_identity,
                           plan_after=plan_identity)
        except Exception as error:
            receipt.update(
                status="FAIL_PARTIAL", exit_code=1,
                failure=str(receipt["failure"]) + ";POSTCHECK:" + str(error))
    return finalize_receipt(output / "receipt.json", receipt, budget)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha", required=True)
    args = parser.parse_args()
    result = execute(args.config, args.config_sha)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ("tools_before", "tools_after")},
                     sort_keys=True))
    raise SystemExit(result.get("exit_code", 0))
