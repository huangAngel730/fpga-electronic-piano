"""Generate current-schema SOFTWARE fixtures for T052 P0-2.

These fixtures never carry an RTL origin and cannot qualify actual mode.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("t052_p0_2_checker", HERE / "checker.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

MANIFEST = (
    checker.ROOT
    / "code/docs/test/t052_publication_acceptance_20261012"
    / "CONTROL_PREPARATION_20261012/P0_1_DRIVER_20261013"
    / "combination_manifest.json"
)
MANIFEST_SHA = "0949f09747f517b08b36d6df78f8712111bb84f2da152b5a6969986532421b6c"
PLAN = (
    checker.ROOT
    / "code/docs/test/t052_publication_acceptance_20261012"
    / "M2_CONTROL_PLAN_20261012/controls_proposed.jsonl"
)


def write_case(root: Path, name: str, rows: dict[str, list[dict]]) -> None:
    case = root / name
    case.mkdir()
    for track, values in rows.items():
        (case / f"{track}.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in values),
            encoding="utf-8",
        )


def generate(output: Path) -> None:
    if output.exists():
        raise ValueError("FIXTURE_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    manifest = checker.load_manifest(MANIFEST, MANIFEST_SHA)
    expected = checker.expected_window(PLAN)
    baseline = {
        track: [checker.metadata(manifest, track, True)] + copy.deepcopy(expected[track])
        for track in checker.TRACKS
    }
    write_case(output, "normal_software", baseline)

    suppressed = copy.deepcopy(baseline)
    for row in suppressed["observations"][1:-1]:
        row.update(calc_ready=0, result_valid=0, result_req_id=0)
    suppressed["publications"] = [
        suppressed["publications"][0],
        {"type": "END", "accepted": 0, "published": 0,
         "cancelled": 0, "open": 0},
    ]
    write_case(output, "reject_all_ready_valid_zero", suppressed)

    forged = copy.deepcopy(baseline)
    for track in checker.TRACKS:
        forged[track][0]["observer_sha256"] = "0" * 64
    write_case(output, "reject_forged_source_sha", forged)

    (output / "manifest.json").write_text(json.dumps({
        "schema": "T052_P0_2_SOFTWARE_FIXTURES_V1",
        "evidence_kind": "SOFTWARE_FIXTURE",
        "actual_RTL": False,
        "cases": {
            "normal_software": {"exit_code": 0, "diagnostic": None},
            "reject_all_ready_valid_zero": {
                "exit_code": 1,
                "diagnostic": "SOURCE_CALENDAR_PINS:0",
            },
            "reject_forged_source_sha": {
                "exit_code": 1,
                "diagnostic": "SOURCE_META:controls",
            },
        },
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        generate(args.output)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "diagnostic": str(error)}, sort_keys=True))
        return 1
    print(json.dumps({"status": "SOFTWARE_FIXTURES_WRITTEN",
                      "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
