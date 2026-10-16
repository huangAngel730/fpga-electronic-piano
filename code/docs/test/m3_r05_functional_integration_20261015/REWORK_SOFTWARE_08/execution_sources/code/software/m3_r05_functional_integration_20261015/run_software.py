"""New R05 policy/ledger software tests; no ModelSim/RTL execution."""
from datetime import datetime, timezone
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from common import HERE, ROOT, DOCS, Refusal, identity, write_new, json_bytes, snapshot_sources
from input_binding import inspect_archive
from test_software import GOOD, ledger_fixture, encoded


def run(output):
    output = output.resolve()
    if output.parent != DOCS.resolve() or output.name == "coordinator":
        raise Refusal("OUTPUT_SCOPE", "output outside own directory")
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    before = snapshot_sources()
    receipt = {
        "schema": "M3_R05_SOFTWARE_SELFTEST_V1", "status": "RUNNING",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "machine": platform.node(), "python": identity(sys.executable),
        "source_before": before, "single_budget_s": 90, "total_budget_s": 300,
        "calls": [], "functional_ModelSim_calls": 0, "RTL_calls": 0,
        "board_release_allowed": False,
    }
    write_new(output / "PLAN.json", receipt)
    calls = receipt["calls"]

    def invoke(name, argv, expected, diagnostic=None):
        began = time.monotonic()
        budget = min(90, 300 - (began - start))
        if budget <= 0:
            raise TimeoutError("software total budget exhausted")
        timeout = False
        try:
            child = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   timeout=budget, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            stdout, stderr, code = child.stdout, child.stderr, child.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", None
            timeout = True
        out, err = output / (name + ".stdout.log"), output / (name + ".stderr.log")
        out.write_bytes(stdout)
        err.write_bytes(stderr)
        call = {
            "name": name, "argv": list(map(str, argv)), "cwd": str(ROOT),
            "exit_code": code, "expected_exit": expected, "timeout": timeout,
            "elapsed_s": time.monotonic() - began, "budget_s": budget,
            "stdout": identity(out), "stderr": identity(err),
        }
        if diagnostic:
            try:
                result = json.loads(stdout.decode("utf-8"))
                call["diagnostic"] = result.get("diagnostic", result.get("status"))
            except ValueError:
                call["diagnostic"] = "INVALID_RESULT"
            call["expected_diagnostic"] = diagnostic
        calls.append(call)
        write_new(output / (name + ".receipt.json"), call)
        if timeout or code != expected or diagnostic and call["diagnostic"] != diagnostic:
            raise RuntimeError(name + ": unexpected result, original retained")

    try:
        _, bound = inspect_archive()
        write_new(output / "INPUT_BINDING.json", bound)
        cases = [
            ("positive", GOOD, b"Errors: 00\n", 0, False, 0, None),
            ("missing_pass", GOOD.replace(b"PASS M2", b"NO M2"), b"", 0, False, 1, "EXACT_PASS_MISSING_OR_DUPLICATE"),
            ("fake_pass", GOOD.replace(b"PASS M2", b"NOT PASS M2"), b"", 0, False, 1, "EXACT_PASS_MISSING_OR_DUPLICATE"),
            ("nonzero", GOOD, b"", 7, False, 1, "NONZERO_OR_INVALID_EXIT"),
            ("timeout", GOOD, b"", 0, True, 1, "TIMEOUT_OR_INVALID_FLAG"),
            ("x_summary", GOOD.replace(b"active=4", b"active=x"), b"", 0, False, 1, "SUMMARY_MISSING_OR_X"),
            ("834_summary", GOOD.replace(b"max_cycles=155", b"max_cycles=834"), b"", 0, False, 1, "R05_SUMMARY_PREDICATE"),
            ("cross_stream", GOOD.replace(b"# PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY\n", b""), b"PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY\n", 0, False, 1, "EXACT_PASS_MISSING_OR_DUPLICATE"),
        ]
        for number, diagnostic_text in enumerate((b"Error: synthetic", b"Errors: 1", b"Errors: 01", b"Errors: 0001", b"** Failure: synthetic", b"FATAL: synthetic")):
            for before_error in (False, True):
                for side in ("stdout", "stderr"):
                    bad = diagnostic_text + b"\n"
                    out, err = GOOD, b""
                    if side == "stdout":
                        out = bad + out if before_error else out + bad
                    else:
                        err = bad
                    cases.append((f"diagnostic_{number}_{before_error}_{side}", out, err, 0, False, 1, "TOOL_DIAGNOSTIC"))
        for name, stdout, stderr, exit_code, timeout, expected, diagnostic in cases:
            folder = output / ("SYNTHETIC_" + name)
            folder.mkdir()
            out, err = folder / "vsim.stdout.log", folder / "vsim.stderr.log"
            out.write_bytes(stdout)
            err.write_bytes(stderr)
            write_new(folder / "EVIDENCE_KIND.json", {"kind": "SYNTHETIC_SOFTWARE_FIXTURE_NOT_TOOL_EXECUTION"})
            argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "receipt_cli.py"),
                    "--step", "vsim", "--stdout", str(out), "--stderr", str(err),
                    "--exit-code", str(exit_code), "--timeout", str(timeout).lower(), "--synthetic"]
            invoke(name, argv, expected, diagnostic)
        missing = output / "MISSING_STREAM"
        missing.mkdir()
        (missing / "stdout.log").write_bytes(GOOD)
        invoke("missing_stream", [sys.executable, "-B", "-X", "utf8", str(HERE / "receipt_cli.py"),
               "--step", "vsim", "--stdout", str(missing / "stdout.log"), "--stderr", str(missing / "absent.log"),
               "--exit-code", "0", "--timeout", "false", "--synthetic"], 1, "MISSING_STREAM")
        records = ledger_fixture()
        for name, altered, expected in (
            ("ledger_positive", records, 0),
            ("ledger_missing_tick", records[:100] + records[101:], 1),
        ):
            p = output / ("SYNTHETIC_" + name + ".jsonl")
            p.write_bytes(encoded(altered))
            invoke(name, [sys.executable, "-B", "-X", "utf8", str(HERE / "ledger_cli.py"), str(p)], expected)
        invoke("unit_tests", [sys.executable, "-B", "-X", "utf8", "-m", "unittest", "discover", "-s", str(HERE), "-p", "test_software.py", "-v"], 0)
        receipt["source_after"] = snapshot_sources()
        if receipt["source_after"] != before:
            raise RuntimeError("source changed during software tests")
        receipt["elapsed_s"] = time.monotonic() - start
        if receipt["elapsed_s"] >= 300:
            raise TimeoutError("post-collection budget exhausted")
        receipt["status"] = "SOFTWARE_SELFTEST_PASS"
        receipt["outer_process_count"] = len(calls)
        write_new(output / "RUN_RECEIPT.json", receipt)
        print(receipt["status"], len(calls))
        return 0
    except Exception as exc:
        receipt.update({"status": "SOFTWARE_SELFTEST_FAIL", "error": repr(exc), "elapsed_s": time.monotonic() - start})
        write_new(output / "RUN_RECEIPT.json", receipt)
        print(receipt["status"], receipt["error"])
        return 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    return run(p.parse_args().output)


if __name__ == "__main__":
    sys.exit(main())
