"""NOT_RUN case adapter for F/A provenance."""

from __future__ import annotations

import json
from pathlib import Path

from frame_accept_provenance import diagnose


def _record() -> dict:
    return {"req_id": 0,
            "F": {"cycle": 834, "source_line": 835},
            "A": {"cycle": 835, "source_line": 836},
            "result": {"cycle": 900, "source_line": 901},
            "commit": {"cycle": 901, "source_line": 902},
            "cleanup": {"cycle": 902, "source_line": 903},
            "next_F": {"cycle": 1667, "source_line": 1668},
            "tx_cycles": [{"cycle": 1667, "source_line": 1668},
                          {"cycle": 1668, "source_line": 1669}]}


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    record = _record()
    if case_id == "F_A_DISTINCT":
        report = diagnose([record])
        if report["records"][0]["F"]["cycle"] == report["records"][0]["A"]["cycle"]:
            raise AssertionError("A_REWRITTEN")
    elif case_id == "F_AGE_833_REJECT":
        record["cleanup"] = {"cycle": 1667, "source_line": 1668}
        record["next_F"] = {"cycle": 2000, "source_line": 2001}
        report = diagnose([record])
        row = report["records"][0]
        if row["age_from_A"]["cleanup"] != 832 or row["deadline_checks"]["cleanup"] != "FAIL":
            raise AssertionError(row)
    elif case_id == "NEXT_FRAME_STRICT_BOUND":
        record["cleanup"] = {"cycle": 1000, "source_line": 1001}
        record["next_F"] = {"cycle": 1000, "source_line": 1001}
        report = diagnose([record])
        if report["records"][0]["deadline_checks"]["cleanup"] != "FAIL":
            raise AssertionError(report)
    elif case_id == "TX_833_834_SEPARATE":
        report = diagnose([record])
        if [x["cycle"] for x in report["records"][0]["tx_cycles"]] != [1667, 1668]:
            raise AssertionError("TX_COLLAPSED")
        if report["tx_deadline_used_for_internal_cleanup"]:
            raise AssertionError("TX_REUSED")
    elif case_id == "NEGATIVE_STAGE_ORDER_REJECT":
        record["result"] = {"cycle": 833, "source_line": 834}
        try:
            diagnose([record])
        except Exception as exc:
            if "STAGE_ORDER" not in str(exc):
                raise
        else:
            raise AssertionError("NEGATIVE_STAGE_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "ALL_STAGES_MISSING_PENDING":
        record.update(result=None, commit=None, cleanup=None)
        report = diagnose([record])
        if report["status"] != "PENDING":
            raise AssertionError(report)
    elif case_id == "NEXT_FRAME_MISSING_PENDING":
        record["next_F"] = None
        report = diagnose([record])
        if report["status"] != "PENDING":
            raise AssertionError(report)
    else:
        raise KeyError(case_id)
    (output_dir / "input.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"case_id": case_id, "status": "PASS"}
