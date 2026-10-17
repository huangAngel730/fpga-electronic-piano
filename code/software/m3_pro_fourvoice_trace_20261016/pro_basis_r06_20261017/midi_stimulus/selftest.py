"""Pure-software checks for the R06 MIDI stimulus plan."""

import argparse
import copy
import json
from pathlib import Path

from generate import generate, load_json, write_driver_files


def reject(params, cases, mutate, expected):
    p, c = copy.deepcopy(params), copy.deepcopy(cases)
    mutate(p, c)
    try:
        generate(p, c)
    except ValueError as exc:
        assert str(exc) == expected, (str(exc), expected)
        return
    raise AssertionError("negative accepted: " + expected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parameters", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    params, cases = load_json(args.parameters), load_json(args.cases)
    plan = generate(params, cases)

    assert plan["bit_cycles"] == 1280
    assert len(plan["events"]) == 23
    assert [e["event_seq"] for e in plan["events"]] == list(range(1, 24))
    assert all(a["stop_cycle_exclusive"] <= b["start_cycle"]
               for a, b in zip(plan["bytes"], plan["bytes"][1:]))
    hold = [e for e in plan["events"] if e["scenario"] == "four_hold"]
    assert [e["note"] for e in hold] == [60, 64, 67, 72]
    assert len({e["final_stop_cycle_exclusive"] for e in hold}) == 4
    assert [e["velocity7"] for e in hold] == [24, 52, 88, 120]
    zero = next(e for e in plan["events"] if e["scenario"] == "velocity_zero")
    assert zero["normalized_kind"] == "note_off" and zero["velocity10"] == 0
    assert any(row["role"] == "realtime" and row["value"] == 0xF8
               for row in plan["bytes"])
    assert len(plan["reset_plan"]) == 4 and len(plan["ready_plan"]) == 3
    assert plan["reset_plan"][0]["cycle"] == 0
    assert plan["bytes"][0]["start_cycle"] >= (
        plan["reset_plan"][1]["cycle"] +
        params["timing"]["initial_idle_bits"] * plan["bit_cycles"])
    assert all(e["allocation_release_generation"] == "PENDING_M1_SOURCE_SEMANTICS"
               for e in plan["events"])

    reject(params, cases, lambda p, c: p.__setitem__("clock_hz", 40_000_001),
           "NON_INTEGER_BIT_CYCLES")
    reject(params, cases,
           lambda p, c: c["actions"][5].__setitem__("velocity", 128),
           "MIDI_DATA_RANGE")
    reject(params, cases,
           lambda p, c: c["actions"][5].__setitem__("event_seq", 2),
           "EVENT_SEQ_CONTIGUOUS")
    reject(params, cases,
           lambda p, c: c["actions"][5].__setitem__("status", "running"),
           "RUNNING_STATUS_NOT_ACTIVE")

    write_driver_files(plan, args.output)
    print(json.dumps({"status": "PASS", "positive_checks": 13,
                      "negative_checks": 4, "events": 23,
                      "bytes": len(plan["bytes"]), "hdl_runs": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
