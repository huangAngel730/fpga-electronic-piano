"""Independent fixture calendar, never a PCM oracle or observed DUT trace."""
import copy
import json

SCHEMA = "M3_C_FOUR_LANE_CALENDAR_V1"
SCOPE = "SYNTHETIC_FIXTURE_NOT_PRO_DUT"
PRIORITY = {"RESET": 0, "EVENT": 1, "FRAME": 2, "OFFER": 3, "ACCEPT": 4,
            "LANE_TICK": 5, "RETURN": 6, "PUBLISH": 7, "CANCEL": 8,
            "CONSUME": 9, "END": 10}


def strict_load(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def default_plan():
    """Plain input only: four solos, chord, releases, cancel and reset."""
    starts = [20 + (n * 2500) // 3 for n in range(19)]
    notes = [60, 64, 67, 72]
    events = []
    for lane, note in enumerate(notes):
        for frame, action in ((2 * lane, "NOTE_ON"), (2 * lane + 1, "NOTE_OFF")):
            events.append({"cycle": starts[frame] - 8, "action": action,
                           "note": note, "velocity": 800 if action == "NOTE_ON" else 0})
    for note in notes:
        events.append({"cycle": starts[8] - 8, "action": "NOTE_ON", "note": note, "velocity": 800})
    for lane, note in enumerate(notes):
        events.append({"cycle": starts[9 + lane] - 8, "action": "NOTE_OFF", "note": note, "velocity": 0})
    events.append({"cycle": starts[13] - 8, "action": "NOTE_ON", "note": 69, "velocity": 640})
    return {"schema": "M3_C_INPUT_PLAN_V1", "scope": SCOPE,
            "clock_hz_fixture": 40000000, "frame_starts": starts,
            "events": events, "initial_epoch": 0,
            "reset_cycles": [starts[15] + 40],
            "cancel_requests": [{"frame": 14, "lane": 2, "after_accept_cycles": 3}],
            "request_stall": {"frame": 13, "lane": 1, "cycles": 3},
            "end_cycle": starts[-1] + 834,
            "fixture_rules": {"slots": "lowest_free_immediate_noteoff_release",
                              "lane_slot_map": [0, 1, 2, 3],
                              "inactive_lanes_tick": True,
                              "request_order": "lane_0_1_2_3_per_frame",
                              "request_base_offset": 4, "lane_spacing": 8,
                              "return_after_accept": 5, "publish_after_accept": 7,
                              "consume_before_next_frame": 2}}


def payload(note, velocity):
    # 64-bit public performance event field positions; source0/channel0.
    event_type = 0 if velocity else 1
    return f"{(event_type << 61) | (note << 46) | (velocity << 36):016x}"


def build(plan):
    if plan != default_plan():
        # V1 intentionally binds a single frozen fixture; other schedules need
        # an explicitly revised fixture contract, not guessed Pro semantics.
        raise ValueError("INPUT_PLAN_NOT_FROZEN_V1")
    rows, slots = [], [None] * 4
    epoch, req_id = plan["initial_epoch"], 0
    resets = plan["reset_cycles"]
    previous = -1
    events = copy.deepcopy(plan["events"])
    for frame, start in enumerate(plan["frame_starts"]):
        for reset in resets:
            if previous < reset < start:
                epoch += 1
                req_id = 0
                slots = [None] * 4
                rows.append({"kind":"RESET", "cycle":reset, "epoch":epoch})
        for index, event in enumerate(events):
            if previous < event["cycle"] < start:
                note, velocity = event["note"], event["velocity"]
                if event["action"] == "NOTE_ON":
                    slot = slots.index(None)
                    slots[slot] = (note, velocity)
                else:
                    slot = next(i for i, value in enumerate(slots) if value is not None and value[0] == note)
                    slots[slot] = None
                rows.append({"kind":"EVENT", "cycle":start, "epoch":epoch,
                             "input_cycle":event["cycle"], "event_id":index + 1,
                             "accepted_cycle":event["cycle"] + 1 + sum(x["cycle"] == event["cycle"] for x in events[:index]),
                             "action":event["action"], "slot":slot, "note":note,
                             "data_hex":payload(note, velocity)})
        rows.append({"kind":"FRAME", "cycle":start, "epoch":epoch, "frame":frame})
        for lane in range(4):
            req_id += 1
            value = slots[lane]
            data = {"active":value is not None, "note":value[0] if value else None,
                    "velocity":value[1] if value else 0}
            ident = {"epoch":epoch, "frame":frame, "slot":lane, "lane":lane,
                     "req_id":req_id, "data":data}
            offer_cycle = start + 4 + 8 * lane
            stall = plan["request_stall"]
            wait = stall["cycles"] if (frame, lane) == (stall["frame"], stall["lane"]) else 0
            accepted = offer_cycle + wait
            for cycle in range(offer_cycle, accepted + 1):
                rows.append(dict(ident, kind="OFFER", cycle=cycle, valid=1,
                                 ready=int(cycle == accepted)))
            rows.append(dict(ident, kind="ACCEPT", cycle=accepted))
            rows.append(dict(ident, kind="LANE_TICK", cycle=accepted))
            cancellation = next((accepted + x["after_accept_cycles"] for x in plan["cancel_requests"]
                                 if (x["frame"], x["lane"]) == (frame, lane)), None)
            reset = next((x for x in resets if start < x < start + 833), None)
            if reset is not None and (cancellation is None or reset < cancellation):
                cancellation = reset
            stages = [(accepted + 5,"RETURN"), (accepted + 7,"PUBLISH"),
                      ((plan["frame_starts"][frame + 1] if frame + 1 < len(plan["frame_starts"]) else plan["end_cycle"]) - 2,"CONSUME")]
            for cycle, kind in stages:
                if cancellation is None or cycle < cancellation:
                    rows.append(dict(ident, kind=kind, cycle=cycle))
            if cancellation is not None:
                rows.append(dict(ident, kind="CANCEL", cycle=cancellation,
                                 reason="RESET" if cancellation == reset else "ACCEPTED_CANCEL"))
        previous = start
    rows.append({"kind":"END", "cycle":plan["end_cycle"], "epoch":epoch})
    # Reset-bound cancellation is recorded in old epoch at the reset cycle;
    # cancellation sorts before RESET to settle old transactions explicitly.
    rows.sort(key=lambda r:(r["cycle"], -1 if r["kind"] == "CANCEL" and r.get("reason") == "RESET" else PRIORITY[r["kind"]], r.get("lane", -1), r.get("event_id", -1)))
    return [{"kind":"HEADER", "schema":SCHEMA, "scope":SCOPE,
             "clock_hz_fixture":40000000, "sample_phase":"ABSTRACT_CYCLE_TRANSACTION_ORDER_NO_DUT_SAMPLING"}] + rows


def encode(rows):
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")
