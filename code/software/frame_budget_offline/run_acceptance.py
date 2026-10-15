#!/usr/bin/env python3
"""Run the bounded synthetic acceptance set and preserve a receipt."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_case(name: str, args: list[str], expected_exit: int) -> dict[str, object]:
    command = [sys.executable, "-B", *args]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return {
        "name": name,
        "command": command,
        "cwd": str(ROOT),
        "expected_exit_code": expected_exit,
        "actual_exit_code": completed.returncode,
        "passed": completed.returncode == expected_exit,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    EVIDENCE.mkdir(exist_ok=True)
    cases = [
        run_case(
            "unit_tests",
            ["-m", "unittest", "-v", "test_frame_budget_offline.py"],
            0,
        ),
        run_case(
            "valid_833_834_distribution",
            [
                "frame_budget_offline.py",
                "samples/pass_833_834.csv",
                "--summary",
                "evidence/pass_summary.json",
            ],
            0,
        ),
        run_case(
            "reject_processing_834",
            [
                "frame_budget_offline.py",
                "samples/fail_processing_834.csv",
                "--summary",
                "evidence/fail_processing_834_summary.json",
            ],
            1,
        ),
        run_case(
            "reject_underrun",
            [
                "frame_budget_offline.py",
                "samples/fail_underrun.csv",
                "--summary",
                "evidence/fail_underrun_summary.json",
            ],
            1,
        ),
        run_case(
            "reject_missing_field_schema",
            [
                "frame_budget_offline.py",
                "samples/error_missing_field.csv",
                "--summary",
                "evidence/error_missing_field_summary.json",
            ],
            2,
        ),
    ]
    files = [
        ROOT / "README.md",
        ROOT / "frame_budget_offline.py",
        ROOT / "run_acceptance.py",
        ROOT / "test_frame_budget_offline.py",
        ROOT / "samples" / "pass_833_834.csv",
        ROOT / "samples" / "fail_processing_834.csv",
        ROOT / "samples" / "fail_underrun.csv",
        ROOT / "samples" / "error_missing_field.csv",
    ]
    receipt = {
        "schema": "r04_frame_budget_offline_acceptance_v1",
        "scope": "SYNTHETIC_ANALYZER_ONLY_NO_MODELSIM",
        "python_executable": sys.executable,
        "python_version": sys.version,
        "cases": cases,
        "source_identities": {
            str(path.relative_to(ROOT)): {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        },
        "status": "PASS" if all(case["passed"] for case in cases) else "FAIL",
        "limitations": [
            "Only synthetic CSV inputs were analyzed.",
            "ModelSim, RTL simulation, synthesis, PnR, STA, and device calls were not run.",
            "This receipt does not prove the R04 whole-system frame budget.",
        ],
    }
    receipt_path = EVIDENCE / "ACCEPTANCE_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    log_lines = [
        f"{case['name']}: expected={case['expected_exit_code']} "
        f"actual={case['actual_exit_code']} "
        f"result={'PASS' if case['passed'] else 'FAIL'}"
        for case in cases
    ]
    log_lines.append(f"OVERALL: {receipt['status']}")
    (EVIDENCE / "acceptance.txt").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8", newline="\n"
    )
    print("\n".join(log_lines))
    print(f"receipt={receipt_path}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
