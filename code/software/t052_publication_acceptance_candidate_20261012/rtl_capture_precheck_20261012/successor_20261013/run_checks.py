"""Bounded, software-only verification runner for T052 P0-2."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
MANIFEST = (
    ROOT / "code/docs/test/t052_publication_acceptance_20261012"
    / "CONTROL_PREPARATION_20261012/P0_1_DRIVER_20261013"
    / "combination_manifest.json"
)
MANIFEST_SHA = "0949f09747f517b08b36d6df78f8712111bb84f2da152b5a6969986532421b6c"
PLAN = (
    ROOT / "code/docs/test/t052_publication_acceptance_20261012"
    / "M2_CONTROL_PLAN_20261012/controls_proposed.jsonl"
)
RAW = (
    ROOT / "code/docs/evidence/m2_ab_failure_t052_static_review_20261013"
    / "RAW_EVIDENCE.zip"
)
TOTAL_LIMIT = 300
STEP_LIMIT = 90


def identity(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def invoke(label: str, argv: list[str], output: Path, expected_exit: int,
           expected_diagnostic: str | None, deadline: float) -> dict:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("TOTAL_BUDGET_EXHAUSTED")
    limit = min(STEP_LIMIT, remaining)
    start = time.monotonic()
    try:
        completed = subprocess.run(
            argv, cwd=HERE, capture_output=True, timeout=limit, check=False,
        )
        timed_out = False
        stdout, stderr = completed.stdout, completed.stderr
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        exit_code = 124
    (output / f"{label}.stdout.txt").write_bytes(stdout)
    (output / f"{label}.stderr.txt").write_bytes(stderr)
    diagnostic = None
    if stdout:
        try:
            diagnostic = json.loads(stdout.decode("utf-8").splitlines()[-1]).get(
                "diagnostic"
            )
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            pass
    record = {
        "label": label,
        "argv": argv,
        "exit_code": exit_code,
        "expected_exit": expected_exit,
        "diagnostic": diagnostic,
        "timed_out": timed_out,
        "elapsed_seconds": time.monotonic() - start,
        "stdout": identity(output / f"{label}.stdout.txt"),
        "stderr": identity(output / f"{label}.stderr.txt"),
    }
    (output / f"{label}.receipt.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    if timed_out or exit_code != expected_exit:
        raise RuntimeError(f"STEP_RESULT:{label}:{exit_code}")
    if expected_diagnostic is not None and diagnostic != expected_diagnostic:
        raise RuntimeError(f"STEP_DIAGNOSTIC:{label}:{diagnostic}")
    return record


def fixture_argv(case: Path) -> list[str]:
    argv = [
        sys.executable, "-I", "-S", "-B", "-X", "utf8", str(HERE / "checker.py"),
        "fixture", "--manifest", str(MANIFEST), "--manifest-sha", MANIFEST_SHA,
        "--plan", str(PLAN),
    ]
    for track in ("controls", "observations", "publications", "resets"):
        argv.extend(["--" + track, str(case / f"{track}.jsonl")])
    return argv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        print(json.dumps({"status": "FAIL", "diagnostic": "OUTPUT_EXISTS"}))
        return 1
    output.mkdir(parents=True)
    started = time.monotonic()
    frozen = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths = [
        HERE / "checker.py", HERE / "fixtures.py", HERE / "test_checker.py",
        HERE / "run_checks.py", MANIFEST, PLAN, RAW,
        HERE.parents[1] / "publication.py",
    ]
    for item in (*frozen["sources"].values(), *frozen["tools"].values()):
        path = Path(item["path"])
        paths.append(path if path.is_absolute() else ROOT / path)
    before = {str(path): identity(path) for path in paths}
    deadline = started + TOTAL_LIMIT
    steps = []
    status, error = "T052_P0_2_SOFTWARE_PASS", None
    try:
        steps.append(invoke(
            "01_unit_tests",
            [sys.executable, "-I", "-S", "-B", "-X", "utf8",
             str(HERE / "test_checker.py")], output, 0, None, deadline,
        ))
        corpus = output / "software_corpus"
        steps.append(invoke(
            "02_generate_fixtures",
            [sys.executable, "-I", "-S", "-B", "-X", "utf8",
             str(HERE / "fixtures.py"), "--output", str(corpus)],
            output, 0, None, deadline,
        ))
        cases = (
            ("03_normal_software", "normal_software", 0, None),
            ("04_reject_all_ready_valid_zero", "reject_all_ready_valid_zero", 1,
             "SOURCE_CALENDAR_PINS:0"),
            ("05_reject_forged_source_sha", "reject_forged_source_sha", 1,
             "SOURCE_META:controls"),
        )
        for label, case, exit_code, diagnostic in cases:
            steps.append(invoke(
                label, fixture_argv(corpus / case), output, exit_code,
                diagnostic, deadline,
            ))
    except (OSError, RuntimeError, TimeoutError) as exception:
        status, error = "T052_P0_2_SOFTWARE_FAIL", str(exception)
    after = {name: identity(Path(name)) for name in before}
    if before != after:
        status, error = "T052_P0_2_SOFTWARE_FAIL", "INPUT_DRIFT"
    if time.monotonic() >= deadline:
        status, error = "T052_P0_2_SOFTWARE_FAIL", "TOTAL_BUDGET"
    receipt = {
        "schema": "T052_P0_2_SOFTWARE_RECEIPT_V1",
        "status": status,
        "exit_code": 0 if error is None else 1,
        "error": error,
        "evidence_kind": "SOFTWARE_ONLY",
        "manifest_sha256": MANIFEST_SHA,
        "expected_ledger": {"accepted": 6, "published": 3,
                            "cancelled": 3, "open": 0},
        "m2_counterexamples": {
            "archive": before[str(RAW)],
            "handling": "READ_ORIGINAL_MEMBERS_WITHOUT_SCHEMA_CONVERSION",
            "all_zero_rejected": error is None,
            "forged_source_rejected": error is None,
        },
        "source_input_before": before,
        "source_input_after": after,
        "source_input_unchanged": before == after,
        "total_limit_seconds": TOTAL_LIMIT,
        "per_step_limit_seconds": STEP_LIMIT,
        "elapsed_seconds": time.monotonic() - started,
        "steps": steps,
        "RTL_run": False,
        "HDL_tool_run": False,
        "RTL_verified": False,
        "T052_complete": False,
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n",
    )
    if time.monotonic() >= deadline:
        receipt["status"] = "T052_P0_2_SOFTWARE_FAIL"
        receipt["exit_code"] = 1
        receipt["error"] = "TOTAL_BUDGET_AFTER_RECEIPT"
        (output / "FAIL_AFTER_RECEIPT.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        status = receipt["status"]
    print(json.dumps({"status": status, "receipt": str(output / "receipt.json")},
                     sort_keys=True))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
