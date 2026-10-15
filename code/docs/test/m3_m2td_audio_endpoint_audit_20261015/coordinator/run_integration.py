"""Connect the two independent deliveries using only the frozen raw report."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"integration_R[0-9]{2}", args.run_id):
        parser.error("run-id must be integration_RNN")
    coordinator = Path(__file__).resolve().parent
    repo = coordinator.parents[4]
    software = repo / "code/software/m3_m2td_audio_endpoint_audit_20261015"
    checker = software / "endpoint_audit.py"
    observations_file = coordinator.parent / "targets.json"
    source_zip = repo / (
        "code/docs/evidence/m2_m1td_physical_20261015/"
        "M2_138K_M1TD_整机PnR_STA_20261015.zip"
    )
    output = coordinator / args.run_id
    output.mkdir(exist_ok=False)
    proposal_file = coordinator.parent / "STA_PROPOSAL_NOT_EXECUTABLE.tcl.txt"
    protected = [checker, observations_file, proposal_file, source_zip, Path(__file__).resolve()]
    protected += sorted(software.glob("*.py"))
    before = {str(path): digest(path) for path in protected}
    observations = json.loads(observations_file.read_text(encoding="utf-8"))
    assert observations["board_release_allowed"] is False
    assert digest(source_zip) == observations["source_archive"]["sha256"]
    sys.path.insert(0, str(software))
    from endpoint_audit import SCHEMA, directed_prefixes, parse_report

    with zipfile.ZipFile(source_zip) as archive:
        report_bytes = archive.read(observations["report_member"])
    assert hashlib.sha256(report_bytes).hexdigest() == observations["report_sha256"]
    metadata = parse_report(report_bytes)["metadata"]
    proposal = proposal_file.read_text(encoding="utf-8")
    query_checks = []
    for target in observations["targets"]:
        for analysis in ("setup", "hold"):
            prefixes = directed_prefixes(analysis, target)
            query_checks.append({
                "target_id": target["id"], "analysis": analysis,
                "checker_prefixes": prefixes,
                "proposal_matches": any(
                    prefix.removeprefix("Report Command:")
                    + " -max_paths 1 -max_common_paths 1" in proposal
                    for prefix in prefixes
                ),
            })
    steps = []
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    for target in observations["targets"]:
        case = output / target["id"]
        case.mkdir()
        plan = {
            "schema": SCHEMA,
            "clock": "sys_clk",
            "period_ns": "25",
            "source": {
                "kind": "FROZEN_PHYSICAL_ZIP",
                "report_sha256": observations["report_sha256"],
                "archive_sha256": observations["source_archive"]["sha256"],
                "member": observations["report_member"],
                "metadata": metadata,
            },
            "targets": [{
                "id": target["id"],
                "from_node": target["from_node"],
                "to_node": target["to_node"],
                # First check raw pair coverage. This does not waive directed
                # command requirements for M2's future targeted STA delivery.
                "require_directed": False,
            }],
        }
        plan_file = case / "checker_targets.json"
        write_json(plan_file, plan)
        command = [
            sys.executable, "-B", "-X", "utf8", str(checker),
            "--zip", str(source_zip), "--zip-sha256", digest(source_zip),
            "--targets", str(plan_file), "--targets-sha256", digest(plan_file),
        ]
        started = time.monotonic()
        result = subprocess.run(command, cwd=repo, env=environment, capture_output=True, timeout=30)
        (case / "stdout.log").write_bytes(result.stdout)
        (case / "stderr.log").write_bytes(result.stderr)
        parsed = json.loads(result.stdout.decode("utf-8"))
        expected = "MISSING_" + target["missing_analysis"].upper()
        matched = result.returncode == 1 and parsed.get("diagnostic") == expected
        matched = matched and parsed.get("board_release_allowed") is False
        steps.append({
            "target_id": target["id"], "command": command, "cwd": str(repo),
            "exit_code": result.returncode, "elapsed_seconds": time.monotonic() - started,
            "expected_diagnostic": expected, "actual_diagnostic": parsed.get("diagnostic"),
            "matched_expected_incomplete_coverage": matched,
            "targets_sha256": digest(plan_file),
            "stdout_sha256": digest(case / "stdout.log"),
            "stderr_sha256": digest(case / "stderr.log"),
        })
    after = {str(path): digest(path) for path in protected}
    matched = before == after and bool(steps) and all(
        step["matched_expected_incomplete_coverage"] for step in steps
    ) and all(check["proposal_matches"] for check in query_checks)
    receipt = {
        "status": "INTEGRATION_MATCHED_PENDING_STA" if matched else "INTEGRATION_FAILED",
        "scope": "L0/L1_TWO_DELIVERIES_RAW_REPORT_CROSSCHECK",
        "python_executable": sys.executable,
        "python_sha256": digest(Path(sys.executable)),
        "inputs_before": before, "inputs_after": after,
        "steps": steps, "query_checks": query_checks, "board_release_allowed": False,
        "new_sta_executed": False,
        "limitation": "Expected rejection confirms incomplete coverage, not an STA violation or a physical PASS.",
    }
    write_json(output / "INTEGRATION_RECEIPT.json", receipt)
    print(json.dumps({"status": receipt["status"], "cases": len(steps), "source_stable": before == after}))
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
