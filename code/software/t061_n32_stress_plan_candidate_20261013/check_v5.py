"""C v5: live acceptance qualification ahead of the frozen v4 audit.

Only this successor changes. The capture, v4 plan, mathematics and original
checker remain byte-identical. A correct value from a future/expired ID is
never sufficient evidence of a currently accepted result transaction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_v4
from generate_v4 import generate
from n32c_common import read_jsonl, records_sha256


def live_qualification(raw: bytes) -> dict:
    live = None
    first = False
    first_cycle = None
    last_k_cycle = None
    last_k_publish = None
    held = False
    ready = None
    counts = {"accepts": 0, "publications": 0, "qualified_K": 0,
              "cancel_edges": 0, "reset_edges": 0, "abort_edges": 0}
    for line in raw.decode("ascii").splitlines():
        row = line.split()
        if not row:
            continue
        tag = row[0]
        if tag == "D":
            check_v4.require(len(row) == 11, "C5_DRIVE_SCHEMA")
            ready = check_v4.dec(row[8], 0, 1)
            if row[2] == "0":
                live, first, first_cycle, last_k_cycle, last_k_publish, held = None, False, None, None, None, False
            continue
        if tag == "J":
            check_v4.require(len(row) == 3, "C5_ACCEPT_SCHEMA")
            check_v4.require(live is None, "C5_OVERLAPPING_LIVE_ACCEPT")
            live, first = check_v4.hx(row[2], 32), False
            first_cycle, last_k_cycle, last_k_publish, held = None, None, None, False
            counts["accepts"] += 1
        elif tag in ("X", "R", "Z", "RA"):
            if held:
                check_v4.require(check_v4.dec(row[1]) <= last_k_cycle+1,
                                 "C5_HOLD_PUBLIC_OBSERVATION_GAP")
            live, first, first_cycle, last_k_cycle, last_k_publish, held = None, False, None, None, None, False
            if tag != "RA":
                counts[{"X": "cancel_edges", "R": "reset_edges", "Z": "abort_edges"}[tag]] += 1
        elif tag in ("F", "K", "P"):
            check_v4.require(len(row) == (8 if tag == "K" else 6), "C5_RESULT_SCHEMA")
            check_v4.require(live is not None, "C5_RESULT_WITHOUT_LIVE_ACCEPT")
            check_v4.require(check_v4.hx(row[2], 32) == live, "C5_RESULT_LIVE_ID")
            if tag == "F":
                check_v4.require(not first, "C5_DUPLICATE_FIRST_VALID")
                first = True
                first_cycle = check_v4.dec(row[1])
            elif tag == "K":
                check_v4.require(first, "C5_PUBLIC_RESULT_BEFORE_FIRST_VALID")
                cycle = check_v4.dec(row[1])
                if last_k_cycle is None:
                    check_v4.require(cycle == first_cycle, "C5_FIRST_VALID_PUBLIC_OBSERVATION")
                else:
                    check_v4.require(cycle != last_k_cycle, "C5_DUPLICATE_PUBLIC_RESULT_CYCLE")
                    if held:
                        check_v4.require(cycle == last_k_cycle+1, "C5_HOLD_PUBLIC_OBSERVATION_GAP")
                publish = check_v4.dec(row[7], 0, 1)
                check_v4.require(ready is not None and publish == ready, "C5_PUBLIC_READY_HANDSHAKE")
                last_k_cycle, last_k_publish, held = cycle, publish, not bool(publish)
                counts["qualified_K"] += 1
            else:
                check_v4.require(first, "C5_PUBLISH_BEFORE_FIRST_VALID")
                check_v4.require(last_k_cycle == check_v4.dec(row[1]) and last_k_publish == 1 and ready == 1,
                                 "C5_PUBLISH_WITHOUT_PUBLIC_HANDSHAKE")
                counts["publications"] += 1
                live, first, first_cycle, last_k_cycle, last_k_publish, held = None, False, None, None, None, False
    return {**counts, "live_at_end": live}


def check(raw, plan, expected, *, mathematical=True, identity=True):
    qualified = live_qualification(raw)
    result = check_v4.check(raw, plan, expected, mathematical=mathematical, identity=identity)
    check_v4.require(qualified["live_at_end"] is None, "C5_END_WITH_LIVE_ACCEPT")
    result["live_qualification"] = qualified
    result["checker_successor"] = "V5_LIVE_ACCEPTANCE_QUALIFIED"
    return result


def mutations(raw, plan, expected):
    # Keep the exact v4 16 complete-capture mutations and their original
    # diagnostics, then add only the newly identified successor conditions.
    result = check_v4.mutations(raw, plan, expected)
    original = raw.decode("ascii").splitlines(keepends=True)
    additions = []

    def run(name, changed, diagnostic, explanation):
        payload = "".join(changed).encode("ascii")
        check_v4.require(payload != raw, "C5_MUTATION_NO_CHANGE:"+name)
        try:
            check(payload, plan, expected, mathematical=False, identity=False)
        except ValueError as error:
            reason = str(error)
            check_v4.require(reason.startswith(diagnostic),
                             "C5_MUTATION_WRONG_DIAGNOSTIC:"+name+":"+reason)
            additions.append(dict(name=name, exit_code=1, reason=reason,
                                  capture_sha256=hashlib.sha256(payload).hexdigest(),
                                  bytes=len(payload), explanation=explanation))
            return
        raise ValueError("C5_MUTATION_MISACCEPT:"+name)

    k_indices = [i for i, line in enumerate(original) if line.startswith("K ")]
    check_v4.require(k_indices, "C5_NO_PUBLIC_RESULT")
    first_k = k_indices[0]
    target = original[first_k].split()
    source = next(original[i].split() for i in k_indices
                  if original[i].split()[3:5] != target[3:5])
    changed = original.copy(); row = target.copy(); row[3:5] = source[3:5]
    changed[first_k] = " ".join(row)+"\n"
    run("WRONG_BEAT_PCM", changed, "C4_INPUT_GOLDEN_PCM",
        "Another real publication's stereo PCM is substituted at the current live ID.")

    # The normal C ledger has no clipped=1 frame. Exchanging two normal zero
    # values would not mutate anything. Instead, move a complete authentic
    # K row, including its correct clip value, to an invalid post-cancel edge.
    cancel_index = next(i for i, line in enumerate(original) if line.startswith("X "))
    cancel_cycle = original[cancel_index].split()[1]
    changed = original.copy(); row = target.copy(); row[1] = cancel_cycle
    changed.insert(cancel_index+1, " ".join(row)+"\n")
    run("WRONG_BEAT_CLIPPED_VALIDITY", changed, "C5_RESULT_WITHOUT_LIVE_ACCEPT",
        "A genuine complete PCM/clip payload is replayed after cancellation. This checks clip qualification; it does not claim exchange of differing normal clip values.")

    hold_id = next(op["result_id"] for op in plan[1:-1]
                   if op.get("op") == "sample" and op.get("min_hold_cycles", 0))
    changed = [line for line in original if not (line.startswith("K ") and
               int(line.split()[2], 16) == hold_id and line.split()[7] == "0")]
    run("REQUIRED_HOLD_DROP", changed, "C5_FIRST_VALID_PUBLIC_OBSERVATION",
        "Remove every authentic valid/no-handshake observation from the required HOLD transaction.")

    read_index = next(i for i, line in enumerate(original) if line.startswith("RY "))
    changed = original.copy(); row = changed[read_index].split(); row[3] = f"{int(row[3], 16)^1:x}"
    changed[read_index] = " ".join(row)+"\n"
    run("BAD_READ_COMMITTED_CONTEXT", changed, "C4_READ_COMMITTED_CONTEXT",
        "Change one bit of the pre-NBA public read response while preserving the request and latency.")

    accept_index = next(i for i, line in enumerate(original) if line.startswith("J "))
    accept_cycle = original[accept_index].split()[1]
    changed = original.copy(); row = target.copy(); row[1] = accept_cycle
    changed.insert(accept_index, " ".join(row)+"\n")
    run("RESULT_BEFORE_ACCEPT", changed, "C5_RESULT_WITHOUT_LIVE_ACCEPT",
        "Use the future legal ID and its authentic correct PCM/clip, immediately before its J acceptance.")

    future = next(original[i].split() for i in k_indices
                  if original[i].split()[2] != target[2])
    changed = original.copy(); row = future.copy(); row[1] = target[1]
    changed.insert(first_k, " ".join(row)+"\n")
    run("FUTURE_VALID_ID_DURING_OTHER_LIVE", changed, "C5_RESULT_LIVE_ID",
        "Insert a future legal ID with its correct complete payload while another request is live.")
    changed = original.copy(); row = target.copy(); row[1] = accept_cycle
    changed.insert(accept_index+1, " ".join(row)+"\n")
    run("K_BEFORE_FIRST_VALID", changed, "C5_PUBLIC_RESULT_BEFORE_FIRST_VALID",
        "Correct live ID/PCM/clip is presented after J but before its independent first-valid edge.")
    changed = original.copy(); changed.insert(first_k+1, changed[first_k])
    run("DUPLICATE_K", changed, "C5_DUPLICATE_PUBLIC_RESULT_CYCLE",
        "Duplicate a complete authentic K row on its same edge; one live result may have only one K per edge.")
    result["mutations"] += additions
    result["rejected"] = len(result["mutations"])
    result["checker_successor"] = "V5_LIVE_ACCEPTANCE_QUALIFIED"
    result["new_rejected"] = len(additions)
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ("input", "plan", "expected", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--mutations-only", action="store_true")
    args = parser.parse_args()
    try:
        raw, plan, expected = args.input.read_bytes(), read_jsonl(args.plan), read_jsonl(args.expected)
        if args.mutations_only:
            wanted_plan, wanted_expected = generate()
            check_v4.require(records_sha256(plan) == records_sha256(wanted_plan) and
                             records_sha256(expected) == records_sha256(wanted_expected),
                             "C5_MUTATION_INPUT_IDENTITY")
            check(raw, plan, expected, mathematical=False, identity=False)
            result = mutations(raw, plan, expected)
        else:
            result = check(raw, plan, expected)
        code = 0
    except (ValueError, OSError, UnicodeError, KeyError, IndexError, StopIteration) as error:
        result, code = dict(status="REJECT", reason=str(error)), 1
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
