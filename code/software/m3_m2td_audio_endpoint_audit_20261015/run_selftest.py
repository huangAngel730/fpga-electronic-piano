"""Bounded SOFTWARE ONLY selftest; preserve each real process's dual streams."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

import endpoint_audit as audit
import fixtures


HERE = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def file_id(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": audit.sha256(data)}


def snapshot():
    return {
        path.name: file_id(path)
        for path in sorted(HERE.iterdir())
        if path.is_file() and path.suffix in (".py", ".md", ".json")
    }


def run(output: Path) -> int:
    output = output.resolve()
    if output.parent != (HERE / "runs").resolve():
        raise ValueError("output must be a new direct child of this task's runs/")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    before = snapshot()
    calls = []
    receipt = {
        "schema": "m3_audio_endpoint_software_run_v1",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "machine": platform.node(), "platform": platform.platform(),
        "python_version": sys.version, "python": file_id(sys.executable),
        "cwd": str(fixtures.ROOT), "output": str(output),
        "single_process_budget_s": 90, "total_budget_s": 300,
        "source_before": before, "calls": calls,
        "board_release_allowed": False, "new_sta_executed": False,
        "eda_calls": 0, "status": "RUNNING",
    }
    deps = {}
    for name in (
        "html.parser", "html.entities", "json", "decimal", "hashlib",
        "zipfile", "argparse", "unittest", "subprocess", "pathlib",
    ):
        module = importlib.import_module(name)
        deps[name] = file_id(module.__file__)
    receipt["python_dependencies"] = deps
    write_json(output / "EXECUTION_PLAN.json", receipt)

    def invoke(name, argv, expected_exit, expected_diagnostic=None):
        remaining = 300 - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("total software budget exhausted")
        timeout = min(90, remaining)
        began = time.monotonic()
        timed_out = False
        try:
            process = subprocess.run(
                argv, cwd=fixtures.ROOT, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=timeout, check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            stdout, stderr, exit_code = process.stdout, process.stderr, process.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr = exc.stdout or b"", exc.stderr or b""
            exit_code = None
            timed_out = True
        out = output / f"{name}.stdout.txt"
        err = output / f"{name}.stderr.txt"
        out.write_bytes(stdout)
        err.write_bytes(stderr)
        item = {
            "name": name, "argv": argv, "cwd": str(fixtures.ROOT),
            "exit_code": exit_code, "expected_exit": expected_exit,
            "elapsed_s": time.monotonic() - began, "budget_s": timeout,
            "timeout": timed_out, "stdout": file_id(out), "stderr": file_id(err),
            "expected_diagnostic": expected_diagnostic,
        }
        if expected_diagnostic:
            try:
                parsed = json.loads(stdout.decode("utf-8"))
                actual = parsed.get("diagnostic", parsed.get("status"))
            except (ValueError, UnicodeError):
                actual = "INVALID_RESULT"
            item["actual_diagnostic"] = actual
        item["passed"] = (
            not timed_out and exit_code == expected_exit
            and (not expected_diagnostic or item["actual_diagnostic"] == expected_diagnostic)
        )
        calls.append(item)
        write_json(output / "RUN_RECEIPT.json", receipt)
        if not item["passed"]:
            raise RuntimeError(f"{name}: unexpected result (failure retained)")

    try:
        original, parsed = fixtures.original()
        originals = output / "originals"
        originals.mkdir()
        (originals / "timing.html").write_bytes(original)
        with zipfile.ZipFile(fixtures.ARCHIVE) as archive:
            (originals / "MANIFEST.json").write_bytes(archive.read("MANIFEST.json"))
        write_json(originals / "PARSED_OBSERVATIONS.json", parsed)
        receipt["input_archive"] = file_id(fixtures.ARCHIVE)
        receipt["input_report"] = file_id(originals / "timing.html")
        receipt["actual_report_summary"] = {
            "setup_rows": sum(p["analysis"] == "setup" for p in parsed["paths"]),
            "hold_rows": sum(p["analysis"] == "hold" for p in parsed["paths"]),
            "all_audio_target_setup_hold": False,
        }
        actual_plan = fixtures.target_plan(original, parsed["metadata"], frozen=True)
        target_file = originals / "targets.json"
        target_file.write_bytes(fixtures.serialize(actual_plan))
        base = [sys.executable, "-B", "-X", "utf8", str(HERE / "endpoint_audit.py")]
        invoke("original_pitch_hold_only", base + [
            "--zip", str(fixtures.ARCHIVE), "--zip-sha256", audit.FROZEN_ZIP_SHA,
            "--targets", str(target_file), "--targets-sha256",
            audit.sha256(target_file.read_bytes()),
        ], 1, "MISSING_SETUP")
        for name, data, plan, expected in fixtures.matrix():
            folder = output / name
            folder.mkdir()
            report_file = folder / "SYNTHETIC_report.html"
            plan_file = folder / "targets.json"
            report_file.write_bytes(data)
            plan_file.write_bytes(fixtures.serialize(plan))
            invoke(name, base + [
                "--report", str(report_file), "--targets", str(plan_file),
                "--targets-sha256", audit.sha256(plan_file.read_bytes()),
            ], 0 if expected == "SPECIFIED_REPORT_ENDPOINTS_SHOWN" else 1, expected)
        invoke("unit_tests", [
            sys.executable, "-B", "-X", "utf8", "-m", "unittest", "discover",
            "-s", str(HERE), "-p", "test_endpoint_audit.py", "-v",
        ], 0)
        after = snapshot()
        receipt["source_after"] = after
        if before != after:
            raise RuntimeError("source changed during execution")
        receipt["elapsed_s"] = time.monotonic() - started
        if receipt["elapsed_s"] > 300:
            raise TimeoutError("post-artifact total software budget exhausted")
        receipt["status"] = "SOFTWARE_SELFTEST_PASS"
        receipt["software_process_count"] = len(calls)
        write_json(output / "RUN_RECEIPT.json", receipt)
        print(json.dumps({
            "status": receipt["status"], "software_process_count": len(calls),
            "elapsed_s": receipt["elapsed_s"], "receipt": str(output / "RUN_RECEIPT.json"),
            "new_sta_executed": False, "board_release_allowed": False,
        }))
        return 0
    except Exception as exc:
        receipt.update({
            "status": "SOFTWARE_SELFTEST_FAIL", "failure": repr(exc),
            "elapsed_s": time.monotonic() - started, "source_after": snapshot(),
            "software_process_count": len(calls),
        })
        write_json(output / "RUN_RECEIPT.json", receipt)
        print(json.dumps({"status": receipt["status"], "failure": repr(exc)}))
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    sys.exit(main())
