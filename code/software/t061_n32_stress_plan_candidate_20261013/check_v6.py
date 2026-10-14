"""C v6 independent reset suffix checker and authentic capture mutations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_v4
from check_v5 import live_qualification
from check_prefix_v6 import clocked_audit
from generate_v6 import generate
from n32c_common import read_jsonl, records_sha256


def core_bytes(raw):
    """Validate/remove only the simulator's non-capture $finish footer."""
    lines = raw.splitlines(keepends=True)
    if lines and re.fullmatch(rb".*[/\\]tb_c_n32_r1_v6\.sv:[0-9]+: \$finish called at [0-9]+ \(1ps\)\r?\n?", lines[-1]):
        return b"".join(lines[:-1])
    return raw


def check(raw, plan, expected, *, mathematical=True, identity=True):
    if identity:
        wanted_plan, wanted_expected = generate("SHORT_SUFFIX")
        check_v4.require(records_sha256(plan) == records_sha256(wanted_plan) and
                         records_sha256(expected) == records_sha256(wanted_expected),
                         "C6_SUFFIX_INPUT_IDENTITY")
    qualified = live_qualification(raw)
    core = core_bytes(raw)
    ledger = check_v4.check(core, plan, expected, mathematical=False, identity=False)
    check_v4.require(qualified["live_at_end"] is None, "C6_SUFFIX_END_LIVE_ACCEPT")
    result = dict(status="N32_C_STRESS_PASS_T061_PARTIAL" if mathematical else "N32_C_SUFFIX_FAST_LEDGER_VALID_ONLY",
                  profile="SHORT_SUFFIX_RESET_FRESH_INPUTS_C05_C09_ONLY",
                  prefix_continuity_claim=False, complete_C_capture=False,
                  independent_initial_state="RESET_FRESH_FOUR_VOICE_EVENTS",
                  live_qualification=qualified, publications=ledger["published"],
                  capture_sha256=hashlib.sha256(raw).hexdigest(), capture_bytes=len(raw),
                  plan_sha256=records_sha256(plan), expected_sha256=records_sha256(expected),
                  task_complete=False, T061_complete=False, physical_STA="NOT_RUN")
    if mathematical:
        result["independent_clocked_math"] = clocked_audit(core, require_end=True)
    return result


def mutations(raw, plan, expected):
    original = raw.decode("ascii").splitlines(keepends=True)
    results = []

    def location(tag):
        return next(i for i, line in enumerate(original) if line.startswith(tag+" "))

    def run(name, changed, diagnostic, scope="SOFTWARE_MUTATION_OF_COMPLETE_REAL_SUFFIX_CAPTURE"):
        payload = "".join(changed).encode("ascii")
        check_v4.require(payload != raw, "C6_MUTATION_NO_CHANGE:"+name)
        try:
            check(payload, plan, expected, mathematical=False, identity=False)
        except ValueError as error:
            reason = str(error)
            check_v4.require(reason.startswith(diagnostic), "C6_MUTATION_WRONG_DIAGNOSTIC:"+name+":"+reason)
            results.append(dict(name=name, exit_code=1, reason=reason, scope=scope,
                                capture_sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload)))
            return
        raise ValueError("C6_MUTATION_MISACCEPT:"+name)

    for tag, dropped, duplicated in (("I", "C4_OPERATION_ACCEPT_COUNT", "C4_OPERATION_ACCEPT_COUNT"),
                                    ("J", "C5_RESULT_WITHOUT_LIVE_ACCEPT", "C5_OVERLAPPING_LIVE_ACCEPT"),
                                    ("P", "C5_OVERLAPPING_LIVE_ACCEPT", "C5_RESULT_WITHOUT_LIVE_ACCEPT")):
        index = location(tag)
        changed = original.copy(); del changed[index]
        run("DROP_"+tag, changed, dropped)
        changed = original.copy(); changed.insert(index, changed[index])
        run("DUPLICATE_"+tag, changed, duplicated)
    first_k = location("K")
    target = original[first_k].split()
    for name, field, diagnostic in (("WRONG_RESULT_ID", 2, "C5_RESULT_LIVE_ID"),
                                    ("LEFT_1LSB", 3, "C4_INPUT_GOLDEN_PCM"),
                                    ("RIGHT_1LSB", 4, "C4_INPUT_GOLDEN_PCM"),
                                    ("CLIPPED_FLIP", 6, "C4_CLIPPED_ALIGNMENT")):
        changed = original.copy(); row = target.copy()
        row[field] = f"{int(row[field],16)^0x80000000:x}" if field == 2 else str(1-int(row[field]) if field == 6 else int(row[field])+1)
        changed[first_k] = " ".join(row)+"\n"
        run(name, changed, diagnostic)
    changed = original.copy(); row = target.copy(); del row[6]
    changed[first_k] = " ".join(row)+"\n"
    run("CLIPPED_MISSING", changed, "C5_RESULT_SCHEMA")
    k_indices = [i for i, line in enumerate(original) if line.startswith("K ")]
    proxy = next(i for i in k_indices if original[i].split()[3:5] == ["-8388608", "-8388608"] and original[i].split()[6] == "0")
    changed = original.copy(); row = changed[proxy].split(); row[6] = "1"
    changed[proxy] = " ".join(row)+"\n"
    run("CLIPPED_FULLSCALE_PROXY", changed, "C4_CLIPPED_ALIGNMENT")
    source = next(original[i].split() for i in k_indices if original[i].split()[3:5] != target[3:5])
    changed = original.copy(); row = target.copy(); row[3:5] = source[3:5]
    changed[first_k] = " ".join(row)+"\n"
    run("WRONG_BEAT_PCM", changed, "C4_INPUT_GOLDEN_PCM")
    hold_id = next(op["result_id"] for op in plan[1:-1] if op.get("min_hold_cycles", 0))
    changed = [line for line in original if not (line.startswith("K ") and int(line.split()[2],16) == hold_id and line.split()[7] == "0")]
    run("REQUIRED_HOLD_DROP", changed, "C5_FIRST_VALID_PUBLIC_OBSERVATION")
    index = location("RY"); changed = original.copy(); row = changed[index].split(); row[3] = f"{int(row[3],16)^1:x}"
    changed[index] = " ".join(row)+"\n"
    run("BAD_READ_COMMITTED_CONTEXT", changed, "C4_READ_COMMITTED_CONTEXT")
    candidate = None
    for i, line in enumerate(original):
        if line.startswith("U "): candidate = i
        elif line.startswith("OP ") and line.split()[3] == "END" and candidate is not None:
            if plan[int(line.split()[2])+1]["op"] == "note_on": break
    check_v4.require(candidate is not None, "C6_IDENTITY_MUTATION_POINT")
    changed = original.copy(); row = changed[candidate].split(); row[9] = f"{int(row[9],16)^1:x}"
    changed[candidate] = " ".join(row)+"\n"
    run("WRONG_SLOT_IDENTITY", changed, "C4_PUBLIC_ROUTE_IDENTITY_OR_STEAL")
    accept = location("J"); accept_cycle = original[accept].split()[1]
    changed = original.copy(); row = target.copy(); row[1] = accept_cycle
    changed.insert(accept, " ".join(row)+"\n")
    run("RESULT_BEFORE_ACCEPT", changed, "C5_RESULT_WITHOUT_LIVE_ACCEPT")
    changed = original.copy(); changed.insert(accept+1, " ".join(row)+"\n")
    run("K_BEFORE_FIRST_VALID", changed, "C5_PUBLIC_RESULT_BEFORE_FIRST_VALID")
    future = next(original[i].split() for i in k_indices if original[i].split()[2] != target[2])
    changed = original.copy(); row = future.copy(); row[1] = target[1]
    changed.insert(first_k, " ".join(row)+"\n")
    run("FUTURE_VALID_ID_DURING_OTHER_LIVE", changed, "C5_RESULT_LIVE_ID")
    changed = original.copy(); changed.insert(first_k+1, changed[first_k])
    run("DUPLICATE_K", changed, "C5_DUPLICATE_PUBLIC_RESULT_CYCLE")
    for tag, name in (("X", "STALE_AFTER_CANCEL"), ("R", "STALE_AFTER_RESET"), ("X", "WRONG_BEAT_CLIPPED_VALIDITY")):
        index = location(tag) if tag == "X" else [i for i, line in enumerate(original) if line.startswith("R ")][-1]
        changed = original.copy(); row = target.copy(); row[1] = original[index].split()[1]
        changed.insert(index+1, " ".join(row)+"\n")
        run(name, changed, "C5_RESULT_WITHOUT_LIVE_ACCEPT")
    return dict(status="N32_C_MUTATIONS_PASS", profile="SHORT_SUFFIX_ONLY", rejected=len(results),
                mutations=results, original_sha256=hashlib.sha256(raw).hexdigest(),
                prefix_steal_mutation="SEPARATE_ORIGINAL_PREFIX_QUALIFICATION",
                wrongbeat_clip_scope="AUTHENTIC_CLIP_PAYLOAD_QUALIFICATION_NORMAL_VALUES_ALL_ZERO",
                left_right_swap="NOT_APPLICABLE_EQUAL_STEREO_SINGLE_CHANNEL_1LSB_USED")


def main():
    parser = argparse.ArgumentParser()
    for name in ("input", "plan", "expected", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--mutations-only", action="store_true")
    args = parser.parse_args()
    try:
        raw, plan, expected = args.input.read_bytes(), read_jsonl(args.plan), read_jsonl(args.expected)
        if args.mutations_only:
            check(raw, plan, expected, mathematical=False)
            result = mutations(raw, plan, expected)
        else:
            result = check(raw, plan, expected)
        code = 0
    except (ValueError, OSError, UnicodeError, KeyError, IndexError, StopIteration) as error:
        result, code = dict(status="REJECT", reason=str(error)), 1
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
