"""Bounded pure-software preparation checks, with actual argv and receipts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import prepare_d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    output, project = args.output.resolve(), args.project.resolve()
    output_base = (ROOT / "code/output").resolve()
    if (output.exists() or output == output_base or not output.is_relative_to(output_base)
            or project.exists()):
        raise ValueError("D_NEW_EVIDENCE_AND_PROJECT_REQUIRED")
    output.mkdir()
    guard_dir = prepare_d.GUARD_DIR
    sources = [*HERE.glob("*.py"), HERE / "m3_n32_resource.sv", *guard_dir.glob("*.py")]
    sources += [p / filename for p in prepare_d.SEALS.values()
                for filename in ("seal.json", "MANIFEST.json", "snapshot.zip.b64")]
    sources += [prepare_d.TOOL_REFERENCE]
    before = {str(p): prepare_d.identity(p) for p in sources}
    python_before = prepare_d.identity(sys.executable)
    prefix = [sys.executable, "-I", "-S", "-B", "-X", "utf8"]
    builder = str(HERE / "prepare_d.py")
    steps = [
        ("prepare", [*prefix, builder, "prepare", "--project", str(project)], 0),
        ("exact_verify", [*prefix, builder, "verify", "--project", str(project)], 0),
        ("guard", [*prefix, str(guard_dir / "clock_guard.py"), "--project", str(project),
                   "--output", str(output / "guard_report.json")], 0),
        ("software_selftests", [*prefix, "-m", "unittest", "discover", "-s", str(guard_dir),
                                "-p", "test_clock_guard.py", "-v"], 0),
        ("execute_lock", [*prefix, builder, "execute", "--project", str(project)], 1),
        ("overwrite_lock", [*prefix, builder, "prepare", "--project", str(project)], 1),
    ]
    receipt = {"schema": "N32_D_SOFTWARE_CHECK_RECEIPT_V1", "status": "FAIL_PARTIAL",
               "exit_code": 1, "machine": socket.gethostname(), "steps": [],
               "sources_before": before, "python_before": python_before,
               "project": str(project), "actual_EDA_calls": 0, "RTL_calls": 0,
               "resources": "UNKNOWN", "STA": "NOT_RUN", "automatic_retries": 0}
    (output / "attempt.json").write_bytes(prepare_d.canonical(receipt))
    try:
        for name, argv, expected_exit in steps:
            if name == "guard":
                argv = [*argv, "--manifest-sha", prepare_d.identity(project / "manifest.json")["sha256"]]
            remaining = 900 - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError("D_TOTAL_BUDGET")
            step = {"name": name, "argv": argv, "cwd": str(ROOT), "expected_exit": expected_exit,
                    "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "timeout_seconds": min(90, remaining)}
            step_start = time.monotonic()
            out, err = output / (name + ".stdout.bin"), output / (name + ".stderr.bin")
            with out.open("xb") as stdout, err.open("xb") as stderr:
                try:
                    result = subprocess.run(argv, cwd=ROOT, stdin=subprocess.DEVNULL,
                                            stdout=stdout, stderr=stderr,
                                            timeout=step["timeout_seconds"], check=False)
                    step.update(exit_code=result.returncode, timeout=False)
                except subprocess.TimeoutExpired:
                    step.update(exit_code=None, timeout=True)
            step.update(elapsed_seconds=time.monotonic() - step_start,
                        ended_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        stdout=prepare_d.identity(out), stderr=prepare_d.identity(err))
            receipt["steps"].append(step)
            (output / (name + ".receipt.json")).write_bytes(prepare_d.canonical(step))
            if step["timeout"] or step["exit_code"] != expected_exit:
                raise ValueError("D_STEP_FAILED:" + name)
            if name == "prepare":
                prepared_set = {p.relative_to(project).as_posix(): prepare_d.identity(p)
                                for p in project.rglob("*") if p.is_file()}
        after_set = {p.relative_to(project).as_posix(): prepare_d.identity(p)
                     for p in project.rglob("*") if p.is_file()}
        if after_set != prepared_set:
            raise ValueError("D_CHECKS_MUTATED_PROJECT")
        receipt["sources_after"] = {p: prepare_d.identity(p) for p in before}
        receipt["python_after"] = prepare_d.identity(sys.executable)
        if receipt["sources_after"] != before or receipt["python_after"] != python_before:
            raise ValueError("D_SOURCE_OR_PYTHON_DRIFT")
        receipt["project_files"] = after_set
        receipt["manifest"] = prepare_d.identity(project / "manifest.json")
        receipt.update(status="N32_D_PREPARATION_AND_SOFTWARE_CHECKS_PASS", exit_code=0)
    except Exception as error:
        receipt["failure"] = type(error).__name__ + ":" + str(error)
    receipt["elapsed_seconds"] = time.monotonic() - started
    if receipt["elapsed_seconds"] >= 900:
        receipt.update(status="FAIL_PARTIAL", exit_code=1, failure="D_FINAL_TOTAL_BUDGET")
    (output / "receipt.json").write_bytes(prepare_d.canonical(receipt))
    if time.monotonic() - started >= 900:
        receipt.update(status="FAIL_PARTIAL", exit_code=1, failure="D_POST_RECEIPT_TOTAL_BUDGET")
        (output / "receipt.json").write_bytes(prepare_d.canonical(receipt))
    print(json.dumps({key: receipt[key] for key in ("status", "exit_code", "elapsed_seconds")}, sort_keys=True))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
