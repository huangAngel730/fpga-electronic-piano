"""Independent synthetic transport fixture for the R06 checker only."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from tx_clock_reset_checker import CANONICAL_FIELDS


MODULUS = 1 << 32
BCLK_NCO_STEP = 659_706_977
CLOCK_HZ = 40_000_000
FINAL_CYCLE = 7_600
SEGMENTS = (
    {"epoch": 0, "reset_start": 1, "active_start": 7, "end": 3_799},
    {"epoch": 1, "reset_start": 3_800, "active_start": 3_806, "end": 7_589},
    {"epoch": 2, "reset_start": 7_590, "active_start": FINAL_CYCLE + 1,
     "end": FINAL_CYCLE},
)


def frame_cycles(segment: dict[str, int]) -> list[int]:
    """Closed-form plan, independent of the emitted trace rows."""
    result = []
    index = 1
    while True:
        cycle = segment["active_start"] - 1 + (
            index * 128 * MODULUS + BCLK_NCO_STEP - 1
        ) // BCLK_NCO_STEP
        if cycle > segment["end"]:
            return result
        result.append(cycle)
        index += 1


def oracle_values(epoch: int, req_id: int) -> tuple[int, int, int]:
    table = {
        (0, 0): (127, 128, 0),
        (0, 1): (-129, 8_388_607, 1),
        (1, 0): (1_234_567, -2_345_678, 0),
        # Deliberately identical PCM to ID0: identity must not use equality.
        (1, 1): (1_234_567, -2_345_678, 0),
        (1, 2): (-8_388_608, 8_388_607, 1),
    }
    return table.get((epoch, req_id), (65_535, -65_535, 0))


def build_documents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any],
                               list[dict[str, Any]]]:
    plans = {segment["epoch"]: frame_cycles(segment) for segment in SEGMENTS}
    transactions = []
    operations: dict[int, list[tuple[str, tuple[Any, ...]]]] = defaultdict(list)

    for segment in SEGMENTS[:2]:
        epoch = segment["epoch"]
        frames = plans[epoch]
        for req_id, frame in enumerate(frames[:-1]):
            request_cycle = frame + 1
            if epoch == 0 and req_id == 2:
                cancel_cycle = request_cycle + 20
                result_cycle = commit_cycle = None
                operations[request_cycle].append(("REQUEST", (epoch, req_id)))
                operations[cancel_cycle].append(("CANCEL", (epoch, req_id)))
            else:
                result_cycle = request_cycle + 30
                commit_cycle = request_cycle + 31
                cancel_cycle = None
                operations[request_cycle].append(("REQUEST", (epoch, req_id)))
                operations[result_cycle].append(("RESULT", (epoch, req_id)))
                operations[commit_cycle].append(("COMMIT", (epoch, req_id)))
            transactions.append({
                "epoch": epoch, "req_id": req_id,
                "request_cycle": request_cycle, "result_cycle": result_cycle,
                "commit_cycle": commit_cycle, "cancel_cycle": cancel_cycle,
            })
        if epoch == 0:
            req_id = len(frames) - 1
            request_cycle = frames[-1] + 1
            operations[request_cycle].append(("REQUEST", (epoch, req_id)))
            operations[SEGMENTS[1]["reset_start"]].append(
                ("RESET_CANCEL", (epoch, req_id))
            )
            transactions.append({
                "epoch": epoch, "req_id": req_id,
                "request_cycle": request_cycle, "result_cycle": None,
                "commit_cycle": None,
                "cancel_cycle": SEGMENTS[1]["reset_start"],
            })

    oracle = {
        "schema": "M3_R06_PCM24_ORACLE_V1",
        "authority": "SYNTHETIC_INDEPENDENT_ORACLE",
        "records": [
            {"epoch": item["epoch"], "req_id": item["req_id"],
             "left": oracle_values(item["epoch"], item["req_id"])[0],
             "right": oracle_values(item["epoch"], item["req_id"])[1],
             "clip": oracle_values(item["epoch"], item["req_id"])[2]}
            for item in transactions if item["commit_cycle"] is not None
        ],
    }

    tx_expectations = []
    for segment in SEGMENTS[:2]:
        epoch = segment["epoch"]
        held_id = None
        for cycle in plans[epoch]:
            newly_committed = [
                item for item in transactions
                if item["epoch"] == epoch and item["commit_cycle"] is not None
                and item["commit_cycle"] < cycle
                and (held_id is None or item["req_id"] != held_id)
            ]
            not_adopted = [item for item in newly_committed
                           if not any(tx["epoch"] == epoch and tx["req_id"] == item["req_id"]
                                      and tx["kind"] == "NEW" for tx in tx_expectations)]
            if not_adopted:
                held_id = max(not_adopted, key=lambda item: item["commit_cycle"])["req_id"]
                kind = "NEW"
            elif held_id is not None:
                kind = "HOLD"
            else:
                kind = "STARTUP"
            tx_expectations.append({"epoch": epoch, "cycle": cycle,
                                    "kind": kind,
                                    "req_id": None if kind == "STARTUP" else held_id})

    calendar = {
        "schema": "M3_R06_TX_TRANSACTION_CALENDAR_V1",
        "authority": "SYNTHETIC_INDEPENDENT_CALENDAR",
        "independent_of_trace": True,
        "tx_selection_plan_authoritative": True,
        "transactions": transactions,
        "tx_expectations": tx_expectations,
    }
    frame_plan = {
        "schema": "M3_R06_TX_FRAME_PLAN_V1",
        "authority": "SYNTHETIC_INDEPENDENT_PLAN",
        "independent_of_trace": True,
        "epochs": [{"epoch": epoch, "cycles": cycles}
                   for epoch, cycles in sorted(plans.items())],
        "finish": {"epoch": 2, "cycle": FINAL_CYCLE},
    }

    operations_by_cycle = operations
    tx_by_cycle = {(item["epoch"], item["cycle"]): item
                   for item in tx_expectations}
    rows = []
    segment_index = 0
    phase = bclk = ws = din = slot = shift = 0
    latched = (0, 0)
    pending: tuple[int, int, int, int] | None = None
    held: tuple[int, int, int, int] | None = None
    frame_number = 0

    for cycle in range(1, FINAL_CYCLE + 1):
        while cycle > SEGMENTS[segment_index]["end"]:
            segment_index += 1
            phase = bclk = ws = din = slot = shift = 0
            latched = (0, 0)
            pending = held = None
            frame_number = 0
        segment = SEGMENTS[segment_index]
        epoch = segment["epoch"]
        reset = cycle < segment["active_start"]
        pll_locked = int(not reset and cycle >= segment["active_start"] + 4)
        audio_stable = int(not reset and cycle >= segment["active_start"] + 12)
        pa_en = int(audio_stable and cycle >= segment["active_start"] + 16)
        if reset:
            phase = bclk = ws = din = slot = shift = 0
            latched = (0, 0)
            pending = held = None
            frame_number = 0
        carry = int(not reset and phase + BCLK_NCO_STEP >= MODULUS)
        frame_tick = int(bool(carry and bclk and slot == 63))
        row = {field: 0 for field in CANONICAL_FIELDS}
        row.update({
            "cycle": cycle, "epoch": epoch, "rst_n": int(not reset),
            "frame_tick": frame_tick, "bclk": bclk, "ws": ws, "din": din,
            "pll_locked": pll_locked, "audio_stable": audio_stable,
            "pa_en": pa_en, "finish": int(cycle == FINAL_CYCLE),
            "time_ps": cycle * 25_000,
        })
        for action, args in operations_by_cycle.get(cycle, []):
            op_epoch, req_id = args
            if action == "REQUEST":
                row.update({"req_valid": 1, "req_ready": 1, "req_id": req_id})
            elif action == "RESULT":
                left, right, clip = oracle_values(op_epoch, req_id)
                row.update({"result_valid": 1, "result_ready": 1,
                            "result_id": req_id, "result_left": left,
                            "result_right": right, "result_clip_mask": clip})
            elif action == "COMMIT":
                left, right, clip = oracle_values(op_epoch, req_id)
                row.update({"commit": 1, "commit_id": req_id,
                            "commit_left": left, "commit_right": right,
                            "commit_clip": clip})
            elif action == "CANCEL":
                row.update({"cancel": 1, "cancel_reason": "FIXTURE_CANCEL"})
            elif action == "RESET_CANCEL":
                row["cancel_reason"] = "RESET_ENTRY"

        if frame_tick:
            frame_number += 1
            expected = tx_by_cycle[(epoch, cycle)]
            if expected["kind"] == "STARTUP":
                selected = (0, 0, 0, None)
            elif pending is not None:
                selected = pending
            elif held is not None:
                selected = held
            else:
                raise AssertionError("fixture TX plan has no selected value")
            left, right, clip, req_id = selected
            row.update({
                "tx_sample_valid": 1, "tx_frame_id": frame_number,
                "tx_req_id": 0 if req_id is None else req_id,
                "tx_left": left, "tx_right": right, "tx_clip": clip,
                "tx_hold": int(expected["kind"] == "HOLD"),
                "tx_startup_zero": int(expected["kind"] == "STARTUP"),
            })
        rows.append(row)

        if reset:
            continue
        phase = (phase + BCLK_NCO_STEP) % MODULUS
        if carry:
            if bclk:
                ws = slot // 32
                if slot % 32 == 16:
                    value = latched[0 if slot >= 32 else 1]
                    value = min(32767, max(-32768, (value + 128) // 256))
                    shift = (value & 0xFFFF) << 16
                else:
                    shift = (shift << 1) & 0xFFFFFFFF
                din = shift >> 31
                slot = (slot + 1) % 64
            bclk ^= 1
        if frame_tick:
            if pending is not None:
                held = pending
                pending = None
            selected = held
            latched = (0, 0) if selected is None else selected[:2]
        for action, args in operations_by_cycle.get(cycle, []):
            op_epoch, req_id = args
            if action == "COMMIT":
                left, right, clip = oracle_values(op_epoch, req_id)
                pending = (left, right, clip, req_id)
            elif action in {"CANCEL", "RESET_CANCEL"}:
                pass

    return calendar, frame_plan, oracle, rows


def binding(inputs_sha256: dict[str, str]) -> dict[str, Any]:
    return {
        "schema": "M3_R06_TX_CLOCK_RESET_BINDING_V1",
        "mode": "SYNTHETIC_SELFTEST_ONLY",
        "clock_hz": CLOCK_HZ,
        "sample_phase": "SYS_POSEDGE_PRE_NBA",
        "serial_format": "PT8211_32BIT_SLOT_LSBJ16_WS_LOW_RIGHT_HIGH_LEFT",
        "pcm24_to_pcm16": "SATURATE((PCM24+128)//256)",
        "trace_authority": "SYNTHETIC_FIXTURE",
        "tx_sidecar_authority": "SYNTHETIC_EXPLICIT_SIDECAR",
        "pins_authority": "SYNTHETIC_PIN_STREAM",
        "timebase_authority": "SYNTHETIC_40MHZ_TIMEBASE",
        "finish_authority": "SYNTHETIC_EXPLICIT_FINISH",
        "inputs_sha256": inputs_sha256,
    }
