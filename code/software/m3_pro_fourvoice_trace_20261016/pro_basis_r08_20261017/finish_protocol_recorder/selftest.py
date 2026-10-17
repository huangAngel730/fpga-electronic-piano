"""NOT_RUN case adapter for finish protocol."""

from __future__ import annotations

import json
from pathlib import Path

from finish_protocol_recorder import FinishReject, inspect_finish


def _input() -> dict:
    end = {"epoch": 1, "cycle": 2000, "capture_id": "cap",
           "source_id": "source"}
    return {"origin": "SYNTHETIC", "capture_id": "cap", "source_id": "source",
            "frozen_finish": {"epoch": 1, "cycle": 2000},
            "end_rows": [end], "monitor_end_rows": [dict(end)],
            "input_stopped": True,
            "last_plan_frame": {"epoch": 0, "cycle": 1667, "source_line": 1668},
            "observed_last_frame": {"epoch": 0, "cycle": 1667, "source_line": 1668},
            "unfinished_transactions": [], "tx_tail_complete": True,
            "process_receipt": {"exit_code": 0, "stdout_closed": True,
                                "stderr_closed": True, "timeout_cleanup": False}}


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    value = _input()
    if case_id == "SYNTHETIC_COMPLETE":
        report = inspect_finish(value)
        if report["status"] != "SYNTHETIC_FINISH_ACCEPTED":
            raise AssertionError(report)
    elif case_id == "REAL_RECEIPT_MISSING_PENDING":
        value["origin"] = "REAL_CANDIDATE"
        value["process_receipt"] = None
        report = inspect_finish(value)
        if report["status"] != "PENDING_REAL_RECEIPT":
            raise AssertionError(report)
    elif case_id == "EMPTY_END_IDENTITY_REJECT":
        value["end_rows"] = [{}]
        try:
            inspect_finish(value)
        except FinishReject as exc:
            if "END_IDENTITY_MISSING" not in str(exc): raise
        else: raise AssertionError("EMPTY_END_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "EMPTY_CAPTURE_SOURCE_REJECT":
        value["capture_id"] = ""
        value["source_id"] = ""
        value["end_rows"][0]["capture_id"] = ""
        value["end_rows"][0]["source_id"] = ""
        value["monitor_end_rows"][0]["capture_id"] = ""
        value["monitor_end_rows"][0]["source_id"] = ""
        try:
            inspect_finish(value)
        except FinishReject as exc:
            if "CAPTURE_SOURCE_IDENTITY" not in str(exc): raise
        else: raise AssertionError("EMPTY_CAPTURE_SOURCE_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "CONTRADICTORY_MONITOR_REJECT":
        value["monitor_end_rows"][0]["cycle"] = 1
        try:
            inspect_finish(value)
        except FinishReject as exc:
            if "END_MONITOR_MISMATCH" not in str(exc): raise
        else: raise AssertionError("CONTRADICTORY_END_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "NULL_LAST_FRAMES_REJECT":
        value["last_plan_frame"] = None
        value["observed_last_frame"] = None
        try:
            inspect_finish(value)
        except FinishReject as exc:
            if "LAST_FRAME_IDENTITY_MISSING" not in str(exc): raise
        else: raise AssertionError("NULL_FRAMES_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "INVALID_LAST_FRAME_IDENTITY_REJECT":
        invalid = {"epoch": -1, "cycle": 1667, "source_line": 0}
        value["last_plan_frame"] = invalid
        value["observed_last_frame"] = dict(invalid)
        try:
            inspect_finish(value)
        except FinishReject as exc:
            if "LAST_FRAME_IDENTITY_INVALID" not in str(exc): raise
        else: raise AssertionError("INVALID_FRAME_IDENTITY_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    else:
        mutation = {"DOUBLE_END": ("end_rows", [{"cycle": 1}, {"cycle": 2}], "END_COUNT"),
                    "TAIL_FRAME_MISSING": ("observed_last_frame", None, "LAST_FRAME_IDENTITY_MISSING"),
                    "TIMEOUT_NOT_FINISH": ("process_receipt", {"exit_code": 1, "stdout_closed": True, "stderr_closed": True, "timeout_cleanup": True}, "TIMEOUT_CLEANUP")}
        if case_id not in mutation:
            raise KeyError(case_id)
        key, changed, expected = mutation[case_id]
        value[key] = changed
        try:
            inspect_finish(value)
        except FinishReject as exc:
            if expected not in str(exc):
                raise
        else:
            raise AssertionError("INVALID_FINISH_ACCEPTED")
        report = {"status": "EXPECTED_REJECT", "reason": expected}
    (output_dir / "input.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"case_id": case_id, "status": "PASS"}
