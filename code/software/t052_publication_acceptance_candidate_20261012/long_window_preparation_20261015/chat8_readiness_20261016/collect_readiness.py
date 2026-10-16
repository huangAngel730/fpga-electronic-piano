"""Current-machine T052 preflight evidence only. NEVER execute HDL/checker.

Old runner/Job sources are imported read-only. Only -V tools and two Python
environment probes are permitted. No approval, allowance or actual cwd created.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[4]
TB = ROOT / "code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015"
DOCS = ROOT / "code/docs/test/t052_publication_acceptance_20261012/LONG_WINDOW_PREPARATION_20261015"
DECISION = ROOT / "code/docs/M3_T052长窗R02补件_M2限定复核与执行决定_2026-10-16.md"
sys.path.insert(0, str(PARENT))
import bounded_runner as old_runner  # noqa: E402; no execute()/main() call

ANCHORS = {
    "controls.hex": "fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0",
    "expected_publications.jsonl": "5096c3ce4596574efb0c9e13629e27ae9b27f49d0a7e777c39cf324c80f136f6",
    "M1_INPUT_CONFIRMATION.md": "56574246ebd7fe75bf59ea7f583ffe2c00f5593b8567230dbb6992cfe857b555",
    "readonly/t052_polyphony_test_source.sv": "89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb",
    "readonly/dds_oscillator.sv": "3cd758e28da8f76a30da38cb2dfcd458db5743d4ea4f38e072a43d7f83719f04",
    "readonly/pcm_mixer_4voice.sv": "93fb6e88e55ea84f2e322b0cf8b94a1a2c2e13618e302e7d24ec8657c92bb99a",
    "readonly/sine_1024_8192.mem": "5e1dbd3797f353686f5e567831b56d6dcf9bee55c423097b471ade93203e84b2",
}
R02_SHA = "3776ea3d85f09099e7b33f5705d79300c4475697b5a0f1cfaed3dcfd603d54ee"
OLD_PROPOSAL_SHA = "2a05f0fdff73b4f65c8c7898535b12369055fccdb36f21e1fe0eea756d8611f9"
DECISION_SHA = "01c9bda6c78dffa573a68c8eaeb13aead259e8c87fd3713bd810e9b6fcb6c075"


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    old_runner.write_json(path, value)


def ident(path):
    return old_runner.identity(path)


def env_sha(environment):
    raw = json.dumps(environment, sort_keys=True, ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def namespace_state(path):
    path = Path(path)
    return {"path": str(path), "lexists": os.path.lexists(path),
            "parent_exists": path.parent.is_dir(),
            "resolved": str(path.resolve()), "ascii": str(path).isascii(),
            "at_utc": utc(), "is_reservation": False}


def compare_environment(observed, expected):
    for key in ("PATH", "IVERILOG_ROOT", "COMPUTERNAME"):
        if observed.get(key) != expected.get(key):
            raise ValueError("JOB_EXPLICIT_ENVIRONMENT_MISMATCH:" + key)
    if observed.get("environment_sha256") != env_sha(expected):
        raise ValueError("JOB_FULL_ENVIRONMENT_HASH_MISMATCH")


def inventory(suite):
    paths = {suite / "bin/iverilog.exe", suite / "bin/vvp.exe", Path(sys.executable)}
    for folder, glob in ((suite / "bin", "*.dll"), (suite / "lib", "*.dll"),
                         (suite / "lib/ivl", "*"), (Path(sys.executable).parent, "*.dll"),
                         (Path(sys.executable).parent / "DLLs", "*.dll"),
                         (Path(sys.executable).parent / "DLLs", "*.pyd")):
        paths.update(p for p in folder.glob(glob) if p.is_file())
    system = Path(os.environ["SystemRoot"]) / "System32"
    paths.update(system / n for n in ("kernel32.dll", "KernelBase.dll", "ntdll.dll"))
    return {str(p.resolve()): ident(p) for p in sorted(paths)}


def collect(prepared, output, suite):
    allowed = DOCS.parent / "long_window_preparation_20261015/chat8_readiness_20261016"
    if not output.is_relative_to(allowed.resolve()):
        raise ValueError("READINESS_OUTPUT_OUTSIDE_DISPATCH_SCOPE")
    output.mkdir()  # exclusive; never overwrite earlier evidence
    started = time.monotonic()
    report = {"schema": "T052_CHAT8_READINESS_V1", "started_utc": utc(),
              "status": "FAIL", "approved": False, "execution_authorized": False,
              "new_T052_HDL_compiles": 0, "new_T052_RTL_runs": 0,
              "real_capture_checker_calls": 0, "ModelSim_calls": 0, "Gowin_calls": 0,
              "business_allowance_consumptions": 0, "metadata_queries": 0,
              "python_job_probes": 0, "dynamic_loaded_DLLs": "UNKNOWN",
              "actual_argv": sys.orig_argv, "cwd": str(Path.cwd()), "steps": []}
    ambient = dict(os.environ)
    try:
        proposal_path = DOCS / "LOCKED_RUNNER_R02_PROPOSAL.json"
        package = DOCS / "T052_LONG_RUNNER_R02.zip"
        if old_runner.sha(proposal_path) != OLD_PROPOSAL_SHA or old_runner.sha(package) != R02_SHA:
            raise ValueError("INDEPENDENT_R02_ANCHOR_MISMATCH")
        if old_runner.sha(DECISION) != DECISION_SHA:
            raise ValueError("M2_DECISION_IDENTITY")
        original = old_runner.read_unique(proposal_path)
        if original["approved"] is not False:
            raise ValueError("OLD_PROPOSAL_MUST_REMAIN_FALSE")
        for name, exe in (("compile", "iverilog.exe"), ("run", "vvp.exe")):
            if (suite / "bin" / exe).resolve() != Path(original["commands"][name][0]).resolve():
                raise ValueError("SUITE_DIFFERS_FROM_PINNED_R02_COMMAND:" + name)
        sources = [*PARENT.glob("*.py"), *TB.glob("*.sv"), *HERE.glob("*.py"),
                   DECISION, proposal_path, package]
        source_before = {str(p.resolve()): ident(p) for p in sources}
        with zipfile.ZipFile(package) as archive:
            manifest = json.loads(archive.read("MANIFEST.json"))["members"]
            for path in [*PARENT.glob("*.py"), *TB.glob("*.sv")]:
                expected = manifest[path.relative_to(ROOT).as_posix()]
                if ident(path) != expected:
                    raise ValueError("PINNED_R02_SOURCE_DRIFT:" + path.name)
        inputs = {}
        for relative, digest in ANCHORS.items():
            path = prepared / relative
            spec = ident(path)
            if spec["sha256"] != digest:
                raise ValueError("INDEPENDENT_INPUT_ANCHOR:" + relative)
            inputs[str(path)] = spec
        if inputs[str(prepared / "controls.hex")]["bytes"] != 375598784:
            raise ValueError("FULL_INPUT_SIZE")
        tools_before = inventory(suite)
        # Windows CRT putenv removes empty values from the native environment,
        # although Python's mapping can retain them. Make this normalization
        # explicit and pin the exact removed keys, not an ignored-hash rule.
        removed_empty = sorted(k for k, v in ambient.items() if v == "")
        explicit = {k: v for k, v in ambient.items() if v != ""}
        explicit["PATH"] = os.pathsep.join((str(suite / "bin"), str(suite / "lib"),
                                            ambient.get("PATH", "")))
        explicit["IVERILOG_ROOT"] = str(suite / "lib/ivl")
        report.update(source_before=source_before, inputs_before=inputs,
                      tools_before=tools_before,
                      dependency_scope="CURRENT_STATIC_SUPERSET_NOT_DYNAMIC_CLOSURE",
                      machine=ambient.get("COMPUTERNAME"), python_version=sys.version,
                      windows_version=list(sys.getwindowsversion()),
                      ambient_environment_sha256=env_sha(ambient),
                      explicit_environment_sha256=env_sha(explicit),
                      explicit_empty_environment_keys_removed=removed_empty,
                      explicit_environment={k: explicit.get(k) for k in
                                            ("PATH", "IVERILOG_ROOT", "COMPUTERNAME")},
                      ambient_selected={k: ambient.get(k) for k in ("PATH", "IVERILOG_ROOT")},
                      unlisted_environment="Inherited and hash-bound; values not exported",
                      original_proposal=ident(proposal_path))
        actual = ROOT / "code/output/m3_t052_long_actual_chat8_20261016_01"
        allowance = ROOT / "code/output/m3_t052_long_allowance_chat8_20261016_01"
        resources_before = [namespace_state(actual), namespace_state(allowance)]
        if any(row["lexists"] or not row["parent_exists"] for row in resources_before):
            raise ValueError("UNIQUE_NAMESPACE_ALREADY_OCCUPIED_OR_PARENT_MISSING")
        free = shutil.disk_usage(actual.parent)
        report["disk_before"] = {"path": str(actual.parent), "total": free.total,
                                 "used": free.used, "free": free.free, "at_utc": utc(),
                                 "space_reserved": False, "minimum_required": 2*(1 << 30)}
        if free.free < 2*(1 << 30):
            raise ValueError("DISK_BELOW_2_GIB")
        report["namespace_before"] = resources_before
        limits = dict(old_runner.MAXIMA)
        # Real CreateProcessW environment=None inherits this exact environment.
        # Restore parent environment even on any handled probe/metadata error.
        os.environ.clear()
        os.environ.update(explicit)
        try:
            for name, executable, pattern in (
                ("metadata_iverilog", suite / "bin/iverilog.exe", rb"Icarus Verilog version[^\r\n]+"),
                ("metadata_vvp", suite / "bin/vvp.exe", rb"Icarus Verilog runtime version[^\r\n]+"),
            ):
                report["metadata_queries"] += 1
                step = old_runner.supervise([str(executable), "-V"], output, name,
                                            30, time.monotonic()+30, limits)
                report["steps"].append(step)
                text = (output / (name+".stdout.bin")).read_bytes() + (output / (name+".stderr.bin")).read_bytes()
                version = re.search(pattern, text)
                if step["status"] != "PROCESS_EXIT_ACCEPTABLE" or not version:
                    raise ValueError("CURRENT_VERSION_QUERY_FAILED:" + name)
                step["parsed_version"] = version[0].decode("ascii")
            probes = []
            for name, args in (("job_environment", []),
                               ("job_wrong_root_negative", ["--synthetic-bad-root"])):
                report["python_job_probes"] += 1
                argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "environment_probe.py"), *args]
                step = old_runner.supervise(argv, output, name, 10, time.monotonic()+10, limits)
                report["steps"].append(step)
                if step["status"] != "PROCESS_EXIT_ACCEPTABLE" or not step["streams_complete"]:
                    raise ValueError("ENVIRONMENT_PROBE_PROCESS_FAILED:" + name)
                observed = json.loads((output / (name+".stdout.bin")).read_text(encoding="utf-8"))
                try:
                    compare_environment(observed, explicit)
                    outcome = "EXACT_JOB_ENVIRONMENT_MATCH"
                except ValueError as exc:
                    outcome = str(exc)
                expected = "JOB_EXPLICIT_ENVIRONMENT_MISMATCH:IVERILOG_ROOT" if args else "EXACT_JOB_ENVIRONMENT_MATCH"
                if outcome != expected:
                    raise ValueError("ENVIRONMENT_ORACLE_FAILED:" + name + ":" + outcome)
                probes.append({"name": name, "expected": expected, "actual": outcome,
                               "observed": observed, "status": "SOFTWARE_CHECK_PASS"})
            report["environment_checks"] = probes
        finally:
            os.environ.clear()
            os.environ.update(ambient)
        candidate = dict(original)
        candidate.update(approved=False, approval_id="PENDING_CHAT8_M2_EXACT_APPROVAL",
                         decision_reference=str(DECISION), machine=ambient.get("COMPUTERNAME"),
                         environment_sha256=env_sha(explicit), output=str(actual),
                         allowance_directory=str(allowance),
                         environment_setup={k: explicit[k] for k in ("PATH", "IVERILOG_ROOT")},
                         empty_environment_keys_to_remove=removed_empty,
                         environment_rule="Verify listed keys are empty and remove them, set the two overrides before invoking unchanged runner; inherit all other current values; match full environment SHA",
                         identities={**source_before, **inputs, **tools_before},
                         tool_versions=[s["parsed_version"] for s in report["steps"][:2]],
                         supervisor_source_sha256=old_runner.sha(PARENT / "bounded_runner.py"))
        copies = {str(prepared / rel): rel for rel in ANCHORS if rel != "expected_publications.jsonl"}
        copies.update({str(p.resolve()): p.name for p in TB.glob("*.sv")})
        candidate["copies"] = copies
        candidate["commands"] = {
            "compile": list(original["commands"]["compile"]),
            "run": list(original["commands"]["run"]),
            "check": [sys.executable, "-B", "-X", "utf8", str(PARENT / "check_capture.py"),
                      "--capture", str(actual), "--report", str(actual / "capture_review.json")],
        }
        # Validate only existing identities in the same explicit environment.
        # Do NOT flip approved or invoke approval/execute to test the pipeline.
        os.environ.clear()
        os.environ.update(explicit)
        try:
            old_runner.verify_identities(candidate)
        finally:
            os.environ.clear()
            os.environ.update(ambient)
        write(output / "UNAPPROVED_UNIQUE_COMBINATION.json", candidate)
        report["actual_code_output_refusal_write"] = "WRITE_PROBE_SCOPE_NOT_GRANTED"
        report["minimal_unexecuted_refusal_probe_request"] = {
            "new_directory": str(ROOT / "code/output/m3_t052_chat8_refusal_probe_20261016_01"),
            "action": "Exclusive Python synthetic_refusal.json write/read/hash; retain original",
            "execute_calls": 0, "HDL_calls": 0, "allowance_consumptions": 0,
            "performed": False,
            "scope_decision": "Coordinator requires preserving the two-directory dispatch write set"}
        after_sources = {str(p.resolve()): ident(p) for p in sources}
        after_inputs = {p: ident(Path(p)) for p in inputs}
        after_tools = inventory(suite)
        if source_before != after_sources or inputs != after_inputs or tools_before != after_tools:
            raise ValueError("READINESS_SOURCE_INPUT_TOOL_DRIFT")
        report.update(source_after=after_sources, inputs_after=after_inputs, tools_after=after_tools,
                      namespace_after=[namespace_state(actual), namespace_state(allowance)],
                      allowance_state="ABSENT_UNCONSUMED; M2 must authorize/provision empty fixed directory before execution",
                      old_proposal_after=ident(proposal_path))
        if any(row["lexists"] for row in report["namespace_after"]):
            raise ValueError("NAMESPACE_BECAME_OCCUPIED")
        free = shutil.disk_usage(actual.parent)
        report["disk_after"] = {"free": free.free, "at_utc": utc(), "space_reserved": False}
        if free.free < 2*(1 << 30):
            raise ValueError("DISK_AFTER_BELOW_2_GIB")
        report["status"] = "SOURCE_ENV_RESOURCE_MATERIAL_COMPLETE_WRITE_PROBE_SCOPE_NOT_GRANTED"
        report["exit_code"] = 3
    except BaseException as exc:
        report.update(status="READINESS_FAIL_OR_INCOMPLETE", diagnostic=repr(exc), exit_code=1)
    finally:
        os.environ.clear()
        os.environ.update(ambient)
        report["finished_utc"] = utc()
        report["elapsed_seconds"] = time.monotonic()-started
        write(output / "READINESS_RECEIPT.json", report)
    print(json.dumps({k: report[k] for k in ("status", "exit_code", "metadata_queries", "python_job_probes")}))
    return report["exit_code"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suite", type=Path, default=Path("D:/Gowin/oss-cad-suite"))
    args = parser.parse_args()
    return collect(args.prepared.resolve(), args.output.resolve(), args.suite.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
