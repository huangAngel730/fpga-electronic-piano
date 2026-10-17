"""Build a lossless mechanical oracle handoff bundle from public trace inputs.

This tool verifies and copies source bytes, then emits a per-row association
index.  It does not reconstruct M1 arithmetic or infer expected values from
DUT-private state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


SCHEMA = "M3_R07_ORACLE_BUNDLE_BRIDGE_INPUT_V1"
OUTPUT_SCHEMA = "M3_R07_ORACLE_MECHANICAL_BUNDLE_V1"
LEGACY_PROFILE = "R06_SETTLED_SIMULTANEOUS_LANE_TICKS_V1"
REQUIRED_ROLES = {
    "midi_plan",
    "normalized_trace",
    "normalized_binding",
    "frame_plan",
    "capture_contract",
    "normalized_row_schema",
    "observer_exports",
    "source_replacements",
    "normalized_intake_contract",
    "event_calendar_contract",
    "r7a_record_schema",
}


class BridgeError(ValueError):
    """Input cannot be packaged without losing or inventing evidence."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
            for value in values
        ),
        encoding="utf-8",
        newline="\n",
    )


def reject_float(value: str) -> None:
    raise BridgeError("NONINTEGER_JSON_NUMBER:" + value)


def reject_constant(value: str) -> None:
    raise BridgeError("NONFINITE_JSON_NUMBER:" + value)


def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise BridgeError("DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def loads_json(raw: bytes, where: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise BridgeError("UNREADABLE_JSON:" + where + ":" + str(error)) from error


def read_json(path: Path) -> Any:
    return loads_json(path.read_bytes(), str(path))


def checked_int(value: Any, where: str) -> int:
    if type(value) is not int or value < 0:
        raise BridgeError("NONNEGATIVE_INTEGER_REQUIRED:" + where)
    return value


def resolve_descriptor(root: Path, desc: dict[str, Any]) -> Path:
    required = {"role", "path", "bytes", "sha256"}
    if type(desc) is not dict or set(desc) != required:
        raise BridgeError("BAD_INPUT_DESCRIPTOR")
    path = Path(desc["path"])
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    if not path.is_file():
        raise BridgeError("INPUT_MISSING:" + desc["role"])
    if path.stat().st_size != desc["bytes"] or sha256(path) != desc["sha256"]:
        raise BridgeError("INPUT_IDENTITY_MISMATCH:" + desc["role"])
    return path


def load_trace(
    path: Path,
    required_fields: list[str],
    record_schema: dict[str, Any],
    capture_id: str,
) -> tuple[list[dict[str, Any]], list[bytes], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    raw_lines: list[bytes] = []
    records: list[dict[str, Any]] = []
    previous_cycle = -1
    required_record = set(record_schema.get("required", []))
    if required_record != {
        "schema", "capture_id", "origin", "source", "fields",
        "extensions", "missing_reasons", "events",
    }:
        raise BridgeError("R7A_RECORD_SCHEMA_REQUIRED_SET")
    for line_number, raw in enumerate(path.read_bytes().splitlines(), start=1):
        if not raw.strip():
            raise BridgeError("EMPTY_TRACE_LINE:" + str(line_number))
        record = loads_json(raw, f"{path}:{line_number}")
        if type(record) is not dict:
            raise BridgeError("TRACE_ROW_OBJECT_REQUIRED:" + str(line_number))
        if set(record) != required_record:
            raise BridgeError("R7A_RECORD_FIELD_SET:" + str(line_number))
        if record["schema"] != "M3_R7A_PUBLIC_ROW_V1":
            raise BridgeError("R7A_RECORD_SCHEMA:" + str(line_number))
        if record["capture_id"] != capture_id:
            raise BridgeError("R7A_CAPTURE_ID_MISMATCH:" + str(line_number))
        if record["origin"] not in {"SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"}:
            raise BridgeError("R7A_ORIGIN:" + str(line_number))
        row = record["fields"]
        if type(row) is not dict or set(row) != set(required_fields):
            raise BridgeError("R7A_FIELDS_NOT_EXACT_61:" + str(line_number))
        missing = [name for name in required_fields if name not in row]
        if missing:
            raise BridgeError(
                "TRACE_REQUIRED_FIELD_MISSING:"
                + str(line_number)
                + ":"
                + ",".join(missing)
            )
        cycle = checked_int(row["cycle"], f"line{line_number}.cycle")
        checked_int(row["epoch"], f"line{line_number}.epoch")
        if cycle <= previous_cycle:
            raise BridgeError("TRACE_CYCLE_NOT_STRICTLY_INCREASING:" + str(line_number))
        source = record["source"]
        if type(source) is not dict or source.get("line") != line_number:
            raise BridgeError("R7A_SOURCE_LINE_MISMATCH:" + str(line_number))
        if source.get("cycle") != row["cycle"] or source.get("epoch") != row["epoch"]:
            raise BridgeError("R7A_SOURCE_TIME_IDENTITY_MISMATCH:" + str(line_number))
        if source.get("sampling_phase") != "POSEDGE_PRE_NBA":
            raise BridgeError("R7A_SAMPLING_PHASE:" + str(line_number))
        extensions = record["extensions"]
        if type(extensions) is not dict or extensions.get("schema") != "M3_R7A_TX_EXTENSION_V1":
            raise BridgeError("R7A_EXTENSION_SCHEMA:" + str(line_number))
        if type(record["missing_reasons"]) is not dict or type(record["events"]) is not list:
            raise BridgeError("R7A_METADATA_TYPES:" + str(line_number))
        previous_cycle = cycle
        rows.append(row)
        raw_lines.append(raw)
        records.append(record)
    if not rows:
        raise BridgeError("EMPTY_TRACE")
    return rows, raw_lines, records


def line_index_sha256(raw_lines: list[bytes]) -> str:
    payload = b"".join(
        str(line_number).encode("ascii")
        + b":"
        + hashlib.sha256(raw).hexdigest().encode("ascii")
        + b"\n"
        for line_number, raw in enumerate(raw_lines, start=1)
    )
    return hashlib.sha256(payload).hexdigest()


def tri_flag(value: Any) -> bool | None:
    if value == 0 and type(value) is int:
        return False
    if value == 1 and type(value) is int:
        return True
    return None


def tri_and(left: Any, right: Any) -> bool | None:
    left_flag = tri_flag(left)
    right_flag = tri_flag(right)
    if left_flag is False or right_flag is False:
        return False
    if left_flag is True and right_flag is True:
        return True
    return None


def tri_nonzero_mask(value: Any) -> bool | None:
    if type(value) is int:
        return value != 0
    if type(value) is str and value and set(value) <= {"0", "1"}:
        return int(value, 2) != 0
    return None


def frame_entries(frame_plan: dict[str, Any]) -> set[tuple[int, int]]:
    if frame_plan.get("independent_of_trace") is not True:
        raise BridgeError("FRAME_PLAN_NOT_INDEPENDENT")
    entries: set[tuple[int, int]] = set()
    for epoch_entry in frame_plan.get("epochs", []):
        epoch = checked_int(epoch_entry.get("epoch"), "frame_plan.epoch")
        for cycle in epoch_entry.get("frame_cycles", []):
            key = (epoch, checked_int(cycle, "frame_plan.frame_cycle"))
            if key in entries:
                raise BridgeError("DUPLICATE_FRAME_PLAN_ENTRY:" + str(key))
            entries.add(key)
    if not entries:
        raise BridgeError("EMPTY_FRAME_PLAN")
    return entries


def midi_events(plan: dict[str, Any]) -> list[dict[str, Any]]:
    events = plan.get("events")
    if type(events) is not list or not events:
        raise BridgeError("EMPTY_MIDI_EVENT_PLAN")
    result = []
    for event in events:
        required = {"event_seq", "expected_event_hex", "arrival_window"}
        if not required <= event.keys():
            raise BridgeError("MIDI_EVENT_PLAN_FIELDS")
        result.append(event)
    return result


def match_event(row: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = tri_and(row["event_valid"], row["event_ready"])
    if accepted is False:
        return {"status": "NOT_ACCEPTED", "event_seq": None, "candidates": []}
    if accepted is None:
        return {"status": "PENDING_UNKNOWN_HANDSHAKE", "event_seq": None, "candidates": []}
    payload_candidates = []
    window_candidates = []
    for event in events:
        window = event["arrival_window"]
        if int(event["expected_event_hex"], 16) == row["event_data"]:
            payload_candidates.append(event["event_seq"])
            if window["min_cycle"] <= row["cycle"] <= window["max_cycle"]:
                window_candidates.append(event["event_seq"])
    if len(window_candidates) == 1:
        return {
            "status": "PLAN_PAYLOAD_AND_WINDOW_UNIQUE",
            "event_seq": window_candidates[0],
            "candidates": payload_candidates,
        }
    if len(payload_candidates) == 1:
        return {
            "status": "PLAN_PAYLOAD_UNIQUE_OUTSIDE_ARRIVAL_WINDOW",
            "event_seq": payload_candidates[0],
            "candidates": payload_candidates,
        }
    return {
        "status": "PENDING_AMBIGUOUS_OR_MISSING_PLAN_ASSOCIATION",
        "event_seq": None,
        "candidates": payload_candidates,
    }


def explicit_signals(row: dict[str, Any]) -> list[str]:
    signals = []
    reset = tri_flag(row["rst_n"])
    frame = tri_flag(row["frame_tick"])
    event_accept = tri_and(row["event_valid"], row["event_ready"])
    request_accept = tri_and(row["req_valid"], row["req_ready"])
    common_advance = tri_nonzero_mask(row["advance_mask"])
    if reset is False:
        signals.append("RESET_ACTIVE")
    elif reset is None:
        signals.append("RESET_UNKNOWN")
    if frame is True:
        signals.append("FRAME_F")
    elif frame is None:
        signals.append("FRAME_F_UNKNOWN")
    if event_accept is True:
        signals.append("EVENT_ACCEPT")
    elif event_accept is None:
        signals.append("EVENT_ACCEPT_UNKNOWN")
    if row["apply_valid"] == 1:
        signals.append("EVENT_APPLY")
    if request_accept is True:
        signals.append("REQUEST_A")
    elif request_accept is None:
        signals.append("REQUEST_A_UNKNOWN")
    if common_advance is True:
        signals.append("COMMON_ADVANCE")
    elif common_advance is None:
        signals.append("COMMON_ADVANCE_UNKNOWN")
    if row["result_valid"] == 1 and row["result_ready"] == 1:
        signals.append("RESULT")
    if row["commit"] == 1:
        signals.append("COMMIT")
    if row["cancel"] == 1:
        signals.append("CANCEL")
    if row["config_valid"] == 1 and row["config_ready"] == 1:
        signals.append("CONFIG_ACCEPT")
    if row["effect_input_valid"] == 1 and row["effect_input_ready"] == 1:
        signals.append("EFFECT_ACCEPT")
    if row["tx_sample_valid"] == 1:
        signals.append("TX_SAMPLE")
    if row["finish"] == 1:
        signals.append("FINISH")
    return signals


def build_index(
    rows: list[dict[str, Any]],
    raw_lines: list[bytes],
    records: list[dict[str, Any]],
    events: list[dict[str, Any]],
    planned_frames: set[tuple[int, int]],
) -> list[dict[str, Any]]:
    index = []
    observed_frames = set()
    for line_number, (row, raw, record) in enumerate(
        zip(rows, raw_lines, records), start=1
    ):
        key = (row["epoch"], row["cycle"])
        is_frame = tri_flag(row["frame_tick"])
        request_accept = tri_and(row["req_valid"], row["req_ready"])
        if is_frame is True:
            observed_frames.add(key)
        event_association = match_event(row, events)
        index.append(
            {
                "schema": "M3_R07_ORACLE_ROW_INDEX_V1",
                "input_line": line_number,
                "raw_line_sha256": hashlib.sha256(raw).hexdigest(),
                "cycle": row["cycle"],
                "epoch": row["epoch"],
                "signals": explicit_signals(row),
                "r7a_events": record["events"],
                "source": record["source"],
                "extensions": record["extensions"],
                "missing_reasons": record["missing_reasons"],
                "midi_event_association": event_association,
                "apply_event_seq_explicit": (
                    row["apply_event_seq"] if row["apply_valid"] == 1 else None
                ),
                "frame_plan_match": key in planned_frames if is_frame is True else None,
                "frame_f": is_frame,
                "request_a": request_accept,
                "request_id_raw": row["req_id"],
                "request_id_when_accepted": row["req_id"] if request_accept is True else None,
                "advance_mask_raw": row["advance_mask"],
                "common_advance": tri_nonzero_mask(row["advance_mask"]),
                "unknown_reasons": [
                    reason
                    for condition, reason in (
                        (is_frame is None, "frame_tick is X/Z/null or malformed"),
                        (request_accept is None, "req_valid/req_ready handshake is X/Z/null or malformed"),
                        (tri_nonzero_mask(row["advance_mask"]) is None, "advance_mask is X/Z/null or malformed"),
                    )
                    if condition
                ],
                "tx": {
                    "sample_valid": row["tx_sample_valid"],
                    "frame_id": row["tx_frame_id"],
                    "req_id": row["tx_req_id"],
                    "left": row["tx_left"],
                    "right": row["tx_right"],
                    "clip": row["tx_clip"],
                    "hold": row["tx_hold"],
                    "startup_zero": row["tx_startup_zero"],
                },
            }
        )
    if observed_frames != planned_frames:
        missing = sorted(planned_frames - observed_frames)
        extra = sorted(observed_frames - planned_frames)
        raise BridgeError(
            "FRAME_PLAN_TRACE_MISMATCH:missing=" + str(missing) + ":extra=" + str(extra)
        )
    return index


def build_bundle(binding_path: Path, root: Path, output: Path) -> dict[str, Any]:
    binding = read_json(binding_path)
    if type(binding) is not dict or binding.get("schema") != SCHEMA:
        raise BridgeError("BINDING_SCHEMA")
    if output.exists():
        raise BridgeError("OUTPUT_EXISTS")
    if binding.get("mode") not in {"SYNTHETIC_FIXTURE", "REAL_CAPTURE"}:
        raise BridgeError("BINDING_MODE")
    if not binding.get("capture_id") or not binding.get("scene"):
        raise BridgeError("CAPTURE_ID_OR_SCENE")
    inputs = binding.get("inputs")
    if type(inputs) is not list:
        raise BridgeError("INPUTS_ARRAY_REQUIRED")
    roles = [item.get("role") if type(item) is dict else None for item in inputs]
    if len(roles) != len(set(roles)) or set(roles) != REQUIRED_ROLES:
        raise BridgeError("INPUT_ROLE_SET")
    paths = {item["role"]: resolve_descriptor(root, item) for item in inputs}

    row_schema = read_json(paths["normalized_row_schema"])
    required_fields = row_schema.get("required")
    if type(required_fields) is not list or len(required_fields) != 61:
        raise BridgeError("NORMALIZED_ROW_SCHEMA_NOT_61_FIELDS")
    record_schema = read_json(paths["r7a_record_schema"])
    rows, raw_lines, records = load_trace(
        paths["normalized_trace"], required_fields, record_schema, binding["capture_id"]
    )
    normalized_binding = read_json(paths["normalized_binding"])
    if normalized_binding.get("schema") != "M3_R07_ORACLE_BRIDGE_CAPTURE_BINDING_V1":
        raise BridgeError("NORMALIZED_BINDING_SCHEMA")
    bound_trace = normalized_binding.get("trace")
    input_by_role = {item["role"]: item for item in inputs}
    trace_desc = input_by_role["normalized_trace"]
    expected_bound_trace = {
        "sha256": trace_desc["sha256"],
        "bytes": trace_desc["bytes"],
        "row_count": len(rows),
        "line_index_sha256": line_index_sha256(raw_lines),
    }
    if type(bound_trace) is not dict or bound_trace != expected_bound_trace:
        raise BridgeError("NORMALIZED_BINDING_TRACE_IDENTITY_OR_COVERAGE_MISMATCH")
    if normalized_binding.get("input_plan_sha256") != input_by_role["midi_plan"]["sha256"]:
        raise BridgeError("NORMALIZED_BINDING_INPUT_PLAN_MISMATCH")
    if normalized_binding.get("frame_plan_sha256") != input_by_role["frame_plan"]["sha256"]:
        raise BridgeError("NORMALIZED_BINDING_FRAME_PLAN_MISMATCH")
    if normalized_binding.get("record_schema_sha256") != input_by_role["r7a_record_schema"]["sha256"]:
        raise BridgeError("NORMALIZED_BINDING_R7A_SCHEMA_MISMATCH")
    plan = read_json(paths["midi_plan"])
    frame_plan = read_json(paths["frame_plan"])
    events = midi_events(plan)
    frames = frame_entries(frame_plan)
    index = build_index(rows, raw_lines, records, events, frames)

    finish = frame_plan.get("finish")
    finish_rows = [row for row in rows if row["finish"] == 1]
    if (
        type(finish) is not dict
        or len(finish_rows) != 1
        or (finish_rows[0]["epoch"], finish_rows[0]["cycle"])
        != (finish.get("epoch"), finish.get("cycle"))
    ):
        raise BridgeError("FINISH_CONTRACT_MISMATCH")

    output.mkdir(parents=True)
    originals = output / "originals"
    originals.mkdir()
    copied = []
    for item in inputs:
        source = paths[item["role"]]
        suffix = "".join(source.suffixes) or ".bin"
        destination = originals / (item["role"] + suffix)
        shutil.copyfile(source, destination)
        copied.append(
            {
                "role": item["role"],
                "source_path": item["path"],
                "source_sha256": item["sha256"],
                "source_bytes": item["bytes"],
                "copied_path": destination.relative_to(output).as_posix(),
                "copied_sha256": sha256(destination),
                "copied_bytes": destination.stat().st_size,
                "byte_exact": sha256(destination) == item["sha256"],
            }
        )

    index_path = output / "ROW_INDEX.jsonl"
    write_jsonl(index_path, index)
    gaps = {
        "schema": "M3_R07_ORACLE_BRIDGE_CONTRACT_GAPS_V1",
        "legacy_b0_profile": LEGACY_PROFILE,
        "legacy_b0_status": "PENDING_UNSUPPORTED_PROFILE",
        "reason": (
            "The legacy B0 profile cannot losslessly express public FRAME F versus "
            "request acceptance A, same-edge ordering, asynchronous RESET_EDGES, "
            "or TX HOLD/startup metadata. No lossy B0 calendar/public_pcm projection "
            "was generated."
        ),
        "preserved_without_projection": [
            "raw normalized rows",
            "internal trace binding and complete raw-line digest",
            "input line and raw-line SHA",
            "cycle and epoch",
            "FRAME_F and REQUEST_A as separate facts",
            "R7-A same-edge events",
            "R7-A source and extension envelopes",
            "TX frame/request/PCM/clip/HOLD/startup",
            "independent frame plan",
            "MIDI byte/event plan",
            "reset and finish rows",
        ],
        "pending": [
            "PENDING_R7_A_REAL_CAPTURE" if binding.get("r7a_status") != "AVAILABLE" else None,
            "PENDING_M1_SCHEMA_AND_ARITHMETIC_PROFILE_DECISION",
            "PENDING_M1_APPLY_SLOT_RELEASE_RETIRE_GENERATION_SEMANTICS",
            "PENDING_M2_AUTHORITATIVE_CAPTURE_AND_FINISH_CONTRACT",
        ],
        "m1_math_executed": False,
        "expected_values_derived_from_dut": False,
        "board_release_allowed": False,
    }
    gaps["pending"] = [item for item in gaps["pending"] if item is not None]
    gaps_path = output / "CONTRACT_GAPS.json"
    write_json(gaps_path, gaps)

    status = (
        "SOFTWARE_READY_SYNTHETIC_PENDING_M1_PROFILE"
        if binding["mode"] == "SYNTHETIC_FIXTURE"
        else "MECHANICAL_REAL_INPUT_PACKAGED_PENDING_M1_M2_AUTHORITY"
    )
    bundle = {
        "schema": OUTPUT_SCHEMA,
        "status": status,
        "mode": binding["mode"],
        "capture_id": binding["capture_id"],
        "scene": binding["scene"],
        "source_baseline": binding.get("source_baseline"),
        "sampling_phase": read_json(paths["capture_contract"]).get("sampling_phase"),
        "r7a_status": binding.get("r7a_status"),
        "inputs": copied,
        "row_count": len(rows),
        "frame_count": len(frames),
        "midi_event_count": len(events),
        "finish": finish,
        "row_index": {
            "path": index_path.name,
            "bytes": index_path.stat().st_size,
            "sha256": sha256(index_path),
        },
        "contract_gaps": {
            "path": gaps_path.name,
            "bytes": gaps_path.stat().st_size,
            "sha256": sha256(gaps_path),
            "legacy_b0_status": gaps["legacy_b0_status"],
        },
        "math_or_oracle_executed": False,
        "hdl_eda_hardware_executed": False,
        "real_capture_pass": False,
        "board_release_allowed": False,
    }
    bundle_path = output / "BUNDLE.json"
    write_json(bundle_path, bundle)
    manifest = {
        "schema": "M3_R07_ORACLE_BRIDGE_OUTPUT_MANIFEST_V1",
        "files": [
            {
                "path": path.relative_to(output).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in sorted(output.rglob("*"))
            if path.is_file()
        ],
        "self_sha256_excluded": True,
    }
    write_json(output / "MANIFEST.json", manifest)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        bundle = build_bundle(
            args.binding.resolve(), args.root.resolve(), args.output.resolve()
        )
    except (BridgeError, OSError) as error:
        print(
            json.dumps(
                {
                    "schema": "M3_R07_ORACLE_BRIDGE_ERROR_V1",
                    "status": "CONTRACT_REJECTED",
                    "error": str(error),
                    "board_release_allowed": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(bundle, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
