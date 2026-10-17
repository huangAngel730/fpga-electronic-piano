"""Synthetic-only fixtures for the R06 calendar software self-test."""

from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any

from event_calendar import CANONICAL_FIELDS


def empty_row(cycle: int, epoch: int, rst_n: int) -> dict[str, Any]:
    row = {field: 0 for field in CANONICAL_FIELDS}
    row["cycle"] = cycle
    row["epoch"] = epoch
    row["rst_n"] = rst_n
    row["cancel_reason"] = None
    row["config_payload"] = None
    return row


def fixture_binding() -> dict[str, Any]:
    return {
        "schema": "M3_R06_EVENT_CALENDAR_BINDING_V1",
        "mode": "SYNTHETIC_SELFTEST_ONLY",
        "trace_authority": "SYNTHETIC_FIXTURE",
        "source_authority_verified": True,
        "m1_semantics_authoritative": True,
        "m2_capture_contract_authoritative": True,
        "same_edge_priority": ["CANCEL", "RESULT", "COMMIT", "REQUEST"],
        "max_outstanding_per_epoch": 1,
        "cover_all_plan_events": True,
        "warning": "Fixture semantics are not M1/M2 production authority.",
    }


def build_fixture(plan: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    operations: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in plan["reset_plan"]:
        operations[int(item["cycle"])].append({"kind": "reset", "level": int(item["level"])})
    ready_release = max(int(item["cycle"]) for item in plan["ready_plan"] if item["level"])
    for event in plan["events"]:
        seq = int(event["event_seq"])
        valid_cycle = int(event["arrival_window"]["min_cycle"])
        data = int(event["expected_event_hex"], 16)
        if event["scenario"] == "backpressure":
            operations[valid_cycle].append({"kind": "event", "seq": seq,
                                            "data": data, "ready": 0})
            accept_cycle = ready_release
        else:
            accept_cycle = valid_cycle
        operations[accept_cycle].append({"kind": "event", "seq": seq,
                                         "data": data, "ready": 1})
        operations[accept_cycle + 3 + (seq % 5)].append(
            {"kind": "apply", "event": event}
        )

    epoch_frames = {
        0: [50_000, 150_000, 250_000, 350_000, 450_000,
            550_000, 650_000, 750_000, 850_000, 950_000],
        1: [1_005_000, 1_065_000, 1_120_000],
    }
    for epoch, cycles in epoch_frames.items():
        for req_id, cycle in enumerate(cycles, 1):
            operations[cycle].append({"kind": "frame", "req_id": req_id})
            operations[cycle + 5].append({"kind": "result", "req_id": req_id})
            if epoch == 0 and req_id == 4:
                operations[cycle + 5].append({"kind": "cancel", "reason": "FIXTURE_CANCEL"})
            else:
                operations[cycle + 6].append({"kind": "commit", "req_id": req_id})
    finish = {"epoch": 1, "cycle": int(plan["total_cycles"])}
    operations[finish["cycle"]].append({"kind": "finish"})

    rows = []
    slots: list[dict[str, int] | None] = [None, None, None, None]
    releasing: set[int] = set()
    generation = [0, 0, 0, 0]
    rst_n = 0
    epoch = 0
    reset_assertions = 0

    while operations:
        cycle = min(operations)
        actions = operations.pop(cycle)
        row = empty_row(cycle, epoch, rst_n)
        for action in sorted(actions, key=lambda item: 0 if item["kind"] == "reset" else 1):
            kind = action["kind"]
            if kind == "reset":
                rst_n = action["level"]
                if not rst_n:
                    if reset_assertions:
                        epoch += 1
                    reset_assertions += 1
                    slots = [None, None, None, None]
                    releasing.clear()
                row["epoch"] = epoch
                row["rst_n"] = rst_n
            elif kind == "event":
                row["event_valid"] = 1
                row["event_ready"] = action["ready"]
                row["event_data"] = action["data"]
            elif kind == "apply":
                event = action["event"]
                seq = int(event["event_seq"])
                note = int(event["note"])
                row["apply_valid"] = 1
                row["apply_event_seq"] = seq
                row["apply_data"] = int(event["expected_event_hex"], 16)
                if event["normalized_kind"] == "note_on":
                    lane = next((index for index, value in enumerate(slots)
                                 if value is not None and value["note"] == note), None)
                    if lane is None:
                        lane = next((index for index, value in enumerate(slots)
                                     if value is None), 0)
                    generation[lane] += 1
                    slots[lane] = {"source": 0, "channel": int(event["channel"]),
                                   "note": note, "generation": generation[lane]}
                    releasing.discard(lane)
                    row["note_on_mask"] = 1 << lane
                else:
                    lane = next((index for index, value in enumerate(slots)
                                 if value is not None and value["note"] == note), None)
                    if lane is not None:
                        releasing.add(lane)
                        row["note_off_mask"] = 1 << lane
                        operations[cycle + 2].append({"kind": "retire", "lane": lane})
            elif kind == "retire":
                lane = action["lane"]
                if slots[lane] is not None:
                    slots[lane] = None
                    releasing.discard(lane)
                    row["retire_mask"] |= 1 << lane
            elif kind == "frame":
                req_id = action["req_id"]
                row.update({"frame_tick": 1, "req_valid": 1, "req_ready": 1,
                            "req_id": req_id, "advance_mask": 0xF,
                            "advance_frame_req_id": req_id})
            elif kind == "result":
                row.update({"result_valid": 1, "result_ready": 1,
                            "result_id": action["req_id"]})
            elif kind == "commit":
                row.update({"commit": 1, "commit_id": action["req_id"]})
            elif kind == "cancel":
                row["cancel"] = 1
                row["cancel_reason"] = action["reason"]
            elif kind == "finish":
                row["finish"] = 1

        occupied = sum(1 << lane for lane, value in enumerate(slots) if value is not None)
        row["occupied_mask"] = occupied
        row["releasing_mask"] = sum(1 << lane for lane in releasing)
        for lane, value in enumerate(slots):
            if value is None:
                continue
            row["slot_sources"] |= value["source"] << (lane * 4)
            row["slot_channels"] |= value["channel"] << (lane * 4)
            row["slot_notes"] |= value["note"] << (lane * 8)
            row["slot_generations"] |= value["generation"] << (lane * 32)
        rows.append(row)

    frame_plan = {
        "schema": "M3_R06_INDEPENDENT_FRAME_PLAN_V1",
        "authority": "SYNTHETIC_INDEPENDENT_PLAN",
        "independent_of_trace": True,
        "source": "Frozen fixture schedule; never derived from observed frame rows.",
        "epochs": [{"epoch": key, "frame_cycles": value}
                   for key, value in sorted(epoch_frames.items())],
        "finish": finish,
    }
    return rows, frame_plan


def clone_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return copy.deepcopy(rows)
