"""Strict public B1 transport capture replay; no audio mathematics is inferred."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from protocol_oracle import ProtocolOracle, Tag

CW = 635
MASK = (1 << CW) - 1


def require(value, reason):
    if not value:
        raise ValueError(reason)


def unpack(tag, sw):
    return Tag(tag & ((1 << sw) - 1), (tag >> (sw + 36)) & 15,
               (tag >> (sw + 32)) & 15, (tag >> sw) & 0xffffffff,
               tag >> (sw + 40))


def operation(context, tag, control, flags, pedal):
    """Opaque XOR fixture, deliberately unrelated to any sound computation."""
    low = (tag ^ (tag >> 32) ^ control ^ (flags << 20)
           ^ (int(pedal) << 31) ^ 0x5a36c17e) & 0xffffffff
    return (MASK ^ context) ^ low


def replay(raw):
    lines = raw.decode("ascii", "strict").splitlines()
    require(lines and lines[0].startswith("B1_HEADER "), "HEADER_MISSING")
    _, n, latency, mode = lines[0].split()
    n, latency, mode = int(n), int(latency), int(mode)
    require(n in (4, 8, 16, 32) and latency in (1, 3) and mode in (0, 1), "PROFILE")
    sw = (n - 1).bit_length()
    model = ProtocolOracle([(0, 0, 0)] * n, drain_limit=n+12)
    contexts, flags = [0] * n, [0] * n
    configured, controls, pending, visible, rom_done = set(), {}, {}, set(), set()
    counts, cases, frames, latencies, intervals, drains = Counter(), set(), [], [], [], []
    start, previous_issue, read_request, end, last_cycle = None, None, None, None, 0
    frame_issues, frame_returns, drain_count = 0, 0, 0
    current_case, aborts = None, []
    for line in lines[1:]:
        if line.startswith("B1_CASE "):
            require(end is None, "TRAILING_CASE")
            current_case = line.split(maxsplit=1)[1]
            cases.add(current_case)
            continue
        if line.startswith("B1_END "):
            require(end is None, "DUPLICATE_END")
            _, cycle, commits = line.split()
            require(int(commits) == counts["COMMIT"] and not pending, "END_COUNTS_OR_OWNERSHIP")
            require(not model.draining and model.request is None and read_request is None, "END_BUSY")
            end = int(cycle)
            require(end >= last_cycle, "END_CYCLE")
            continue
        if not line.startswith("B1 "):
            # Exactly the simulator's successful $finish trailer is permitted.
            require(end is not None and "$finish called" in line, "UNKNOWN_CAPTURE_LINE")
            continue
        require(end is None, "TRAILING_EVENT")
        fields = line.split()
        _, cycle_s, event, *data = fields
        cycle = int(cycle_s)
        require(cycle >= last_cycle, "CYCLE_ORDER")
        last_cycle = cycle
        arity = {"COLD": 0, "SOFT": 0, "CANCEL": 0, "CTRL": 3, "CFG": 4,
                 "BEGIN": 1, "ISSUE": 5, "ROM_VISIBLE": 1, "ROM": 2,
                 "RESULT": 3, "COMMIT": 2, "DRAIN": 4, "READ_REQ": 1,
                 "READ": 2, "ROM_INFLIGHT_NOT_EMPTY": 0}
        require(event in arity and len(data) == arity[event], "EVENT_SCHEMA")
        hex_columns = {"CTRL": (0, 1), "CFG": (1, 2, 3), "BEGIN": (0,),
                       "ISSUE": (0, 1, 2, 3), "ROM_VISIBLE": (0,), "ROM": (0, 1),
                       "RESULT": (0, 1), "COMMIT": (0,), "READ": (1,)}
        for index, value in enumerate(data):
            require(re.fullmatch("[0-9a-f]+" if index in hex_columns.get(event, ()) else "[0-9]+", value) is not None,
                    "NON_NUMERIC_OR_UNKNOWN_BITS")
        counts[event] += 1
        if event == "COLD":
            model = ProtocolOracle([(0, 0, 0)] * n, drain_limit=n+12)
            contexts, flags = [0] * n, [0] * n
            configured, controls, pending, visible, rom_done = set(), {}, {}, set(), set()
            read_request, start, previous_issue = None, None, None
            drain_count = 0
        elif event in ("CANCEL", "SOFT"):
            if current_case and current_case.startswith("abort_") and model.request is not None:
                phase = int(current_case.split("_")[1])
                require(frame_issues == (0, 0, 0, 1, n, n)[phase], "ABORT_PHASE_ISSUES")
                require(frame_returns == (n if phase == 5 else 0), "ABORT_PHASE_RETURNS")
                aborts.append({"case": current_case, "cycles_after_begin": cycle - start,
                               "issued": frame_issues, "returned": frame_returns})
            if event == "SOFT":
                model.reset()
                contexts, flags = [0] * n, [0] * n
                configured, controls = set(), {}
            else:
                model.cancel()
        elif event == "CTRL":
            identity, control = (int(value, 16) for value in data[:2])
            require(data[2] in ("0", "1") and identity < 256 and control < (1 << 29), "CONTROL_WIDTH")
            pedal = data[2] == "1"
            model.pedal(identity >> 4, identity & 15, pedal)
            controls[identity] = control
        elif event == "CFG":
            slot = int(data[0])
            identity, flag, context = (int(value, 16) for value in data[1:])
            require(identity < (1 << 40) and flag < 4 and context <= MASK, "CONFIG_WIDTH")
            model.replace(slot, identity >> 36, (identity >> 32) & 15, identity & 0xffffffff)
            contexts[slot], flags[slot] = context, flag
            configured.add(slot)
        elif event == "BEGIN":
            require(len(configured) == n and not pending, "BEGIN_UNINITIALIZED_OR_UNDRAINED")
            model.begin(int(data[0], 16))
            start, previous_issue = cycle, None
            frame_issues, frame_returns, drain_count = 0, 0, 0
        elif event == "ISSUE":
            tag, context, flag, control = (int(value, 16) for value in data[:4])
            require(data[4] in ("0", "1"), "PEDAL_WIDTH")
            pedal = data[4] == "1"
            decoded = unpack(tag, sw)
            require(model.issue(decoded.slot) == decoded, "ISSUE_TAG_IDENTITY")
            require(decoded.slot == frame_issues, "SLOT_SCHEDULING_ORDER")
            require(context == contexts[decoded.slot] and flag == flags[decoded.slot], "ISSUE_CONTEXT")
            identity = decoded.source * 16 + decoded.channel
            require(control == controls.get(identity, 0) and pedal == model.pedals[identity], "CONTROL_SNAPSHOT")
            require(cycle - start >= 3, "SYNC_READ_LATENCY")
            if previous_issue is not None:
                require(cycle - previous_issue >= 3, "BANK_READ_PORT_CONFLICT")
                intervals.append(cycle - previous_issue)
            previous_issue = cycle
            require(decoded.slot not in pending, "ENGINE_REUSED_OWNED_SLOT")
            pending[decoded.slot] = (tag, cycle, operation(context, tag, control, flag, pedal), context & 255)
            visible.discard(decoded.slot)
            rom_done.discard(decoded.slot)
            frame_issues += 1
        elif event in ("ROM_VISIBLE", "ROM"):
            tag = int(data[0], 16)
            slot = unpack(tag, sw).slot
            require(slot in pending and pending[slot][0] == tag, "ROM_TAG_OWNERSHIP")
            if event == "ROM_VISIBLE":
                actual = cycle - pending[slot][1]
                require(slot not in visible and actual == latency, "ROM_EXACT_LATENCY")
                latencies.append(actual)
                visible.add(slot)
            else:
                require(slot in visible and slot not in rom_done, "ROM_DUPLICATE_OR_EARLY")
                address = pending[slot][3]
                require(int(data[1], 16) == ((address * 257) ^ 0x5a3c), "ROM_DATA")
                rom_done.add(slot)
        elif event == "RESULT":
            tag, context = (int(value, 16) for value in data[:2])
            require(context <= MASK and data[2] in ("0", "1"), "RESULT_SCHEMA")
            decoded = unpack(tag, sw)
            accepted = model.accept(decoded, context)
            require(accepted == (data[2] == "1"), "RESULT_ACCEPTANCE")
            slot = decoded.slot
            if slot in pending and pending[slot][0] == tag:
                require(slot in rom_done and context == pending[slot][2], "RESULT_OPAQUE_PAYLOAD")
                del pending[slot]
            if accepted:
                frame_returns += 1
            else:
                counts["REJECTED"] += 1
        elif event == "COMMIT":
            require(start is not None and int(data[0], 16) == model.request, "COMMIT_ID")
            require(frame_issues == n and frame_returns == n, "ALL_N_BEFORE_COMMIT")
            contexts = list(model.commit())
            duration = cycle - start
            require(data[1] in ("0", "1") and (data[1] == "1") == (duration >= 834), "DEADLINE_FLAG")
            frames.append({"request": int(data[0], 16), "cycles_to_commit": duration,
                           "deadline_missed": data[1] == "1", "all_N": n})
            drain_count = 0
        elif event == "DRAIN":
            require(all(value in ("0", "1") for value in data), "DRAIN_SCHEMA")
            rom_empty, engine_empty, result_empty, fault = (value == "1" for value in data)
            # The trace is pre-edge. Queue pops on this edge may already have
            # removed pending in the event model; never infer hardware empties
            # from this software queue. Actual RTL ROM latency/tag checks above
            # and TB queue assertions are separate evidence.
            require(model.draining, "SPURIOUS_DRAIN")
            require(fault == model.drain_failed, "DRAIN_FAULT_TIMING")
            if fault:
                counts["FAULT_OBSERVED"] += 1
            else:
                drain_count += 1
                try:
                    released = model.drain_step(rom_empty=rom_empty, engine_empty=engine_empty,
                                                result_empty=result_empty)
                    if released:
                        require(not pending, "FALSE_EMPTY_WITH_PENDING_ENGINE")
                        drains.append(drain_count)
                        drain_count = 0
                except ValueError as error:
                    require(str(error) == "DRAIN_TIMEOUT" and drain_count == n+12, "WRONG_DRAIN_ERROR")
        elif event == "READ_REQ":
            require(model.request is None and not model.draining and read_request is None, "READ_PORT_CONFLICT")
            read_request = (int(data[0]), cycle)
        elif event == "READ":
            slot, context = int(data[0]), int(data[1], 16)
            require(read_request == (slot, cycle - 1), "READ_SYNC_LATENCY")
            require(context == contexts[slot], "ATOMIC_BANK_READBACK")
            read_request = None
        elif event == "ROM_INFLIGHT_NOT_EMPTY":
            require(model.draining, "ROM_EMPTY_GAP_SCOPE")
    require(end is not None and frames and counts["REJECTED"] >= 5, "INCOMPLETE_CAPTURE")
    required = {"config_frame_read_port_priority", "normal_backpressure_reorder_all_identities",
                "wrap_full_tag_reuse_after_real_empty"}
    if mode == 0:
        required |= {f"abort_{phase}_{kind}" for phase in range(6) for kind in range(2)}
        required |= {"timeout_local_reset_cannot_extend_fence", "whole_domain_reset_recovery"}
        require(counts["FAULT_OBSERVED"] > 0, "TIMEOUT_NOT_TESTED")
        require(len(aborts) == 12, "ABORT_PHASE_COVERAGE")
    else:
        required.add("slow_operator_deadline_not_audio_budget")
        require(any(frame["deadline_missed"] for frame in frames), "SLOW_NOT_TESTED")
    require(required <= cases, "MISSING_REQUIRED_CASE")
    return {"status": "B1_PUBLIC_PROTOCOL_MATCH_NOT_AUDIO", "N": n, "ROM_latency": latency,
            "mode": mode, "counts": dict(counts), "cases": sorted(cases), "frames": frames, "aborts": aborts,
            "observed_issue_II_min": min(intervals), "observed_issue_II_max": max(intervals),
            "observed_ROM_latency": sorted(set(latencies)), "observed_drain_max": max(drains),
            "audio_equivalence": False, "CC64_event_service_bound": None,
            "synthesis_STA_device": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-rtl-reject", choices=("CHECK_TAG_GENERATION_OR_UNISSUED", "CHECK_ALL_N_BEFORE_COMMIT"))
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        if args.expect_rtl_reject:
            text = raw.decode("ascii", "strict")
            require("B1_END " not in text and f": {args.expect_rtl_reject}" in text, "NOT_DESIGNATED_RTL_REJECT")
            require("CHECK_TEST_TIMEOUT" not in text, "TIMEOUT_IS_NOT_BEHAVIOR_REJECT")
            result = {"status": "COMPILED_RTL_MUTANT_DESIGNATED_REJECT", "reason": args.expect_rtl_reject}
        else:
            result = replay(raw)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2)
                stream.write("\n")
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, IndexError, KeyError) as error:
        print(json.dumps({"status": "REJECT", "reason": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
