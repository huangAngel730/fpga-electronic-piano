"""Validate normal capture finish and serial tail receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class FinishReject(ValueError):
    pass


def inspect_finish(value: dict[str, Any]) -> dict[str, Any]:
    required = {"origin", "end_rows", "monitor_end_rows", "input_stopped",
                "last_plan_frame", "observed_last_frame", "unfinished_transactions",
                "tx_tail_complete", "process_receipt", "capture_id", "source_id",
                "frozen_finish"}
    if set(value) != required:
        raise FinishReject("INPUT_SHAPE")
    if (not isinstance(value["capture_id"], str) or not value["capture_id"]
            or not isinstance(value["source_id"], str) or not value["source_id"]):
        raise FinishReject("CAPTURE_SOURCE_IDENTITY")
    if len(value["end_rows"]) != 1 or len(value["monitor_end_rows"]) != 1:
        raise FinishReject("END_COUNT")
    end = value["end_rows"][0]
    monitor = value["monitor_end_rows"][0]
    finish = value["frozen_finish"]
    expected_keys = {"epoch", "cycle", "capture_id", "source_id"}
    if (not isinstance(end, dict) or not isinstance(monitor, dict)
            or set(end) != expected_keys or set(monitor) != expected_keys
            or not isinstance(finish, dict) or set(finish) != {"epoch", "cycle"}):
        raise FinishReject("END_IDENTITY_MISSING")
    if end != monitor:
        raise FinishReject("END_MONITOR_MISMATCH")
    if (end["capture_id"] != value["capture_id"]
            or end["source_id"] != value["source_id"]
            or end["epoch"] != finish["epoch"] or end["cycle"] != finish["cycle"]
            or type(end["epoch"]) is not int or type(end["cycle"]) is not int
            or end["epoch"] < 0 or end["cycle"] < 0):
        raise FinishReject("END_FROZEN_FINISH_MISMATCH")
    if value["input_stopped"] is not True:
        raise FinishReject("INPUT_NOT_STOPPED")
    frame_keys = {"epoch", "cycle", "source_line"}
    if (not isinstance(value["last_plan_frame"], dict)
            or not isinstance(value["observed_last_frame"], dict)
            or set(value["last_plan_frame"]) != frame_keys
            or set(value["observed_last_frame"]) != frame_keys):
        raise FinishReject("LAST_FRAME_IDENTITY_MISSING")
    if value["observed_last_frame"] != value["last_plan_frame"]:
        raise FinishReject("TAIL_FRAME_INCOMPLETE")
    if (any(type(value["last_plan_frame"][key]) is not int
            or value["last_plan_frame"][key] < 0
            for key in ("epoch", "cycle"))
            or type(value["last_plan_frame"]["source_line"]) is not int
            or value["last_plan_frame"]["source_line"] < 1):
        raise FinishReject("LAST_FRAME_IDENTITY_INVALID")
    if value["last_plan_frame"]["cycle"] > end["cycle"]:
        raise FinishReject("LAST_FRAME_AFTER_FINISH")
    if value["unfinished_transactions"]:
        raise FinishReject("UNFINISHED_TRANSACTIONS")
    if value["tx_tail_complete"] is not True:
        raise FinishReject("TX_TAIL_INCOMPLETE")
    receipt = value["process_receipt"]
    if not isinstance(receipt, dict):
        return {"schema": "M3_R08_FINISH_PROTOCOL_V1",
                "status": "PENDING_REAL_RECEIPT", "first_violation": "RECEIPT_MISSING"}
    if receipt.get("timeout_cleanup"):
        raise FinishReject("TIMEOUT_CLEANUP_NOT_NORMAL_FINISH")
    if receipt.get("exit_code") != 0 or receipt.get("stdout_closed") is not True or receipt.get("stderr_closed") is not True:
        raise FinishReject("PROCESS_EXIT_RECEIPT")
    status = ("SYNTHETIC_FINISH_ACCEPTED" if value["origin"] == "SYNTHETIC"
              else "PENDING_REAL_AUTHORITY")
    return {"schema": "M3_R08_FINISH_PROTOCOL_V1", "status": status,
            "finish_cycle": end["cycle"], "capture_id": value["capture_id"],
            "source_id": value["source_id"],
            "last_plan_frame": value["last_plan_frame"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = inspect_finish(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
