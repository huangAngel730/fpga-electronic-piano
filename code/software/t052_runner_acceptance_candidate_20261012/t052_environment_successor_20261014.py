"""Environment-normalizing successor for the authorized T052 one-shot.

The preflight performs no external tool invocation.  The full worker reuses the
frozen oneshot implementation after replacing only its environment comparison
with a field-reporting, path-equivalence-aware check.  Tool paths, bytes, SHA,
commands, inputs, budgets, and checker logic remain frozen.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys


ROOT = Path("E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano")
HERE = Path(__file__).resolve().parent
PYTHON = Path(
    "C:/Users/songdongkuan/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/python.exe"
)
ONESHOT = (
    ROOT / "code/software/t052_publication_acceptance_candidate_20261012/"
    "rtl_capture_precheck_20261012/oneshot_20261013/oneshot.py"
)
CHECKER = (
    ROOT / "code/software/t052_publication_acceptance_candidate_20261012/"
    "rtl_capture_precheck_20261012/successor_20261013/checker.py"
)
SUPERVISOR = HERE / "supervisor_20261013.py"
RUNNER_TAIL = HERE / "runner_tail_20261013.py"
RUNNER = HERE / "runner.py"
WINDOWS_JOB = HERE / "windows_job.py"

PREFLIGHT_ROOT = ROOT / "code/output/m3_t052_env_preflight_prepare_20261014_01"
PREFLIGHT_CONFIG = PREFLIGHT_ROOT / "prepared/config.json"
PREFLIGHT_OUTPUT = PREFLIGHT_ROOT / "prepared/actual_once"
PREFLIGHT_MARKER = PREFLIGHT_ROOT / "prepared/consumed.json"

FULL_ROOT = ROOT / "code/output/m3_t052_full_capture_prepare_20261014_03"
FULL_CONFIG = FULL_ROOT / "prepared/config.json"
FULL_MANIFEST = FULL_ROOT / "prepared/manifest.json"
FULL_OUTPUT = FULL_ROOT / "prepared/actual_once"
FULL_MARKER = FULL_ROOT / "prepared/consumed.json"
FULL_OUTER_MARKER = FULL_ROOT / "outer_consumed.json"
FULL_APPROVAL = FULL_ROOT / "approval.json"
FULL_BINDING = FULL_ROOT / "environment_successor_binding.json"
FULL_PARENT = ROOT / "code/output/m3_t052_full_capture_parent_20261014_03"

OLD_ROOT = ROOT / "code/output/m3_t052_full_capture_prepare_20261014_01"
OLD_CONFIG = OLD_ROOT / "prepared/config.json"
OLD_MARKER = OLD_ROOT / "prepared/consumed.json"
OLD_PARENT = ROOT / "code/output/m3_t052_full_capture_parent_20261014_01"
OLD_OBSERVATION = OLD_PARENT / "observation.json"
OLD_CHILD_RECEIPT = OLD_PARENT / "child.receipt.json"
OLD_CHILD_STDOUT = OLD_PARENT / "child.stdout.bin"
OLD_CHILD_STDERR = OLD_PARENT / "child.stderr.bin"

EXPECTED_SOURCE_SHA = {
    "dut": "89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb",
    "dds": "3cd758e28da8f76a30da38cb2dfcd458db5743d4ea4f38e072a43d7f83719f04",
    "mixer": "93fb6e88e55ea84f2e322b0cf8b94a1a2c2e13618e302e7d24ec8657c92bb99a",
    "rom": "5e1dbd3797f353686f5e567831b56d6dcf9bee55c423097b471ade93203e84b2",
    "tb": "d6712a053b0a20b27c3227bbbc36776c654a56f42e5c558fb63103c3653c4d24",
    "observer": "d8bb2dd012c2dcb5ef31caf4ee5399e3a1b84514068816d0d932068c780ea88a",
    "driver_mem": "060d9cf951e8cb2eaf98283b0de758812aed21dfecfd5554814c5ac7f02d0e82",
}
EXPECTED_PLAN_SHA = "b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02"
EXPECTED_CALENDAR_SHA = "0fdf4bb1530453cbbce14136bcae082ca1ff28e04d96402065f4c916ecf36058"
EXPECTED_TOOL_SHA = {
    "compile": "5c1f4e38c6dc0807aeab8814d63af97313bef5813e815e17021ae8e36e0a0bab",
    "runtime": "d38cc76e6946136aaf46db8a3bf34bec2a54bad564dfe146686579ca2d39c9ed",
    "python": "d41bad46673f64e0d02f23797f53f90ccf60f27d6eda8d86dd2d4bbeae5a858c",
}
PATH_FIELDS = {"SystemRoot", "WINDIR", "COMSPEC", "TEMP", "TMP", "IVERILOG_ROOT"}
EXACT_FIELDS = {"PYTHONHASHSEED", "PYTHONIOENCODING"}
EXPECTED_ENV_FIELDS = PATH_FIELDS | EXACT_FIELDS | {"PATH"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalized_path(value):
    return os.path.normcase(os.path.abspath(os.path.normpath(str(value))))


def path_record(expected, actual):
    expected_norm = normalized_path(expected)
    actual_norm = normalized_path(actual)
    equivalent = expected_norm == actual_norm
    if equivalent and Path(expected).exists() and Path(actual).exists():
        equivalent = os.path.samefile(expected, actual)
    return {"expected": expected, "actual": actual,
            "expected_normalized": expected_norm,
            "actual_normalized": actual_norm, "equivalent": equivalent}


def environment_audit(expected, actual, suite, output):
    require(set(expected) == EXPECTED_ENV_FIELDS, "EXPECTED_ENV_FIELDS")
    require(set(actual) == EXPECTED_ENV_FIELDS, "ACTUAL_ENV_FIELDS")
    suite = Path(suite).resolve()
    output = Path(output).resolve()
    system = Path(expected["SystemRoot"])
    required_paths = {
        "SystemRoot": system,
        "WINDIR": system,
        "COMSPEC": system / "System32/cmd.exe",
        "TEMP": output / "work",
        "TMP": output / "work",
        "IVERILOG_ROOT": suite / "lib/ivl",
    }
    for key, required in required_paths.items():
        require(path_record(expected[key], str(required))["equivalent"],
                "EXPECTED_ENV_CONSTRUCTION:" + key)
    expected_path_parts = expected["PATH"].split(os.pathsep)
    required_path_parts = [str(suite / "bin"), str(suite / "lib"),
                           str(system / "System32")]
    require(len(expected_path_parts) == len(required_path_parts)
            and all(path_record(left, right)["equivalent"]
                    for left, right in zip(expected_path_parts, required_path_parts)),
            "EXPECTED_ENV_CONSTRUCTION:PATH")
    require(expected["PYTHONHASHSEED"] == "0", "EXPECTED_PYTHONHASHSEED")
    require(expected["PYTHONIOENCODING"] == "utf-8", "EXPECTED_PYTHONIOENCODING")

    fields = {}
    for key in sorted(PATH_FIELDS):
        fields[key] = path_record(expected[key], actual[key])
    expected_parts = expected["PATH"].split(os.pathsep)
    actual_parts = actual["PATH"].split(os.pathsep)
    path_parts = []
    if len(expected_parts) == len(actual_parts):
        path_parts = [path_record(left, right)
                      for left, right in zip(expected_parts, actual_parts)]
    fields["PATH"] = {"expected": expected["PATH"], "actual": actual["PATH"],
                      "expected_parts": expected_parts, "actual_parts": actual_parts,
                      "parts": path_parts,
                      "equivalent": len(expected_parts) == len(actual_parts)
                      and all(item["equivalent"] for item in path_parts)}
    for key in sorted(EXACT_FIELDS):
        fields[key] = {"expected": expected[key], "actual": actual[key],
                       "equivalent": expected[key] == actual[key]}
    raw_differences = {key: value for key, value in fields.items()
                       if value["expected"] != value["actual"]}
    non_equivalent = [key for key, value in fields.items() if not value["equivalent"]]
    require(not non_equivalent,
            "ENVIRONMENT_NON_EQUIVALENT:" + ",".join(non_equivalent))
    return {"schema": "T052_ENVIRONMENT_AUDIT_V1", "expected": expected,
            "actual_constructed": actual, "fields": fields,
            "raw_differences": raw_differences,
            "non_equivalent_fields": non_equivalent,
            "explicit_tool_environment": expected,
            "policy": "PATH_EQUIVALENCE_ONLY_FOR_PATH_FIELDS; EXACT_OTHER_FIELDS"}


def successor_verify(config_path, pinned_sha, *, require_fresh=True):
    old = load_module("t052_frozen_oneshot_verify", ONESHOT)
    config_path = Path(config_path).resolve()
    old.need(old.identity(config_path)["sha256"] == pinned_sha, "CONFIG_EXTERNAL_PIN")
    config = old.read(config_path)
    old.need(config["schema"] == old.SCHEMA and config["execution_authorized"] is False,
             "CONFIG_NOT_PREPARATION")
    old.need(config["machine"] == platform.node(), "MACHINE_IDENTITY")
    old.need(config["budgets_seconds"] == old.BUDGETS
             and all(type(value) is int for value in config["budgets_seconds"].values()),
             "BUDGETS")
    old.need(config["calls"] == {"compile": 1, "run": 1, "check": 1,
                                  "version_queries": 0}
             and all(type(value) is int for value in config["calls"].values()), "CALLS")
    old.check_file(config["signed_manifest"])
    old.need(config["signed_manifest"]["sha256"] == old.OLD_SHA, "SIGNED_MANIFEST_PIN")
    for path, expected in config["software"].items():
        old.need(old.identity(path) == expected, "SOFTWARE_IDENTITY:" + path)
    for required in (ONESHOT, CHECKER, RUNNER_TAIL, RUNNER, WINDOWS_JOB):
        old.need(required.as_posix() in config["software"], "SOFTWARE_CLOSURE")
    old.check_file(config["manifest"])
    old.need(old.identity(CHECKER)["sha256"] == old.CHECKER_SHA,
             "SIGNED_CHECKER_CHANGED")
    checker = old.import_file("t052_successor_checker", CHECKER)
    manifest = checker.load_manifest(config["manifest"]["path"],
                                     config["manifest"]["sha256"])
    original = old.read(old.OLD_MANIFEST)
    for field in ("sources", "calendar", "plan"):
        old.need(manifest[field] == original[field], "ORIGINAL_CHANGED:" + field)
    old.need(Path(manifest["tools"]["python"]["path"]).resolve()
             == Path(sys.executable).resolve(), "PYTHON_IDENTITY")
    output = Path(config["output"]).resolve()
    old.need(output == config_path.parent / "actual_once"
             and output.is_relative_to(ROOT / "code/output"), "EXECUTION_OUTPUT_SCOPE")
    old.need(Path(config["marker"]).resolve() == config_path.parent / "consumed.json",
             "MARKER_SCOPE")
    suite = Path(manifest["tools"]["compile"]["path"]).parents[1]
    compile_argv = list(original["compile_argv"])
    compile_argv[0] = manifest["tools"]["compile"]["path"]
    compile_argv[1:1] = ["-B", str(suite / "lib/ivl")]
    run_argv = list(original["run_argv"])
    run_argv[0] = manifest["tools"]["runtime"]["path"]
    run_argv = [("+TOOL_SHA=" + manifest["tools"]["runtime"]["sha256"])
                if value.startswith("+TOOL_SHA=") else value for value in run_argv]
    old.need(manifest["compile_argv"] == compile_argv
             and manifest["run_argv"] == run_argv, "COMMAND_SCOPE")
    inventory = old.tool_inventory(suite)
    old.need(manifest["tools"] == inventory, "TOOL_INVENTORY_DRIFT")
    actual_environment = old.fixed_environment(suite, output / "work")
    audit = environment_audit(config["environment"], actual_environment, suite, output)
    if require_fresh:
        old.need(not Path(config["marker"]).exists(), "PERMIT_ALREADY_CONSUMED")
        old.need(not output.exists(), "EXECUTION_OUTPUT_EXISTS")
    return config, manifest, checker, audit


def preflight(config_path, config_sha):
    config_path = Path(config_path).resolve()
    minimal = read_json(config_path)
    output = Path(minimal["output"]).resolve()
    marker = Path(minimal["marker"]).resolve()
    require(output == PREFLIGHT_OUTPUT.resolve() and marker == PREFLIGHT_MARKER.resolve(),
            "PREFLIGHT_SCOPE")
    require(not output.exists() and not marker.exists(), "PREFLIGHT_ATTEMPT_OCCUPIED")
    record = {"schema": "T052_ZERO_TOOL_ENV_PREFLIGHT_V1", "status": "FAIL_LOCKED",
              "exit_code": 1, "config": {"path": str(config_path), **identity(config_path)},
              "machine": platform.node(), "attempt": 1,
              "actual_calls": {"compile": 0, "run": 0, "check": 0, "gowin": 0},
              "automatic_retries": 0, "successor": {"path": str(Path(__file__).resolve()),
                                                       **identity(__file__)}}
    try:
        config, manifest, _, audit = successor_verify(config_path, config_sha)
        record.update(status="ZERO_TOOL_PREFLIGHT_PASS", exit_code=0,
                      environment_audit=audit, tool_files=len(manifest["tools"]),
                      source_sha={role: item["sha256"]
                                  for role, item in manifest["sources"].items()},
                      plan_sha256=manifest["plan"]["sha256"],
                      calendar_sha256=manifest["calendar"]["sha256"])
    except Exception as error:
        record["diagnostic"] = type(error).__name__ + ":" + str(error)
    write_new(marker, {"schema": "T052_ZERO_TOOL_PREFLIGHT_MARKER_V1",
                       "attempt": 1, "config_sha256": config_sha,
                       "machine": platform.node(), "automatic_retries": 0,
                       "actual_calls": record["actual_calls"],
                       "status": record["status"]})
    output.mkdir(parents=True)
    record["marker"] = {"path": str(marker), **identity(marker)}
    write_new(output / "receipt.json", record)
    return record


def bind_full(config_sha):
    require(platform.node() == "LAPTOP-KSS1MRR7", "MACHINE_MISMATCH")
    require(identity(FULL_CONFIG)["sha256"] == config_sha, "CONFIG_SHA")
    require(not FULL_APPROVAL.exists() and not FULL_BINDING.exists(), "BINDING_EXISTS")
    require(not FULL_OUTPUT.exists() and not FULL_MARKER.exists()
            and not FULL_OUTER_MARKER.exists() and not FULL_PARENT.exists(),
            "FULL_ATTEMPT_OCCUPIED")
    preflight_receipt = PREFLIGHT_OUTPUT / "receipt.json"
    require(preflight_receipt.is_file() and PREFLIGHT_MARKER.is_file(),
            "PREFLIGHT_EVIDENCE_MISSING")
    preflight_record = read_json(preflight_receipt)
    require(preflight_record["status"] == "ZERO_TOOL_PREFLIGHT_PASS"
            and preflight_record["exit_code"] == 0
            and preflight_record["actual_calls"]
            == {"compile": 0, "run": 0, "check": 0, "gowin": 0},
            "PREFLIGHT_NOT_PASS")
    config = read_json(FULL_CONFIG)
    manifest = read_json(FULL_MANIFEST)
    require(config["machine"] == platform.node(), "CONFIG_MACHINE")
    require(config["budgets_seconds"] == {"total": 300, "compile": 90,
                                           "run": 90, "check": 90}, "BUDGETS")
    require(config["calls"] == {"compile": 1, "run": 1, "check": 1,
                                 "version_queries": 0}, "CALLS")
    require({role: item["sha256"] for role, item in manifest["sources"].items()}
            == EXPECTED_SOURCE_SHA, "SOURCE_SHA_SET")
    require(manifest["plan"]["sha256"] == EXPECTED_PLAN_SHA, "PLAN_SHA")
    require(manifest["calendar"]["sha256"] == EXPECTED_CALENDAR_SHA, "CALENDAR_SHA")
    require(len(manifest["tools"]) == 1014, "TOOL_COUNT")
    require({role: manifest["tools"][role]["sha256"] for role in EXPECTED_TOOL_SHA}
            == EXPECTED_TOOL_SHA, "PRIMARY_TOOL_SHA")
    for path in (OLD_CONFIG, OLD_MARKER, OLD_OBSERVATION, OLD_CHILD_RECEIPT,
                 OLD_CHILD_STDOUT, OLD_CHILD_STDERR):
        require(path.is_file(), "OLD_FAILURE_EVIDENCE_MISSING:" + str(path))
    approval = {"schema": "T052_128_ONESHOT_APPROVAL_V1",
                "scope": "ONE_COMPILE_ONE_128_EDGE_RUN_ONE_CHECK",
                "approved": True, "config_sha256": config_sha,
                "machine": config["machine"], "calls": config["calls"],
                "budgets_seconds": config["budgets_seconds"],
                "accept_static_dependency_inventory": True}
    write_new(FULL_APPROVAL, approval)
    evidence_paths = [OLD_CONFIG, OLD_MARKER, OLD_OBSERVATION, OLD_CHILD_RECEIPT,
                      OLD_CHILD_STDOUT, OLD_CHILD_STDERR,
                      PREFLIGHT_CONFIG, PREFLIGHT_MARKER, preflight_receipt]
    binding = {
        "schema": "T052_ENVIRONMENT_SUCCESSOR_BINDING_V1",
        "status": "PREPARED_AWAITING_INDEPENDENT_AUDIT",
        "machine": platform.node(), "automatic_retries": 0,
        "config": {"path": str(FULL_CONFIG.resolve()), **identity(FULL_CONFIG)},
        "manifest": {"path": str(FULL_MANIFEST.resolve()), **identity(FULL_MANIFEST)},
        "approval": {"path": str(FULL_APPROVAL.resolve()), **identity(FULL_APPROVAL)},
        "successor": {"path": str(Path(__file__).resolve()), **identity(__file__)},
        "preflight": {"path": str(preflight_receipt.resolve()),
                       **identity(preflight_receipt)},
        "sealed_evidence": {str(path.resolve()): identity(path) for path in evidence_paths},
        "frozen_sources": EXPECTED_SOURCE_SHA,
        "plan_sha256": EXPECTED_PLAN_SHA, "calendar_sha256": EXPECTED_CALENDAR_SHA,
        "tool_files": len(manifest["tools"]), "primary_tools": EXPECTED_TOOL_SHA,
        "compile_argv": manifest["compile_argv"], "run_argv": manifest["run_argv"],
        "calls": config["calls"], "budgets_seconds": config["budgets_seconds"],
        "outer_total_seconds": 300,
        "outer_marker": str(FULL_OUTER_MARKER.resolve()),
        "child_marker": str(FULL_MARKER.resolve()),
        "output": str(FULL_OUTPUT.resolve()), "parent": str(FULL_PARENT.resolve()),
    }
    write_new(FULL_BINDING, binding)
    return {"status": binding["status"], "config": binding["config"],
            "approval": binding["approval"], "binding": {"path": str(FULL_BINDING.resolve()),
                                                             **identity(FULL_BINDING)}}


def worker_full(config_sha, approval_sha):
    old = load_module("t052_frozen_oneshot_worker", ONESHOT)
    captured = {}

    def patched_verify(config_path, pinned_sha):
        config, manifest, checker, audit = successor_verify(config_path, pinned_sha)
        captured["audit"] = audit
        return config, manifest, checker

    old.verify = patched_verify
    result = old.execute(FULL_CONFIG, config_sha, FULL_APPROVAL, approval_sha)
    if FULL_OUTPUT.is_dir() and "audit" in captured:
        write_new(FULL_OUTPUT / "environment_precheck.json", captured["audit"])
    print(json.dumps(result, ensure_ascii=False))
    return result


def launch_full(config_sha, approval_sha, binding_sha):
    require(platform.node() == "LAPTOP-KSS1MRR7", "MACHINE_MISMATCH")
    require(identity(FULL_CONFIG)["sha256"] == config_sha, "CONFIG_SHA")
    require(identity(FULL_APPROVAL)["sha256"] == approval_sha, "APPROVAL_SHA")
    require(identity(FULL_BINDING)["sha256"] == binding_sha, "BINDING_SHA")
    require(not FULL_OUTPUT.exists() and not FULL_MARKER.exists()
            and not FULL_OUTER_MARKER.exists() and not FULL_PARENT.exists(),
            "ATTEMPT_OCCUPIED")
    binding = read_json(FULL_BINDING)
    require(binding["schema"] == "T052_ENVIRONMENT_SUCCESSOR_BINDING_V1"
            and binding["status"] == "PREPARED_AWAITING_INDEPENDENT_AUDIT"
            and binding["machine"] == platform.node()
            and binding["automatic_retries"] == 0, "BINDING_STATUS")
    require(binding["config"]["sha256"] == config_sha
            and binding["approval"]["sha256"] == approval_sha
            and identity(__file__) == {key: binding["successor"][key]
                                       for key in ("bytes", "sha256")},
            "CONTROL_BINDING")
    for label, path in (("config", FULL_CONFIG), ("manifest", FULL_MANIFEST),
                        ("approval", FULL_APPROVAL)):
        expected = binding[label]
        require(Path(expected["path"]).resolve() == path.resolve()
                and identity(path) == {key: expected[key]
                                       for key in ("bytes", "sha256")},
                "CONTROL_FILE_DRIFT:" + label)
    for path, expected in binding["sealed_evidence"].items():
        require(Path(path).is_absolute() and identity(path) == expected,
                "SEALED_EVIDENCE_DRIFT:" + path)
    write_new(FULL_OUTER_MARKER,
              {"schema": "T052_ENVIRONMENT_SUCCESSOR_OUTER_MARKER_V1",
               "attempt": 1, "machine": platform.node(),
               "config_sha256": config_sha, "approval_sha256": approval_sha,
               "binding_sha256": binding_sha, "automatic_retries": 0})

    supervisor = load_module("t052_environment_supervisor", SUPERVISOR)
    argv = [str(PYTHON.resolve()), "-I", "-S", "-B", "-X", "utf8",
            str(Path(__file__).resolve()), "worker-full",
            "--config-sha", config_sha, "--approval-sha", approval_sha]
    source_paths = [Path(__file__).resolve(), ONESHOT, CHECKER, SUPERVISOR,
                    RUNNER_TAIL, RUNNER, WINDOWS_JOB, FULL_CONFIG, FULL_MANIFEST,
                    FULL_APPROVAL, FULL_BINDING, FULL_OUTER_MARKER,
                    PREFLIGHT_CONFIG, PREFLIGHT_MARKER, PREFLIGHT_OUTPUT / "receipt.json",
                    OLD_CONFIG, OLD_MARKER, OLD_OBSERVATION, OLD_CHILD_RECEIPT,
                    OLD_CHILD_STDOUT, OLD_CHILD_STDERR]
    sources = {str(path.resolve()): identity(path) for path in source_paths}
    result = supervisor.observe_run(FULL_PARENT, argv, ROOT,
                                    FULL_OUTPUT / "receipt.json", sources,
                                    total_seconds=300, step_seconds=300)
    print(json.dumps(result, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--config", type=Path, required=True)
    pre.add_argument("--config-sha", required=True)
    bind = sub.add_parser("bind-full")
    bind.add_argument("--config-sha", required=True)
    worker = sub.add_parser("worker-full")
    worker.add_argument("--config-sha", required=True)
    worker.add_argument("--approval-sha", required=True)
    launch = sub.add_parser("launch-full")
    launch.add_argument("--config-sha", required=True)
    launch.add_argument("--approval-sha", required=True)
    launch.add_argument("--binding-sha", required=True)
    args = parser.parse_args()
    try:
        if args.mode == "preflight":
            result = preflight(args.config, args.config_sha)
        elif args.mode == "bind-full":
            result = bind_full(args.config_sha)
        elif args.mode == "worker-full":
            result = worker_full(args.config_sha, args.approval_sha)
        else:
            result = launch_full(args.config_sha, args.approval_sha, args.binding_sha)
    except Exception as error:
        result = {"status": "FAIL_LOCKED", "exit_code": 1,
                  "diagnostic": type(error).__name__ + ":" + str(error)}
    print(json.dumps(result, ensure_ascii=False))
    return result.get("exit_code", 0)


if __name__ == "__main__":
    raise SystemExit(main())
