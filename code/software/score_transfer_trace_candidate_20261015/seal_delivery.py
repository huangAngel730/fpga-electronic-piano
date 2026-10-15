"""Create a non-overwriting offline delivery archive for the T057 trace candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile


SOURCE_NAMES = (
    "score_trace_verify.py",
    "selftest.py",
    "run_repo_gate.py",
    "seal_delivery.py",
    "README.md",
    "RECOVERY_CASES.md",
    "FROZEN_INPUTS.json",
)


def digest(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"missing evidence directory {source}")
    shutil.copytree(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selftest", type=Path, required=True)
    parser.add_argument("--existing-report", type=Path, required=True)
    parser.add_argument("--repo-gate", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output already exists; refuse overwrite")
    selftest_receipt = json.loads(
        (args.selftest / "selftest_receipt.json").read_text(encoding="utf-8")
    )
    existing_report = json.loads(
        (args.existing_report / "report.json").read_text(encoding="utf-8")
    )
    if selftest_receipt.get("status") != "PASS" or selftest_receipt.get("scenario_count", 0) < 43:
        raise ValueError("selftest receipt is not the expected >=43-scenario PASS")
    here = Path(__file__).resolve().parent
    for name in ("score_trace_verify.py", "selftest.py"):
        current = digest(here / name)["sha256"]
        if selftest_receipt.get("source_sha256", {}).get(name) != current:
            raise ValueError(f"selftest source hash does not bind current {name}")
    required_scenarios = {
        "positive_normal", "positive_fragmented", "positive_coalesced_retry",
        "positive_late_duplicate_response", "negative_same_identity_changed_body_pending",
        "negative_nack_then_successful_recovery", "negative_malformed_hex",
        "negative_expected_records_capacity", "positive_fixed_hex_golden",
    }
    observed_scenarios = {item.get("name") for item in selftest_receipt.get("scenarios", [])}
    if not required_scenarios <= observed_scenarios:
        raise ValueError("selftest receipt lacks required boundary scenarios")
    if (existing_report.get("input_mode") != "legacy_rtl_capture" or
            existing_report.get("status") != "INVALID" or
            existing_report.get("exit_code") != 2):
        raise ValueError("existing report input identity")
    finding_codes = {item.get("code") for item in existing_report.get("findings", [])}
    if "CONTRACT_IMPLEMENTATION_DIVERGENCE_COMMIT_NACK8_SESSION" not in finding_codes:
        raise ValueError("existing report lacks frozen COMMIT/NACK8 divergence")
    decoded_sha = next(
        (item["sha256"] for item in existing_report["file_identities"]
         if item["role"] == "legacy_rtl_capture_decoded"), None
    )
    if decoded_sha != "c6ed14c912ebd40db72e3ffe04691deb1006fab77ef538ac0050ec5db1c7ce28":
        raise ValueError("historical decoded capture SHA mismatch")
    gate_stdout = (args.repo_gate / "stdout.bin").read_bytes()
    gate_stderr = (args.repo_gate / "stderr.bin").read_bytes()
    gate_receipt = json.loads((args.repo_gate / "receipt.json").read_text(encoding="utf-8"))
    if (gate_receipt.get("status") != "PASS" or gate_receipt.get("exit_code") != 0 or
            gate_receipt.get("cwd") != str(Path(__file__).resolve().parents[3]) or
            gate_receipt.get("stdout_sha256") != hashlib.sha256(gate_stdout).hexdigest() or
            gate_receipt.get("stderr_sha256") != hashlib.sha256(gate_stderr).hexdigest() or
            b"All repository checks passed." not in gate_stdout or gate_stderr):
        raise ValueError("repository gate is not a clean PASS")
    args.output.mkdir(parents=True)
    source_dir = args.output / "source"
    source_dir.mkdir()
    for name in SOURCE_NAMES:
        shutil.copy2(here / name, source_dir / name)
    copy_tree(args.selftest, args.output / "selftest")
    copy_tree(args.existing_report, args.output / "existing_rtl")
    copy_tree(args.repo_gate, args.output / "repo_gate")
    receipt = {
        "schema": 1,
        "status": "PASS",
        "validation_level": "offline_software_only",
        "commands": {
            "selftest": selftest_receipt.get("invocation"),
            "existing_capture": "<bundled-python> -B -X utf8 score_trace_verify.py --legacy-capture <frozen-capture> --base64 --mode recover --output <new-output>",
            "repository_gate": gate_receipt["command"],
        },
        "exit_codes": {"selftest": 0, "existing_capture": 2, "repository_gate": 0},
        "selftest": {"status": "PASS", "scenarios": selftest_receipt["scenario_count"],
                     "synthetic_fixture_only": True},
        "existing_capture": {
            "status": existing_report["status"],
            "decoded_sha256": decoded_sha,
            "interpretation": (
                "Historical ModelSim acceptance capture contains intentional bad frames/NACK cases "
                "and the frozen COMMIT/NACK8 contract divergence; it is not a clean hardware log."
            ),
        },
        "repository_gate": {
            "status": "PASS",
            "stdout_sha256": hashlib.sha256(gate_stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(gate_stderr).hexdigest(),
        },
        "existing_hardware_tx_rx_logs_found": False,
        "hardware_verified": False,
        "serial_opened": False,
        "rtl_or_eda_run_by_this_task": False,
        "git_write_performed": False,
    }
    (args.output / "delivery_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest: dict[str, dict[str, object]] = {}
    for path in sorted(args.output.rglob("*")):
        if path.is_file() and path.name not in ("MANIFEST.json", "T057_TRACE_DELIVERY.zip"):
            manifest[path.relative_to(args.output).as_posix()] = digest(path)
    (args.output / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    archive_path = args.output / "T057_TRACE_DELIVERY.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file() and path != archive_path:
                archive.write(path, path.relative_to(args.output).as_posix())
    print(json.dumps({"status": "PASS", "archive": str(archive_path),
                      "archive_sha256": digest(archive_path)["sha256"],
                      "files": len(manifest)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
