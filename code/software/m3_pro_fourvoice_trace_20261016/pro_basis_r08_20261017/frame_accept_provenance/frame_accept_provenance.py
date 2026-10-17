"""F/A/result/commit/cleanup provenance and deadline diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class ProvenanceReject(ValueError):
    pass


def diagnose(records: list[dict[str, Any]]) -> dict[str, Any]:
    output = []
    overall_pending = False
    overall_fail = False
    for index, item in enumerate(records):
        required = {"req_id", "F", "A", "result", "commit", "cleanup",
                    "next_F", "tx_cycles"}
        if set(item) != required:
            raise ProvenanceReject(f"RECORD_SHAPE_{index}")
        for name in ("F", "A"):
            stage = item[name]
            if (not isinstance(stage, dict) or set(stage) != {"cycle", "source_line"}
                    or type(stage["cycle"]) is not int or stage["cycle"] < 0
                    or type(stage["source_line"]) is not int or stage["source_line"] < 1):
                raise ProvenanceReject(f"{name}_EVIDENCE_{index}")
        f_cycle, a_cycle = item["F"]["cycle"], item["A"]["cycle"]
        if a_cycle < f_cycle:
            raise ProvenanceReject(f"F_A_ORDER_{index}")
        next_stage = item["next_F"]
        if next_stage is not None and (not isinstance(next_stage, dict)
                or set(next_stage) != {"cycle", "source_line"}
                or type(next_stage.get("cycle")) is not int
                or type(next_stage.get("source_line")) is not int
                or next_stage["cycle"] <= f_cycle
                or next_stage["source_line"] < 1):
            raise ProvenanceReject(f"NEXT_F_EVIDENCE_{index}")
        next_cycle = None if next_stage is None else next_stage["cycle"]
        tx_cycles = item["tx_cycles"]
        if (not isinstance(tx_cycles, list)
                or any(not isinstance(stage, dict)
                       or set(stage) != {"cycle", "source_line"}
                       or type(stage["cycle"]) is not int or stage["cycle"] < 0
                       or type(stage["source_line"]) is not int
                       or stage["source_line"] < 1 for stage in tx_cycles)):
            raise ProvenanceReject(f"TX_EVIDENCE_{index}")
        row = {"req_id": item["req_id"], "F": item["F"], "A": item["A"],
               "age_from_F": {}, "age_from_A": {}, "deadline_checks": {},
               "tx_cycles": list(tx_cycles)}
        prior_cycle = a_cycle
        for name in ("result", "commit", "cleanup"):
            stage = item[name]
            if stage is None:
                row["age_from_F"][name] = None
                row["age_from_A"][name] = None
                row["deadline_checks"][name] = "PENDING"
                overall_pending = True
                continue
            if (not isinstance(stage, dict) or set(stage) != {"cycle", "source_line"}
                    or type(stage["cycle"]) is not int or stage["cycle"] < 0
                    or type(stage["source_line"]) is not int or stage["source_line"] < 1):
                raise ProvenanceReject(f"{name.upper()}_EVIDENCE_{index}")
            cycle = stage["cycle"]
            if cycle < prior_cycle:
                raise ProvenanceReject(f"STAGE_ORDER_{name.upper()}_{index}")
            prior_cycle = cycle
            age_f, age_a = cycle - f_cycle, cycle - a_cycle
            if age_f < 0 or age_a < 0:
                raise ProvenanceReject(f"NEGATIVE_AGE_{name.upper()}_{index}")
            row["age_from_F"][name] = age_f
            row["age_from_A"][name] = age_a
            if next_cycle is None:
                row["deadline_checks"][name] = "PENDING_NEXT_FRAME_BOUND"
                overall_pending = True
            else:
                check = "PASS" if age_f < 833 and cycle < next_cycle else "FAIL"
                row["deadline_checks"][name] = check
                overall_fail |= check == "FAIL"
        output.append(row)
    return {"schema": "M3_R08_FRAME_ACCEPT_PROVENANCE_V1",
            "status": ("FAIL" if overall_fail else
                       "PENDING" if overall_pending else "PASS"),
            "records": output, "accept_rewritten_to_frame": False,
            "tx_deadline_used_for_internal_cleanup": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = diagnose(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
