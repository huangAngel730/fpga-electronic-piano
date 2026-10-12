"""Bounded T052 runner successor with fail-closed provenance receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

if os.name == "nt":
    from windows_job import WindowsJob


SCHEMA = "T052_RUNNER_ACCEPTANCE_V1"
STEP_LIMITS = {"compile": 300.0, "simulate": 900.0, "check": 600.0}
REQUIRED_ROLES = {"DUT", "TB", "ROM", "CHECKER"}
CRITICAL_NAMES = {"tb_t052_polyphony.capture", "tb_t052_requests.log"}


class RunnerFailure(ValueError):
    """Expected fail-closed runner diagnostic."""


def require(condition, diagnostic):
    if not condition:
        raise RunnerFailure(diagnostic)


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def load_json(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda value: require(False, "NONFINITE_JSON:" + value),
    )


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write_json(path, value, exclusive=True):
    mode = "x" if exclusive else "w"
    with Path(path).open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def safe_member(root, relative):
    root = Path(root).resolve()
    relative = Path(relative)
    path = (root / relative).resolve()
    require(not relative.is_absolute() and path != root and path.is_relative_to(root),
            "PATH_ESCAPE:" + str(relative))
    require(not any(parent.is_symlink() for parent in (path, *path.parents)),
            "SYMLINK_NOT_ALLOWED:" + str(relative))
    return path


class Budget:
    def __init__(self, seconds, clock=time.monotonic):
        require(type(seconds) in (int, float) and 0 < seconds <= 1800,
                "TOTAL_BUDGET_LIMIT")
        self.seconds = float(seconds)
        self.clock = clock
        self.started = clock()

    def elapsed(self):
        return self.clock() - self.started

    def remaining(self, cap):
        left = self.seconds - self.elapsed()
        require(left > 0, "TOTAL_BUDGET_EXHAUSTED")
        require(type(cap) in (int, float) and cap > 0, "STEP_BUDGET_INVALID")
        return min(float(cap), left)


def _stop_owned_tree(process, job):
    if os.name == "nt":
        require(job is not None, "WINDOWS_JOB_MISSING")
        return job.terminate()
    os.killpg(process.pid, signal.SIGKILL)
    return {"mechanism": "SIGKILL", "owned_process_group": True}


def _run_process(output, label, argv, cwd, cap, budget):
    stdout_path = output / (label + ".stdout.bin")
    stderr_path = output / (label + ".stderr.bin")
    timeout = budget.remaining(cap)
    started = time.monotonic()
    timed_out = False
    cleanup = None
    launch_error = None
    exit_code = None
    process = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        job = WindowsJob() if os.name == "nt" else None
        options = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | 0x4}
            if job
            else {"start_new_session": True}
        )
        try:
            process = subprocess.Popen(
                list(map(str, argv)),
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                **options,
            )
            if job:
                job.attach_and_resume(process)
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                cleanup = _stop_owned_tree(process, job)
                exit_code = process.wait(timeout=5)
        except Exception as error:
            launch_error = type(error).__name__ + ":" + str(error)
            if process is not None and process.poll() is None:
                try:
                    cleanup = _stop_owned_tree(process, job)
                    process.wait(timeout=5)
                except Exception as cleanup_error:
                    launch_error += ";CLEANUP:" + str(cleanup_error)
        finally:
            if job:
                job.close()
    receipt = {
        "label": label,
        "argv": list(map(str, argv)),
        "cwd": str(cwd),
        "pid": process.pid if process else None,
        "timeout_cap_seconds": cap,
        "effective_timeout_seconds": timeout,
        "elapsed_seconds": time.monotonic() - started,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "cleanup": cleanup,
        "launch_error": launch_error,
        "stdout": identity(stdout_path),
        "stderr": identity(stderr_path),
    }
    write_json(output / (label + ".receipt.json"), receipt)
    return receipt


def _snapshot_inputs(config, config_path, budget):
    root_value = config["input_root"]
    root = Path(root_value)
    if not root.is_absolute():
        root = (config_path.parent / root).resolve()
    require(root.is_dir(), "INPUT_ROOT_MISSING")
    roles = set()
    result = {}
    for entry in config["inputs"]:
        budget.remaining(60)
        require(set(entry) == {"path", "role", "bytes", "sha256"},
                "INPUT_ENTRY_FIELDS")
        path = safe_member(root, entry["path"])
        require(path.is_file(), "INPUT_MISSING:" + entry["path"])
        actual = identity(path)
        require(actual == {"bytes": entry["bytes"], "sha256": entry["sha256"]},
                "INPUT_IDENTITY:" + entry["path"])
        require(Path(entry["path"]).name not in CRITICAL_NAMES,
                "STALE_CRITICAL_INPUT:" + entry["path"])
        roles.add(entry["role"])
        result[entry["path"]] = {**actual, "role": entry["role"]}
    require(REQUIRED_ROLES <= roles, "REQUIRED_INPUT_ROLE_MISSING")
    return root, result


def _snapshot_tools(config, budget):
    require(type(config["tools"]) is dict and config["tools"], "TOOLS_EMPTY")
    result = {}
    for name, entry in config["tools"].items():
        budget.remaining(60)
        require(set(entry) == {"path", "bytes", "sha256", "version_args"},
                "TOOL_ENTRY_FIELDS:" + name)
        path = Path(entry["path"])
        require(path.is_absolute() and path.is_file(), "TOOL_MISSING_OR_RELATIVE:" + name)
        actual = identity(path)
        require(actual == {"bytes": entry["bytes"], "sha256": entry["sha256"]},
                "TOOL_IDENTITY:" + name)
        require(type(entry["version_args"]) is list, "TOOL_VERSION_ARGS:" + name)
        result[name] = {**actual, "path": str(path), "version_args": entry["version_args"]}
    return result


def _validate_profile(config):
    require(config.get("schema") == SCHEMA, "CONFIG_SCHEMA")
    require(config.get("profile") == "SOFTWARE_FAKE_TOOLS_ONLY_OR_EXPLICIT_FUTURE_TOOL",
            "CONFIG_PROFILE")
    require(type(config.get("total_seconds")) in (int, float)
            and 0 < config["total_seconds"] <= 1800, "TOTAL_BUDGET_LIMIT")
    steps = config.get("steps")
    require(type(steps) is list and [item.get("kind") for item in steps]
            == ["compile", "simulate", "check"], "JOINT_STEP_ORDER")
    labels = set()
    for item in steps:
        require(set(item) == {"label", "kind", "tool", "args", "timeout_seconds",
                              "expected_artifacts", "required_marker"},
                "STEP_FIELDS")
        require(item["label"] not in labels, "DUPLICATE_STEP_LABEL")
        labels.add(item["label"])
        require(0 < item["timeout_seconds"] <= STEP_LIMITS[item["kind"]],
                "STEP_LIMIT_EXCEEDS_V5:" + item["kind"])
        require(type(item["args"]) is list and type(item["expected_artifacts"]) is list,
                "STEP_LIST_FIELDS")
        for relative in item["expected_artifacts"]:
            require(Path(relative).name not in {"receipt.json"}, "RESERVED_ARTIFACT")
    require(set(config.get("critical_artifacts", [])) == CRITICAL_NAMES,
            "CRITICAL_ARTIFACT_CONTRACT")


def _collect_artifacts(root, budget):
    artifacts = {}
    if root.exists():
        for path in root.rglob("*"):
            budget.remaining(60)
            if path.is_file():
                artifacts[path.relative_to(root).as_posix()] = identity(path)
    return artifacts


def run(config_path, output):
    """Run one configuration. The output directory must not already exist."""
    config_path = Path(config_path).resolve()
    output = Path(output).resolve()
    require(not output.exists(), "OUTPUT_EXISTS_REFUSE_OVERWRITE")
    output.mkdir(parents=True)
    receipt = {
        "schema": SCHEMA,
        "status": "FAIL_PARTIAL",
        "exit_code": 1,
        "failure": None,
        "steps": [],
        "automatic_retries": 0,
        "runtime_scope": "SOFTWARE_RUNNER; TOOLS_DEFINED_BY_EXACT_CONFIG",
        "T052_complete": False,
        "RTL_verified_by_this_delivery": False,
        "EDA_runs_by_qualification": 0,
    }
    budget = None
    work = output / "work"
    try:
        require(config_path.is_file(), "CONFIG_MISSING")
        config_identity = identity(config_path)
        config = load_json(config_path)
        _validate_profile(config)
        budget = Budget(config["total_seconds"])
        receipt.update(config=config_identity, total_seconds=config["total_seconds"])
        input_root, inputs_before = _snapshot_inputs(config, config_path, budget)
        tools_before = _snapshot_tools(config, budget)
        receipt.update(input_root=str(input_root), inputs_before=inputs_before,
                       tools_before=tools_before)
        work.mkdir()
        for relative, expected in inputs_before.items():
            target = safe_member(work, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(safe_member(input_root, relative).read_bytes())
            require(identity(target) == {key: expected[key] for key in ("bytes", "sha256")},
                    "SNAPSHOT_COPY_IDENTITY:" + relative)
        for critical in CRITICAL_NAMES:
            require(not safe_member(work, critical).exists(), "STALE_CRITICAL_ARTIFACT:" + critical)
        for name, tool in tools_before.items():
            version = _run_process(
                output,
                "tool_version_" + name,
                [tool["path"], *tool["version_args"]],
                work,
                60,
                budget,
            )
            receipt["steps"].append(version)
            require(not version["timed_out"] and version["launch_error"] is None
                    and version["exit_code"] == 0, "TOOL_VERSION_FAILED:" + name)
        produced_by = {}
        for item in config["steps"]:
            require(item["tool"] in tools_before, "STEP_TOOL_UNKNOWN:" + item["tool"])
            expected_paths = [safe_member(work, name) for name in item["expected_artifacts"]]
            for path in expected_paths:
                require(not path.exists(), "PREEXISTING_STEP_ARTIFACT:" + path.name)
            tool = tools_before[item["tool"]]["path"]
            step_receipt = _run_process(
                output,
                item["label"],
                [tool, *item["args"]],
                work,
                item["timeout_seconds"],
                budget,
            )
            receipt["steps"].append(step_receipt)
            raw = ((output / (item["label"] + ".stdout.bin")).read_bytes()
                   + (output / (item["label"] + ".stderr.bin")).read_bytes())
            require(not step_receipt["timed_out"] and step_receipt["launch_error"] is None,
                    "STEP_TIMEOUT_OR_LAUNCH:" + item["label"])
            require(step_receipt["exit_code"] == 0, "STEP_EXIT_NONZERO:" + item["label"])
            marker = item["required_marker"]
            require(marker is None or marker.encode("utf-8") in raw,
                    "STEP_MARKER_MISSING:" + item["label"])
            for relative, path in zip(item["expected_artifacts"], expected_paths):
                require(path.is_file(), "STEP_ARTIFACT_MISSING:" + relative)
                produced_by[relative] = {
                    "step": item["label"],
                    **identity(path),
                }
            budget.remaining(60)
        for critical in CRITICAL_NAMES:
            require(critical in produced_by, "CRITICAL_ARTIFACT_NOT_THIS_RUN:" + critical)
        inputs_after_root, inputs_after = _snapshot_inputs(config, config_path, budget)
        tools_after = _snapshot_tools(config, budget)
        require(inputs_after_root == input_root and inputs_after == inputs_before,
                "INPUT_DRIFT")
        require(tools_after == tools_before, "TOOL_DRIFT")
        require(identity(config_path) == config_identity, "CONFIG_DRIFT")
        receipt.update(
            status="JOINT_COMPILE_SIMULATE_CHECK_PASS",
            exit_code=0,
            produced_by=produced_by,
            inputs_after=inputs_after,
            tools_after=tools_after,
        )
    except Exception as error:
        receipt["failure"] = type(error).__name__ + ":" + str(error)
    if budget is None:
        budget = Budget(1800)
    try:
        receipt["visible_artifacts"] = _collect_artifacts(work, budget)
    except Exception as error:
        receipt["status"] = "FAIL_PARTIAL"
        receipt["exit_code"] = 1
        receipt["failure"] = (receipt["failure"] + "; " if receipt["failure"] else "") \
            + "ARTIFACT_COLLECTION:" + str(error)
    receipt["elapsed_seconds"] = budget.elapsed()
    if receipt["elapsed_seconds"] >= budget.seconds:
        receipt["status"] = "FAIL_PARTIAL"
        receipt["exit_code"] = 1
        receipt["failure"] = (receipt["failure"] + "; " if receipt["failure"] else "") \
            + "TOTAL_BUDGET_EXHAUSTED_AT_FINALIZATION"
    write_json(output / "receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.config, args.output)
    print(json.dumps({"status": result["status"], "exit_code": result["exit_code"],
                      "failure": result["failure"]}))
    raise SystemExit(result["exit_code"])
