"""Generate an independent physical MIDI byte/time plan for R06."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def velocity10(value: int) -> int:
    return (value << 3) | (value >> 4)


def packed_event(params: dict, kind: str, note: int, velocity: int) -> int:
    enc = params["public_event_encoding"]
    midi = params["midi"]
    is_on = kind == "note_on" and velocity != 0
    event_type = enc["event_note_on"] if is_on else enc["event_note_off"]
    vel = velocity10(velocity) if is_on else 0
    return ((event_type & 7) << 61) | ((midi["source_id"] & 15) << 57) | (
        (midi["channel"] & 15) << 53
    ) | ((note & 127) << 46) | ((vel & 1023) << 36)


def validate_inputs(params: dict, cases: dict) -> None:
    require(params["schema"] == "M3_R06_MIDI_STIMULUS_PARAMETERS_V1", "PARAM_SCHEMA")
    require(cases["schema"] == "M3_R06_MIDI_STIMULUS_CASES_V1", "CASE_SCHEMA")
    require(type(params["clock_hz"]) is int and params["clock_hz"] > 0, "CLOCK")
    require(type(params["baud"]) is int and params["baud"] > 0, "BAUD")
    require(params["clock_hz"] % params["baud"] == 0, "NON_INTEGER_BIT_CYCLES")
    require(params["uart"] == {
        "data_bits": 8, "parity": "NONE", "stop_bits": 1,
        "idle_level": 1, "bit_order": "LSB_FIRST"}, "UART_8N1")
    seqs = []
    for action in cases["actions"]:
        require(action["op"] in {"reset", "ready", "wait_us", "message"}, "ACTION_OP")
        if action["op"] == "message":
            require(action["kind"] in {"note_on", "note_off"}, "MESSAGE_KIND")
            require(action["status"] in {"full", "running"}, "STATUS_MODE")
            require(0 <= action["note"] <= 127 and 0 <= action["velocity"] <= 127,
                    "MIDI_DATA_RANGE")
            seqs.append(action["event_seq"])
    require(seqs == list(range(1, len(seqs) + 1)), "EVENT_SEQ_CONTIGUOUS")


def generate(params: dict, cases: dict) -> dict:
    validate_inputs(params, cases)
    bit_cycles = params["clock_hz"] // params["baud"]
    byte_cycles = bit_cycles * 10
    cursor = 0
    last_reset_release = None
    running_status = None
    byte_rows = []
    reset_rows = []
    ready_rows = []
    events = []
    byte_seq = 0

    def emit(value: int, role: str, event_seq: int | None, scenario: str) -> int:
        nonlocal cursor, byte_seq
        require(0 <= value <= 255, "BYTE_RANGE")
        start = cursor
        stop = start + byte_cycles
        byte_seq += 1
        byte_rows.append({"byte_seq": byte_seq, "event_seq": event_seq,
                          "scenario": scenario, "role": role, "value": value,
                          "start_cycle": start, "stop_cycle_exclusive": stop})
        cursor = stop
        return byte_seq

    for action in cases["actions"]:
        op = action["op"]
        if op == "wait_us":
            cursor += (params["clock_hz"] * action["value"]) // 1_000_000
        elif op == "reset":
            reset_rows.append({"cycle": cursor, "level": action["level"],
                               "label": action["label"]})
            if action["level"] == 0:
                running_status = None
            else:
                last_reset_release = cursor
        elif op == "ready":
            ready_rows.append({"cycle": cursor, "level": action["level"],
                               "label": action["label"]})
        else:
            if last_reset_release is not None:
                cursor = max(cursor, last_reset_release +
                             params["timing"]["initial_idle_bits"] * bit_cycles)
            channel = params["midi"]["channel"]
            status = (params["midi"]["note_on_status_base"] if action["kind"] == "note_on"
                      else params["midi"]["note_off_status_base"]) | channel
            first_byte_seq = byte_seq + 1
            if action["status"] == "full":
                emit(status, "status", action["event_seq"], action["scenario"])
                running_status = status
            else:
                require(running_status == status, "RUNNING_STATUS_NOT_ACTIVE")
            emit(action["note"], "note", action["event_seq"], action["scenario"])
            if action.get("realtime_after_data_index") == 0:
                emit(params["midi"]["realtime_clock_byte"], "realtime",
                     None, action["scenario"])
            final_seq = emit(action["velocity"], "velocity", action["event_seq"],
                             action["scenario"])
            final_stop = cursor
            is_note_on = action["kind"] == "note_on" and action["velocity"] != 0
            events.append({
                "event_seq": action["event_seq"], "scenario": action["scenario"],
                "midi_kind": action["kind"], "normalized_kind": "note_on" if is_note_on else "note_off",
                "channel": channel, "note": action["note"], "velocity7": action["velocity"],
                "velocity10": velocity10(action["velocity"]) if is_note_on else 0,
                "source_byte_seq_first": first_byte_seq, "source_byte_seq_final": final_seq,
                "final_stop_cycle_exclusive": final_stop,
                "arrival_window": {
                    "min_cycle": final_stop + params["timing"]["event_window_min_cycles_after_final_stop"],
                    "max_cycle": final_stop + params["timing"]["event_window_max_cycles_after_final_stop"]
                },
                "expected_event_hex": f"{packed_event(params, action['kind'], action['note'], action['velocity']):016x}",
                "allocation_release_generation": "PENDING_M1_SOURCE_SEMANTICS"
            })
            cursor += params["timing"]["inter_message_idle_bits"] * bit_cycles

    require(all(a["stop_cycle_exclusive"] <= b["start_cycle"]
                for a, b in zip(byte_rows, byte_rows[1:])), "BYTE_OVERLAP")
    return {"schema": "M3_R06_MIDI_STIMULUS_PLAN_V1", "parameters": params,
            "bit_cycles": bit_cycles, "byte_cycles": byte_cycles,
            "total_cycles": cursor, "bytes": byte_rows, "events": events,
            "reset_plan": reset_rows, "ready_plan": ready_rows,
            "semantic_status": "INPUT_COMPLETE_SLOT_RELEASE_PREEMPT_PENDING_M1"}


def write_driver_files(plan: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    with (output / "bytes.drv").open("w", encoding="ascii", newline="\n") as stream:
        for row in plan["bytes"]:
            stream.write(f"{row['start_cycle']} {row['value']:02x} {row['byte_seq']}\n")
    for name, rows in (("reset.drv", plan["reset_plan"]), ("ready.drv", plan["ready_plan"])):
        with (output / name).open("w", encoding="ascii", newline="\n") as stream:
            for row in rows:
                stream.write(f"{row['cycle']} {row['level']}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parameters", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = generate(load_json(args.parameters), load_json(args.cases))
    write_driver_files(plan, args.output)
    print(json.dumps({"status": "PASS", "events": len(plan["events"]),
                      "bytes": len(plan["bytes"]), "total_cycles": plan["total_cycles"],
                      "parameters_sha256": sha256(args.parameters),
                      "cases_sha256": sha256(args.cases)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
