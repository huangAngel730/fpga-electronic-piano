"""Full N32 R1 lifecycle of the pinned hybrid candidate, not physical STA."""
import argparse
import json
from pathlib import Path

from b2c_check import check as reference_check

STATUS = "B2H_N32_LONG_LIFECYCLE_PASS_T061_PARTIAL"


def check(raw):
    if raw.splitlines()[0:1] != [b"B2C 32 1 1"]:
        raise ValueError("N32_LONG_HEADER")
    result = reference_check(raw, sizes=(32,), responses=(1,),
                             identity_controls=True, extra_long_events=1)
    # Coverage is counted ONLY after independent route/math/time verification.
    # A reset starts another domain; it must not look like real retirement.
    previous = None
    retirements = [0]*32
    states = [set() for _ in range(32)]
    triple_active = high_pair_after_release = cadence = 0
    previous_request = None
    for line in raw.decode("ascii").splitlines()[1:]:
        row = line.split()
        if row[0] == "R":
            previous = previous_request = None
        elif row[0] == "U":
            occupied, releasing = int(row[4], 16), int(row[5], 16)
            if previous is not None:
                old_occupied, old_releasing = previous
                retired = old_occupied & old_releasing & ~occupied
                for i in range(32):
                    retirements[i] += bool(retired & (1 << i))
            previous = occupied, releasing
        elif row[0] == "J":
            cycle = int(row[1])
            cadence += previous_request is not None and cycle-previous_request == 833
            previous_request = cycle
        elif row[0] == "L":
            states[int(row[3])].add(int(row[10]))
        elif row[0] == "C":
            occupied = int(row[3], 16)
            source, channel = int(row[8], 16), int(row[9], 16)
            identity = all(((source >> (i*4)) & 15) == 15 and
                           ((channel >> (i*4)) & 15) == 15 for i in (3, 11, 27))
            if identity:
                triple_active += all(occupied & (1 << i) for i in (3, 11, 27))
                high_pair_after_release += bool(occupied & (1 << 3) and occupied & (1 << 27)
                                               and not occupied & (1 << 11))
    if not all(retirements) or sum(retirements) != result["lifecycle"]["retirements"]:
        raise ValueError("ALL32_REAL_RETIREMENT_COVERAGE")
    if states[31] != set(range(5)):
        raise ValueError("SLOT31_FULL_ADSR_REQUIRED")
    if not triple_active or not high_pair_after_release:
        raise ValueError("THREE_SHARED_IDENTITIES_RELEASE_REQUIRED")
    if cadence < 10000:
        raise ValueError("LONG_833_CADENCE_REQUIRED")
    if result["deadline_misses"]:
        raise ValueError("N32_LONG_DEADLINE_MISS")
    result.update(status=STATUS, sample_deadline_qualified=True,
                  real_retirements_by_slot=retirements,
                  public_ADSR_states_by_slot=[sorted(s) for s in states],
                  same_identity_3_11_27_active_frames=triple_active,
                  same_identity_11_retired_3_27_active_frames=high_pair_after_release,
                  exact_833_request_intervals=cadence,
                  N32_fixture_long_lifecycle="VERIFIED",
                  general_sustained_performance="NOT_VERIFIED",
                  production_N32="NOT_ADMITTED")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result, code = check(args.input.read_bytes()), 0
    except (ValueError, OSError, UnicodeError) as error:
        result, code = dict(status="REJECT", reason=str(error)), 1
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
