"""R7 profile intake candidate for R6-3.

L0 / NOT_RUN.  This is an additive candidate and does not replace the signed
R6-3 implementation.  It preserves R7-A rows and builds explicit F,
first-valid, A, TX and raw-cancel ledgers without projecting them into D3.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROW_SCHEMA = "M3_R7A_PUBLIC_ROW_V1"
EXTENSION_SCHEMA = "M3_R7A_TX_EXTENSION_V1"
REPORT_SCHEMA = "M3_R63_R07_INTAKE_REPORT_V1"
EXPECTED_KEYS = {
    "schema", "capture_id", "origin", "source", "fields", "extensions",
    "missing_reasons", "events",
}
EXPECTED_SOURCE_KEYS = {
    "raw_sha256", "reset_edges_sha256", "line", "cycle", "epoch",
    "time_ps", "sampling_phase",
}
EXPECTED_FIELD_NAMES = {
    "cycle", "epoch", "rst_n", "frame_tick", "event_valid", "event_ready",
    "event_data", "apply_valid", "apply_event_seq", "apply_data",
    "occupied_mask", "releasing_mask", "note_on_mask", "note_off_mask",
    "retire_mask", "slot_sources", "slot_channels", "slot_notes",
    "slot_generations", "req_valid", "req_ready", "req_id", "advance_mask",
    "advance_frame_req_id", "result_valid", "result_ready", "result_id",
    "result_left", "result_right", "result_clip_mask", "commit", "commit_id",
    "commit_left", "commit_right", "commit_clip", "cancel", "cancel_reason",
    "config_valid", "config_ready", "config_payload", "effect_input_valid",
    "effect_input_ready", "effect_input_id", "effect_input_left",
    "effect_input_right", "effect_input_clip_mask", "tx_sample_valid",
    "tx_frame_id", "tx_req_id", "tx_left", "tx_right", "tx_clip", "tx_hold",
    "tx_startup_zero", "bclk", "ws", "din", "pll_locked", "audio_stable",
    "pa_en", "finish",
}
EXPECTED_EXTENSION_KEYS = {
    "schema", "obs_core_clk", "obs_polyphonic_valid",
    "obs_tx_metadata_valid", "obs_tx_req_id_valid", "obs_tx_clip_mask",
    "obs_metadata_error", "obs_frame_id_overflow", "uart_tx",
    "raw_tx_req_id_bits",
}
EXPECTED_EVENTS = {
    "FRAME_F", "ACCEPT_A", "RESULT_TRANSFER", "COMMIT", "TX_ADOPT",
    "FINISH",
}


class IntakeReject(ValueError):
    """Deterministic malformed or contradictory R7 profile evidence."""


def _known_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise IntakeReject(f"{label}_BOOL")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if any(char in "xXzZ" for char in value):
            return None
        if not value or any(char not in "01" for char in value):
            raise IntakeReject(f"{label}_BITS")
        return int(value, 2)
    raise IntakeReject(f"{label}_TYPE")


def _known_bit(value: Any, label: str) -> int | None:
    result = _known_int(value, label)
    if result not in {None, 0, 1}:
        raise IntakeReject(f"{label}_NOT_BIT")
    return result


def _is_sha256(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise IntakeReject(f"JSON_LINE_{line_number}:{exc.msg}") from exc
        if not isinstance(value, dict):
            raise IntakeReject(f"ROW_{line_number}_NOT_OBJECT")
        rows.append(value)
    if not rows:
        raise IntakeReject("EMPTY_CAPTURE")
    return rows


def _row_epoch(row: dict[str, Any], line: int,
               pending: set[str]) -> int | None:
    source_epoch = _known_int(row["source"].get("epoch"),
                              f"LINE_{line}_SOURCE_EPOCH")
    field_epoch = _known_int(row["fields"].get("epoch"),
                             f"LINE_{line}_FIELD_EPOCH")
    if source_epoch is not None and field_epoch is not None and source_epoch != field_epoch:
        raise IntakeReject(f"LINE_{line}_EPOCH_MISMATCH")
    epoch = source_epoch if source_epoch is not None else field_epoch
    if epoch is None:
        pending.add("PENDING_RESET_PHASE")
    return epoch


def _oldest_open_frame(frames: list[dict[str, Any]], epoch: int,
                       label: str) -> dict[str, Any]:
    candidates = [item for item in frames
                  if item["epoch"] == epoch and item["A"] is None]
    if not candidates:
        raise IntakeReject(f"{label}_WITHOUT_FRAME")
    return candidates[0]


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    capture_id = None
    origin = None
    source_identity = None
    prior_time_ps = -1
    pending: set[str] = set()
    frames: list[dict[str, Any]] = []
    transactions: dict[tuple[int, int], dict[str, Any]] = {}
    tx_samples: list[dict[str, Any]] = []
    raw_frame_cancels: list[dict[str, Any]] = []
    held: dict[int, dict[str, Any]] = {}
    finish_rows = []
    preserved_rows = []

    for input_line, row in enumerate(rows, 1):
        if set(row) != EXPECTED_KEYS or row.get("schema") != ROW_SCHEMA:
            raise IntakeReject(f"LINE_{input_line}_R7A_SHAPE")
        if (not isinstance(row["source"], dict)
                or not isinstance(row["fields"], dict)
                or not isinstance(row["extensions"], dict)
                or not isinstance(row["missing_reasons"], dict)
                or not isinstance(row["events"], list)):
            raise IntakeReject(f"LINE_{input_line}_PAYLOAD_SHAPE")
        if set(row["source"]) != EXPECTED_SOURCE_KEYS:
            raise IntakeReject(f"LINE_{input_line}_SOURCE_SHAPE")
        if (row["source"].get("sampling_phase") != "POSEDGE_PRE_NBA"
                or not _is_sha256(row["source"].get("raw_sha256"))
                or not _is_sha256(row["source"].get("reset_edges_sha256"))):
            raise IntakeReject(f"LINE_{input_line}_SOURCE_IDENTITY")
        if set(row["fields"]) != EXPECTED_FIELD_NAMES:
            raise IntakeReject(f"LINE_{input_line}_FIELD_PROFILE")
        if (set(row["extensions"]) != EXPECTED_EXTENSION_KEYS
                or row["extensions"].get("schema") != EXTENSION_SCHEMA):
            raise IntakeReject(f"LINE_{input_line}_EXTENSION_PROFILE")
        if (row["extensions"].get("obs_core_clk") != 1
                or row["extensions"].get("obs_polyphonic_valid") != 1):
            raise IntakeReject(f"LINE_{input_line}_PUBLIC_SAMPLE_PROFILE")
        if (len(row["events"]) != len(set(row["events"]))
                or not set(row["events"]).issubset(EXPECTED_EVENTS)):
            raise IntakeReject(f"LINE_{input_line}_EVENT")
        if (not isinstance(row["capture_id"], str) or not row["capture_id"]
                or row["origin"] not in {
                    "SYNTHETIC_SCHEMA_FIXTURE",
                    "HDL_PUBLIC_CAPTURE_UNVERIFIED",
                }):
            raise IntakeReject(f"LINE_{input_line}_CAPTURE_IDENTITY")
        if capture_id is None:
            capture_id = row["capture_id"]
            origin = row["origin"]
            source_identity = (
                row["source"]["raw_sha256"],
                row["source"]["reset_edges_sha256"],
                row["source"]["sampling_phase"],
            )
        if row["capture_id"] != capture_id or row["origin"] != origin:
            raise IntakeReject(f"LINE_{input_line}_CAPTURE_IDENTITY")
        if source_identity != (
                row["source"]["raw_sha256"],
                row["source"]["reset_edges_sha256"],
                row["source"]["sampling_phase"],
        ):
            raise IntakeReject(f"LINE_{input_line}_SOURCE_IDENTITY_CHANGED")

        source_line = row["source"].get("line")
        cycle = row["source"].get("cycle")
        time_ps = row["source"].get("time_ps")
        field_cycle = row["fields"].get("cycle")
        if (type(source_line) is not int or type(cycle) is not int
                or type(time_ps) is not int or source_line < 1 or cycle < 0
                or time_ps < 0):
            raise IntakeReject(f"LINE_{input_line}_UNKNOWN_SOURCE_POSITION")
        if source_line != input_line or cycle != input_line - 1:
            raise IntakeReject(f"LINE_{input_line}_SOURCE_SEQUENCE")
        if type(field_cycle) is not int or field_cycle != cycle:
            raise IntakeReject(f"LINE_{input_line}_CYCLE_MISMATCH")
        if time_ps <= prior_time_ps and input_line > 1:
            raise IntakeReject(f"LINE_{input_line}_TIME_SEQUENCE")
        prior_time_ps = time_ps
        epoch = _row_epoch(row, input_line, pending)
        fields = row["fields"]
        ext = row["extensions"]
        rst_n = _known_bit(fields.get("rst_n"),
                           f"LINE_{input_line}_RST_N")
        active = rst_n == 1
        if rst_n is None:
            pending.add("PENDING_RESET_VALIDITY")

        preserved_rows.append({
            "input_line": input_line,
            "source_line": source_line,
            "cycle": cycle,
            "epoch": epoch,
            "row": copy.deepcopy(row),
        })

        frame_signal = _known_bit(fields.get("frame_tick"),
                                  f"LINE_{input_line}_FRAME")
        if active and frame_signal is None:
            pending.add("PENDING_FRAME_VALIDITY")
        if ("FRAME_F" in row["events"]) != (active and frame_signal == 1):
            raise IntakeReject(f"LINE_{input_line}_FRAME_EVENT_MISMATCH")
        if active and frame_signal == 1:
            if epoch is None:
                pending.add("PENDING_FRAME_EPOCH")
            else:
                frames.append({
                    "epoch": epoch,
                    "frame_ordinal": 1 + sum(item["epoch"] == epoch for item in frames),
                    "F": {"cycle": cycle, "source_line": source_line},
                    "first_valid": None,
                    "A": None,
                    "req_id": None,
                    "advance_observations": [],
                })

        req_valid = _known_bit(fields.get("req_valid"),
                               f"LINE_{input_line}_REQ_VALID")
        req_ready = _known_bit(fields.get("req_ready"),
                               f"LINE_{input_line}_REQ_READY")
        req_id = _known_int(fields.get("req_id"), f"LINE_{input_line}_REQ_ID")
        accept_pulse = active and req_valid == 1 and req_ready == 1
        if ("ACCEPT_A" in row["events"]) != accept_pulse:
            raise IntakeReject(f"LINE_{input_line}_ACCEPT_EVENT_MISMATCH")
        if active and req_valid == 1:
            if epoch is None:
                pending.add("PENDING_REQUEST_EPOCH")
            else:
                frame = _oldest_open_frame(frames, epoch,
                                           f"LINE_{input_line}_REQUEST")
                if frame["first_valid"] is None:
                    frame["first_valid"] = {"cycle": cycle,
                                             "source_line": source_line}
                    frame["req_id"] = req_id
                elif frame["req_id"] is None and req_id is not None:
                    frame["req_id"] = req_id
                elif frame["req_id"] is not None and req_id is not None and frame["req_id"] != req_id:
                    raise IntakeReject(f"LINE_{input_line}_STALLED_REQUEST_CHANGED")
                if req_id is None:
                    pending.add("PENDING_REQUEST_ID")
                if req_ready == 1:
                    if "ACCEPT_A" not in row["events"]:
                        raise IntakeReject(f"LINE_{input_line}_ACCEPT_EVENT_MISSING")
                    frame["A"] = {"cycle": cycle, "source_line": source_line}
                    if req_id is not None:
                        key = (epoch, req_id)
                        if key in transactions:
                            raise IntakeReject(f"LINE_{input_line}_DUPLICATE_ACCEPT")
                        transactions[key] = {
                            "epoch": epoch,
                            "req_id": req_id,
                            "frame_ordinal": frame["frame_ordinal"],
                            "F": copy.deepcopy(frame["F"]),
                            "first_valid": copy.deepcopy(frame["first_valid"]),
                            "A": copy.deepcopy(frame["A"]),
                            "result": None,
                            "commit": None,
                            "tx_adoption": None,
                            "state": "ACCEPTED",
                        }
                elif req_ready is None:
                    pending.add("PENDING_REQUEST_READY")
        elif active and req_valid is None:
            pending.add("PENDING_REQUEST_VALIDITY")

        advance_mask = _known_int(fields.get("advance_mask"),
                                  f"LINE_{input_line}_ADVANCE_MASK")
        advance_req_id = _known_int(fields.get("advance_frame_req_id"),
                                    f"LINE_{input_line}_ADVANCE_ID")
        if active and advance_mask is not None and advance_mask != 0:
            candidates = [item for item in frames if item["epoch"] == epoch and (
                item["req_id"] is None or advance_req_id is None
                or item["req_id"] == advance_req_id
            )]
            if len(candidates) != 1:
                raise IntakeReject(f"LINE_{input_line}_ADVANCE_ASSOCIATION")
            candidates[0]["advance_observations"].append({
                "cycle": cycle,
                "source_line": source_line,
                "mask": advance_mask,
                "req_id": advance_req_id,
            })
        elif active and advance_mask is None:
            pending.add("PENDING_M1_ADVANCE")

        result_transfer = active and (
            _known_bit(fields.get("result_valid"), f"LINE_{input_line}_RESULT_VALID") == 1
            and _known_bit(fields.get("result_ready"), f"LINE_{input_line}_RESULT_READY") == 1
        )
        if ("RESULT_TRANSFER" in row["events"]) != result_transfer:
            raise IntakeReject(f"LINE_{input_line}_RESULT_EVENT_MISMATCH")
        if result_transfer:
            result_id = _known_int(fields.get("result_id"),
                                   f"LINE_{input_line}_RESULT_ID")
            key = None if epoch is None or result_id is None else (epoch, result_id)
            if key not in transactions:
                raise IntakeReject(f"LINE_{input_line}_RESULT_WITHOUT_ACCEPT")
            if transactions[key]["result"] is not None:
                raise IntakeReject(f"LINE_{input_line}_DUPLICATE_RESULT")
            transactions[key]["result"] = {"cycle": cycle,
                                             "source_line": source_line}
            transactions[key]["state"] = "RETURNED"

        commit_pulse = (active and _known_bit(
            fields.get("commit"), f"LINE_{input_line}_COMMIT") == 1)
        if ("COMMIT" in row["events"]) != commit_pulse:
            raise IntakeReject(f"LINE_{input_line}_COMMIT_EVENT_MISMATCH")
        if commit_pulse:
            commit_id = _known_int(fields.get("commit_id"),
                                   f"LINE_{input_line}_COMMIT_ID")
            key = None if epoch is None or commit_id is None else (epoch, commit_id)
            if key not in transactions or transactions[key]["result"] is None:
                raise IntakeReject(f"LINE_{input_line}_COMMIT_WITHOUT_RESULT")
            if transactions[key]["commit"] is not None:
                raise IntakeReject(f"LINE_{input_line}_DUPLICATE_COMMIT")
            transactions[key]["commit"] = {"cycle": cycle,
                                             "source_line": source_line}
            transactions[key]["state"] = "COMMITTED_PENDING_TX"

        raw_cancel = _known_bit(fields.get("cancel"),
                                f"LINE_{input_line}_RAW_CANCEL")
        if active and raw_cancel == 1:
            raw_frame_cancels.append({
                "epoch": epoch,
                "cycle": cycle,
                "source_line": source_line,
                "raw_cancel_reason": fields.get("cancel_reason"),
                "business_cancel_derived": False,
            })
            pending.add("PENDING_TRANSACTION_CANCEL_RULE")
        elif active and raw_cancel is None:
            pending.add("PENDING_RAW_CANCEL_VALIDITY")

        tx_valid = _known_bit(fields.get("tx_sample_valid"),
                              f"LINE_{input_line}_TX_VALID")
        tx_sample_pulse = active and tx_valid == 1
        if ("TX_ADOPT" in row["events"]) != tx_sample_pulse:
            raise IntakeReject(f"LINE_{input_line}_TX_SAMPLE_EVENT_MISMATCH")
        if tx_sample_pulse:
            startup = _known_bit(fields.get("tx_startup_zero"),
                                 f"LINE_{input_line}_TX_STARTUP")
            hold = _known_bit(fields.get("tx_hold"),
                              f"LINE_{input_line}_TX_HOLD")
            metadata_valid = _known_bit(ext.get("obs_tx_metadata_valid"),
                                        f"LINE_{input_line}_TX_META_VALID")
            req_id_valid = _known_bit(ext.get("obs_tx_req_id_valid"),
                                      f"LINE_{input_line}_TX_ID_VALID")
            tx_req_id = _known_int(fields.get("tx_req_id"),
                                   f"LINE_{input_line}_TX_REQ_ID")
            if req_id_valid == 0 and tx_req_id is not None:
                raise IntakeReject(f"LINE_{input_line}_INVALID_TX_ID_PRESENT")
            if startup == 1 and hold == 1:
                raise IntakeReject(f"LINE_{input_line}_STARTUP_AND_HOLD")
            record = {
                "epoch": epoch,
                "cycle": cycle,
                "source_line": source_line,
                "kind": "UNKNOWN",
                "req_id": tx_req_id if req_id_valid == 1 else None,
                "req_id_valid": req_id_valid,
                "metadata_valid": metadata_valid,
                "left": fields.get("tx_left"),
                "right": fields.get("tx_right"),
                "clip_any": fields.get("tx_clip"),
                "clip_mask": ext.get("obs_tx_clip_mask"),
                "metadata_error": ext.get("obs_metadata_error"),
                "frame_id_overflow": ext.get("obs_frame_id_overflow"),
                "consumes_pending": False,
            }
            if startup == 1:
                if req_id_valid == 1 or tx_req_id is not None:
                    raise IntakeReject(f"LINE_{input_line}_STARTUP_HAS_ID")
                record["kind"] = "STARTUP"
            elif hold == 1:
                record["kind"] = "HOLD"
                if epoch is not None and req_id_valid == 1 and tx_req_id is not None:
                    if epoch not in held or held[epoch]["req_id"] != tx_req_id:
                        raise IntakeReject(f"LINE_{input_line}_HOLD_ID")
                else:
                    pending.add("PENDING_TX_METADATA")
            elif (startup == 0 and hold == 0 and metadata_valid == 1
                  and req_id_valid == 1 and tx_req_id is not None):
                record["kind"] = "ADOPTION"
                key = None if epoch is None else (epoch, tx_req_id)
                if key not in transactions or transactions[key]["commit"] is None:
                    raise IntakeReject(f"LINE_{input_line}_ADOPTION_WITHOUT_COMMIT")
                if transactions[key]["tx_adoption"] is not None:
                    raise IntakeReject(f"LINE_{input_line}_DUPLICATE_ADOPTION")
                record["consumes_pending"] = True
                transactions[key]["tx_adoption"] = {"cycle": cycle,
                                                       "source_line": source_line}
                transactions[key]["state"] = "ADOPTED_HELD"
                held[epoch] = {"req_id": tx_req_id,
                               "cycle": cycle,
                               "source_line": source_line}
            else:
                pending.add("PENDING_TX_METADATA")
            tx_samples.append(record)
        elif active and tx_valid is None:
            pending.add("PENDING_TX_VALIDITY")

        finish_signal = _known_bit(fields.get("finish"),
                                   f"LINE_{input_line}_FINISH")
        if ("FINISH" in row["events"]) != (finish_signal == 1):
            raise IntakeReject(f"LINE_{input_line}_FINISH_EVENT_MISMATCH")
        if finish_signal == 1:
            finish_rows.append({"epoch": epoch, "cycle": cycle,
                                "source_line": source_line})

    if len(finish_rows) != 1:
        raise IntakeReject(f"FINISH_COUNT_{len(finish_rows)}")
    for frame in frames:
        if frame["first_valid"] is None:
            pending.add("PENDING_FIRST_VALID")
        if frame["A"] is None:
            pending.add("PENDING_ACCEPT_A")
    for transaction in transactions.values():
        pending_by_state = {
            "ACCEPTED": "PENDING_RESULT",
            "RETURNED": "PENDING_COMMIT",
            "COMMITTED_PENDING_TX": "PENDING_TX_ADOPTION",
        }
        if transaction["state"] in pending_by_state:
            pending.add(pending_by_state[transaction["state"]])
    if origin == "HDL_PUBLIC_CAPTURE_UNVERIFIED":
        pending.add("PENDING_SOURCE_PROVENANCE")

    status = ("SYNTHETIC_MECHANICS_CANDIDATE" if not pending
              else sorted(pending)[0])
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "capture_id": capture_id,
        "origin": origin,
        "sampling_phase": "POSEDGE_PRE_NBA",
        "preserved_rows": preserved_rows,
        "frames": frames,
        "transactions": [transactions[key] for key in sorted(transactions)],
        "tx_samples": tx_samples,
        "held_at_finish": held,
        "raw_frame_cancels": raw_frame_cancels,
        "business_cancels": [],
        "business_cancel_status": "PENDING_TRANSACTION_CANCEL_RULE",
        "legacy_d3_projection_status": "PENDING_UNSUPPORTED_PROFILE",
        "legacy_d3_records": [],
        "pending_reasons": sorted(pending),
        "finish": finish_rows[0],
        "real_pro_intake_pass": False,
        "board_release_allowed": False,
    }


def run_file(input_path: Path, output_path: Path) -> dict[str, Any]:
    report = analyze(_load_jsonl(input_path))
    report["input"] = {"path": str(input_path), "sha256": _sha256(input_path)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-rows", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_file(args.public_rows, args.output)
    print(json.dumps({"status": report["status"],
                      "real_pro_intake_pass": False}))
    return 0 if report["status"] == "SYNTHETIC_MECHANICS_CANDIDATE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
