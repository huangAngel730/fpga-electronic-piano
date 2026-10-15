"""Real Python fake-process supervision tests; no HDL compile/run permitted.

Every invocation requires a fresh --output. All handled failures, raw streams,
and case receipts are retained. PASS applies ONLY to these software fixtures.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import time
import traceback
import zipfile

import bounded_runner as runner
from fake_process import process_creation

HERE = Path(__file__).resolve().parent


def approval_fixture(output):
    """Metadata-only fake approval, never passed to execute()."""
    identities = {str(p.resolve()): runner.identity(p) for p in HERE.glob("*.py")}
    executable = str(Path(sys.executable).resolve())
    identities[executable] = runner.identity(Path(executable))
    frozen = {
        "controls.hex": "fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0",
        "M1_INPUT_CONFIRMATION.md": "56574246ebd7fe75bf59ea7f583ffe2c00f5593b8567230dbb6992cfe857b555",
        "readonly/t052_polyphony_test_source.sv": "89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb",
        "readonly/dds_oscillator.sv": "3cd758e28da8f76a30da38cb2dfcd458db5743d4ea4f38e072a43d7f83719f04",
        "readonly/pcm_mixer_4voice.sv": "93fb6e88e55ea84f2e322b0cf8b94a1a2c2e13618e302e7d24ec8657c92bb99a",
        "readonly/sine_1024_8192.mem": "5e1dbd3797f353686f5e567831b56d6dcf9bee55c423097b471ade93203e84b2",
    }
    copies = {}
    for relative, digest in frozen.items():
        source = str((output / "FAKE_METADATA_NOT_EXECUTABLE" / relative).resolve())
        copies[source] = relative
        identities[source] = {"bytes": 0, "sha256": digest}
    tb = HERE.parents[3] / "code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015"
    for name in ("tb_t052_long.sv", "t052_long_observer.sv"):
        source = str((tb / name).resolve())
        copies[source] = name
        identities[source] = runner.identity(Path(source))
    return {"schema": "T052_LONG_ONE_SHOT_M2_V1", "approved": True,
            "machine": os.environ.get("COMPUTERNAME"),
            "format": "T052_LONG_PUBLIC_HEX_V1", "approval_id": "FAKE_NO_EXECUTION",
            "decision_reference": "FAKE_METADATA_TEST_NOT_M2_PERMISSION",
            "environment_sha256": runner.environment_sha(),
            "limits": dict(runner.MAXIMA), "output": str(output / "never_execute"),
            "allowance_directory": str(output), "identities": identities,
            "copies": copies, "supervisor_source_sha256": runner.sha(HERE / "bounded_runner.py"),
            "commands": {name: [executable, "-B", str(HERE / "fake_process.py"), "normal"]
                         for name in ("compile", "run", "check")}}


def main():
    if not __debug__:
        print("REFUSED: ASSERTIONS_DISABLED_PYTHON_OPTIMIZATION", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir()  # exclusive, no prior evidence overwritten
    original_out, original_err = sys.stdout, sys.stderr
    raw_out = (output / "test.stdout.bin").open("xb", buffering=0)
    raw_err = (output / "test.stderr.bin").open("xb", buffering=0)

    class Tee:
        def __init__(self, original, raw):
            self.original, self.raw = original, raw

        def write(self, text):
            self.raw.write(text.encode("utf-8"))
            return self.original.write(text)

        def flush(self):
            self.raw.flush()
            self.original.flush()

    sys.stdout, sys.stderr = Tee(original_out, raw_out), Tee(original_err, raw_err)
    started = time.monotonic()
    results = []
    initial_sources = {str(p): runner.identity(p) for p in
                       (HERE / "bounded_runner.py", HERE / "win_job.py",
                        HERE / "fake_process.py", Path(__file__).resolve(),
                        Path(sys.executable))}
    with zipfile.ZipFile(output / "source_before.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in ("bounded_runner.py", "win_job.py", "fake_process.py",
                         "test_bounded_runner.py"):
            archive.write(HERE / filename, filename)

    def check_case(name, expected, action):
        directory = output / name
        directory.mkdir()
        result = {"case": name, "expected_diagnostic": expected, "status": "FAIL"}
        try:
            result.update(action(directory))
            result["status"] = "PASS"
        except BaseException as exc:
            result["error"] = repr(exc)
            result["traceback"] = traceback.format_exc()
        result["files"] = {str(p.relative_to(directory)): runner.identity(p)
                           for p in directory.rglob("*") if p.is_file()}
        runner.write_json(directory / "case.json", result)
        results.append(result)
        print(name + ": " + result["status"], flush=True)

    def process_case(mode, expected, seconds=2, total_seconds=10):
        def run(directory):
            limits = {"stream_bytes": 16*1024, "capture_bytes": 64*1024,
                      "output_bytes": 128*1024, "poll_seconds": 0.01}
            argv = [sys.executable, "-B", "-X", "utf8",
                    str(HERE / "fake_process.py"), mode]
            receipt = runner.supervise(argv, directory, "fake", seconds,
                                       time.monotonic()+total_seconds, limits)
            assert receipt["diagnostic"] in expected, receipt
            assert receipt["status"] == ("PROCESS_EXIT_ACCEPTABLE" if expected == {"NONE"} else "FAIL"), receipt
            assert receipt["job_empty_after_termination"] is True, receipt
            assert set(receipt["streams"]) == {"fake.stdout.bin", "fake.stderr.bin"}, receipt
            assert receipt["elapsed_seconds"] < 8, receipt
            if mode == "capture_limit":
                assert receipt["final_capture_bytes"] > limits["capture_bytes"]
                assert receipt["final_output_bytes"] < limits["output_bytes"]
            stopped = {}
            for identity_file in directory.glob("*.identity.json"):
                before = json.loads(identity_file.read_text(encoding="utf-8"))
                after = process_creation(before["pid"])
                same_live = (after is not None and after["alive"] and
                             after["creation_filetime"] == before["creation_filetime"])
                assert not same_live, (before, after)
                stopped[identity_file.name] = {"before": before, "after": after,
                                               "same_identity_alive": same_live}
            if mode in ("tree_timeout", "orphan"):
                assert set(stopped) == {"child.identity.json", "grandchild.identity.json"}, stopped
                sizes_before = {p.name: p.stat().st_size for p in directory.glob("*.heartbeat")}
                time.sleep(0.1)
                sizes_after = {p.name: p.stat().st_size for p in directory.glob("*.heartbeat")}
                assert sizes_before == sizes_after
            return {"receipt": receipt, "descendants": stopped, "actual_argv": argv}
        return run

    cases = [
        ("normal", {"NONE"}, 2, 10),
        ("stdout_limit", {"STREAM_LIMIT_OR_PIPE_ERROR", "STREAM_LIMIT"}, 2, 10),
        ("stderr_limit", {"STREAM_LIMIT_OR_PIPE_ERROR", "STREAM_LIMIT"}, 2, 10),
        ("capture_limit", {"FINAL_FILE_LIMIT", "CAPTURE_LIMIT"}, 2, 10),
        ("output_limit", {"FINAL_FILE_LIMIT", "OUTPUT_LIMIT"}, 2, 10),
        ("tree_timeout", {"STEP_TIMEOUT"}, 1.5, 10),
        ("orphan", {"DESCENDANTS_REMAIN"}, 2, 10),
        ("nonzero", {"PROCESS_EXIT_NONZERO"}, 2, 10),
        ("error", {"ERROR_DIAGNOSTIC"}, 2, 10),
        ("fatal", {"ERROR_DIAGNOSTIC"}, 2, 10),
        ("failure", {"ERROR_DIAGNOSTIC"}, 2, 10),
        ("sleep", {"TOTAL_TIMEOUT"}, 2, 0.4),
    ]
    for mode, expected, seconds, total in cases:
        check_case(mode, sorted(expected), process_case(mode, expected, seconds, total))

    def optimized_refusal(directory):
        target = directory / "must_not_exist"
        receipt = runner.supervise(
            [sys.executable, "-B", "-O", "-X", "utf8", str(Path(__file__).resolve()),
             "--output", str(target)], directory, "optimized", 2,
            time.monotonic()+10, {"stream_bytes": 16*1024, "capture_bytes": 64*1024,
                                 "output_bytes": 128*1024, "poll_seconds": 0.01})
        assert receipt["diagnostic"] == "PROCESS_EXIT_NONZERO", receipt
        assert receipt["exit_code"] == 1, receipt
        assert not target.exists()
        assert b"ASSERTIONS_DISABLED_PYTHON_OPTIMIZATION" in (
            directory / "optimized.stderr.bin").read_bytes()
        return {"receipt": receipt, "optimized_entry_refused_before_output": True}

    check_case("optimized_entry_refused", "PROCESS_EXIT_NONZERO", optimized_refusal)

    def refusal(directory, callable_, expected):
        try:
            callable_()
        except (ValueError, OSError) as exc:
            assert expected in str(exc), str(exc)
            record = {"status": "EXPECTED_REFUSAL", "diagnostic": str(exc),
                      "no_process_started": True}
            runner.write_json(directory / "raw_refusal.json", record)
            return record
        raise AssertionError("expected refusal " + expected)

    def consume_twice(directory):
        path = directory / "compile.consumed.json"
        runner.consume(path, {"status": "CONSUMED_NO_RETRY", "scope": "PYTHON_FAKE_ONLY"})
        first = runner.identity(path)
        result = refusal(directory, lambda: runner.consume(path, {"overwritten": True}), "File exists")
        assert runner.identity(path) == first
        return result

    check_case("duplicate_consume", "File exists", consume_twice)
    fixture = approval_fixture(output)

    def fake_metadata_valid(directory):
        runner.validate_approval(fixture)
        # This checks syntax/identity declarations only, never execution.
        # Fake frozen paths cannot pass actual byte-identity verification.
        result = refusal(directory, lambda: runner.verify_identities(fixture),
                         "FAKE_METADATA_NOT_EXECUTABLE")
        result["metadata_validation_only"] = "ACCEPTED_NOT_EXECUTION_PERMISSION"
        return result

    check_case("fake_metadata_valid_not_executable", "FAKE_PATH_IDENTITY_REFUSED",
               fake_metadata_valid)
    for name, mutation, expected in (
            ("approval_missing", lambda a: a.update(approved=False), "M2_APPROVAL_REQUIRED"),
            ("approval_machine", lambda a: a.update(machine="WRONG_MACHINE"), "MACHINE_IDENTITY"),
            ("approval_format", lambda a: a.update(format="WRONG_FORMAT"), "FORMAT_IDENTITY"),
            ("approval_budget", lambda a: a["limits"].update(run=301), "BUDGET:run"),
            ("approval_source", lambda a: a.update(supervisor_source_sha256="0"*64), "SUPERVISOR_IDENTITY")):
        modified = copy.deepcopy(fixture)
        mutation(modified)
        check_case(name, expected, lambda d, a=modified, e=expected:
                   refusal(d, lambda: runner.validate_approval(a), e))

    def drift(directory):
        source = directory / "source.txt"
        source.write_text("original\n", encoding="utf-8")
        approval = {"identities": {str(source): runner.identity(source)},
                    "environment_sha256": runner.environment_sha()}
        source.write_text("changed\n", encoding="utf-8")
        return refusal(directory, lambda: runner.verify_identities(approval), "IDENTITY_DRIFT")

    check_case("identity_drift", "IDENTITY_DRIFT", drift)
    check_case("environment_drift", "ENVIRONMENT_DRIFT", lambda d:
               refusal(d, lambda: runner.verify_identities(
                   {"identities": {}, "environment_sha256": "0"*64}),
                   "ENVIRONMENT_DRIFT"))

    def blocked_raw_log(directory):
        # Real filesystem failure in the raw writer: preserve a directory at
        # the requested stdout path so xb cannot silently replace it.
        (directory / "fake.stdout.bin").mkdir()
        receipt = runner.supervise(
            [sys.executable, "-B", str(HERE / "fake_process.py"), "normal"],
            directory, "fake", 2, time.monotonic()+10,
            {"stream_bytes": 16*1024, "capture_bytes": 64*1024,
             "output_bytes": 128*1024, "poll_seconds": 0.01})
        assert receipt["status"] == "FAIL", receipt
        assert receipt["streams_complete"] is False, receipt
        assert receipt["job_empty_after_termination"] is True, receipt
        assert receipt["diagnostic"] == "STREAM_LIMIT_OR_PIPE_ERROR", receipt
        return {"receipt": receipt, "raw_stdout_missing": True}

    check_case("raw_log_unavailable", "STREAM_LIMIT_OR_PIPE_ERROR", blocked_raw_log)

    def scan_contract(directory):
        (directory / "controls.hex").write_bytes(b"X" * 1000)
        (directory / "observations.hex").write_bytes(b"Y" * 37)
        (directory / "compile.stdout.bin").write_bytes(b"A" * 13)
        (directory / "compile.stderr.bin").write_bytes(b"B" * 17)
        total, capture = runner.scan_sizes(directory)
        assert (total, capture) == (1067, 67), (total, capture)
        return {"total_bytes": total, "capture_bytes": capture,
                "controls_counted_only_in_total": True}

    check_case("capture_accounting", "TOTAL_1067_CAPTURE_67", scan_contract)

    def artifact_case(kind):
        def run(directory):
            receipt = runner.supervise(
                [sys.executable, "-B", str(HERE / "fake_process.py"), "normal"],
                directory, "run", 2, time.monotonic()+10,
                {"stream_bytes": 16*1024, "capture_bytes": 64*1024,
                 "output_bytes": 128*1024, "poll_seconds": 0.01})
            assert receipt["status"] == "PROCESS_EXIT_ACCEPTABLE", receipt
            if kind == "missing_compile_artifact":
                return refusal(directory, lambda: runner.validate_required_artifacts(
                    directory, "compile"), "COMPILE_ARTIFACT_MISSING")
            if kind == "missing_marker":
                return refusal(directory, lambda: runner.validate_required_artifacts(
                    directory, "run"), "RUN_FINISH_MARKER_MISSING_OR_DUPLICATE")
            # Separate synthetic artifact helper directory preserves raw child
            # stdout/stderr byte-for-byte; it is not an actual RTL capture.
            artifacts = directory / "synthetic_artifact_fixture"
            artifacts.mkdir()
            marker = b"T052_LONG_CAPTURE_FINISHED_NOT_ACCEPTANCE_PASS\n"
            (artifacts / "run.stdout.bin").write_bytes(marker * (2 if kind == "duplicate_marker" else 1))
            if kind == "duplicate_marker":
                return refusal(directory, lambda: runner.validate_required_artifacts(
                    artifacts, "run"), "RUN_FINISH_MARKER_MISSING_OR_DUPLICATE")
            for name in runner.CAPTURE_NAMES:
                (artifacts / name).write_bytes(b"synthetic-only\n")
            (artifacts / "observations.hex").unlink()
            if kind == "empty_capture":
                (artifacts / "observations.hex").touch()
            return refusal(directory, lambda: runner.validate_required_artifacts(
                artifacts, "run"), "CAPTURE_MISSING_OR_EMPTY:observations.hex")
        return run

    for kind in ("missing_compile_artifact", "missing_marker", "duplicate_marker",
                 "missing_capture", "empty_capture"):
        check_case(kind, "MISSING_OR_EMPTY_ARTIFACT_REJECTED", artifact_case(kind))
    final_sources = {p: runner.identity(Path(p)) for p in initial_sources}
    summary = {"status": "PASS" if all(r["status"] == "PASS" for r in results) and
               initial_sources == final_sources else "FAIL",
               "validation": "SOFTWARE_PYTHON_FAKE_PROCESSES_ONLY",
               "new_hdl_compile_count": 0, "new_rtl_run_count": 0,
               "execute_called": False, "actual_argv": sys.argv,
               "actual_orig_argv": sys.orig_argv,
               "cwd": str(Path.cwd()), "python": sys.version,
               "source_before": initial_sources, "source_after": final_sources,
               "elapsed_seconds": time.monotonic()-started, "cases": results}
    summary["exit_code"] = 0 if summary["status"] == "PASS" else 1
    print(json.dumps({"status": summary["status"], "cases": len(results)}))
    sys.stdout.flush()
    sys.stderr.flush()
    sys.stdout, sys.stderr = original_out, original_err
    raw_out.close()
    raw_err.close()
    summary["raw_streams"] = {p.name: runner.identity(p) for p in
                              (output / "test.stdout.bin", output / "test.stderr.bin")}
    summary["source_before_zip"] = runner.identity(output / "source_before.zip")
    runner.write_json(output / "summary.json", summary)
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
