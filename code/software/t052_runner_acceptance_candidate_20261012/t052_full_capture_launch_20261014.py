"""Bind and supervise one authorized T052 128-edge full capture.

Preparation and binding never invoke Icarus, VVP, or the checker.  The launch
delegates the already frozen compile/run/check sequence to ``oneshot.py`` and
adds a parent-owned 300 second process-tree limit.  No retry path exists.
"""
import argparse
import hashlib
import importlib.util
import json
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

PREPARE_ROOT = ROOT / "code/output/m3_t052_full_capture_prepare_20261014_01"
PREPARED = PREPARE_ROOT / "prepared"
CONFIG = PREPARED / "config.json"
MANIFEST = PREPARED / "manifest.json"
APPROVAL = PREPARE_ROOT / "approval.json"
BINDING = PREPARE_ROOT / "diagnostic_config_binding.json"
OUTPUT = PREPARED / "actual_once"
MARKER = PREPARED / "consumed.json"
PARENT = ROOT / "code/output/m3_t052_full_capture_parent_20261014_01"

DIAG_PREPARE = ROOT / "code/output/m3_t052_compile_only_diagnostic_prepare_20261014_02"
DIAG_CONFIG = DIAG_PREPARE / "config.json"
DIAG_MARKER = DIAG_PREPARE / "consumed.json"
DIAG_OUTPUT = ROOT / "code/output/m3_t052_compile_only_diagnostic_20261014_02"
DIAG_RECEIPT = DIAG_OUTPUT / "receipt.json"
DIAG_COMPILE = DIAG_OUTPUT / "compile.receipt.json"
DIAG_PARENT = ROOT / "code/output/m3_t052_compile_only_diagnostic_20261014_02_parent"
DIAG_OBSERVATION = DIAG_PARENT / "observation.json"
DIAG_COMPLETION = DIAG_PARENT / "completion.json"
DIAG_CONFIG_SHA = "294f4552ba364135851a6697c9f0a63f7402fd313fc555ee7241cfe0df093416"
DIAG_ARTIFACT_SHA = "3f5b7a54ad024c8e6da8a26e1d1413a8987cfca50e25c4e1e088fa874fb5d3d8"

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
EXPECTED_TOOL_SHA = {
    "compile": "5c1f4e38c6dc0807aeab8814d63af97313bef5813e815e17021ae8e36e0a0bab",
    "runtime": "d38cc76e6946136aaf46db8a3bf34bec2a54bad564dfe146686579ca2d39c9ed",
    "python": "d41bad46673f64e0d02f23797f53f90ccf60f27d6eda8d86dd2d4bbeae5a858c",
}


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


def source_identity(item):
    path = Path(item["path"])
    if not path.is_absolute():
        path = ROOT / path
    if "member" in item:
        import zipfile
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(item["member"])
        actual = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    else:
        actual = identity(path)
    require(actual == {key: item[key] for key in ("bytes", "sha256")},
            "SOURCE_IDENTITY:" + str(item["path"]))
    return actual


def bind(config_sha):
    require(platform.node() == "LAPTOP-KSS1MRR7", "MACHINE_MISMATCH")
    require(identity(CONFIG)["sha256"] == config_sha, "CONFIG_EXTERNAL_PIN")
    require(identity(DIAG_CONFIG)["sha256"] == DIAG_CONFIG_SHA, "DIAGNOSTIC_CONFIG_PIN")
    for path in (DIAG_MARKER, DIAG_RECEIPT, DIAG_COMPILE,
                 DIAG_OBSERVATION, DIAG_COMPLETION):
        require(path.is_file(), "DIAGNOSTIC_EVIDENCE_MISSING:" + str(path))
    require(not APPROVAL.exists() and not BINDING.exists(), "BINDING_ALREADY_EXISTS")
    require(not OUTPUT.exists() and not MARKER.exists() and not PARENT.exists(),
            "NEW_ATTEMPT_OCCUPIED")

    config = read_json(CONFIG)
    manifest = read_json(MANIFEST)
    diag = read_json(DIAG_CONFIG)
    diag_receipt = read_json(DIAG_RECEIPT)
    diag_compile = read_json(DIAG_COMPILE)
    diag_observation = read_json(DIAG_OBSERVATION)

    require(config["machine"] == platform.node(), "CONFIG_MACHINE")
    require(config["budgets_seconds"] == {"total": 300, "compile": 90,
                                           "run": 90, "check": 90}, "BUDGETS")
    require(config["calls"] == {"compile": 1, "run": 1, "check": 1,
                                 "version_queries": 0}, "CALLS")
    require(Path(config["output"]).resolve() == OUTPUT.resolve(), "OUTPUT_BINDING")
    require(Path(config["marker"]).resolve() == MARKER.resolve(), "MARKER_BINDING")
    require(identity(MANIFEST) == {key: config["manifest"][key]
                                   for key in ("bytes", "sha256")}, "MANIFEST_PIN")
    require(manifest["plan"]["sha256"] == EXPECTED_PLAN_SHA, "PLAN_SHA")
    require({role: item["sha256"] for role, item in manifest["sources"].items()}
            == EXPECTED_SOURCE_SHA, "SOURCE_SHA_SET")
    require({role: manifest["tools"][role]["sha256"] for role in EXPECTED_TOOL_SHA}
            == EXPECTED_TOOL_SHA, "PRIMARY_TOOL_SHA_SET")
    for item in [manifest["plan"], manifest["calendar"],
                 *manifest["sources"].values(), *manifest["tools"].values()]:
        source_identity(item)

    require(diag_receipt["status"] == "COMPILE_ONLY_PASS_NOT_RUN"
            and diag_receipt["exit_code"] == 0
            and diag_receipt["artifact"]["executed"] is False
            and diag_receipt["artifact"]["sha256"] == DIAG_ARTIFACT_SHA,
            "DIAGNOSTIC_STATUS")
    require(diag_compile["exit_code"] == 0 and diag_compile["timed_out"] is False
            and diag_compile["launch_error"] is None, "DIAGNOSTIC_COMPILE")
    require(diag_observation["status"] == "OBSERVED_ZERO_EXIT"
            and diag_observation["automatic_retries"] == 0, "DIAGNOSTIC_PARENT")
    require(set(diag["tools"]) == set(manifest["tools"]),
            "DIAGNOSTIC_TOOL_ROLES")
    for role, current in manifest["tools"].items():
        previous = diag["tools"][role]
        require({key: previous[key] for key in ("bytes", "sha256")}
                == {key: current[key] for key in ("bytes", "sha256")}
                and Path(previous["path"]).resolve() == Path(current["path"]).resolve(),
                "DIAGNOSTIC_TOOL_BINDING:" + role)
    require(diag["compile_argv"] == manifest["compile_argv"],
            "DIAGNOSTIC_COMPILE_ARGV")
    require(diag_receipt["sources_before"] == diag_receipt["sources_after"],
            "DIAGNOSTIC_SOURCE_DRIFT")
    require(diag_receipt["tools_before"] == diag_receipt["tools_after"],
            "DIAGNOSTIC_TOOL_DRIFT")

    approval = {
        "schema": "T052_128_ONESHOT_APPROVAL_V1",
        "scope": "ONE_COMPILE_ONE_128_EDGE_RUN_ONE_CHECK",
        "approved": True,
        "config_sha256": config_sha,
        "machine": config["machine"],
        "calls": config["calls"],
        "budgets_seconds": config["budgets_seconds"],
        "accept_static_dependency_inventory": True,
    }
    write_new(APPROVAL, approval)
    approval_identity = identity(APPROVAL)
    binding = {
        "schema": "T052_FULL_CAPTURE_DIAGNOSTIC_BINDING_V1",
        "status": "PREPARED_AWAITING_INDEPENDENT_AUDIT",
        "machine": platform.node(),
        "config": {"path": str(CONFIG.resolve()), **identity(CONFIG)},
        "manifest": {"path": str(MANIFEST.resolve()), **identity(MANIFEST)},
        "approval": {"path": str(APPROVAL.resolve()), **approval_identity},
        "diagnostic_originals": {
            str(path.resolve()): identity(path) for path in
            (DIAG_CONFIG, DIAG_MARKER, DIAG_RECEIPT, DIAG_COMPILE,
             DIAG_OBSERVATION, DIAG_COMPLETION)
        },
        "frozen_sources": EXPECTED_SOURCE_SHA,
        "frozen_plan_sha256": EXPECTED_PLAN_SHA,
        "primary_tools": EXPECTED_TOOL_SHA,
        "tool_files": len(manifest["tools"]),
        "compile_argv": manifest["compile_argv"],
        "run_argv": manifest["run_argv"],
        "budgets_seconds": config["budgets_seconds"],
        "calls": config["calls"],
        "automatic_retries": 0,
        "forbidden_artifacts": [
            str((ROOT / "code/output/m3_t052_oneshot_prepare_20261013_02/"
                 "prepared/actual_once/work/t052_control_v2.vvp").resolve()),
            str((DIAG_OUTPUT / "work/t052_control_v2.vvp").resolve()),
        ],
        "new_artifact_required": str((OUTPUT / "work/t052_control_v2.vvp").resolve()),
        "outer_total_seconds": 300,
    }
    write_new(BINDING, binding)
    return {"status": binding["status"], "config": binding["config"],
            "approval": binding["approval"], "binding": {"path": str(BINDING.resolve()),
                                                             **identity(BINDING)}}


def launch(config_sha, approval_sha, binding_sha):
    require(platform.node() == "LAPTOP-KSS1MRR7", "MACHINE_MISMATCH")
    require(identity(CONFIG)["sha256"] == config_sha, "CONFIG_SHA")
    require(identity(APPROVAL)["sha256"] == approval_sha, "APPROVAL_SHA")
    require(identity(BINDING)["sha256"] == binding_sha, "BINDING_SHA")
    require(not OUTPUT.exists() and not MARKER.exists() and not PARENT.exists(),
            "ATTEMPT_OCCUPIED")
    binding = read_json(BINDING)
    require(binding["schema"] == "T052_FULL_CAPTURE_DIAGNOSTIC_BINDING_V1"
            and binding["status"] == "PREPARED_AWAITING_INDEPENDENT_AUDIT",
            "BINDING_STATUS")
    require(binding["machine"] == platform.node()
            and binding["automatic_retries"] == 0, "BINDING_MACHINE_OR_RETRY")
    require(binding["config"]["sha256"] == config_sha
            and binding["approval"]["sha256"] == approval_sha,
            "CONTROL_BINDING")
    require(identity(MANIFEST) == {key: binding["manifest"][key]
                                   for key in ("bytes", "sha256")},
            "BINDING_MANIFEST_DRIFT")
    require(str(MANIFEST.resolve()) == binding["manifest"]["path"],
            "BINDING_MANIFEST_PATH")
    for path, expected in binding["diagnostic_originals"].items():
        require(Path(path).is_absolute() and identity(path) == expected,
                "DIAGNOSTIC_ORIGINAL_DRIFT:" + path)

    spec = importlib.util.spec_from_file_location("t052_full_supervisor", SUPERVISOR)
    supervisor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(supervisor)
    argv = [str(PYTHON.resolve()), "-I", "-S", "-B", "-X", "utf8",
            str(ONESHOT.resolve()), "execute", "--config", str(CONFIG.resolve()),
            "--config-sha", config_sha, "--approval", str(APPROVAL.resolve()),
            "--approval-sha", approval_sha]
    source_paths = [Path(__file__).resolve(), ONESHOT, CHECKER, SUPERVISOR,
                    RUNNER_TAIL, RUNNER, WINDOWS_JOB, CONFIG, MANIFEST,
                    APPROVAL, BINDING, DIAG_CONFIG, DIAG_MARKER,
                    DIAG_RECEIPT, DIAG_COMPILE, DIAG_OBSERVATION, DIAG_COMPLETION]
    sources = {str(path.resolve()): identity(path) for path in source_paths}
    result = supervisor.observe_run(PARENT, argv, ROOT, OUTPUT / "receipt.json",
                                    sources, total_seconds=300, step_seconds=300)
    print(json.dumps(result, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    bind_parser = sub.add_parser("bind")
    bind_parser.add_argument("--config-sha", required=True)
    launch_parser = sub.add_parser("launch")
    launch_parser.add_argument("--config-sha", required=True)
    launch_parser.add_argument("--approval-sha", required=True)
    launch_parser.add_argument("--binding-sha", required=True)
    args = parser.parse_args()
    try:
        if args.mode == "bind":
            result = bind(args.config_sha)
        else:
            result = launch(args.config_sha, args.approval_sha, args.binding_sha)
    except Exception as error:
        result = {"status": "FAIL_LOCKED", "exit_code": 1,
                  "diagnostic": type(error).__name__ + ":" + str(error)}
    print(json.dumps(result, ensure_ascii=False))
    return result.get("exit_code", 0)


if __name__ == "__main__":
    raise SystemExit(main())
