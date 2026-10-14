"""Qualify an authentic completed C00-C04 prefix without manufacturing END.

The failed complete run and its original raw bytes remain historical failures.
This reports only the exact byte prefix ending at the input-selected final
C04 publication, independently replaying every router/DSP/calendar edge.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_v4
from check_v5 import live_qualification
from generate_v4 import generate
from n32c_common import read_jsonl, records_sha256


def clocked_audit(raw, *, require_end):
    """Independent model replay; only original R/I/J/X and frozen ROM inputs."""
    oracle = check_v4.Oracle(1, 32, identity_controls=True)
    groups, extras = {}, {}
    ended = False
    for line in raw.decode("ascii").splitlines()[2:]:
        row = line.split()
        if not row or row[0] == "OP":
            continue
        tag = row[0]
        if tag in check_v4.STANDARD:
            groups.setdefault(check_v4.dec(row[1]), []).append(row)
            ended |= tag == "END"
        elif tag in check_v4.EXTRA:
            extras.setdefault(check_v4.dec(row[1]), []).append(row)
        elif "$finish called" not in line:
            raise ValueError("C6_CLOCK_UNKNOWN_ROW:"+tag)
    check_v4.require(ended == require_end, "C6_CLOCK_END_PROFILE")
    for cycle in sorted(set(groups) | set(extras)):
        rows = groups.get(cycle, [])
        if hasattr(oracle, "router") and cycle > oracle.cycle+1:
            oracle.advance(cycle-1, [])
        pre_done, pre_gens = 0, None
        if hasattr(oracle, "router"):
            pre_gens = [s["generation"] for s in oracle.router.slots]
            pre_done = sum(int(s["occupied"] and s["releasing"] and
                              env.snapshot()["public_state"] == 0 and not oracle.router.on & (1 << i)) << i
                           for i, (s, env) in enumerate(zip(oracle.router.slots, oracle.env)))
        old_pending = dict(oracle.router.pending) if hasattr(oracle, "router") else {}
        if rows and rows[0][0] == "R":
            check_v4.require(len(rows) == 1, "C6_CLOCK_RESET_CONFLICT")
            oracle.counts["R"] += 1
            oracle.reset(cycle)
        elif rows and rows[0][0] == "END":
            check_v4.require(len(rows) == 1 and oracle.frame is None, "C6_CLOCK_END_LIVE_FRAME")
            keys = ("I", "J", "C", "A", "L", "P", "X", "Z", "W", "G", "Y", "F")
            check_v4.require([check_v4.dec(x) for x in rows[0][2:]] == [oracle.counts[k] for k in keys], "C6_CLOCK_END_COUNTS")
        elif hasattr(oracle, "router"):
            oracle.advance(cycle, rows)
        else:
            check_v4.require(not rows, "C6_CLOCK_MISSING_RESET")
        for row in extras.get(cycle, []):
            if row[0] == "CS":
                frame = oracle.frame
                check_v4.require(frame is not None and "slots" in frame and
                                 check_v4.hx(row[2], 32) == frame["id"], "C6_CLOCK_SNAPSHOT_ID")
                slots, controls = frame["slots"], frame["control"]
                values = [check_v4.packed([int(s["occupied"]) for s in slots], 1),
                          check_v4.packed([s["source"] for s in slots], 4),
                          check_v4.packed([s["channel"] for s in slots], 4),
                          check_v4.packed([s["generation"] for s in slots], 32),
                          check_v4.packed([c[0] for c in controls], 12) |
                          check_v4.packed([c[1] for c in controls], 12) << 384 |
                          check_v4.packed([c[2] for c in controls], 5) << 768]
                check_v4.require([check_v4.hx(v, w) for v, w in zip(row[3:], (32, 128, 128, 1024, 928))] == values,
                                 "C6_CLOCK_SNAPSHOT_CONTROL_IDENTITY")
            elif row[0] == "CR":
                mask, gens = check_v4.hx(row[2], 32), check_v4.hx(row[3], 1024)
                pending = {**old_pending, **oracle.router.pending}
                check_v4.require(mask != 0 and mask == sum(1 << i for i in pending) and
                                 all(not mask & (1 << i) or pending.get(i) == (gens >> (32*i)) & 0xffffffff
                                     for i in range(32)), "C6_CLOCK_CONTROL_RELEASE_MASK_GENERATION")
            elif row[0] == "RD":
                slot, gen, mask = check_v4.dec(row[2], 0, 31), check_v4.hx(row[3], 32), check_v4.hx(row[4], 32)
                check_v4.require(mask != 0 and mask == pre_done and
                                 slot == (mask & -mask).bit_length()-1 and pre_gens[slot] == gen,
                                 "C6_CLOCK_RELEASE_DONE_MASK_GENERATION")
    check_v4.require(oracle.frame is None, "C6_CLOCK_PREFIX_LIVE_FRAME")
    oracle.lifecycle.update(oracle.router.counts)
    return dict(counts=dict(oracle.counts), lifecycle=dict(oracle.lifecycle),
                coverage=dict(oracle.coverage), last_cycle=oracle.cycle,
                max_request_to_result_cycles=max(oracle.durations, default=0))


def check_prefix(raw, plan, expected, *, mathematical=True):
    wanted_plan, wanted_expected = generate()
    check_v4.require(records_sha256(plan) == records_sha256(wanted_plan) and
                     records_sha256(expected) == records_sha256(wanted_expected), "C6_PREFIX_FROZEN_V4_INPUT_IDENTITY")
    operations = plan[1:-1]
    completed_index = max(op["index"] for op in operations if op["case_id"] == "C04_CC64_MULTI_RECYCLE")
    check_v4.require(operations[completed_index]["op"] == "sample", "C6_PREFIX_BOUNDARY_PLAN")
    result_id = operations[completed_index]["result_id"]
    offset = 0
    candidates = []
    for line in raw.splitlines(keepends=True):
        offset += len(line)
        row = line.split()
        if len(row) == 6 and row[0] == b"P" and int(row[2], 16) == result_id:
            candidates.append((offset, int(row[1])))
    check_v4.require(len(candidates) == 1, "C6_PREFIX_BOUNDARY_PUBLICATION_UNIQUE")
    publication_end, cycle = candidates[0]
    # Include every remaining original row on the same actual edge. No
    # observer or OP metadata is manufactured or reordered at the boundary.
    cut = publication_end
    trailing = raw[publication_end:]
    for line in trailing.splitlines(keepends=True):
        row = line.split()
        if len(row) > 1 and row[1].isdigit():
            if int(row[1]) > cycle:
                break
            check_v4.require(int(row[1]) == cycle, "C6_PREFIX_BOUNDARY_TIME_ORDER")
        cut += len(line)
    prefix = raw[:cut]
    check_v4.require(prefix.endswith(b"\n") and not any(line.startswith(b"END ") for line in prefix.splitlines()),
                     "C6_PREFIX_NO_FABRICATED_END")
    # Reuse the frozen v4 front-end validation exactly until its legitimate
    # missing-END stop. This exception is expected solely in this prefix API.
    try:
        check_v4.check(prefix, plan, expected, mathematical=False, identity=False)
    except ValueError as error:
        check_v4.require(str(error) == "C4_MISSING_END_OR_PENDING_READ", "C6_PREFIX_FRONTEND:"+str(error))
    else:
        raise ValueError("C6_PREFIX_UNEXPECTED_COMPLETE_PASS")
    qualified = live_qualification(prefix)
    check_v4.require(qualified["live_at_end"] is None, "C6_PREFIX_LIVE_ACCEPT")
    ledger = [r for r in expected[1:-1] if r["plan_index"] <= completed_index]
    events = [r["event_word"] for r in ledger if r["record"] == "EVENT"]
    samples = [r["result_id"] for r in ledger if r["record"] == "TXN"]
    publications = {r["result_id"] for r in ledger if r["record"] == "TXN" and r["disposition"] == "PUBLISH"}
    read_slots = [r["slot"] for r in ledger if r["record"] == "READ"]
    actual_events, actual_samples, actual_publications, actual_reads = [], [], [], []
    ended_ops = set()
    open_op = None
    read_pending = []
    retired_slots = set()
    for line in prefix.decode("ascii").splitlines()[2:]:
        row = line.split()
        if row[0] == "I": actual_events.append(check_v4.hx(row[2], 64))
        elif row[0] == "J": actual_samples.append(check_v4.hx(row[2], 32))
        elif row[0] == "P": actual_publications.append(check_v4.hx(row[2], 32))
        elif row[0] == "RQ":
            slot = check_v4.dec(row[2], 0, 31)
            actual_reads.append(slot); read_pending.append((int(row[1]), slot))
        elif row[0] == "RY":
            check_v4.require(read_pending, "C6_PREFIX_READ_RESPONSE_WITHOUT_REQUEST")
            request_cycle, slot = read_pending.pop(0)
            check_v4.require(int(row[1]) == request_cycle+1 and int(row[2]) == slot,
                             "C6_PREFIX_READ_RESPONSE_LATENCY_OR_SLOT")
        elif row[0] == "RT":
            retired_slots.add(check_v4.dec(row[2], 0, 31))
        elif row[0] == "OP":
            if row[3] == "END":
                ended_ops.add(int(row[2])); open_op = None
            else:
                open_op = int(row[2])
    check_v4.require(actual_events == events, "C6_PREFIX_EVENT_ACCEPT_SEQUENCE")
    check_v4.require(actual_samples == samples, "C6_PREFIX_SAMPLE_ACCEPT_SEQUENCE")
    check_v4.require(len(actual_publications) == len(publications) and set(actual_publications) == publications,
                     "C6_PREFIX_PUBLICATION_SET")
    check_v4.require(actual_reads == read_slots, "C6_PREFIX_READ_ACCEPT_SEQUENCE")
    check_v4.require(not read_pending, "C6_PREFIX_PENDING_READ")
    check_v4.require(retired_slots == {0, 1, 2, 3}, "C6_PREFIX_FOUR_REAL_RETIREMENT_OBSERVATIONS")
    check_v4.require(set(range(completed_index+1)) <= ended_ops, "C6_PREFIX_COMPLETED_OPERATION_RANGE")
    check_v4.require(open_op in (None, completed_index+1), "C6_PREFIX_OPEN_OPERATION")
    result = dict(status="N32_C_C00_C04_PARTIAL_PREFIX_VALID_ONLY" if mathematical else "N32_C_PREFIX_FAST_LEDGER_VALID_ONLY",
                  original_run_status="FAILED_C05_C06_DRIVER_DEADLOCK_RETAINED",
                  original_capture_sha256=hashlib.sha256(raw).hexdigest(), original_capture_bytes=len(raw),
                  prefix_sha256=hashlib.sha256(prefix).hexdigest(), prefix_bytes=cut,
                  byte_range=[0, cut], final_publication_id=result_id, final_publication_cycle=cycle,
                  completed_plan_indices=[0, completed_index], open_unaccepted_operation=open_op,
                  plan_sha256=records_sha256(plan), expected_sha256=records_sha256(expected),
                  retired_slots=sorted(retired_slots), pending_reads=0,
                  open_operation_scope="C05_CONTROL_DRIVER_BEGUN_WITHOUT_ACCEPT_BEFORE_CUT",
                  live_qualification=qualified, accepted_events=len(events), accepted_samples=len(samples),
                  publications=len(publications), reads=len(read_slots), fabricated_END=False,
                  complete_C_capture=False, task_complete=False, T061_complete=False, physical_STA="NOT_RUN")
    if mathematical:
        result["independent_clocked_math"] = clocked_audit(prefix, require_end=False)
        check_v4.require(result["independent_clocked_math"]["lifecycle"]["retirements"] >= 4,
                         "C6_PREFIX_FOUR_REAL_RETIREMENTS")
    return result


def prefix_mutations(raw, plan, expected):
    baseline = check_prefix(raw, plan, expected, mathematical=False)
    lines = raw.decode("ascii").splitlines(keepends=True)
    victim = next(op["index"] for op in plan[1:-1] if op["op"] == "note_on" and
                  op.get("source") == 3 and op.get("channel") == 15 and op.get("note") == 100)
    candidate = None
    for index, line in enumerate(lines):
        if line.startswith("U "):
            candidate = index
        elif line.startswith("OP ") and line.split()[3] == "END" and int(line.split()[2]) == victim:
            break
    check_v4.require(candidate is not None, "C6_PREFIX_STEAL_MUTATION_POINT")
    changed = lines.copy(); row = changed[candidate].split()
    for field, width in ((4, 1), (5, 1), (6, 10), (7, 32), (8, 8), (9, 4), (10, 4), (11, 32)):
        value, mask = int(row[field],16), (1 << width)-1
        a, b = value & mask, (value >> width) & mask
        row[field] = f"{(value & ~(mask | (mask << width))) | b | (a << width):x}"
    changed[candidate] = " ".join(row)+"\n"
    payload = "".join(changed).encode("ascii")
    try:
        check_prefix(payload, plan, expected, mathematical=False)
    except ValueError as error:
        reason = str(error)
        check_v4.require(reason == "C6_PREFIX_FRONTEND:C4_PUBLIC_ROUTE_IDENTITY_OR_STEAL",
                         "C6_PREFIX_STEAL_MUTATION_DIAGNOSTIC:"+reason)
        return dict(status="N32_C_PREFIX_MUTATIONS_PASS", rejected=1,
                    original_capture_sha256=hashlib.sha256(raw).hexdigest(),
                    prefix_sha256=baseline["prefix_sha256"],
                    mutations=[dict(name="WRONG_33RD_NOTE_STEAL_VICTIM", reason=reason, exit_code=1,
                                    capture_sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))],
                    complete_C_capture=False, task_complete=False)
    raise ValueError("C6_PREFIX_WRONG_STEAL_MISACCEPT")


def reuse_math(result, report_path, report_sha, executed_source, source_sha):
    report_bytes = report_path.read_bytes()
    source_bytes = executed_source.read_bytes()
    check_v4.require(hashlib.sha256(report_bytes).hexdigest() == report_sha and
                     hashlib.sha256(source_bytes).hexdigest() == source_sha,
                     "C6_PREFIX_REUSED_EVIDENCE_IDENTITY")
    old = json.loads(report_bytes)
    check_v4.require(old["status"] == "N32_C_C00_C04_PARTIAL_PREFIX_VALID_ONLY", "C6_PREFIX_REUSED_STATUS")
    for key in ("original_capture_sha256", "prefix_sha256", "prefix_bytes", "byte_range",
                "final_publication_cycle", "final_publication_id", "accepted_events",
                "accepted_samples", "publications", "reads"):
        check_v4.require(old[key] == result[key], "C6_PREFIX_REUSED_BOUNDARY:"+key)

    def engine_dump(text):
        module = ast.parse(text)
        function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "clocked_audit")
        return ast.dump(function, include_attributes=False)

    check_v4.require(engine_dump(source_bytes.decode("utf-8")) ==
                     engine_dump(Path(__file__).read_text(encoding="utf-8")), "C6_PREFIX_REUSED_ENGINE_CHANGED")
    check_v4.require(old["independent_clocked_math"]["lifecycle"]["retirements"] >= 4 and
                     old["live_qualification"]["live_at_end"] is None, "C6_PREFIX_REUSED_MATH_SCOPE")
    result["independent_clocked_math"] = old["independent_clocked_math"]
    result["status"] = "N32_C_C00_C04_PARTIAL_PREFIX_VALID_ONLY"
    result["reused_math_execution"] = dict(status="REUSED", report=str(report_path), report_sha256=report_sha,
                                          executed_checker=str(executed_source), executed_checker_sha256=source_sha,
                                          engine_AST_identical=True,
                                          new_execution_scope="BOUNDARY_FULL_CYCLE_READ_DRAIN_AND_FOUR_RT_FAST_INCREMENT_ONLY")
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ("input", "plan", "expected", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--fast-only", action="store_true")
    parser.add_argument("--mutations-only", action="store_true")
    parser.add_argument("--reuse-math-report", type=Path)
    parser.add_argument("--reuse-report-sha256")
    parser.add_argument("--reuse-executed-source", type=Path)
    parser.add_argument("--reuse-source-sha256")
    args = parser.parse_args()
    try:
        raw, plan, expected = args.input.read_bytes(), read_jsonl(args.plan), read_jsonl(args.expected)
        if args.mutations_only:
            result = prefix_mutations(raw, plan, expected)
        else:
            result = check_prefix(raw, plan, expected,
                                  mathematical=not args.fast_only and args.reuse_math_report is None)
            if args.reuse_math_report is not None:
                check_v4.require(all((args.reuse_report_sha256, args.reuse_executed_source, args.reuse_source_sha256)),
                                 "C6_PREFIX_REUSED_ARGUMENTS")
                result = reuse_math(result, args.reuse_math_report, args.reuse_report_sha256,
                                    args.reuse_executed_source, args.reuse_source_sha256)
        result["executed_checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        code = 0
    except (ValueError, OSError, UnicodeError, KeyError, IndexError) as error:
        result, code = dict(status="REJECT", reason=str(error)), 1
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
