"""Generate the deterministic T061 N32-C input plan and independent ledger.

The generated ledger is deliberately NOT executable for RTL acceptance until
the exact B snapshot and frozen independent PCM model are bound.  Routing,
identity, control, cancellation, and reset expectations are computed solely
from the generated inputs.
"""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
from typing import Any

from n32c_common import (
    CONTROL_EVENT_SPECS,
    ContractError,
    Slot,
    control_digest,
    is_reparse_point,
    pack_event,
    public_slots,
    records_sha256,
    slot_digest,
    write_jsonl,
)


class StressOracle:
    """Input-driven symbolic oracle for the C stress contract."""

    def __init__(self) -> None:
        self.slots = [Slot(age=index) for index in range(32)]
        self.pedals: set[tuple[int, int]] = set()
        self.controls: dict[str, int] = {}
        self.reset_lifetime = 0
        self.event_serial = 0
        self.accept_serial = 0
        self.focus = (0, 0, 0)
        self.events: list[dict[str, Any]] = []
        self.txns: list[dict[str, Any]] = []
        self.reads: list[dict[str, Any]] = []
        self.timeline: list[dict[str, Any]] = []

    def _choose(self, identity: tuple[int, int, int]) -> int:
        matches = [i for i, slot in enumerate(self.slots)
                   if (slot.occupied or slot.releasing)
                   and slot.identity() == identity]
        if matches:
            return min(matches)
        idle = [i for i, slot in enumerate(self.slots)
                if not slot.occupied and not slot.releasing]
        if idle:
            return min(idle)
        return min(range(32), key=lambda i: (self.slots[i].age, i))

    def _event(self, index: int, *, event_type: int, source: int,
               channel: int, note: int = 0, velocity: int = 0,
               expression: int = 0, control_id: int = 0,
               control_value: int = 0) -> None:
        word = pack_event(
            event_type=event_type,
            source=source,
            channel=channel,
            note=note,
            velocity=velocity,
            expression=expression,
            control_id=control_id,
            control_value=control_value,
        )
        record = {
            "record": "EVENT",
            "event_serial": self.event_serial,
            "plan_index": index,
            "reset_lifetime": self.reset_lifetime,
            "event_type": event_type,
            "source": source,
            "channel": channel,
            "note": note,
            "velocity": velocity,
            "expression": expression,
            "control_id": control_id,
            "control_value": control_value,
            "event_word": word,
        }
        self.events.append(record)
        self.timeline.append(record)
        self.event_serial += 1

    def apply(self, index: int, op: dict[str, Any]) -> None:
        name = op["op"]
        if name == "note_on":
            identity = op["source"], op["channel"], op["note"]
            self._event(index, event_type=0, source=identity[0],
                        channel=identity[1], note=identity[2],
                        velocity=op["velocity"], expression=op["expression"])
            target = self._choose(identity)
            old_age = self.slots[target].age
            for lane, slot in enumerate(self.slots):
                if lane != target and slot.age > old_age:
                    slot.age -= 1
            generation = (self.slots[target].generation + 1) & 0xFFFFFFFF
            self.slots[target] = Slot(
                occupied=True,
                releasing=False,
                deferred=False,
                source=identity[0],
                channel=identity[1],
                note=identity[2],
                velocity=op["velocity"],
                generation=generation,
                age=31,
            )
            self.focus = identity
        elif name == "note_off":
            identity = op["source"], op["channel"], op["note"]
            self._event(index, event_type=1, source=identity[0],
                        channel=identity[1], note=identity[2])
            for slot in self.slots:
                if slot.occupied and slot.identity() == identity:
                    if (identity[0], identity[1]) in self.pedals:
                        slot.deferred = True
                    else:
                        slot.releasing = True
                    self.focus = identity
        elif name == "cc64":
            source, channel, down = op["source"], op["channel"], op["down"]
            value = 4095 if down else 0
            self._event(index, event_type=4, source=source, channel=channel,
                        control_id=6, control_value=value)
            identity = source, channel
            if down:
                self.pedals.add(identity)
            else:
                self.pedals.discard(identity)
                for slot in self.slots:
                    if (slot.occupied and slot.deferred
                            and (slot.source, slot.channel) == identity):
                        slot.deferred = False
                        slot.releasing = True
        elif name == "await_release_done":
            lane = op["slot"]
            slot = self.slots[lane]
            if slot.releasing:
                self.slots[lane] = Slot(age=slot.age,
                                        generation=slot.generation)
        elif name == "control_event":
            event_type, control_id = CONTROL_EVENT_SPECS[op["control"]]
            self._event(index, event_type=event_type,
                        source=op["source"], channel=op["channel"],
                        control_id=control_id, control_value=op["value"])
            key = f"{op['source']}:{op['channel']}:{op['control']}"
            self.controls[key] = op["value"]
        elif name == "sample":
            disposition = op["disposition"]
            record = {
                "record": "TXN",
                "reset_lifetime": self.reset_lifetime,
                "accept_serial": self.accept_serial,
                "plan_index": index,
                "result_id": op["result_id"],
                "disposition": disposition,
                "identity_digest": slot_digest(self.slots),
                "control_digest": control_digest(self.controls, self.pedals),
                "focus_source": self.focus[0],
                "focus_channel": self.focus[1],
                "focus_note": self.focus[2],
                "active_count": sum(slot.occupied for slot in self.slots),
                "min_hold_cycles": op.get("min_hold_cycles", 0),
                "left_pcm": None,
                "right_pcm": None,
                "clipped": None,
                "pcm_provenance": "WAIT_B_FROZEN_MATH",
            }
            self.txns.append(record)
            self.timeline.append(record)
            self.accept_serial += 1
        elif name == "reset":
            self.slots = [Slot(age=lane) for lane in range(32)]
            self.pedals.clear()
            self.controls = {}
            self.focus = (0, 0, 0)
            self.reset_lifetime += 1
        elif name == "read":
            lane = op["slot"]
            slot = self.slots[lane]
            record = {
                "record": "READ",
                "read_serial": len(self.reads),
                "plan_index": index,
                "reset_lifetime": self.reset_lifetime,
                "slot": lane,
                "occupied": slot.occupied,
                "releasing": slot.releasing,
                "source": slot.source,
                "channel": slot.channel,
                "note": slot.note,
                "generation": slot.generation,
                "context": None,
                "context_provenance": "WAIT_B_FROZEN_MATH",
            }
            self.reads.append(record)
            self.timeline.append(record)
        elif name in ("cancel", "set_result_ready", "tick", "wait_idle"):
            return
        else:
            raise ContractError(f"UNKNOWN_OP:{name}")


def build_operations() -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []

    def add(case: str, op: str, **fields: Any) -> None:
        operations.append({"case_id": case, "op": op, **fields})

    def read_all(case: str) -> None:
        for slot in range(32):
            add(case, "read", slot=slot)

    # C00: every actual run starts from a captured asynchronous reset
    # assertion.  No pre-reset transaction is silently inherited.
    add("C00_INITIAL_RESET", "reset")
    add("C00_INITIAL_RESET", "wait_idle")

    # C01: occupy all 32 slots, sample, then force the 33rd-note LRU steal.
    for lane in range(32):
        add("C01_FILL32_STEAL33", "note_on", source=lane // 16,
            channel=lane % 16, note=36 + lane, velocity=700 + lane,
            expression=900)
    add("C01_FILL32_STEAL33", "sample", result_id=0x1000,
        disposition="PUBLISH")
    read_all("C01_FILL32_STEAL33")
    add("C01_FILL32_STEAL33", "note_on", source=3, channel=15,
        note=100, velocity=1000, expression=1023)
    add("C01_FILL32_STEAL33", "sample", result_id=0x1001,
        disposition="PUBLISH")
    read_all("C01_FILL32_STEAL33")

    # C02/C03: fast retrigger, release retrigger, and same-note isolation.
    add("C02_RETRIGGER", "note_on", source=3, channel=15, note=100,
        velocity=801, expression=777)
    read_all("C02_RETRIGGER")
    add("C02_RETRIGGER", "note_off", source=3, channel=15, note=100)
    read_all("C02_RETRIGGER")
    add("C02_RETRIGGER", "note_on", source=3, channel=15, note=100,
        velocity=802, expression=778)
    read_all("C02_RETRIGGER")
    for source, channel in ((4, 0), (4, 1), (5, 0)):
        add("C03_IDENTITY_ISOLATION", "note_on", source=source,
            channel=channel, note=64, velocity=600 + channel,
            expression=850)
    add("C03_IDENTITY_ISOLATION", "note_off", source=4, channel=1,
        note=64)
    add("C03_IDENTITY_ISOLATION", "sample", result_id=0x1002,
        disposition="PUBLISH")

    # C04: sustain defers four releases, then releases and recycles them.
    add("C04_CC64_MULTI_RECYCLE", "wait_idle")
    add("C04_CC64_MULTI_RECYCLE", "reset")
    add("C04_CC64_MULTI_RECYCLE", "cc64", source=6, channel=2, down=True)
    for note in (70, 71, 72, 73):
        add("C04_CC64_MULTI_RECYCLE", "note_on", source=6, channel=2,
            note=note, velocity=720, expression=900)
        add("C04_CC64_MULTI_RECYCLE", "note_off", source=6, channel=2,
            note=note)
    add("C04_CC64_MULTI_RECYCLE", "sample", result_id=0x1003,
        disposition="PUBLISH")
    add("C04_CC64_MULTI_RECYCLE", "cc64", source=6, channel=2, down=False)
    add("C04_CC64_MULTI_RECYCLE", "sample", result_id=0x1004,
        disposition="PUBLISH")
    read_all("C04_CC64_MULTI_RECYCLE")
    # Completion is a real public handshake.  Reclaim four releasing lanes,
    # prove they read idle, then allocate four new identities into free lanes.
    for slot in range(4):
        add("C04_CC64_MULTI_RECYCLE", "await_release_done", slot=slot)
    read_all("C04_CC64_MULTI_RECYCLE")
    for offset, note in enumerate((74, 75, 76, 77)):
        add("C04_CC64_MULTI_RECYCLE", "note_on", source=6, channel=2,
            note=note, velocity=760 + offset, expression=901)
    read_all("C04_CC64_MULTI_RECYCLE")
    add("C04_CC64_MULTI_RECYCLE", "sample", result_id=0x1005,
        disposition="PUBLISH")

    # C05/C06: consecutive controls plus explicit result/read backpressure.
    for control, value in (("pitch_bend", 3072), ("modulation", 511),
                           ("pitch_range", 12), ("pitch_bend", 1024)):
        add("C05_CONTROL_SNAPSHOTS", "control_event", source=6, channel=2,
            control=control, value=value)
        add("C05_CONTROL_SNAPSHOTS", "sample", result_id=0x1100 + value,
            disposition="PUBLISH")
    add("C05_CONTROL_SNAPSHOTS", "tick")
    add("C06_READ_HOLD_RECOVERY", "set_result_ready", value=0)
    add("C06_READ_HOLD_RECOVERY", "sample", result_id=0x1200,
        disposition="PUBLISH", min_hold_cycles=5)
    for _ in range(5):
        add("C06_READ_HOLD_RECOVERY", "tick")
    for slot in (0, 7, 15, 23, 31):
        add("C06_READ_HOLD_RECOVERY", "read", slot=slot)
    add("C06_READ_HOLD_RECOVERY", "set_result_ready", value=1)

    # C07: transactions accepted before cancel/reset must never publish.
    add("C07_CANCEL_RESET", "wait_idle")
    add("C07_CANCEL_RESET", "sample", result_id=0x1300,
        disposition="CANCEL")
    add("C07_CANCEL_RESET", "cancel")
    add("C07_CANCEL_RESET", "wait_idle")
    add("C07_CANCEL_RESET", "sample", result_id=0x1301,
        disposition="CANCEL")
    add("C07_CANCEL_RESET", "reset")
    add("C07_CANCEL_RESET", "note_on", source=7, channel=7, note=84,
        velocity=900, expression=900)
    add("C07_CANCEL_RESET", "sample", result_id=0x1302,
        disposition="PUBLISH")

    # C08: bounded high-density burst with identity and control churn.
    for index in range(96):
        source = (index * 5) & 15
        channel = (index * 7) & 15
        note = 40 + (index % 48)
        if index % 9 == 0:
            add("C08_HIGH_DENSITY", "cc64", source=source,
                channel=channel, down=(index // 9) % 2 == 0)
        add("C08_HIGH_DENSITY", "note_on", source=source, channel=channel,
            note=note, velocity=512 + (index * 11) % 511,
            expression=600 + (index * 13) % 423)
        if index % 3 == 0:
            add("C08_HIGH_DENSITY", "note_off", source=source,
                channel=channel, note=note)
        if index % 8 == 7:
            add("C08_HIGH_DENSITY", "sample", result_id=0x2000 + index,
                disposition="PUBLISH")
    return operations


def generate() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    operations = build_operations()
    plan_body = [
        {"record": "PLAN", "index": index, "cycle_hint": index * 8,
         **operation}
        for index, operation in enumerate(operations)
    ]
    plan_meta = {
        "record": "META",
        "schema": "t061-n32c-plan-v3",
        "n": 32,
        "response": 1,
        "clock_hz": 40_000_000,
        "seed": 0x4E333243,
        "b_dependency_status": "WAIT_B_EXACT_PASS",
        "original_prepared_path_status": "MISSING",
        "allocator_readonly_alias":
            "code/rtl/common/polyphony_scaling_candidate/b2c_voice_allocator.sv",
        "allocator_sha256":
            "9fec9f838a9ef333d01d1b79ecf77d137e41bc0c5e78a40d2820c37739506061",
    }
    plan_without_end = [plan_meta, *plan_body]
    plan_end = {
        "record": "END",
        "operations": len(plan_body),
        "body_sha256": records_sha256(plan_without_end),
    }
    plan = [*plan_without_end, plan_end]
    plan_sha = records_sha256(plan)

    oracle = StressOracle()
    for index, operation in enumerate(operations):
        oracle.apply(index, operation)
    expected_meta = {
        "record": "META",
        "schema": "t061-n32c-expected-v3",
        "plan_sha256": plan_sha,
        "audio_math_status": "WAIT_B_FROZEN_MATH",
        "executable_for_rtl_acceptance": False,
        "b_review_key": "WAIT_B_EXACT_PASS",
        "b_fingerprint": "WAIT_B_EXACT_PASS",
    }
    # Preserve plan-time ordering.  The capture checker independently replays
    # the plan against a single edge timeline and must not sort by record type.
    expected_without_end = [expected_meta, *oracle.timeline]
    expected_end = {
        "record": "END",
        "events": len(oracle.events),
        "transactions": len(oracle.txns),
        "publish_transactions": sum(
            txn["disposition"] == "PUBLISH" for txn in oracle.txns),
        "cancel_transactions": sum(
            txn["disposition"] == "CANCEL" for txn in oracle.txns),
        "reads": len(oracle.reads),
        "body_sha256": records_sha256(expected_without_end),
    }
    return plan, [*expected_without_end, expected_end]


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT_ROOT = ROOT / "code" / "output"


def _is_reparse(path: Path) -> bool:
    return is_reparse_point(path)


def safe_output_path(requested: Path, source_vectors: bool) -> Path:
    target = Path(os.path.abspath(requested))
    source_target = Path(os.path.abspath(HERE / "vectors"))
    if source_vectors:
        if target != source_target:
            raise ContractError("SOURCE_VECTOR_PATH")
        return target
    root = Path(os.path.abspath(OUTPUT_ROOT))
    if not root.exists():
        raise ContractError("OUTPUT_ROOT_MISSING")
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ContractError("OUTPUT_OUTSIDE_CODE_OUTPUT") from exc
    if target == root or target.exists():
        raise ContractError("OUTPUT_MUST_BE_NEW_SUBDIRECTORY")
    cursor = target.parent
    while cursor != root:
        if cursor.exists() and _is_reparse(cursor):
            raise ContractError("OUTPUT_REPARSE_COMPONENT")
        cursor = cursor.parent
    if _is_reparse(root):
        raise ContractError("OUTPUT_ROOT_REPARSE")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-vectors", action="store_true")
    args = parser.parse_args()
    output = safe_output_path(args.output, args.source_vectors)
    # Source vectors are a versioned snapshot inside this authorized C
    # directory, so an explicit --source-vectors refresh may replace only
    # those three deterministic files.  Ordinary evidence outputs remain
    # create-once under code/output.
    output.mkdir(parents=True, exist_ok=args.source_vectors)
    plan, expected = generate()
    write_jsonl(output / "plan.jsonl", plan)
    write_jsonl(output / "expected_skeleton.jsonl", expected)
    receipt = {
        "status": "PASS_SOFTWARE_PLAN_ONLY",
        "plan_records": len(plan),
        "expected_records": len(expected),
        "plan_sha256": records_sha256(plan),
        "expected_sha256": records_sha256(expected),
        "rtl_status": "NOT_RUN_WAIT_B",
        "gowin_status": "NOT_RUN_PROHIBITED",
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
