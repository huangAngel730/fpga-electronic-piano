"""Exact FULL C00-C09 successor; never upgrade prefix/suffix composition."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_v4
import check_v6
from generate_v6 import build_v6_operations, generate
from full_steal_successor import mutate_full_steal
from n32c_common import read_jsonl, records_sha256


def input_identity(plan, expected):
    check_v4.require(plan[0].get("segment") == "FULL" and
                     expected[0].get("segment") == "FULL", "C_FULL_SEGMENT_REQUIRED")
    cases = {op["case_id"].split("_")[0] for op in plan[1:-1]}
    check_v4.require(cases == {"C%02d" % i for i in range(10)}, "C_FULL_CASE_SET")
    wanted_plan, wanted_expected = generate("FULL")
    check_v4.require(records_sha256(plan) == records_sha256(wanted_plan) and
                     records_sha256(expected) == records_sha256(wanted_expected),
                     "C_FULL_INPUT_IDENTITY")


def check(raw, plan, expected, *, mathematical=True):
    input_identity(plan, expected)
    # The old routine performs the full ordered OP ledger, live F/K/P and END
    # checks and independent clocked math. Its SHORT identity is bypassed only
    # after the exact FULL input pair above is independently reconstructed.
    result = check_v6.check(raw, plan, expected, mathematical=mathematical, identity=False)
    if mathematical:
        check_v4.require(result["independent_clocked_math"]["lifecycle"]["retirements"] >= 4,
                         "C_FULL_REAL_RETIREMENT_REQUIRED")
    result.update(profile="FULL_C00_C09_SINGLE_CONTINUOUS_CAPTURE",
                  complete_C_capture=True, single_continuous_full_C_run=True,
                  capture_composition=False, prefix_continuity_claim=False,
                  independent_initial_state="ORIGINAL_FULL_INPUT_RESET_SEQUENCE",
                  cases=["C%02d" % i for i in range(10)],
                  operations=len(plan)-2,
                  status=("N32_C_STRESS_PASS_T061_PARTIAL" if mathematical
                          else "N32_C_FULL_FAST_LEDGER_VALID_ONLY"))
    rows = [line.split() for line in raw.decode("ascii").splitlines() if line.startswith("K ")]
    result["observed_payload_scope"] = {
        "clipped_values": sorted({int(row[6]) for row in rows}),
        "clipped_one_observation_edges": sum(int(row[6]) for row in rows),
        "unequal_stereo_observation_edges": sum(row[3] != row[4] for row in rows),
        "fullscale_without_clip_observation_edges": sum(
            row[3:5] == ["-8388608", "-8388608"] and row[6] == "0" for row in rows)}
    return result


def mutations(raw, plan, expected):
    # Preserve all 23 existing complete-capture rejection checks, now applied
    # to the new authentic FULL capture, without reusing old mutant results.
    report = check_v6.mutations(raw, plan, expected)
    original = raw.decode("ascii").splitlines(keepends=True)
    for item in report["mutations"]:
        item["scope"] = "SOFTWARE_MUTATION_OF_COMPLETE_REAL_FULL_CAPTURE"
    changed, metadata = mutate_full_steal(original, build_v6_operations("FULL"))
    payload = "".join(changed).encode("ascii")
    try:
        check_v6.check(payload, plan, expected, mathematical=False, identity=False)
    except ValueError as error:
        reason = str(error)
        check_v4.require(reason == "C4_PUBLIC_ROUTE_IDENTITY_OR_STEAL",
                         "C_FULL_STEAL_DIAGNOSTIC:" + reason)
        report["mutations"].append({"name": "WRONG_STEAL_VICTIM_FULL", "exit_code": 1,
            "reason": reason, "capture_sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload), "scope": "SOFTWARE_MUTATION_OF_COMPLETE_REAL_FULL_CAPTURE",
            "mutation_point": metadata})
    else:
        raise ValueError("C_FULL_STEAL_MUTATION_MISACCEPT")
    report.update(profile="FULL_C00_C09_SINGLE_CONTINUOUS_CAPTURE",
                  rejected=len(report["mutations"]),
                  prefix_steal_mutation="REPLACED_BY_NEW_FULL_CAPTURE_STEAL_MUTATION",
                  evidence_kind="SOFTWARE_CAPTURE_MUTATIONS_NOT_RTL_MUTANTS")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "plan", "expected", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--mutations-only", action="store_true")
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        plan, expected = read_jsonl(args.plan), read_jsonl(args.expected)
        if args.mutations_only:
            check(raw, plan, expected, mathematical=False)
            result = mutations(raw, plan, expected)
        else:
            result = check(raw, plan, expected)
        code = 0
    except (ValueError, OSError, UnicodeError, KeyError, IndexError, StopIteration) as error:
        result, code = {"status": "REJECT", "reason": str(error)}, 1
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
