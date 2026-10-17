"""Independent R06 event/transaction calendar checker.

The checker consumes only an independent MIDI plan and canonical public-port
rows.  It never reads private DUT wave, envelope, phase, or final-state-only
signals to infer an application event.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


CANONICAL_FIELDS = (
    "cycle", "epoch", "rst_n", "frame_tick", "event_valid",
    "event_ready", "event_data", "apply_valid", "apply_event_seq",
    "apply_data", "occupied_mask", "releasing_mask", "note_on_mask",
    "note_off_mask", "retire_mask", "slot_sources", "slot_channels",
    "slot_notes", "slot_generations", "req_valid", "req_ready",
    "req_id", "advance_mask", "advance_frame_req_id", "result_valid",
    "result_ready", "result_id", "result_left", "result_right",
    "result_clip_mask", "commit", "commit_id", "commit_left",
    "commit_right", "commit_clip", "cancel", "cancel_reason",
    "config_valid", "config_ready", "config_payload",
    "effect_input_valid", "effect_input_ready", "effect_input_id",
    "effect_input_left", "effect_input_right", "effect_input_clip_mask",
    "tx_sample_valid", "tx_frame_id", "tx_req_id", "tx_left",
    "tx_right", "tx_clip", "tx_hold", "tx_startup_zero", "bclk", "ws",
    "din", "pll_locked", "audio_stable", "pa_en", "finish",
)

INTEGER_FIELDS = tuple(
    field for field in CANONICAL_FIELDS
    if field not in {"cancel_reason", "config_payload"}
)


class CalendarReject(Exception):
    """Deterministic rejection of malformed or contradictory evidence."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


class CalendarPending(Exception):
    """Evidence is structurally readable but lacks an authority dependency."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CalendarReject("JSON_OBJECT_REQUIRED", str(path))
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, text in enumerate(stream, 1):
            if not text.strip():
                raise CalendarReject("BLANK_TRACE_LINE", str(line_number))
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise CalendarReject("TRACE_JSON", f"line={line_number}:{exc}") from exc
            if not isinstance(row, dict):
                raise CalendarReject("TRACE_ROW_OBJECT", str(line_number))
            missing = [field for field in CANONICAL_FIELDS if field not in row]
            if missing:
                raise CalendarReject(
                    "MISSING_CANONICAL_FIELD",
                    f"line={line_number},fields={','.join(missing)}",
                )
            row = dict(row)
            row["__line"] = line_number
            rows.append(row)
    if not rows:
        raise CalendarReject("EMPTY_TRACE")
    return rows


def as_int(row: dict[str, Any], field: str) -> int:
    value = row[field]
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise CalendarReject(
                "UNKNOWN_REQUIRED_FIELD", f"line={row['__line']},field={field}"
            ) from exc
    raise CalendarReject(
        "UNKNOWN_REQUIRED_FIELD", f"line={row['__line']},field={field}"
    )


def validate_rows(rows: list[dict[str, Any]]) -> None:
    previous_cycle = -1
    seen = set()
    for row in rows:
        cycle = as_int(row, "cycle")
        epoch = as_int(row, "epoch")
        if cycle < previous_cycle:
            raise CalendarReject("CYCLE_NOT_MONOTONIC", str(row["__line"]))
        key = (epoch, cycle)
        if key in seen:
            raise CalendarReject("DUPLICATE_EPOCH_CYCLE", f"{epoch}:{cycle}")
        seen.add(key)
        previous_cycle = cycle
        for field in INTEGER_FIELDS:
            as_int(row, field)


def validate_authority(binding: dict[str, Any], frame_plan: dict[str, Any]) -> str:
    if binding.get("schema") != "M3_R06_EVENT_CALENDAR_BINDING_V1":
        raise CalendarReject("BINDING_SCHEMA")
    mode = binding.get("mode")
    if mode == "SYNTHETIC_SELFTEST_ONLY":
        if binding.get("trace_authority") != "SYNTHETIC_FIXTURE":
            raise CalendarPending("PENDING_SOURCE_AUTHORITY")
        expected_frame_authority = "SYNTHETIC_INDEPENDENT_PLAN"
        pass_status = "PASS_SYNTHETIC_FIXTURE_ONLY"
    elif mode == "REAL_PUBLIC_TRACE":
        if binding.get("trace_authority") != "REAL_PUBLIC_TRACE":
            raise CalendarPending("PENDING_SOURCE_AUTHORITY")
        expected_frame_authority = "M2_FROZEN_CAPTURE_CONTRACT"
        pass_status = "PASS_REAL_PUBLIC_TRACE"
    else:
        raise CalendarPending("PENDING_SOURCE_AUTHORITY", "mode")
    if not binding.get("source_authority_verified"):
        raise CalendarPending("PENDING_SOURCE_AUTHORITY", "source")
    if not binding.get("m1_semantics_authoritative"):
        raise CalendarPending("PENDING_M1_SEMANTICS")
    if not binding.get("m2_capture_contract_authoritative"):
        raise CalendarPending("PENDING_M2_CAPTURE_CONTRACT")
    priority = binding.get("same_edge_priority")
    required = {"CANCEL", "RESULT", "COMMIT", "REQUEST"}
    if not isinstance(priority, list) or set(priority) != required:
        raise CalendarPending("PENDING_SAME_EDGE_PRIORITY")
    if frame_plan.get("schema") != "M3_R06_INDEPENDENT_FRAME_PLAN_V1":
        raise CalendarPending("PENDING_FRAME_PLAN", "schema")
    if frame_plan.get("authority") != expected_frame_authority:
        raise CalendarPending("PENDING_FRAME_PLAN", "authority")
    if not frame_plan.get("independent_of_trace"):
        raise CalendarPending("PENDING_FRAME_PLAN", "independence")
    return pass_status


def packed_lane(value: int, lane: int, width: int) -> int:
    return (value >> (lane * width)) & ((1 << width) - 1)


def analyze(
    plan: dict[str, Any],
    binding: dict[str, Any],
    frame_plan: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if plan.get("schema") != "M3_R06_MIDI_STIMULUS_PLAN_V1":
        raise CalendarReject("MIDI_PLAN_SCHEMA")
    validate_rows(rows)
    pass_status = validate_authority(binding, frame_plan)

    planned = {int(item["event_seq"]): item for item in plan["events"]}
    unmatched = set(planned)
    pending_event: dict[str, Any] | None = None
    accepted: dict[int, dict[str, Any]] = {}
    applied: dict[int, dict[str, Any]] = {}
    transactions: dict[tuple[int, int], dict[str, Any]] = {}
    canceled_keys: set[tuple[int, int]] = set()
    observed_frames: dict[int, list[int]] = {}
    frame_ledger = []
    lifecycle = []
    priority = binding["same_edge_priority"]
    previous_occupied: dict[int, int] = {}
    finish_rows = []
    same_edge_resolutions = []

    def match_event(data: int, cycle: int) -> int:
        candidates = []
        for seq in sorted(unmatched):
            item = planned[seq]
            window = item["arrival_window"]
            if int(item["expected_event_hex"], 16) == data and (
                int(window["min_cycle"]) <= cycle <= int(window["max_cycle"])
            ):
                candidates.append(seq)
        if len(candidates) != 1:
            raise CalendarReject(
                "EVENT_PLAN_MATCH", f"cycle={cycle},candidates={candidates}"
            )
        return candidates[0]

    for row in rows:
        cycle = as_int(row, "cycle")
        epoch = as_int(row, "epoch")
        rst_n = as_int(row, "rst_n")
        occupied = as_int(row, "occupied_mask")
        releasing = as_int(row, "releasing_mask")
        note_on = as_int(row, "note_on_mask")
        note_off = as_int(row, "note_off_mask")
        retire = as_int(row, "retire_mask")
        for name, value in (
            ("occupied_mask", occupied), ("releasing_mask", releasing),
            ("note_on_mask", note_on), ("note_off_mask", note_off),
            ("retire_mask", retire), ("advance_mask", as_int(row, "advance_mask")),
        ):
            if value & ~0xF:
                raise CalendarReject("MASK_RANGE", f"{name}@{cycle}")
        if not rst_n:
            if occupied or releasing:
                raise CalendarReject("RESET_NOT_EMPTY", f"epoch={epoch},cycle={cycle}")
            pending_event = None
        else:
            if releasing & ~occupied:
                raise CalendarReject("RELEASING_NOT_OCCUPIED", str(cycle))
            if note_on & ~occupied:
                raise CalendarReject("NOTE_ON_NOT_OCCUPIED", str(cycle))
            if note_off & ~occupied:
                raise CalendarReject("NOTE_OFF_NOT_OCCUPIED", str(cycle))
            if retire & occupied:
                raise CalendarReject("RETIRED_STILL_OCCUPIED", str(cycle))
            prior = previous_occupied.get(epoch, 0)
            added = occupied & ~prior
            removed = prior & ~occupied
            if added & ~note_on:
                raise CalendarReject("OCCUPIED_ADDED_WITHOUT_NOTE_ON", str(cycle))
            if removed & ~retire:
                raise CalendarReject("OCCUPIED_REMOVED_WITHOUT_RETIRE", str(cycle))
            if (note_on or note_off) and not as_int(row, "apply_valid"):
                raise CalendarReject("LIFECYCLE_WITHOUT_APPLY", str(cycle))
        previous_occupied[epoch] = occupied

        if as_int(row, "event_valid"):
            data = as_int(row, "event_data")
            if pending_event is None:
                seq = match_event(data, cycle)
                pending_event = {"event_seq": seq, "data": data,
                                 "first_valid_cycle": cycle, "epoch": epoch}
            elif pending_event["data"] != data or pending_event["epoch"] != epoch:
                raise CalendarReject("STALLED_EVENT_CHANGED", str(cycle))
            if as_int(row, "event_ready"):
                seq = int(pending_event["event_seq"])
                accepted[seq] = {**pending_event, "accept_cycle": cycle}
                unmatched.remove(seq)
                pending_event = None

        if as_int(row, "apply_valid"):
            seq = as_int(row, "apply_event_seq")
            if seq not in accepted:
                raise CalendarReject("APPLY_WITHOUT_ACCEPT", f"seq={seq}")
            if seq in applied:
                raise CalendarReject("DUPLICATE_APPLY_EVENT_SEQ", f"seq={seq}")
            data = as_int(row, "apply_data")
            if data != accepted[seq]["data"]:
                raise CalendarReject("APPLY_DATA_MISMATCH", f"seq={seq}")
            applied[seq] = {"epoch": epoch, "cycle": cycle, "data": data}

        if note_on or note_off or retire:
            lifecycle.append({
                "epoch": epoch, "cycle": cycle, "apply_event_seq": (
                    as_int(row, "apply_event_seq") if as_int(row, "apply_valid") else None
                ),
                "occupied_mask": occupied, "releasing_mask": releasing,
                "note_on_mask": note_on, "note_off_mask": note_off,
                "retire_mask": retire,
                "active_notes": [
                    packed_lane(as_int(row, "slot_notes"), lane, 8)
                    for lane in range(4) if occupied & (1 << lane)
                ],
            })

        if as_int(row, "frame_tick"):
            observed_frames.setdefault(epoch, []).append(cycle)
            if not (as_int(row, "req_valid") and as_int(row, "req_ready")):
                raise CalendarReject("FRAME_WITHOUT_REQUEST", f"{epoch}:{cycle}")
            if as_int(row, "advance_mask") != 0xF:
                raise CalendarReject("ADVANCE_MASK_NOT_1111", f"{epoch}:{cycle}")
            if as_int(row, "advance_frame_req_id") != as_int(row, "req_id"):
                raise CalendarReject("ADVANCE_REQ_ID_MISMATCH", f"{epoch}:{cycle}")
            frame_ledger.append({"epoch": epoch, "cycle": cycle,
                                 "req_id": as_int(row, "req_id"),
                                 "advance_mask": as_int(row, "advance_mask")})
        elif as_int(row, "advance_mask"):
            raise CalendarReject("ADVANCE_WITHOUT_FRAME", f"{epoch}:{cycle}")

        actions = []
        if as_int(row, "req_valid") and as_int(row, "req_ready"):
            actions.append("REQUEST")
        if as_int(row, "result_valid") and as_int(row, "result_ready"):
            actions.append("RESULT")
        if as_int(row, "commit"):
            actions.append("COMMIT")
        if as_int(row, "cancel"):
            actions.append("CANCEL")
        if len(actions) > 1:
            same_edge_resolutions.append({"epoch": epoch, "cycle": cycle,
                                          "signals": actions,
                                          "priority": priority})
        for action in sorted(actions, key=priority.index):
            if action == "REQUEST":
                req_id = as_int(row, "req_id")
                key = (epoch, req_id)
                if key in transactions:
                    raise CalendarReject("DUPLICATE_REQUEST", f"{epoch}:{req_id}")
                live = [t for t in transactions.values()
                        if t["epoch"] == epoch and t["state"] in {"REQUESTED", "RETURNED"}]
                if len(live) >= int(binding.get("max_outstanding_per_epoch", 1)):
                    raise CalendarReject("OUTSTANDING_LIMIT", str(epoch))
                transactions[key] = {"epoch": epoch, "req_id": req_id,
                                     "request_cycle": cycle, "state": "REQUESTED"}
            elif action == "CANCEL":
                live_keys = [key for key, txn in transactions.items()
                             if key[0] == epoch and txn["state"] in {"REQUESTED", "RETURNED"}]
                if len(live_keys) != 1:
                    raise CalendarReject("CANCEL_OPEN_COUNT", f"{epoch}:{len(live_keys)}")
                key = live_keys[0]
                txn = transactions[key]
                txn["state"] = "CANCELED"
                txn["cancel_cycle"] = cycle
                txn["cancel_reason"] = row["cancel_reason"]
                canceled_keys.add(key)
            elif action == "RESULT":
                req_id = as_int(row, "result_id")
                key = (epoch, req_id)
                if key in canceled_keys and as_int(row, "cancel"):
                    transactions[key]["same_edge_result_suppressed"] = True
                    continue
                if key not in transactions:
                    raise CalendarReject("RESULT_UNKNOWN", f"{epoch}:{req_id}")
                if transactions[key]["state"] == "CANCELED":
                    raise CalendarReject("RESULT_AFTER_CANCEL", f"{epoch}:{req_id}")
                transactions[key]["state"] = "RETURNED"
                transactions[key]["result_cycle"] = cycle
            elif action == "COMMIT":
                req_id = as_int(row, "commit_id")
                key = (epoch, req_id)
                if key in canceled_keys:
                    raise CalendarReject("COMMIT_AFTER_CANCEL", f"{epoch}:{req_id}")
                if key not in transactions:
                    old = [item for item in transactions if item[1] == req_id]
                    code = "CROSS_EPOCH_COMMIT" if old else "COMMIT_UNKNOWN"
                    raise CalendarReject(code, f"{epoch}:{req_id}")
                if transactions[key]["state"] != "RETURNED":
                    raise CalendarReject("COMMIT_BEFORE_RESULT", f"{epoch}:{req_id}")
                transactions[key]["state"] = "COMMITTED"
                transactions[key]["commit_cycle"] = cycle

        if as_int(row, "finish"):
            finish_rows.append({"epoch": epoch, "cycle": cycle})

    if pending_event is not None:
        raise CalendarReject("UNACCEPTED_STALLED_EVENT", str(pending_event["event_seq"]))
    if binding.get("cover_all_plan_events"):
        if unmatched:
            raise CalendarReject("MISSING_PLANNED_EVENT", str(sorted(unmatched)))
        missing_apply = sorted(set(accepted) - set(applied))
        if missing_apply:
            raise CalendarReject("UNAPPLIED_EVENT", str(missing_apply))

    expected_frames = {
        int(item["epoch"]): [int(cycle) for cycle in item["frame_cycles"]]
        for item in frame_plan.get("epochs", [])
    }
    for epoch in sorted(set(expected_frames) | set(observed_frames)):
        expected = expected_frames.get(epoch, [])
        observed = observed_frames.get(epoch, [])
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        if missing:
            raise CalendarReject("MISSING_FRAME_CYCLE", f"epoch={epoch}:{missing}")
        if extra:
            raise CalendarReject("EXTRA_FRAME_CYCLE", f"epoch={epoch}:{extra}")
        if len(observed) != len(set(observed)):
            raise CalendarReject("DUPLICATE_FRAME_CYCLE", str(epoch))
    expected_finish = frame_plan.get("finish")
    if len(finish_rows) != 1:
        raise CalendarReject("MISSING_OR_DUPLICATE_FINISH", str(len(finish_rows)))
    if finish_rows[0] != expected_finish:
        raise CalendarReject("FINISH_MISMATCH", json.dumps(finish_rows[0]))
    live = [txn for txn in transactions.values()
            if txn["state"] in {"REQUESTED", "RETURNED"}]
    if live:
        raise CalendarReject("OPEN_TRANSACTION_AT_FINISH", str(len(live)))

    return {
        "schema": "M3_R06_EVENT_CALENDAR_REPORT_V1",
        "status": pass_status,
        "real_pro_calendar_pass": pass_status == "PASS_REAL_PUBLIC_TRACE",
        "accepted_events": [accepted[key] for key in sorted(accepted)],
        "applied_events": [dict(event_seq=key, **applied[key]) for key in sorted(applied)],
        "transactions": [transactions[key] for key in sorted(transactions)],
        "lifecycle": lifecycle,
        "frame_ledger": frame_ledger,
        "observed_frames": observed_frames,
        "same_edge_resolutions": same_edge_resolutions,
        "finish": finish_rows[0],
        "counts": {"rows": len(rows), "planned_events": len(planned),
                   "accepted": len(accepted), "applied": len(applied),
                   "frames": sum(len(value) for value in observed_frames.values()),
                   "transactions": len(transactions)},
    }


def run_files(plan_path: Path, trace_path: Path, binding_path: Path,
              frame_plan_path: Path, output_path: Path) -> tuple[int, dict[str, Any]]:
    identities = {
        "plan": {"path": str(plan_path), "sha256": sha256(plan_path)},
        "trace": {"path": str(trace_path), "sha256": sha256(trace_path)},
        "binding": {"path": str(binding_path), "sha256": sha256(binding_path)},
        "frame_plan": {"path": str(frame_plan_path), "sha256": sha256(frame_plan_path)},
    }
    try:
        report = analyze(load_json(plan_path), load_json(binding_path),
                         load_json(frame_plan_path), load_jsonl(trace_path))
        exit_code = 0
    except CalendarPending as exc:
        report = {"schema": "M3_R06_EVENT_CALENDAR_REPORT_V1", "status": exc.code,
                  "detail": exc.detail, "real_pro_calendar_pass": False}
        exit_code = 3
    except CalendarReject as exc:
        report = {"schema": "M3_R06_EVENT_CALENDAR_REPORT_V1", "status": "REJECT",
                  "error": exc.code, "detail": exc.detail,
                  "real_pro_calendar_pass": False}
        exit_code = 2
    report["inputs"] = identities
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return exit_code, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--frame-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    exit_code, report = run_files(args.plan, args.trace, args.binding,
                                  args.frame_plan, args.output)
    print(json.dumps({"status": report["status"],
                      "error": report.get("error"), "exit_code": exit_code}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
