"""Bounded pure-software audit, raw evidence and deterministic identity seal."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import zipfile
from pathlib import Path


SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[2]


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "tmp").mkdir()
    environment = dict(os.environ)
    environment["TMP"] = environment["TEMP"] = str(output / "tmp")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    source_before = {p.name: identity(p) for p in sorted(SOURCE.glob("*.py"))}
    old_core = REPO / "code/software/r04_receipt_check/receipt_check.py"
    commands = [
        ("baseline_expected_defect", 1, [sys.executable, "-B", "-X", "utf8",
          "reproduce_diagnostics.py", "--baseline", "--core", str(old_core),
          "--output", str(output / "baseline_cases")]),
        ("fixed_diagnostic_matrix", 0, [sys.executable, "-B", "-X", "utf8",
          "reproduce_diagnostics.py", "--core", str(SOURCE / "receipt_check.py"),
          "--output", str(output / "fixed_cases")]),
        ("unit_tests", 0, [sys.executable, "-B", "-X", "utf8", "-m", "unittest",
                           "discover", "-s", str(SOURCE), "-p", "test_*.py", "-v"]),
    ]
    started = time.monotonic()
    calls = []
    for name, expected, command in commands:
        remaining = 300 - (time.monotonic() - started)
        if remaining <= 0:
            break
        step_started = time.monotonic()
        timeout = False
        try:
            process = subprocess.run(command, cwd=SOURCE, env=environment,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     timeout=min(90, remaining), check=False)
            code, stdout, stderr = process.returncode, process.stdout, process.stderr
        except subprocess.TimeoutExpired as exc:
            timeout = True
            code, stdout, stderr = 124, exc.stdout or b"", exc.stderr or b""
        (output / f"{name}.stdout.txt").write_bytes(stdout)
        (output / f"{name}.stderr.txt").write_bytes(stderr)
        calls.append({"name": name, "command": command, "cwd": str(SOURCE),
                      "exit_code": code, "expected_exit_code": expected,
                      "timed_out": timeout, "elapsed_seconds": time.monotonic() - step_started,
                      "passed": code == expected and not timeout})
        if code != expected or timeout:
            break
    source_after = {p.name: identity(p) for p in sorted(SOURCE.glob("*.py"))}
    # This archive preserves all raw synthetic case files, including the old
    # false acceptance and exact original source bytes; no old file is rewritten.
    archive_path = output / "SYNTHETIC_DIAGNOSTIC_CASES.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for folder in (output / "baseline_cases", output / "fixed_cases"):
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(output).as_posix())
    passed = (len(calls) == len(commands) and all(c["passed"] for c in calls)
              and source_before == source_after and time.monotonic() - started <= 300)
    receipt = {
        "schema": "m3_r04_audit_software_selftest_v1", "status": "PASS" if passed else "FAIL",
        "evidence_kind": "SYNTHETIC_SOFTWARE_ONLY", "machine": platform.node(),
        "python": {"path": sys.executable, "version": sys.version,
                   "identity": identity(Path(sys.executable))},
        "runtime_dependency_identities": {
            str(Path(module.__file__).resolve()): identity(Path(module.__file__))
            for module in list(sys.modules.values())
            if getattr(module, "__file__", None) and Path(module.__file__).is_file()
        },
        "source_before": source_before, "source_after": source_after,
        "baseline_core": {"path": str(old_core), **identity(old_core)},
        "calls": calls, "actual_test_child_calls": len(calls), "actual_modelsim_calls": 0,
        "total_budget_seconds": 300, "per_step_budget_seconds": 90,
        "elapsed_seconds": time.monotonic() - started,
        "real_r04_status": "PENDING", "t052_long_rtl": "NOT_RUN_OLD_4207_UNKNOWN",
        "per_request_deadline": "UNKNOWN",
        "artifacts": {p.name: identity(p) for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "SOFTWARE_SELFTEST_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "actual_test_child_calls": len(calls),
                      "actual_modelsim_calls": 0, "output": str(output)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
