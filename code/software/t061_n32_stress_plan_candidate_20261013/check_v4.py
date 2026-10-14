"""Actual N32-C v4 input/port and frozen independent clocked math checker."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_v4 import ROOT, generate
from n32c_common import read_jsonl, records_sha256

sys.path.insert(0, str(ROOT / "code/software/polyphony_scaling_candidate"))
from b2c_check import Oracle, dec, hx, require, packed  # noqa: E402

STANDARD = {"R": 2, "I": 3, "J": 3, "U": 12, "G": 7, "W": 6,
            "C": 11, "A": 3, "L": 11, "F": 6, "P": 6, "X": 2,
            "Z": 3, "Y": 4, "END": 14}
EXTRA = {"D": 11, "AS": 8, "RA": 4, "RQ": 3, "RY": 4, "RS": 4,
         "CS": 8, "CR": 4, "RD": 5, "RT": 5, "K": 8}


def check(raw: bytes, plan, expected, *, mathematical=True, identity=True):
    if identity:
        golden_plan, golden_expected = generate()
        require(records_sha256(plan) == records_sha256(golden_plan), "C4_PLAN_INPUT_IDENTITY")
        require(records_sha256(expected) == records_sha256(golden_expected), "C4_EXPECTED_INPUT_ONLY_MATH_IDENTITY")
    lines = raw.decode("ascii").splitlines()
    require(lines[:2] == ["B2C 32 1 0", "C4 PUBLIC_PORTS PRE_NBA_INPUTS POST_NBA_LANES SAMPLE_INTERVAL_833"], "C4_HEADER")
    if lines and re.fullmatch(r".*[/\\]tb_c_n32_r1_v4\.sv:[0-9]+: \$finish called at [0-9]+ \(1ps\)", lines[-1]):
        lines.pop()
    operations = plan[1:-1]
    ledger = {r["plan_index"]: r for r in expected[1:-1]}
    txns = {r["result_id"]: r for r in expected if r["record"] == "TXN"}
    oracle = Oracle(1, 32, identity_controls=True)
    groups = {}
    extras = []
    by_extra = {}
    op_start, op_end = {}, {}
    current = -1
    completed = -1
    ended = False
    drive = None
    readiness = None
    latest_route = None
    ready_by_op = {}
    planned_ready = 1
    for i, operation in enumerate(operations):
        if operation["op"] == "reset":
            planned_ready = 1
        elif operation["op"] == "set_result_ready":
            planned_ready = operation["value"]
        ready_by_op[i] = planned_ready
    last_sample = None
    port_counts = Counter()
    seen_result = set()
    seen_first = set()
    snapshots = Counter()
    hold_counts = Counter()
    public_result_counts = Counter()
    fullscale_unclipped = False
    done_seen = set()
    read_queue = []
    for line in lines[2:]:
        row = line.split()
        require(bool(row) and not ended, "C4_TRAILING_AFTER_END")
        tag = row[0]
        if tag == "OP":
            require(len(row) in (4, 5), "C4_OP_SCHEMA")
            cycle, index = dec(row[1]), dec(row[2], 0, len(operations)-1)
            if row[3] == "BEGIN":
                require(len(row) == 5 and current == -1 and index == completed+1,
                        "C4_OPERATION_BEGIN_SEQUENCE")
                require(row[4] == operations[index]["op"], "C4_OPERATION_KIND")
                current = index
                op_start[index] = cycle
            else:
                require(len(row) == 4 and row[3] == "END" and current == index,
                        "C4_OPERATION_END_SEQUENCE")
                op_end[index] = cycle
                if index in ledger and ledger[index]["record"] == "EVENT":
                    require(latest_route is not None, "C4_MISSING_PUBLIC_ROUTE")
                    slots = ledger[index]["slots_after"]
                    wanted = [packed([int(s[k]) for s in slots], w) for k, w in
                              (("occupied", 1), ("releasing", 1), ("velocity", 10), ("fcw", 32),
                               ("note", 8), ("source", 4), ("channel", 4), ("generation", 32))]
                    require([hx(v, w) for v, w in zip(latest_route[4:],
                             (32, 32, 320, 1024, 256, 128, 128, 1024))] == wanted,
                            "C4_PUBLIC_ROUTE_IDENTITY_OR_STEAL")
                completed, current = index, -1
            continue
        require(tag in STANDARD or tag in EXTRA, "C4_UNKNOWN_ROW:"+tag)
        require(len(row) == (STANDARD.get(tag) or EXTRA[tag]), "C4_ROW_SCHEMA:"+tag)
        cycle = dec(row[1])
        if tag in STANDARD:
            groups.setdefault(cycle, []).append(row)
            if tag == "END":
                require(completed == len(operations)-1 and current == -1,
                        "C4_INCOMPLETE_PLAN")
                ended = True
        else:
            extras.append((cycle, current, row))
            by_extra.setdefault(cycle, []).append(row)
        if tag == "D":
            vals = [dec(row[i], 0, 1) for i in (2, 3, 4, 6, 8, 9)]
            hx(row[5], 64); hx(row[7], 32); dec(row[10], 0, 31)
            # Width below is intentionally checked separately from values.
            drive = row
            if current >= 0:
                op = operations[current]
                kind = op["op"]
                require(int(row[8]) == ready_by_op[current], "C4_RESULT_READY_DRIVE")
                require(row[2] == "1" or kind == "reset", "C4_UNPLANNED_RESET_DRIVE")
                require(row[3] == "0" or kind == "cancel", "C4_UNPLANNED_CANCEL_DRIVE")
                require(row[4] == "0" or kind in ("note_on", "note_off", "cc64", "control_event"), "C4_UNPLANNED_EVENT_DRIVE")
                require(row[6] == "0" or kind == "sample", "C4_UNPLANNED_SAMPLE_DRIVE")
                require(row[9] == "0" or kind in ("read", "read_stall"), "C4_UNPLANNED_READ_DRIVE")
                if row[4] == "1":
                    require(hx(row[5], 64) == ledger[current]["event_word"], "C4_HELD_EVENT_DRIVE")
                if row[6] == "1":
                    require(hx(row[7], 32) == ledger[current]["result_id"], "C4_HELD_SAMPLE_DRIVE")
                if row[9] == "1":
                    require(int(row[10]) == op["slot"], "C4_HELD_READ_DRIVE")
        if tag == "AS":
            dec(row[2], 0, 15); dec(row[3], 0, 12)
            for value in row[4:]:
                dec(value, 0, 1)
            readiness = row
        if tag == "U":
            latest_route = row
        if tag == "I":
            require(readiness is not None and readiness[5] == "1", "C4_EVENT_READY_QUALIFICATION")
            require(drive is not None and drive[2:5] == ["1", "0", "1"] and
                    drive[5] == row[2], "C4_EVENT_DRIVE")
            require(current in ledger and ledger[current]["record"] == "EVENT",
                    "C4_EVENT_OUTSIDE_PLAN")
            require(hx(row[2], 64) == ledger[current]["event_word"], "C4_EVENT_WORD")
            port_counts[(current, "I")] += 1
        if tag == "J":
            require(readiness is not None and readiness[6] == "1", "C4_SAMPLE_READY_QUALIFICATION")
            require(drive is not None and drive[2:4] == ["1", "0"] and
                    drive[6] == "1" and drive[7] == row[2], "C4_SAMPLE_DRIVE")
            require(current in ledger and ledger[current]["record"] == "TXN",
                    "C4_SAMPLE_OUTSIDE_PLAN")
            require(hx(row[2], 32) == ledger[current]["result_id"], "C4_SAMPLE_ID")
            if last_sample is not None:
                require(cycle-last_sample >= 833, "C4_SAMPLE_INTERVAL")
            last_sample = cycle
            port_counts[(current, "J")] += 1
        if tag == "R":
            require(drive is not None and drive[2] == "0", "C4_RESET_DRIVE")
            require(current >= 0 and operations[current]["op"] == "reset", "C4_RESET_OUTSIDE_PLAN")
            last_sample = None
            done_seen.clear()
            port_counts[(current, "R")] += 1
        if tag == "RA":
            dec(row[2], 0, 12); dec(row[3], 0, 12)
            require(current >= 0 and operations[current]["op"] == "reset", "C4_RESET_ASSERT_OUTSIDE_PLAN")
            if current > 0 and operations[current-1]["op"] == "cancel":
                require(row[2] == "12", "C4_CANCEL_DRAIN_RESET_BOUNDARY")
            port_counts[(current, "RA")] += 1
        if tag == "X":
            require(drive is not None and drive[3] == "1", "C4_CANCEL_DRIVE")
            require(current >= 0 and operations[current]["op"] == "cancel", "C4_CANCEL_OUTSIDE_PLAN")
            port_counts[(current, "X")] += 1
        if tag == "RQ":
            require(readiness is not None and readiness[7] == "1", "C4_READ_READY_QUALIFICATION")
            require(drive is not None and drive[9] == "1" and drive[10] == row[2], "C4_READ_DRIVE")
            require(current in ledger and ledger[current]["record"] == "READ", "C4_READ_OUTSIDE_PLAN")
            require(dec(row[2], 0, 31) == ledger[current]["slot"], "C4_READ_SLOT")
            read_queue.append((cycle, current, int(row[2])))
            port_counts[(current, "RQ")] += 1
        if tag == "RY":
            require(read_queue, "C4_READ_RESPONSE_WITHOUT_REQUEST")
            request_cycle, index, slot = read_queue.pop(0)
            require(cycle == request_cycle+1 and dec(row[2], 0, 31) == slot,
                    "C4_PRE_NBA_READ_LATENCY")
            require(hx(row[3], 74) == ledger[index]["context"], "C4_READ_COMMITTED_CONTEXT")
        if tag == "RS":
            require(readiness is not None and readiness[7] == "0", "C4_READ_STALL_READY_QUALIFICATION")
            require(drive is not None and drive[9] == "1" and drive[10] == row[2], "C4_READ_STALL_DRIVE")
            if current >= 0 and operations[current]["op"] == "read_stall":
                require(dec(row[2], 0, 31) == operations[current]["slot"], "C4_READ_STALL_SLOT")
                port_counts[(current, "RS")] += 1
        if tag == "RD":
            hx(row[3], 32); hx(row[4], 32)
            done_seen.add(dec(row[2], 0, 31))
        if tag == "CR":
            require(hx(row[2], 32) != 0, "C4_EMPTY_CONTROL_RELEASE")
            hx(row[3], 1024)
        if tag == "CS":
            rid = hx(row[2], 32)
            require(rid in txns, "C4_CONTROL_SNAPSHOT_ID")
            rec = txns[rid]
            slots, controls = rec["slots_snapshot"], rec["controls_snapshot"]
            wanted = [packed([int(s["occupied"]) for s in slots], 1),
                      packed([s["source"] for s in slots], 4), packed([s["channel"] for s in slots], 4),
                      packed([s["generation"] for s in slots], 32),
                      packed([c[0] for c in controls], 12) | packed([c[1] for c in controls], 12) << 384 |
                      packed([c[2] for c in controls], 5) << 768]
            require([hx(v, w) for v, w in zip(row[3:], (32, 128, 128, 1024, 928))] == wanted,
                    "C4_CONTROL_SNAPSHOT_IDENTITY_OR_VALUE")
            snapshots[rid] += 1
        if tag == "RT":
            slot = dec(row[2], 0, 31)
            require(current >= 0 and operations[current]["op"] == "await_release_done" and
                    slot == operations[current]["slot"] and slot in done_seen,
                    "C4_RETIRE_WITHOUT_REAL_DONE")
            require(not (hx(row[3], 32) | hx(row[4], 32)) & (1 << slot), "C4_RETIRE_PUBLIC_FLAGS")
            port_counts[(current, "RT")] += 1
        if tag in ("F", "P", "K"):
            rid = hx(row[2], 32)
            require(rid in txns and txns[rid]["disposition"] == "PUBLISH", "C4_STALE_OR_CANCEL_RESULT")
            rec = txns[rid]
            require([dec(row[3], -(1 << 23), (1 << 23)-1), dec(row[4], -(1 << 23), (1 << 23)-1)] ==
                    [rec["left_pcm"], rec["right_pcm"]], "C4_INPUT_GOLDEN_PCM")
            if tag == "K":
                dec(row[5], 0, 1)
                require(dec(row[6], 0, 1) == rec["clipped"], "C4_CLIPPED_ALIGNMENT")
                require(drive is not None and dec(row[7], 0, 1) == int(drive[8]), "C4_PUBLIC_HANDSHAKE")
                hold_counts[rid] += int(row[7] == "0")
                public_result_counts[rid] += 1
                fullscale_unclipped |= row[3:5] == ["-8388608", "-8388608"] and row[6] == "0"
            if tag == "F":
                require(rid not in seen_first, "C4_DUPLICATE_FIRST_VALID")
                seen_first.add(rid)
            if tag == "P":
                require(rid in seen_first, "C4_PUBLISH_BEFORE_FIRST_VALID")
                require(rid not in seen_result, "C4_DUPLICATE_PUBLICATION")
                seen_result.add(rid)
    require(ended and not read_queue, "C4_MISSING_END_OR_PENDING_READ")
    for index, op in enumerate(operations):
        tag = {"note_on": "I", "note_off": "I", "cc64": "I", "control_event": "I",
               "sample": "J", "read": "RQ", "reset": "R", "cancel": "X", "await_release_done": "RT"}.get(op["op"])
        if tag:
            require(port_counts[(index, tag)] == 1, "C4_OPERATION_ACCEPT_COUNT:"+str(index))
        if op["op"] == "reset":
            require(port_counts[(index, "RA")] == 1, "C4_RESET_ASSERT_COUNT")
        if op["op"] == "read_stall":
            require(port_counts[(index, "RS")] == op["cycles"], "C4_READ_STALL_COUNT")
    required_results = {rid for rid, rec in txns.items() if rec["disposition"] == "PUBLISH"}
    require(seen_result == required_results, "C4_MISSING_PUBLICATION")
    require(seen_first == required_results, "C4_MISSING_FIRST_VALID")
    require(fullscale_unclipped, "C4_EXACT_FULLSCALE_UNCLIPPED_NOT_OBSERVED")
    for rid, rec in txns.items():
        require(snapshots[rid] == int(rec["disposition"] != "CANCEL"), "C4_SNAPSHOT_COUNT")
        minimum = operations[rec["plan_index"]].get("min_hold_cycles", 0)
        require(hold_counts[rid] >= minimum, "C4_REQUIRED_HOLD_MISSING")
        if rec["disposition"] == "PUBLISH":
            require(public_result_counts[rid] > 0, "C4_CLIPPED_PUBLIC_PORT_MISSING")
    if not mathematical:
        return dict(status="N32_C_FAST_LEDGER_PASS", published=len(seen_result))
    for cycle in sorted(set(groups) | set(by_extra)):
        rows = groups.get(cycle, [])
        if hasattr(oracle, "router") and cycle > oracle.cycle+1:
            oracle.advance(cycle-1, [])
        pre_done = 0
        pre_generations = None
        if hasattr(oracle, "router"):
            pre_generations = [s["generation"] for s in oracle.router.slots]
            pre_done = sum(int(s["occupied"] and s["releasing"] and
                              env.snapshot()["public_state"] == 0 and not oracle.router.on & (1 << i)) << i
                           for i, (s, env) in enumerate(zip(oracle.router.slots, oracle.env)))
        old_pending = dict(oracle.router.pending) if hasattr(oracle, "router") else {}
        if rows and rows[0][0] == "R":
            require(len(rows) == 1, "C4_RESET_CONFLICT")
            oracle.counts["R"] += 1
            oracle.reset(cycle)
        elif rows and rows[0][0] == "END":
            require(len(rows) == 1 and oracle.frame is None, "C4_END_LIVE_FRAME")
            keys = ("I", "J", "C", "A", "L", "P", "X", "Z", "W", "G", "Y", "F")
            require([dec(x) for x in rows[0][2:]] == [oracle.counts[k] for k in keys], "C4_END_COUNTS")
        else:
            if hasattr(oracle, "router"):
                oracle.advance(cycle, rows)
            else:
                require(not rows, "C4_MISSING_RESET")
        for extra in by_extra.get(cycle, []):
            tag = extra[0]
            if tag == "CS":
                f = oracle.frame
                require(f is not None and "slots" in f and hx(extra[2], 32) == f["id"], "C4_CONTROL_SNAPSHOT_ID")
                slots, controls = f["slots"], f["control"]
                values = [packed([int(s["occupied"]) for s in slots], 1),
                          packed([s["source"] for s in slots], 4), packed([s["channel"] for s in slots], 4),
                          packed([s["generation"] for s in slots], 32),
                          packed([c[0] for c in controls], 12) | packed([c[1] for c in controls], 12) << 384 |
                          packed([c[2] for c in controls], 5) << 768]
                require([hx(v, w) for v, w in zip(extra[3:], (32, 128, 128, 1024, 928))] == values,
                        "C4_CONTROL_SNAPSHOT_IDENTITY_OR_VALUE")
            elif tag == "CR":
                mask, gens = hx(extra[2], 32), hx(extra[3], 1024)
                pending = {**old_pending, **oracle.router.pending}
                require(mask != 0 and mask == sum(1 << i for i in pending) and
                        all(not mask & (1 << i) or pending.get(i) == (gens >> (32*i)) & 0xffffffff
                                           for i in range(32)), "C4_CONTROL_RELEASE_IDENTITY")
            elif tag == "RD":
                slot, gen, mask = dec(extra[2], 0, 31), hx(extra[3], 32), hx(extra[4], 32)
                require(mask != 0 and mask == pre_done and slot == (mask & -mask).bit_length()-1 and
                        pre_generations[slot] == gen,
                        "C4_BACKEND_RELEASE_DONE_IDENTITY_OR_STATE")
    oracle.lifecycle.update(oracle.router.counts)
    require(oracle.lifecycle["retirements"] >= 4, "C4_REAL_FOUR_RETIREMENTS")
    return dict(status="N32_C_STRESS_PASS_T061_PARTIAL", counts=dict(oracle.counts),
                lifecycle=dict(oracle.lifecycle), coverage=dict(oracle.coverage), operations=len(operations),
                published=len(seen_result), capture_sha256=hashlib.sha256(raw).hexdigest(),
                plan_sha256=records_sha256(plan), expected_sha256=records_sha256(expected),
                task_complete=False, physical_STA="NOT_RUN")


def mutations(raw, plan, expected):
    """Alter complete original captures; preserve all unaffected lines/bytes."""
    original = raw.decode("ascii").splitlines(keepends=True)
    results = []

    def run(name, changed, diagnostic):
        payload = "".join(changed).encode("ascii")
        require(payload != raw, "C4_MUTATION_NO_CHANGE:"+name)
        try:
            check(payload, plan, expected, mathematical=False, identity=False)
        except ValueError as error:
            reason = str(error)
            require(reason.startswith(diagnostic), "C4_MUTATION_WRONG_DIAGNOSTIC:"+name+":"+reason)
            results.append(dict(name=name, exit_code=1, reason=reason,
                                capture_sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload)))
            return
        raise ValueError("C4_MUTATION_MISACCEPT:"+name)

    def location(tag):
        return next(i for i, line in enumerate(original) if line.startswith(tag+" "))

    for tag in ("I", "J", "P"):
        index = location(tag)
        changed = original.copy(); del changed[index]
        run("DROP_"+tag, changed, {"I": "C4_OPERATION_ACCEPT_COUNT", "J": "C4_OPERATION_ACCEPT_COUNT", "P": "C4_MISSING_PUBLICATION"}[tag])
        changed = original.copy(); changed.insert(index, changed[index])
        run("DUPLICATE_"+tag, changed, {"I": "C4_OPERATION_ACCEPT_COUNT", "J": "C4_SAMPLE_INTERVAL", "P": "C4_DUPLICATE_PUBLICATION"}[tag])
    index = location("K")
    for name, field, delta, diagnostic in (("WRONG_RESULT_ID", 2, 1, "C4_STALE_OR_CANCEL_RESULT"),
                                            ("LEFT_1LSB", 3, 1, "C4_INPUT_GOLDEN_PCM"),
                                            ("RIGHT_1LSB", 4, 1, "C4_INPUT_GOLDEN_PCM"),
                                            ("CLIPPED_FLIP", 6, 1, "C4_CLIPPED_ALIGNMENT")):
        changed = original.copy(); row = changed[index].split()
        row[field] = f"{int(row[field], 16)^0x80000000:x}" if field == 2 else str(int(row[field])+delta if field != 6 else 1-int(row[field]))
        changed[index] = " ".join(row)+"\n"
        run(name, changed, diagnostic)
    changed = original.copy(); row = changed[index].split(); del row[6]
    changed[index] = " ".join(row)+"\n"
    run("CLIPPED_MISSING", changed, "C4_ROW_SCHEMA:K")
    proxy_index = next(i for i, line in enumerate(original) if line.startswith("K ") and
                       line.split()[3:5] == ["-8388608", "-8388608"] and line.split()[6] == "0")
    changed = original.copy(); row = changed[proxy_index].split(); row[6] = "1"
    changed[proxy_index] = " ".join(row)+"\n"
    run("CLIPPED_FULLSCALE_PROXY", changed, "C4_CLIPPED_ALIGNMENT")
    # Mutate the final public snapshot of an event operation, ensuring the
    # changed identity reaches a meaningful independent boundary comparison.
    candidate = None
    for i, line in enumerate(original):
        if line.startswith("U "):
            candidate = i
        elif line.startswith("OP ") and line.split()[3] == "END" and candidate is not None:
            opindex = int(line.split()[2])
            if plan[opindex+1]["op"] == "note_on":
                break
    require(candidate is not None, "C4_NO_IDENTITY_MUTATION_POINT")
    changed = original.copy(); row = changed[candidate].split(); row[9] = f"{int(row[9], 16)^1:x}"
    changed[candidate] = " ".join(row)+"\n"
    run("WRONG_SLOT_IDENTITY", changed, "C4_PUBLIC_ROUTE_IDENTITY_OR_STEAL")
    victim_op = next(op["index"] for op in plan[1:-1] if op["op"] == "note_on" and
                     op.get("source") == 3 and op.get("channel") == 15 and op.get("note") == 100)
    for i, line in enumerate(original):
        if line.startswith("U "):
            candidate = i
        elif line.startswith("OP ") and line.split()[3] == "END" and int(line.split()[2]) == victim_op:
            break
    changed = original.copy(); row = changed[candidate].split()
    # Swap the complete slot-0/slot-1 descriptors to model a real wrong LRU
    # victim at the thirty-third allocation, rather than a generic bit flip.
    for field, width in ((4, 1), (5, 1), (6, 10), (7, 32), (8, 8), (9, 4), (10, 4), (11, 32)):
        value, mask = int(row[field], 16), (1 << width)-1
        a, b = value & mask, (value >> width) & mask
        row[field] = f"{(value & ~(mask | (mask << width))) | b | (a << width):x}"
    changed[candidate] = " ".join(row)+"\n"
    run("WRONG_STEAL_VICTIM", changed, "C4_PUBLIC_ROUTE_IDENTITY_OR_STEAL")
    for tag, rid, name in (("X", 0x1300, "STALE_AFTER_CANCEL"), ("R", 0x1301, "STALE_AFTER_RESET")):
        if tag == "R":
            point = [i for i, line in enumerate(original) if line.startswith("R ")][-1]
        else:
            point = location(tag)
        cycle = int(original[point].split()[1])
        changed = original.copy(); changed.insert(point+1, f"K {cycle} {rid:08x} 0 0 0 0 0\n")
        run(name, changed, "C4_STALE_OR_CANCEL_RESULT")
    return dict(status="N32_C_MUTATIONS_PASS", rejected=len(results), mutations=results,
                original_sha256=hashlib.sha256(raw).hexdigest(),
                left_right_swap="NOT_APPLICABLE_EQUAL_STEREO_USE_SINGLE_CHANNEL_1LSB",
                fullscale_clipped_proxy="EXACT_PCM24_MINIMUM_SUM_WITH_CLIPPED_ZERO")


def main():
    parser = argparse.ArgumentParser()
    for name in ("input", "plan", "expected", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--mutations-only", action="store_true")
    args = parser.parse_args()
    try:
        plan, expected = read_jsonl(args.plan), read_jsonl(args.expected)
        raw = args.input.read_bytes()
        if args.mutations_only:
            wanted_plan, wanted_expected = generate()
            require(records_sha256(plan) == records_sha256(wanted_plan) and
                    records_sha256(expected) == records_sha256(wanted_expected), "C4_MUTATION_INPUT_IDENTITY")
            # Fast ledger validates the complete original first; an ordinary
            # run separately owns the full clocked mathematical acceptance.
            check(raw, plan, expected, mathematical=False, identity=False)
            result = mutations(raw, plan, expected)
        else:
            result = check(raw, plan, expected)
        code = 0
    except (ValueError, OSError, UnicodeError, KeyError, IndexError) as error:
        result, code = dict(status="REJECT", reason=str(error)), 1
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
