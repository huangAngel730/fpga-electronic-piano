"""Compile the independent C v4 JSONL plan into an SV stimulus include.

This generator does not read a DUT trace or execute HDL tools.  All commands
are literal plan inputs; operation completion is decided by public handshakes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def event_word(op: dict) -> int:
    kind = op["op"]
    typ = {"note_on": 0, "note_off": 1, "cc64": 4,
           "control_event": 4}[kind]
    ctl, value = 0, 0
    if kind == "cc64":
        ctl, value = 6, 4095 if op["down"] else 0
    elif kind == "control_event":
        typ, ctl = {"pitch_bend": (3, 0), "modulation": (4, 1),
                    "pitch_range": (4, 4)}[op["control"]]
        value = op["value"]
    fields = [(typ, 3), (op.get("source", 0), 4),
              (op.get("channel", 0), 4), (op.get("note", 0), 7),
              (op.get("velocity", 0), 10),
              (op.get("expression", 0), 10), (ctl, 8), (value, 12), (0, 6)]
    result = 0
    for value, width in fields:
        if type(value) is not int or not 0 <= value < (1 << width):
            raise ValueError("C4_EVENT_FIELD_RANGE")
        result = (result << width) | value
    return result


def generate(plan: Path, output: Path) -> dict:
    raw = plan.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if rows[0]["record"] != "META" or rows[-1]["record"] != "END":
        raise ValueError("C4_PLAN_ENVELOPE")
    operations = rows[1:-1]
    if not 0 < len(operations) <= 20001:
        raise ValueError("C4_PLAN_OPERATION_COUNT")
    memory = output.with_suffix(".mem")
    if output.exists() or memory.exists():
        raise FileExistsError("C4_GENERATED_ASSETS_EXIST")
    opcodes = {"note_on": 1, "note_off": 2, "cc64": 3,
               "control_event": 4, "sample": 5, "read": 6,
               "read_stall": 7, "await_release_done": 8,
               "set_result_ready": 9, "reset": 10, "cancel": 11,
               "wait_idle": 12, "tick": 13}
    commands = []
    for index, op in enumerate(operations):
        if op.get("record") != "PLAN" or op["index"] != index:
            raise ValueError("C4_PLAN_INDEX")
        kind = op["op"]
        if kind not in opcodes:
            raise ValueError("C4_UNKNOWN_OP:" + kind)
        value, delay = 0, 0
        if kind in ("note_on", "note_off", "cc64", "control_event"):
            value = event_word(op)
        elif kind == "sample":
            value, delay = op["result_id"], op.get("min_hold_cycles", 0)
        elif kind in ("read", "await_release_done"):
            value = op["slot"]
        elif kind == "read_stall":
            value, delay = op["slot"], op["cycles"]
        elif kind == "set_result_ready":
            value = op["value"]
        if kind in ("read", "read_stall", "await_release_done") and not (
                type(value) is int and 0 <= value < 32):
            raise ValueError("C4_COMMAND_SLOT_RANGE")
        if kind == "sample" and not (type(value) is int and 0 <= value < 2**32):
            raise ValueError("C4_COMMAND_ID_RANGE")
        if kind == "set_result_ready" and (type(value) is not int or value not in (0, 1)):
            raise ValueError("C4_COMMAND_READY_RANGE")
        if (type(value) is not int or not 0 <= value < 2**64 or
                type(delay) is not int or not 0 <= delay < 2**31):
            raise ValueError("C4_COMMAND_FIELD_RANGE")
        commands.append((opcodes[kind] << 120) | (delay << 64) | value)
    body = ("// Compact dispatch: independent inputs are in c_plan_v4.mem.\n"
            f"load_commands({len(commands)});\n"
            f"for(command_index=0;command_index<{len(commands)};command_index=command_index+1)\n"
            "    run_command(command_index);\n").encode("ascii")
    mem_body = ("\n".join(f"{command:032x}" for command in commands) + "\n").encode("ascii")
    with memory.open("xb") as stream:
        stream.write(mem_body)
    with output.open("xb") as stream:
        stream.write(body)
    return {"plan_sha256": hashlib.sha256(raw).hexdigest(),
            "include_sha256": hashlib.sha256(body).hexdigest(),
            "memory_sha256": hashlib.sha256(mem_body).hexdigest(),
            "operations": len(operations)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.plan, args.output), sort_keys=True))
