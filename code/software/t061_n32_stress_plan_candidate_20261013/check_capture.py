"""Fail-closed, edge-replayed checker for T061 N32-C captures.

Actual mode never trusts META labels to authorize execution. It requires an
externally pinned execution manifest, approval digest, and run receipt. The
capture is one complete PRE_NBA CYCLE record per real clock edge; the checker
replays the input plan without sorting observations into independent streams.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any

from n32c_common import (
    CONTROL_EVENT_SPECS,
    ContractError,
    Slot,
    control_digest,
    exact_keys,
    file_sha256,
    is_reparse_point,
    integer,
    pack_event,
    public_slot_digest,
    public_slots,
    read_jsonl,
    records_sha256,
    require,
    slot_digest,
    strict_json,
    validate_event_record,
    validate_public_slots,
    validate_read_record,
    validate_txn_record,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HEX64 = re.compile(r"[0-9a-f]{64}")

PLAN_META_FIELDS = (
    "record", "schema", "n", "response", "clock_hz", "seed",
    "b_dependency_status", "original_prepared_path_status",
    "allocator_readonly_alias", "allocator_sha256",
)
PLAN_END_FIELDS = ("record", "operations", "body_sha256")
EXPECTED_META_FIELDS = (
    "record", "schema", "plan_sha256", "audio_math_status",
    "executable_for_rtl_acceptance", "b_review_key", "b_fingerprint",
)
EXPECTED_END_FIELDS = (
    "record", "events", "transactions", "publish_transactions",
    "cancel_transactions", "reads", "body_sha256",
)
CAPTURE_META_FIELDS = (
    "record", "schema", "origin", "plan_sha256", "expected_sha256",
    "b_review_key", "b_fingerprint", "sampling_phase",
)
CYCLE_FIELDS = (
    "record", "edge", "plan_index", "reset_lifetime", "rst_n", "cancel",
    "event_valid", "event_ready", "event_word",
    "sample_valid", "sample_ready", "sample_id",
    "result_valid", "result_ready", "result_id", "left_pcm", "right_pcm",
    "clipped", "read_valid", "read_ready", "read_slot", "read_out_valid",
    "read_context", "audio_state", "router_state", "publish",
    "control_snapshot_valid", "control_snapshot_ready",
    "control_snapshot_id", "control_snapshot_value",
    "control_snapshot_occupied", "control_snapshot_sources",
    "control_snapshot_channels", "control_snapshot_generations",
    "control_release_valid", "control_release_ready",
    "control_release_mask", "control_release_generations",
    "backend_release_done_valid", "backend_release_done_ready",
    "backend_release_done_slot", "backend_release_done_generation",
    "backend_release_done_mask", "aborted", "abort_reason", "idle",
    "fault", "slots", "slot_digest",
)
CAPTURE_END_FIELDS = (
    "record", "last_edge", "cycles", "event_accepts", "sample_accepts",
    "results", "hold_cycles", "read_requests", "read_responses", "cancels",
    "resets", "release_done", "control_snapshots", "control_releases",
    "body_sha256",
)


def _repo_path(value: Any, name: str) -> Path:
    require(type(value) is str and value, f"PATH_TYPE:{name}")
    raw = Path(value)
    require(not raw.is_absolute() and ".." not in raw.parts,
            f"PATH_SCOPE:{name}")
    root = Path(os.path.abspath(ROOT))
    resolved = Path(os.path.abspath(root / raw))
    require(resolved.exists(), f"PATH_MISSING:{name}")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"PATH_ESCAPE:{name}") from exc
    cursor = resolved
    while cursor != root:
        require(not is_reparse_point(cursor),
                f"PATH_REPARSE:{name}")
        cursor = cursor.parent
    return resolved


def _file_spec(spec: Any, name: str) -> Path:
    exact_keys(spec, ("path", "bytes", "sha256"), name)
    path = _repo_path(spec["path"], name)
    integer(spec["bytes"], 0, 1 << 40, f"{name}.bytes")
    require(type(spec["sha256"]) is str
            and HEX64.fullmatch(spec["sha256"]) is not None,
            f"SHA_TYPE:{name}")
    require(path.stat().st_size == spec["bytes"]
            and file_sha256(path) == spec["sha256"], f"FILE_IDENTITY:{name}")
    return path


def _external_file_spec(spec: Any, name: str) -> Path:
    """Validate an explicitly pinned external executable/support file.

    Tools are not required to live in the repository.  Their absolute path,
    byte count, and digest are evidence; allowing an unpinned PATH lookup is
    forbidden.
    """
    exact_keys(spec, ("path", "bytes", "sha256"), name)
    require(type(spec["path"]) is str and Path(spec["path"]).is_absolute(),
            f"ABSOLUTE_PATH:{name}")
    path = Path(os.path.abspath(spec["path"]))
    require(path.is_file() and not is_reparse_point(path),
            f"EXTERNAL_FILE:{name}")
    integer(spec["bytes"], 1, 1 << 40, f"{name}.bytes")
    require(type(spec["sha256"]) is str
            and HEX64.fullmatch(spec["sha256"]) is not None,
            f"SHA_TYPE:{name}")
    require(path.stat().st_size == spec["bytes"]
            and file_sha256(path) == spec["sha256"],
            f"FILE_IDENTITY:{name}")
    return path


def _validate_plan(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    require(len(plan) >= 3, "PLAN_EMPTY")
    exact_keys(plan[0], PLAN_META_FIELDS, "plan_meta")
    require(plan[0]["record"] == "META"
            and plan[0]["schema"] == "t061-n32c-plan-v3"
            and plan[0]["n"] == 32 and plan[0]["response"] == 1
            and plan[0]["clock_hz"] == 40_000_000
            and plan[0]["seed"] == 0x4E333243
            and plan[0]["b_dependency_status"] == "WAIT_B_EXACT_PASS"
            and plan[0]["original_prepared_path_status"] == "MISSING"
            and plan[0]["allocator_readonly_alias"]
            == "code/rtl/common/polyphony_scaling_candidate/b2c_voice_allocator.sv"
            and plan[0]["allocator_sha256"]
            == "9fec9f838a9ef333d01d1b79ecf77d137e41bc0c5e78a40d2820c37739506061",
            "PLAN_META")
    body = plan[1:-1]
    base = {"record", "index", "cycle_hint", "case_id", "op"}
    fields = {
        "note_on": {"source", "channel", "note", "velocity", "expression"},
        "note_off": {"source", "channel", "note"},
        "cc64": {"source", "channel", "down"},
        "control_event": {"source", "channel", "control", "value"},
        "sample": {"result_id", "disposition"},
        "set_result_ready": {"value"},
        "tick": set(), "read": {"slot"}, "cancel": set(), "reset": set(),
        "await_release_done": {"slot"}, "wait_idle": set(),
    }
    for index, row in enumerate(body):
        require(row.get("record") == "PLAN" and row.get("index") == index,
                f"PLAN_INDEX:{index}")
        require(row.get("cycle_hint") == index * 8, f"PLAN_HINT:{index}")
        require(type(row.get("case_id")) is str and row["case_id"],
                f"PLAN_CASE:{index}")
        op = row.get("op")
        require(op in fields, f"PLAN_OP:{index}")
        allowed = base | fields[op]
        if op == "sample" and "min_hold_cycles" in row:
            allowed.add("min_hold_cycles")
        require(set(row) == allowed, f"PLAN_FIELDS:{index}:{op}")
        if op in {"note_on", "note_off", "cc64", "control_event"}:
            integer(row["source"], 0, 15, f"plan.source[{index}]")
            integer(row["channel"], 0, 15, f"plan.channel[{index}]")
        if op in {"note_on", "note_off"}:
            integer(row["note"], 0, 127, f"plan.note[{index}]")
        if op == "note_on":
            integer(row["velocity"], 1, 1023, f"plan.velocity[{index}]")
            integer(row["expression"], 0, 1023,
                    f"plan.expression[{index}]")
        elif op == "cc64":
            require(type(row["down"]) is bool, f"PLAN_DOWN:{index}")
        elif op == "control_event":
            require(row["control"] in CONTROL_EVENT_SPECS,
                    f"PLAN_CONTROL:{index}")
            integer(row["value"], 0, 4095, f"plan.value[{index}]")
        elif op == "sample":
            integer(row["result_id"], 0, (1 << 32) - 1,
                    f"plan.result_id[{index}]")
            require(row["disposition"] in {"PUBLISH", "CANCEL"},
                    f"PLAN_DISPOSITION:{index}")
            integer(row.get("min_hold_cycles", 0), 0, 1 << 20,
                    f"plan.min_hold_cycles[{index}]")
        elif op == "set_result_ready":
            require(row["value"] in (0, 1)
                    and type(row["value"]) is int, f"PLAN_READY:{index}")
        elif op in {"read", "await_release_done"}:
            integer(row["slot"], 0, 31, f"plan.slot[{index}]")
    exact_keys(plan[-1], PLAN_END_FIELDS, "plan_end")
    require(plan[-1]["record"] == "END"
            and plan[-1]["operations"] == len(body)
            and plan[-1]["body_sha256"] == records_sha256(plan[:-1]),
            "PLAN_END")
    return body


def _validate_expected(expected: list[dict[str, Any]], plan_sha: str,
                       operations: list[dict[str, Any]],
                       allow_fixture: bool) -> tuple[list[dict[str, Any]],
                                                     list[dict[str, Any]],
                                                     list[dict[str, Any]]]:
    require(len(expected) >= 3, "EXPECTED_EMPTY")
    meta = expected[0]
    exact_keys(meta, EXPECTED_META_FIELDS, "expected_meta")
    require(meta["record"] == "META"
            and meta["schema"] == "t061-n32c-expected-v3"
            and meta["plan_sha256"] == plan_sha, "EXPECTED_META")
    executable = meta["executable_for_rtl_acceptance"] is True
    require(executable or allow_fixture, "EXPECTED_NOT_EXECUTABLE")
    if executable:
        require(meta["audio_math_status"] == "BOUND_INDEPENDENT_FROZEN_MATH",
                "AUDIO_MATH_NOT_BOUND")
        for name in ("b_review_key", "b_fingerprint"):
            require(type(meta[name]) is str and meta[name]
                    and meta[name] != "WAIT_B_EXACT_PASS", f"B_NOT_BOUND:{name}")
    events: list[dict[str, Any]] = []
    txns: list[dict[str, Any]] = []
    reads: list[dict[str, Any]] = []
    plan_lifetimes: list[int] = []
    lifetime = 0
    for operation in operations:
        plan_lifetimes.append(lifetime)
        if operation["op"] == "reset":
            lifetime += 1
    last_plan_index = -1
    next_event_serial = next_accept_serial = next_read_serial = 0
    for row in expected[1:-1]:
        require(type(row) is dict and row.get("record") in {"EVENT", "TXN", "READ"},
                "EXPECTED_RECORD_TYPE")
        require(row["plan_index"] >= last_plan_index, "EXPECTED_TIME_ORDER")
        last_plan_index = row["plan_index"]
        require(row["plan_index"] < len(plan_lifetimes)
                and row["reset_lifetime"]
                == plan_lifetimes[row["plan_index"]],
                "EXPECTED_RESET_LIFETIME")
        if row["record"] == "EVENT":
            validate_event_record(row)
            require(row["event_serial"] == next_event_serial,
                    "EVENT_SERIAL_SEQUENCE")
            next_event_serial += 1
            events.append(row)
        elif row["record"] == "TXN":
            validate_txn_record(row, executable=True)
            require(row["accept_serial"] == next_accept_serial,
                    "ACCEPT_SERIAL_SEQUENCE")
            next_accept_serial += 1
            if executable and row["disposition"] == "PUBLISH":
                require(row["pcm_provenance"] == "INDEPENDENT_FROZEN_MATH",
                        "PCM_PROVENANCE")
            txns.append(row)
        else:
            validate_read_record(row, executable=True)
            require(row["read_serial"] == next_read_serial,
                    "READ_SERIAL_SEQUENCE")
            next_read_serial += 1
            if executable:
                require(row["context_provenance"] == "INDEPENDENT_FROZEN_MATH",
                        "READ_PROVENANCE")
            reads.append(row)
    end = expected[-1]
    exact_keys(end, EXPECTED_END_FIELDS, "expected_end")
    publish = sum(row["disposition"] == "PUBLISH" for row in txns)
    cancel = len(txns) - publish
    require(end == {
        "record": "END", "events": len(events), "transactions": len(txns),
        "publish_transactions": publish, "cancel_transactions": cancel,
        "reads": len(reads), "body_sha256": records_sha256(expected[:-1]),
    }, "EXPECTED_END")
    require(events and txns and reads and publish and cancel, "ZERO_COMPARISON")
    return events, txns, reads


@dataclass
class Replay:
    slots: list[Slot]
    pedals: set[tuple[int, int]]
    controls: dict[str, int]
    focus: tuple[int, int, int]
    reset_lifetime: int = 0
    event_serial: int = 0
    accept_serial: int = 0

    @classmethod
    def create(cls) -> "Replay":
        return cls([Slot(age=lane) for lane in range(32)], set(),
                   {},
                   (0, 0, 0))

    def choose(self, identity: tuple[int, int, int]) -> int:
        matches = [lane for lane, slot in enumerate(self.slots)
                   if (slot.occupied or slot.releasing)
                   and slot.identity() == identity]
        if matches:
            return min(matches)
        idle = [lane for lane, slot in enumerate(self.slots)
                if not slot.occupied and not slot.releasing]
        if idle:
            return min(idle)
        return min(range(32), key=lambda lane: (self.slots[lane].age, lane))

    def apply_event(self, op: dict[str, Any]) -> None:
        name = op["op"]
        if name == "note_on":
            identity = op["source"], op["channel"], op["note"]
            target = self.choose(identity)
            old_age = self.slots[target].age
            for lane, slot in enumerate(self.slots):
                if lane != target and slot.age > old_age:
                    slot.age -= 1
            generation = (self.slots[target].generation + 1) & 0xFFFFFFFF
            self.slots[target] = Slot(
                occupied=True, source=identity[0], channel=identity[1],
                note=identity[2], velocity=op["velocity"],
                generation=generation, age=31)
            self.focus = identity
        elif name == "note_off":
            identity = op["source"], op["channel"], op["note"]
            for slot in self.slots:
                if slot.occupied and slot.identity() == identity:
                    if (identity[0], identity[1]) in self.pedals:
                        slot.deferred = True
                    else:
                        slot.releasing = True
                    self.focus = identity
        elif name == "cc64":
            source, channel = op["source"], op["channel"]
            identity = source, channel
            if op["down"]:
                self.pedals.add(identity)
            else:
                self.pedals.discard(identity)
                for slot in self.slots:
                    if (slot.occupied and slot.deferred
                            and (slot.source, slot.channel) == identity):
                        slot.deferred = False
                        slot.releasing = True
        elif name == "control_event":
            key = f"{op['source']}:{op['channel']}:{op['control']}"
            self.controls[key] = op["value"]
        else:
            raise ContractError(f"REPLAY_EVENT_OP:{name}")

    def reset(self) -> None:
        self.slots = [Slot(age=lane) for lane in range(32)]
        self.pedals.clear()
        self.controls = {}
        self.focus = (0, 0, 0)
        self.reset_lifetime += 1


def _event_word(op: dict[str, Any]) -> int:
    if op["op"] == "note_on":
        return pack_event(event_type=0, source=op["source"],
                          channel=op["channel"], note=op["note"],
                          velocity=op["velocity"], expression=op["expression"])
    if op["op"] == "note_off":
        return pack_event(event_type=1, source=op["source"],
                          channel=op["channel"], note=op["note"])
    if op["op"] == "cc64":
        return pack_event(event_type=4, source=op["source"],
                          channel=op["channel"], control_id=6,
                          control_value=4095 if op["down"] else 0)
    event_type, control_id = CONTROL_EVENT_SPECS[op["control"]]
    return pack_event(event_type=event_type, source=op["source"],
                      channel=op["channel"], control_id=control_id,
                      control_value=op["value"])


def _validate_cycle(row: dict[str, Any], edge: int) -> None:
    exact_keys(row, CYCLE_FIELDS, f"cycle[{edge}]")
    require(row["record"] == "CYCLE" and row["edge"] == edge,
            f"CYCLE_EDGE:{edge}")
    integer(row["plan_index"], -1, (1 << 31) - 1, "plan_index")
    integer(row["reset_lifetime"], 0, (1 << 31) - 1, "reset_lifetime")
    for name in (
        "rst_n", "cancel", "event_valid", "event_ready", "sample_valid",
        "sample_ready", "result_valid", "result_ready", "clipped",
        "read_valid", "read_ready", "read_out_valid", "publish",
        "control_snapshot_valid", "control_snapshot_ready",
        "control_release_valid", "control_release_ready",
        "backend_release_done_valid", "backend_release_done_ready",
        "aborted", "idle", "fault",
    ):
        require(type(row[name]) is bool, f"BOOL:{name}:{edge}")
    for name, low, high in (
        ("event_word", 0, (1 << 64) - 1),
        ("sample_id", 0, (1 << 32) - 1),
        ("result_id", 0, (1 << 32) - 1),
        ("left_pcm", -(1 << 23), (1 << 23) - 1),
        ("right_pcm", -(1 << 23), (1 << 23) - 1),
        ("read_slot", 0, 31), ("read_context", 0, (1 << 74) - 1),
        ("audio_state", 0, 12), ("router_state", 0, 12),
        ("control_snapshot_id", 0, (1 << 32) - 1),
        ("control_snapshot_value", 0, (1 << (32 * 29)) - 1),
        ("control_snapshot_occupied", 0, (1 << 32) - 1),
        ("control_snapshot_sources", 0, (1 << 128) - 1),
        ("control_snapshot_channels", 0, (1 << 128) - 1),
        ("control_snapshot_generations", 0, (1 << 1024) - 1),
        ("control_release_mask", 0, (1 << 32) - 1),
        ("control_release_generations", 0, (1 << 1024) - 1),
        ("backend_release_done_slot", 0, 31),
        ("backend_release_done_generation", 0, (1 << 32) - 1),
        ("backend_release_done_mask", 0, (1 << 32) - 1),
        ("abort_reason", 0, 3),
    ):
        integer(row[name], low, high, name)
    require(row["publish"] is (row["result_valid"]
                                and row["result_ready"]),
            f"PUBLISH_HANDSHAKE:{edge}")
    if row["sample_valid"]:
        require(not row["read_ready"] and not row["event_ready"],
                f"SAMPLE_OWNERSHIP:{edge}")
    if row["read_valid"]:
        require(not row["sample_ready"] and not row["event_ready"],
                f"READ_OWNERSHIP:{edge}")
    if row["cancel"] or not row["rst_n"]:
        require(not row["event_ready"] and not row["sample_ready"]
                and not row["read_ready"] and not row["publish"],
                f"FENCE_READY:{edge}")
    require(row["backend_release_done_ready"] is True,
            f"BACKEND_RELEASE_READY:{edge}")
    require(row["backend_release_done_valid"]
            is bool(row["backend_release_done_mask"]),
            f"BACKEND_RELEASE_VALID_MASK:{edge}")
    if row["backend_release_done_valid"]:
        lowest = (row["backend_release_done_mask"]
                  & -row["backend_release_done_mask"]).bit_length() - 1
        require(row["backend_release_done_slot"] == lowest,
                f"BACKEND_RELEASE_LOWEST_SLOT:{edge}")
    validate_public_slots(row["slots"])
    require(row["slot_digest"] == public_slot_digest(row["slots"]),
            f"SLOT_DIGEST:{edge}")


def _validate_driver(row: dict[str, Any], op: dict[str, Any] | None,
                     ready_state: bool, *, event_waiting: bool,
                     event_settled: bool, release_waiting: bool,
                     release_settled: bool) -> tuple[bool, bool]:
    """Validate plan-driven ports. Return (operation_completed, new_ready)."""
    event_op = op is not None and op["op"] in {
        "note_on", "note_off", "cc64", "control_event",
    }
    sample_op = op is not None and op["op"] == "sample"
    read_op = op is not None and op["op"] == "read"
    release_op = op is not None and op["op"] == "await_release_done"
    require(row["event_valid"] is (event_op and not event_waiting
                                    and not event_settled),
            "DRIVE_EVENT_VALID")
    require(row["sample_valid"] is sample_op, "DRIVE_SAMPLE_VALID")
    require(row["read_valid"] is read_op, "DRIVE_READ_VALID")
    require(row["cancel"] is (op is not None and op["op"] == "cancel"),
            "DRIVE_CANCEL")
    require(row["rst_n"] is not (op is not None and op["op"] == "reset"),
            "DRIVE_RESET")
    next_ready = ready_state
    if op is not None and op["op"] == "set_result_ready":
        next_ready = bool(op["value"])
    require(row["result_ready"] is next_ready, "DRIVE_RESULT_READY")
    if event_op and row["event_valid"]:
        require(row["event_word"] == _event_word(op), "DRIVE_EVENT_WORD")
    if sample_op:
        require(row["sample_id"] == op["result_id"], "DRIVE_SAMPLE_ID")
    if read_op:
        require(row["read_slot"] == op["slot"], "DRIVE_READ_SLOT")
    if op is None:
        return False, next_ready
    if event_op:
        return event_settled, next_ready
    if sample_op:
        return row["sample_ready"], next_ready
    if read_op:
        return row["read_ready"], next_ready
    if release_op:
        return release_settled, next_ready
    if op["op"] == "wait_idle":
        return row["idle"], next_ready
    return True, next_ready


def check_records(plan: list[dict[str, Any]], expected: list[dict[str, Any]],
                  capture: list[dict[str, Any]], *,
                  allow_selftest_fixture: bool = False) -> dict[str, Any]:
    operations = _validate_plan(plan)
    plan_sha = records_sha256(plan)
    events, txns, reads = _validate_expected(
        expected, plan_sha, operations, allow_selftest_fixture)
    require(len(capture) >= 4, "CAPTURE_EMPTY")
    meta = capture[0]
    exact_keys(meta, CAPTURE_META_FIELDS, "capture_meta")
    require(meta["record"] == "META"
            and meta["schema"] == "t061-n32c-capture-v3"
            and meta["plan_sha256"] == plan_sha
            and meta["expected_sha256"] == records_sha256(expected)
            and meta["sampling_phase"] == "PRE_NBA_PUBLIC_PORTS",
            "CAPTURE_META")
    if allow_selftest_fixture:
        require(meta["origin"] == "SELFTEST_FIXTURE_ONLY", "FIXTURE_ORIGIN")
    else:
        require(meta["origin"] == "RTL_SIM_PUBLIC_PORTS_V3", "RTL_ORIGIN")
        require(meta["b_review_key"] == expected[0]["b_review_key"]
                and meta["b_fingerprint"] == expected[0]["b_fingerprint"],
                "B_IDENTITY")

    cycles = capture[1:-1]
    replay = Replay.create()
    plan_pos = 0
    ready_state = True
    event_pos = txn_pos = read_pos = 0
    outstanding: list[dict[str, Any]] = []
    pending_reads: list[tuple[int, dict[str, Any]]] = []
    pending_event: tuple[int, dict[str, Any], int] | None = None
    pending_release: tuple[int, int, int] | None = None
    held_payload: tuple[Any, ...] | None = None
    held_key: tuple[int, int] | None = None
    hold_counts: dict[tuple[int, int], int] = {}
    held_control_snapshot: tuple[Any, ...] | None = None
    held_control_release: tuple[Any, ...] | None = None
    seen_release_done: set[tuple[int, int]] = set()
    counts = {name: 0 for name in (
        "event_accepts", "sample_accepts", "results", "hold_cycles",
        "read_requests", "read_responses", "cancels", "resets",
        "release_done", "control_snapshots", "control_releases",
    )}

    for edge, row in enumerate(cycles):
        _validate_cycle(row, edge)
        op = operations[plan_pos] if plan_pos < len(operations) else None
        require(row["plan_index"] == (plan_pos if op is not None else -1),
                f"PLAN_PROGRESS:{edge}")

        # The reset lifetime begins at the actual asynchronous assertion, and
        # the same captured edge must already expose cleared public state.
        if not row["rst_n"]:
            require(op is not None and op["op"] == "reset",
                    f"UNPLANNED_RESET:{edge}")
            replay.reset()
            pending_event = pending_release = None
            outstanding.clear()
            held_payload = held_key = None
            pending_reads.clear()
        require(row["reset_lifetime"] == replay.reset_lifetime,
                f"RESET_LIFETIME:{edge}")

        event_waiting = pending_event is not None
        release_waiting = pending_release is not None
        event_settled = False
        release_settled = False
        if (pending_event is not None and row["router_state"] == 0
                and edge > pending_event[2]):
            pending_plan, pending_op, _accepted_edge = pending_event
            require(pending_plan == plan_pos, f"EVENT_PLAN_DRIFT:{edge}")
            replay.apply_event(pending_op)
            pending_event = None
            event_settled = True
        if (pending_release is not None and row["router_state"] == 0
                and edge > pending_release[2]):
            lane, generation, _observed_edge = pending_release
            slot = replay.slots[lane]
            require(slot.releasing and slot.generation == generation,
                    f"RELEASE_SETTLE_IDENTITY:{edge}")
            replay.slots[lane] = Slot(age=slot.age,
                                      generation=slot.generation)
            pending_release = None
            release_settled = True

        # Exact semantic comparison occurs only at a stable router boundary.
        # Intermediate FSM states are still captured and range-checked, but
        # an event handshake is never treated as a same-edge slot commit.
        if row["router_state"] == 0:
            require(row["slots"] == public_slots(replay.slots),
                    f"PUBLIC_SLOT_STATE:{edge}")
        if event_waiting and not event_settled:
            require(not row["event_ready"], f"EVENT_BUSY_READY:{edge}")
        require(row["fault"] is False, f"FAULT:{edge}")
        # A cleared transaction ledger is necessary but not sufficient for
        # hardware idle: after cancel the real B datapath remains in DRAIN
        # until its scheduler/backend are empty.  Never manufacture idle from
        # checker bookkeeping.
        if row["idle"]:
            require(not outstanding and held_payload is None,
                    f"IDLE_WITH_OPEN_TRANSACTION:{edge}")
        completed, ready_state = _validate_driver(
            row, op, ready_state, event_waiting=event_waiting,
            event_settled=event_settled, release_waiting=release_waiting,
            release_settled=release_settled)

        if row["event_valid"] and row["event_ready"]:
            require(event_pos < len(events), "EXTRA_EVENT")
            event = events[event_pos]
            require(event["plan_index"] == plan_pos
                    and event["event_word"] == row["event_word"]
                    and event["reset_lifetime"] == replay.reset_lifetime,
                    f"EVENT_IDENTITY:{edge}")
            require(pending_event is None, f"EVENT_OVERLAP:{edge}")
            pending_event = (plan_pos, op, edge)
            replay.event_serial += 1
            event_pos += 1
            counts["event_accepts"] += 1

        if row["sample_valid"] and row["sample_ready"]:
            require(txn_pos < len(txns), "EXTRA_ACCEPT")
            txn = txns[txn_pos]
            require(txn["plan_index"] == plan_pos
                    and txn["reset_lifetime"] == replay.reset_lifetime
                    and txn["accept_serial"] == replay.accept_serial
                    and txn["result_id"] == row["sample_id"]
                    and txn["identity_digest"] == slot_digest(replay.slots)
                    and txn["control_digest"]
                    == control_digest(replay.controls, replay.pedals)
                    and (txn["focus_source"], txn["focus_channel"],
                         txn["focus_note"]) == replay.focus
                    and txn["active_count"]
                    == sum(slot.occupied for slot in replay.slots),
                    f"ACCEPT_CONTEXT:{edge}")
            outstanding.append(txn)
            replay.accept_serial += 1
            txn_pos += 1
            counts["sample_accepts"] += 1

        if row["read_out_valid"]:
            require(pending_reads, f"READ_RESPONSE_WITHOUT_REQUEST:{edge}")
            request_edge, expected_read = pending_reads.pop(0)
            require(edge == request_edge + 1, f"READ_RESPONSE_LATENCY:{edge}")
            require(row["read_context"] == expected_read["context"],
                    f"READ_VALUE:context:{edge}")
            counts["read_responses"] += 1

        if row["read_valid"] and row["read_ready"]:
            require(read_pos < len(reads), "EXTRA_READ_REQUEST")
            expected_read = reads[read_pos]
            require(expected_read["plan_index"] == plan_pos
                    and expected_read["slot"] == row["read_slot"]
                    and expected_read["reset_lifetime"] == replay.reset_lifetime,
                    f"READ_REQUEST:{edge}")
            pending_reads.append((edge, expected_read))
            read_pos += 1
            counts["read_requests"] += 1

        if row["backend_release_done_valid"]:
            mask = row["backend_release_done_mask"]
            for lane in range(32):
                if (mask >> lane) & 1:
                    slot = replay.slots[lane]
                    require(slot.releasing, f"RELEASE_DONE_STATE:{edge}:{lane}")
                    key = lane, slot.generation
                    if key not in seen_release_done:
                        seen_release_done.add(key)
                        counts["release_done"] += 1
            if (op is not None and op["op"] == "await_release_done"
                    and ((mask >> op["slot"]) & 1)):
                slot = replay.slots[op["slot"]]
                pending_release = (op["slot"], slot.generation, edge)

        snapshot_payload = (
            row["control_snapshot_id"], row["control_snapshot_value"],
            row["control_snapshot_occupied"],
            row["control_snapshot_sources"],
            row["control_snapshot_channels"],
            row["control_snapshot_generations"],
        )
        if row["control_snapshot_valid"]:
            if held_control_snapshot is not None:
                require(snapshot_payload == held_control_snapshot,
                        f"CONTROL_SNAPSHOT_HOLD:{edge}")
            if row["control_snapshot_ready"]:
                held_control_snapshot = None
                counts["control_snapshots"] += 1
            else:
                held_control_snapshot = snapshot_payload
        elif held_control_snapshot is not None:
            raise ContractError(f"CONTROL_SNAPSHOT_VALID_DROPPED:{edge}")

        release_payload = (row["control_release_mask"],
                           row["control_release_generations"])
        if row["control_release_valid"]:
            if held_control_release is not None:
                require(release_payload == held_control_release,
                        f"CONTROL_RELEASE_HOLD:{edge}")
            if row["control_release_ready"]:
                held_control_release = None
                counts["control_releases"] += 1
            else:
                held_control_release = release_payload
        elif held_control_release is not None:
            raise ContractError(f"CONTROL_RELEASE_VALID_DROPPED:{edge}")

        payload = (row["result_id"], row["left_pcm"], row["right_pcm"],
                   row["clipped"])
        if row["result_valid"]:
            publish = [txn for txn in outstanding
                       if txn["disposition"] == "PUBLISH"]
            require(publish, f"RESULT_WITHOUT_ACCEPT:{edge}")
            txn = publish[0]
            key = txn["reset_lifetime"], txn["accept_serial"]
            require(payload == (txn["result_id"], txn["left_pcm"],
                                txn["right_pcm"], txn["clipped"]),
                    f"RESULT_PAYLOAD:{edge}")
            if not row["result_ready"]:
                if held_payload is None:
                    held_payload, held_key = payload, key
                require(payload == held_payload and key == held_key,
                        f"HOLD_STABILITY:{edge}")
                hold_counts[key] = hold_counts.get(key, 0) + 1
                counts["hold_cycles"] += 1
            else:
                require(held_payload is None or (payload == held_payload
                                                 and key == held_key),
                        f"HOLD_TO_RESULT:{edge}")
                outstanding.remove(txn)
                held_payload = held_key = None
                counts["results"] += 1
        elif held_payload is not None:
            raise ContractError(f"HOLD_VALID_DROPPED:{edge}")

        if row["cancel"]:
            require(outstanding
                    and all(txn["disposition"] == "CANCEL"
                            for txn in outstanding)
                    and row["aborted"] and row["abort_reason"] == 1,
                    f"CANCEL_FENCE:{edge}")
            outstanding.clear()
            counts["cancels"] += 1
        elif not row["rst_n"]:
            # B uses asynchronous reset.  aborted is explicitly qualified by
            # rst_n, therefore reset itself is not abort_reason=2.
            require(row["aborted"] is False and row["abort_reason"] == 0,
                    f"RESET_SPURIOUS_ABORT:{edge}")
            counts["resets"] += 1
        else:
            require(row["aborted"] is False and row["abort_reason"] == 0,
                    f"SPURIOUS_ABORT:{edge}")

        if completed:
            plan_pos += 1

    require(plan_pos == len(operations), "INCOMPLETE_PLAN")
    require(event_pos == len(events) and txn_pos == len(txns)
            and read_pos == len(reads), "INCOMPLETE_EXPECTED_LEDGER")
    require(not outstanding and not pending_reads and held_payload is None
            and pending_event is None and pending_release is None
            and held_control_snapshot is None
            and held_control_release is None,
            "OPEN_AT_END")
    for txn in txns:
        if txn["disposition"] == "PUBLISH":
            key = txn["reset_lifetime"], txn["accept_serial"]
            require(hold_counts.get(key, 0) >= txn["min_hold_cycles"],
                    f"HOLD_COVERAGE:{key}")
    require(cycles[-1]["plan_index"] == -1 and cycles[-1]["idle"],
            "FINAL_DRAIN_CYCLE")

    end = capture[-1]
    exact_keys(end, CAPTURE_END_FIELDS, "capture_end")
    expected_end = {
        "record": "END", "last_edge": len(cycles) - 1,
        "cycles": len(cycles), **counts,
        "body_sha256": records_sha256(capture[:-1]),
    }
    require(end == expected_end, "CAPTURE_END")
    require(counts["event_accepts"] and counts["sample_accepts"]
            and counts["results"] and counts["read_responses"]
            and counts["cancels"] and counts["resets"]
            and counts["release_done"] and counts["control_snapshots"]
            and counts["control_releases"], "ZERO_COMPARISON")
    return {"status": "PASS", "cycles": len(cycles), **counts}


def _load_actual_context(args: argparse.Namespace, plan_path: Path,
                         expected_path: Path, capture_path: Path) -> None:
    require(args.manifest and args.manifest_sha and args.approval
            and args.approval_sha and args.receipt and args.receipt_sha,
            "ACTUAL_PINS_REQUIRED")
    require(HEX64.fullmatch(args.manifest_sha)
            and HEX64.fullmatch(args.approval_sha)
            and HEX64.fullmatch(args.receipt_sha), "PIN_SHA_TYPE")
    require(file_sha256(args.manifest) == args.manifest_sha,
            "MANIFEST_EXTERNAL_PIN")
    manifest = strict_json(args.manifest.read_text(encoding="utf-8"))
    exact_keys(manifest, (
        "schema", "execution_authorized", "review_key", "fingerprint",
        "b_pass_evidence", "snapshot_root", "plan", "expected",
        "expected_build_receipt", "math", "sources", "source_order",
        "support_files", "tools", "tool_dependencies", "compile_step",
        "run_step", "budget",
    ), "execution_manifest")
    require(manifest["schema"] == "t061-n32c-execution-manifest-v3"
            and manifest["execution_authorized"] is True,
            "EXECUTION_NOT_AUTHORIZED")
    for name in ("review_key", "fingerprint"):
        require(type(manifest[name]) is str and manifest[name],
                f"EXECUTION_ID:{name}")
    require(type(manifest["b_pass_evidence"]) is list
            and manifest["b_pass_evidence"], "B_PASS_EVIDENCE")
    for index, item in enumerate(manifest["b_pass_evidence"]):
        _file_spec(item, f"b_pass_evidence[{index}]")
    snapshot_root = _repo_path(manifest["snapshot_root"], "snapshot_root")
    require("code" in snapshot_root.parts and "output" in snapshot_root.parts,
            "SNAPSHOT_ROOT_SCOPE")
    require(_file_spec(manifest["plan"], "manifest.plan")
            == Path(os.path.abspath(plan_path)),
            "MANIFEST_PLAN_PATH")
    require(_file_spec(manifest["expected"], "manifest.expected")
            == Path(os.path.abspath(expected_path)), "MANIFEST_EXPECTED_PATH")
    expected_build_path = _file_spec(
        manifest["expected_build_receipt"],
        "manifest.expected_build_receipt")
    _file_spec(manifest["math"], "manifest.math")
    require(type(manifest["sources"]) is dict and manifest["sources"],
            "MANIFEST_SOURCE_ROLES")
    for role, spec in manifest["sources"].items():
        path = _file_spec(spec, f"source.{role}")
        require(path == snapshot_root or snapshot_root in path.parents,
                f"SOURCE_OUTSIDE_SNAPSHOT:{role}")
    require(type(manifest["source_order"]) is list
            and manifest["source_order"]
            and set(manifest["source_order"]) == set(manifest["sources"])
            and len(manifest["source_order"]) == len(manifest["sources"]),
            "SOURCE_ORDER")
    require(type(manifest["support_files"]) is dict,
            "SUPPORT_FILE_ROLES")
    for role, spec in manifest["support_files"].items():
        _file_spec(spec, f"support.{role}")
    require(type(manifest["tools"]) is dict
            and set(manifest["tools"]) == {"compile", "runtime"},
            "MANIFEST_TOOL_ROLES")
    for role, spec in manifest["tools"].items():
        _external_file_spec(spec, f"tool.{role}")
    require(type(manifest["tool_dependencies"]) is dict,
            "TOOL_DEPENDENCIES")
    for role, spec in manifest["tool_dependencies"].items():
        _external_file_spec(spec, f"tool_dependency.{role}")
    for name in ("compile_step", "run_step"):
        step = manifest[name]
        exact_keys(step, ("argv", "cwd", "timeout_seconds"), name)
        require(type(step["argv"]) is list and step["argv"]
                and all(type(value) is str and value for value in step["argv"]),
                f"ARGV:{name}")
        require(type(step["cwd"]) is str
                and Path(step["cwd"]).is_absolute(), f"CWD:{name}")
        integer(step["timeout_seconds"], 1, 300, f"TIMEOUT:{name}")
    exact_keys(manifest["budget"],
               ("per_tool_seconds_max", "runner_total_seconds_max",
                "max_attempts"), "manifest.budget")
    require(manifest["budget"] == {
        "per_tool_seconds_max": 300,
        "runner_total_seconds_max": 900,
        "max_attempts": 1,
    }, "MANIFEST_BUDGET")

    expected_build = strict_json(
        expected_build_path.read_text(encoding="utf-8"))
    exact_keys(expected_build, (
        "schema", "status", "review_key", "fingerprint", "plan", "math",
        "roms", "generator", "tool", "argv", "cwd", "output",
    ), "expected_build_receipt")
    require(expected_build["schema"]
            == "t061-n32c-expected-build-receipt-v1"
            and expected_build["status"] == "PASS_INDEPENDENT_RECOMPUTE"
            and expected_build["review_key"] == manifest["review_key"]
            and expected_build["fingerprint"] == manifest["fingerprint"]
            and expected_build["plan"] == manifest["plan"]
            and expected_build["math"] == manifest["math"]
            and expected_build["output"] == manifest["expected"],
            "EXPECTED_BUILD_BINDING")
    require(type(expected_build["roms"]) is list
            and expected_build["roms"], "EXPECTED_BUILD_ROMS")
    for index, spec in enumerate(expected_build["roms"]):
        _file_spec(spec, f"expected_build.rom[{index}]")
    _file_spec(expected_build["generator"], "expected_build.generator")
    _external_file_spec(expected_build["tool"], "expected_build.tool")
    require(type(expected_build["argv"]) is list
            and expected_build["argv"]
            and all(type(value) is str and value
                    for value in expected_build["argv"])
            and type(expected_build["cwd"]) is str
            and Path(expected_build["cwd"]).is_absolute(),
            "EXPECTED_BUILD_COMMAND")

    require(file_sha256(args.approval) == args.approval_sha,
            "APPROVAL_EXTERNAL_PIN")
    approval = strict_json(args.approval.read_text(encoding="utf-8"))
    exact_keys(approval, (
        "schema", "approved", "manifest_sha256", "review_key",
        "fingerprint", "b_pass_evidence", "reviewers", "budget",
    ), "approval")
    require(approval["schema"] == "t061-n32c-dual-approval-v1"
            and approval["approved"] is True
            and approval["manifest_sha256"] == args.manifest_sha
            and approval["review_key"] == manifest["review_key"]
            and approval["fingerprint"] == manifest["fingerprint"]
            and approval["b_pass_evidence"] == manifest["b_pass_evidence"]
            and approval["budget"] == manifest["budget"],
            "APPROVAL_BINDING")
    reviewers = approval["reviewers"]
    require(type(reviewers) is list and len(reviewers) == 2
            and all(type(item) is dict
                    and set(item) == {"role", "identity", "decision"}
                    and type(item["identity"]) is str and item["identity"]
                    and item["decision"] == "APPROVE"
                    for item in reviewers)
            and {item["role"] for item in reviewers}
            == {"reviewer", "pre_reviewer"}, "APPROVAL_REVIEWERS")

    require(file_sha256(args.receipt) == args.receipt_sha,
            "RECEIPT_EXTERNAL_PIN")
    receipt = strict_json(args.receipt.read_text(encoding="utf-8"))
    exact_keys(receipt, (
        "schema", "manifest_sha256", "approval_sha256", "review_key",
        "fingerprint", "machine", "status", "attempts", "steps", "plan",
        "expected", "expected_build_receipt", "capture", "sources_before",
        "sources_after", "tools_before", "tools_after",
    ), "run_receipt")
    require(receipt["schema"] == "t061-n32c-run-receipt-v3"
            and receipt["manifest_sha256"] == args.manifest_sha
            and receipt["approval_sha256"] == args.approval_sha
            and receipt["review_key"] == manifest["review_key"]
            and receipt["fingerprint"] == manifest["fingerprint"]
            and receipt["status"] == "PASS"
            and receipt["attempts"] == 1, "RUN_NOT_SUCCESSFUL")
    machine = receipt["machine"]
    exact_keys(machine, ("hostname", "os", "arch"), "receipt.machine")
    require(all(type(value) is str and value for value in machine.values()),
            "RECEIPT_MACHINE")
    require(type(receipt["steps"]) is list and len(receipt["steps"]) == 2,
            "RECEIPT_STEPS")
    require([step.get("name") for step in receipt["steps"]]
            == ["compile", "run"], "RECEIPT_STEP_ORDER")
    total_elapsed = 0
    for index, step in enumerate(receipt["steps"]):
        exact_keys(step, (
            "name", "argv", "cwd", "executable", "started_utc",
            "ended_utc", "elapsed_seconds", "exit_code", "timeout",
            "stdout", "stderr",
        ), f"receipt.step[{index}]")
        require(step["name"] in {"compile", "run"}
                and type(step["argv"]) is list and step["argv"]
                and type(step["cwd"]) is str and Path(step["cwd"]).is_absolute()
                and type(step["executable"]) is str
                and Path(step["executable"]).is_absolute()
                and type(step["started_utc"]) is str and step["started_utc"]
                and type(step["ended_utc"]) is str and step["ended_utc"],
                f"RECEIPT_STEP_FIELDS:{index}")
        integer(step["elapsed_seconds"], 0, 300,
                f"receipt.step[{index}].elapsed_seconds")
        total_elapsed += step["elapsed_seconds"]
        require(step["exit_code"] == 0 and step["timeout"] is False,
                f"RECEIPT_STEP_FAILURE:{index}")
        contract = manifest[f"{step['name']}_step"]
        tool_role = "compile" if step["name"] == "compile" else "runtime"
        require(step["argv"] == contract["argv"]
                and step["cwd"] == contract["cwd"]
                and step["elapsed_seconds"] <= contract["timeout_seconds"]
                and step["executable"]
                == manifest["tools"][tool_role]["path"],
                f"RECEIPT_STEP_BINDING:{index}")
        _file_spec(step["stdout"], f"receipt.step[{index}].stdout")
        _file_spec(step["stderr"], f"receipt.step[{index}].stderr")
    require(_file_spec(receipt["plan"], "receipt.plan")
            == Path(os.path.abspath(plan_path))
            and _file_spec(receipt["expected"], "receipt.expected")
            == Path(os.path.abspath(expected_path))
            and _file_spec(receipt["capture"], "receipt.capture")
            == Path(os.path.abspath(capture_path)), "RECEIPT_ARTIFACT_PATH")
    require(receipt["expected_build_receipt"]
            == manifest["expected_build_receipt"],
            "EXPECTED_BUILD_RECEIPT_BINDING")
    require(total_elapsed <= manifest["budget"]["runner_total_seconds_max"],
            "RECEIPT_TOTAL_BUDGET")
    require(receipt["sources_before"] == manifest["sources"]
            and receipt["sources_after"] == manifest["sources"]
            and receipt["tools_before"] == manifest["tools"]
            and receipt["tools_after"] == manifest["tools"],
            "RUN_BEFORE_AFTER_IDENTITY")

    expected_meta = read_jsonl(expected_path)[0]
    capture_meta = read_jsonl(capture_path)[0]
    for name in ("review_key", "fingerprint"):
        require(expected_meta[f"b_{name}"] == manifest[name]
                and capture_meta[f"b_{name}"] == manifest[name],
                f"B_IDENTITY_MANIFEST:{name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("fixture", "actual"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--approval-sha")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--receipt-sha")
    args = parser.parse_args()
    try:
        if args.mode == "actual":
            _load_actual_context(args, args.plan, args.expected, args.capture)
        result = check_records(
            read_jsonl(args.plan), read_jsonl(args.expected),
            read_jsonl(args.capture),
            allow_selftest_fixture=args.mode == "fixture",
        )
        result["rtl_verified"] = args.mode == "actual"
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ContractError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "FAIL", "diagnostic": str(exc),
                          "rtl_verified": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
