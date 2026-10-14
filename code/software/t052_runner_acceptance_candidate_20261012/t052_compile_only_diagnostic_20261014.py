"""Prepare and run one source/tool-bound T052 compile-only diagnostic.

The worker never invokes VVP, the T052 checker, Gowin, or a second compile.
The parent and worker both fail closed on identity drift and occupied outputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


ROOT = Path("E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano")
HERE = Path(__file__).resolve().parent
OLD_PREPARED = ROOT / "code/output/m3_t052_oneshot_prepare_20261013_02/prepared"
OLD_CHILD = OLD_PREPARED / "actual_once"
OLD_PARENT = ROOT / "code/output/m3_t052_user_permitted_parent_20261014_01"
OLD_MANIFEST = OLD_PREPARED / "manifest.json"
PLAN_DIR = ROOT / "code/output/m3_t052_compile_only_diagnostic_prepare_20261014_02"
CONFIG = PLAN_DIR / "config.json"
MARKER = PLAN_DIR / "consumed.json"
OUTPUT = ROOT / "code/output/m3_t052_compile_only_diagnostic_20261014_02"
PARENT_OUTPUT = ROOT / "code/output/m3_t052_compile_only_diagnostic_20261014_02_parent"
PREVIOUS_EVENT_RECORD = (
    ROOT / "code/output/m3_t052_compile_only_diagnostic_prepare_20261014_01/"
    "windows_application_events.json"
)
PYTHON = Path(
    "C:/Users/songdongkuan/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/python.exe"
)

SOURCE_NAMES = (
    "readonly/t052_polyphony_test_source.sv",
    "readonly/dds_oscillator.sv",
    "readonly/pcm_mixer_4voice.sv",
    "t052_public_observer_v2.sv",
    "tb_t052_control_128_v2.sv",
    "controls_128.hex",
)

OLD_EVIDENCE = (
    OLD_PARENT / "observation.json",
    OLD_PARENT / "child.receipt.json",
    OLD_PARENT / "child.stdout.bin",
    OLD_PARENT / "child.stderr.bin",
    OLD_CHILD / "receipt.json",
    OLD_CHILD / "compile.receipt.json",
    OLD_CHILD / "compile.stdout.bin",
    OLD_CHILD / "compile.stderr.bin",
    OLD_PREPARED / "consumed.json",
    OLD_PREPARED / "config.json",
    OLD_MANIFEST,
)


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded(value))


def copy_new(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Path(source).open("rb") as incoming, destination.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)


def read_json(path):
    return json.loads(Path(path).read_bytes())


def snapshot(mapping):
    result = {}
    for name, item in mapping.items():
        path = Path(item["path"]).resolve()
        observed = identity(path)
        expected = {key: item[key] for key in ("bytes", "sha256")}
        require(observed == expected, "IDENTITY_DRIFT:" + name)
        result[name] = {"path": str(path), **observed}
    return result


def snapshot_work(work, source_mapping):
    result = {}
    for relative, expected_item in source_mapping.items():
        path = (Path(work) / relative).resolve()
        observed = identity(path)
        expected = {key: expected_item[key] for key in ("bytes", "sha256")}
        require(observed == expected, "WORK_INPUT_DRIFT:" + relative)
        result[relative] = {"path": str(path), **observed}
    return result


def query_windows_events(center):
    script = (
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"
        "$center=[datetime]'" + center.isoformat() + "';"
        "$start=$center.AddMinutes(-3);$end=$center.AddMinutes(3);"
        "Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=$start;EndTime=$end} "
        "-ErrorAction Stop | Where-Object {$_.ProviderName -match "
        "'Application Error|Windows Error Reporting|WER-SystemErrorReporting' "
        "-or $_.Message -match 'iverilog|ivl'} | "
        "Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message | "
        "ConvertTo-Json -Depth 4"
    )
    completed = subprocess.run(
        ["C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-Command", script],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    require(completed.returncode == 0, "WINDOWS_EVENT_QUERY_FAILED")
    return {
        "query_center_local": center.isoformat(),
        "window_minutes": 3,
        "stdout_utf8": completed.stdout.decode("utf-8-sig"),
        "stderr_utf8": completed.stderr.decode("utf-8-sig"),
        "exit_code": completed.returncode,
    }


def prepare():
    require(platform.node() == "LAPTOP-KSS1MRR7", "MACHINE_MISMATCH")
    require(not CONFIG.exists() and not MARKER.exists()
            and not OUTPUT.exists() and not PARENT_OUTPUT.exists(),
            "NEW_OUTPUT_ALREADY_EXISTS")
    require((OLD_PREPARED / "consumed.json").is_file(), "OLD_MARKER_MISSING")
    require((OLD_CHILD / "work/t052_control_v2.vvp").is_file(), "OLD_RESIDUAL_MISSING")
    for path in OLD_EVIDENCE:
        require(path.is_file(), "OLD_EVIDENCE_MISSING:" + str(path))

    old_receipt = read_json(OLD_CHILD / "receipt.json")
    old_compile = read_json(OLD_CHILD / "compile.receipt.json")
    old_observation = read_json(OLD_PARENT / "observation.json")
    require(old_receipt["status"] == "FAIL_PARTIAL" and old_receipt["T052_complete"] is False,
            "OLD_FAILURE_STATUS")
    require(old_compile["exit_code"] == 3221225477, "OLD_FAILURE_CODE")
    require(old_observation["automatic_retries"] == 0, "OLD_RETRY_COUNT")

    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    seal = PLAN_DIR / "sealed_old_attempt"
    for source in OLD_EVIDENCE:
        destination = seal / source.name
        if destination.exists():
            require(identity(destination) == identity(source),
                    "PARTIAL_SEAL_DRIFT:" + source.name)
        else:
            copy_new(source, destination)

    event_path = PLAN_DIR / "windows_application_events.json"
    if not event_path.exists():
        if PREVIOUS_EVENT_RECORD.is_file():
            copy_new(PREVIOUS_EVENT_RECORD, event_path)
        else:
            event_center = __import__("datetime").datetime.fromtimestamp(
                (OLD_CHILD / "compile.receipt.json").stat().st_mtime
            ).astimezone()
            event_record = query_windows_events(event_center)
            write_new(event_path, event_record)

    capsule = PLAN_DIR / "compile_inputs"
    source_map = {}
    for relative in SOURCE_NAMES:
        source = OLD_CHILD / "work" / relative
        require(source.is_file(), "COMPILE_INPUT_MISSING:" + relative)
        destination = capsule / relative
        if destination.exists():
            require(identity(destination) == identity(source),
                    "PARTIAL_INPUT_DRIFT:" + relative)
        else:
            copy_new(source, destination)
        observed = identity(destination)
        require(observed == identity(source), "COMPILE_INPUT_COPY_DRIFT:" + relative)
        source_map[relative] = {"path": str(destination.resolve()), **observed}

    old_manifest = read_json(OLD_MANIFEST)
    tools = snapshot(old_manifest["tools"])
    require(Path(tools["compile"]["path"]).resolve() ==
            Path("D:/Gowin/oss-cad-suite/bin/iverilog.exe").resolve(), "COMPILE_TOOL")
    require(Path(tools["python"]["path"]).resolve() == PYTHON.resolve(), "PYTHON_TOOL")

    compile_argv = old_compile["argv"]
    require(Path(compile_argv[0]).resolve() == Path(tools["compile"]["path"]).resolve(),
            "OLD_COMPILE_TOOL_BINDING")
    environment = dict(old_receipt["environment"])
    environment.update(TEMP=str((OUTPUT / "work").resolve()),
                       TMP=str((OUTPUT / "work").resolve()))
    seal_manifest = {
        str(path.relative_to(PLAN_DIR).as_posix()): identity(path)
        for path in PLAN_DIR.rglob("*") if path.is_file()
    }
    config = {
        "schema": "T052_COMPILE_ONLY_DIAGNOSTIC_V1",
        "permission": "ONE_COMPILE_ONLY_DIAGNOSTIC; NO_VVP_CHECKER_GOWIN_RETRY",
        "machine": "LAPTOP-KSS1MRR7",
        "budgets_seconds": {"outer_total": 120, "compile": 90},
        "calls": {"compile": 1, "vvp": 0, "checker": 0, "gowin": 0, "version_queries": 0},
        "automatic_retries": 0,
        "output": str(OUTPUT.resolve()), "parent_output": str(PARENT_OUTPUT.resolve()),
        "marker": str(MARKER.resolve()),
        "compile_argv": compile_argv, "environment": environment,
        "sources": source_map, "tools": tools,
        "old_failure": {
            "compile_exit_code": old_compile["exit_code"],
            "compile_argv": old_compile["argv"], "compile_cwd": old_compile["cwd"],
            "parent_sources_before": old_observation["sources_before"],
            "parent_sources_after": old_observation["sources_after"],
            "parent_executable_before": old_observation["executable_before"],
            "parent_executable_after": old_observation["executable_after"],
            "old_residual_vvp": {"path": str((OLD_CHILD / "work/t052_control_v2.vvp").resolve()),
                                 **identity(OLD_CHILD / "work/t052_control_v2.vvp")},
            "must_not_run": True,
        },
        "sealed_old_evidence": seal_manifest,
        "event_record": {"path": str(event_path.resolve()), **identity(event_path)},
        "worker": {"path": str(Path(__file__).resolve()), **identity(__file__)},
    }
    write_new(CONFIG, config)
    result = {"status": "PREPARED_COMPILE_ONLY_NOT_RUN", "config": {"path": str(CONFIG), **identity(CONFIG)},
              "sealed_files": len(seal_manifest), "tools": len(tools), "sources": len(source_map)}
    write_new(PLAN_DIR / "PREPARE_RECEIPT.json", result)
    return result


def load_config(path, expected_sha):
    path = Path(path).resolve()
    observed = identity(path)
    require(observed["sha256"] == expected_sha, "CONFIG_SHA")
    config = read_json(path)
    require(config["schema"] == "T052_COMPILE_ONLY_DIAGNOSTIC_V1", "CONFIG_SCHEMA")
    require(config["machine"] == platform.node(), "CONFIG_MACHINE")
    require(config["budgets_seconds"] == {"outer_total": 120, "compile": 90}, "CONFIG_BUDGET")
    require(config["calls"] == {"compile": 1, "vvp": 0, "checker": 0,
                                "gowin": 0, "version_queries": 0}, "CONFIG_CALLS")
    require(config["automatic_retries"] == 0, "CONFIG_RETRIES")
    require(Path(config["worker"]["path"]).resolve() == Path(__file__).resolve()
            and identity(__file__) == {key: config["worker"][key] for key in ("bytes", "sha256")},
            "WORKER_IDENTITY")
    return config, observed


def execute_worker(config_path, expected_sha):
    started = time.monotonic()
    config, config_identity = load_config(config_path, expected_sha)
    require(Path(config["marker"]).is_file(), "PARENT_MARKER_MISSING")
    require(not Path(config["output"]).exists(), "CHILD_OUTPUT_EXISTS")
    source_before = snapshot(config["sources"])
    tool_before = snapshot(config["tools"])
    require(Path(sys.executable).resolve() == Path(tool_before["python"]["path"]).resolve(),
            "PYTHON_IDENTITY")
    output = Path(config["output"])
    work = output / "work"
    output.mkdir(parents=True)
    work.mkdir()
    for relative, item in config["sources"].items():
        copy_new(item["path"], work / relative)
    work_before = snapshot_work(work, config["sources"])
    sys.path.insert(0, str(HERE))
    import runner_tail_20261013 as runner
    budget = runner.Budget(110)
    budget.started = started
    record = {
        "schema": "T052_COMPILE_ONLY_DIAGNOSTIC_RECEIPT_V1",
        "status": "FAIL_PARTIAL", "exit_code": 1, "failure": None,
        "config": config_identity, "calls": config["calls"],
        "automatic_retries": 0, "environment": config["environment"],
        "sources_before": source_before, "tools_before": tool_before,
        "work_inputs_before": work_before,
        "steps": [], "T052_complete": False, "artifact_executed": False,
    }
    saved = {key: os.environ.get(key) for key in config["environment"]}
    try:
        require(budget.remaining(90) == 90, "INSUFFICIENT_COMPILE_BUDGET")
        os.environ.update(config["environment"])
        step = runner._run_process(output, "compile", config["compile_argv"], work, 90, budget)
        record["steps"].append(step)
        require(not step["timed_out"] and step["launch_error"] is None, "COMPILE_TIMEOUT_OR_LAUNCH")
        require(step["exit_code"] == 0, "COMPILE_NONZERO")
        artifact = work / "t052_control_v2.vvp"
        require(artifact.is_file() and artifact.stat().st_size > 0, "COMPILE_ARTIFACT_MISSING")
        record["artifact"] = {"path": str(artifact.resolve()), **identity(artifact), "executed": False}
        record.update(status="COMPILE_ONLY_PASS_NOT_RUN", exit_code=0)
    except Exception as error:
        record["failure"] = type(error).__name__ + ":" + str(error)
        artifact = work / "t052_control_v2.vvp"
        if artifact.is_file():
            record["artifact"] = {"path": str(artifact.resolve()), **identity(artifact), "executed": False}
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            record["sources_after"] = snapshot(config["sources"])
            record["tools_after"] = snapshot(config["tools"])
            record["work_inputs_after"] = snapshot_work(work, config["sources"])
            require(record["sources_before"] == record["sources_after"], "SOURCE_DRIFT")
            require(record["tools_before"] == record["tools_after"], "TOOL_DRIFT")
            require(record["work_inputs_before"] == record["work_inputs_after"],
                    "WORK_INPUT_DRIFT")
            require(identity(config_path) == config_identity, "CONFIG_DRIFT")
        except Exception as error:
            record.update(status="FAIL_PARTIAL", exit_code=1,
                          failure=(record["failure"] or "") + ";POSTCHECK:" + str(error))
    return runner.finalize_receipt(output / "receipt.json", record, budget)


def launch(config_path, expected_sha):
    started = time.monotonic()
    config, config_identity = load_config(config_path, expected_sha)
    output = Path(config["output"])
    parent = Path(config["parent_output"])
    marker = Path(config["marker"])
    require(not output.exists() and not parent.exists() and not marker.exists(), "ATTEMPT_OCCUPIED")
    write_new(marker, {"schema": "T052_COMPILE_ONLY_DIAGNOSTIC_MARKER_V1",
                       "attempt": 1, "machine": platform.node(), "config": config_identity,
                       "automatic_retries": 0})
    supervisor_path = HERE / "supervisor_20261013.py"
    spec = __import__("importlib.util").util.spec_from_file_location("t052_diag_supervisor", supervisor_path)
    supervisor = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(supervisor)
    original_budget = supervisor.runner.Budget

    class ParentBudget(original_budget):
        def __init__(self, seconds):
            super().__init__(seconds)
            self.started = started

    supervisor.runner.Budget = ParentBudget
    worker_argv = [str(PYTHON.resolve()), "-I", "-S", "-B", "-X", "utf8",
                   str(Path(__file__).resolve()), "worker", "--config", str(Path(config_path).resolve()),
                   "--config-sha", expected_sha]
    sources = {}
    for path in (Path(__file__).resolve(), Path(config_path).resolve(), supervisor_path,
                 HERE / "runner_tail_20261013.py", HERE / "runner.py", HERE / "windows_job.py"):
        sources[str(path.resolve())] = identity(path)
    sources[str(marker.resolve())] = identity(marker)
    result = supervisor.observe_run(parent, worker_argv, ROOT, output / "receipt.json", sources,
                                    total_seconds=120, step_seconds=120)
    print(json.dumps(result, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("prepare")
    for name in ("launch", "worker"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--config-sha", required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = prepare()
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.mode == "worker":
        result = execute_worker(args.config, args.config_sha)
        print(json.dumps({key: value for key, value in result.items() if key != "tools_after"},
                         ensure_ascii=False))
        return result["exit_code"]
    return launch(args.config, args.config_sha)["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
