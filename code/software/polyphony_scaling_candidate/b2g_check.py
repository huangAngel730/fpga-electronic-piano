"""Focused N32 real-ROM saturation coverage; unchanged B2a math/time oracle."""
import argparse
import json
from pathlib import Path

from b2_check import check as reference_check

STATUS = "B2G_N32_REAL_SATURATION_PASS_T061_PARTIAL"
RESPONSES = (1, 8)


def check(raw):
    if raw.splitlines()[0:1] not in [[f"B2 32 {r} 0".encode()] for r in RESPONSES]:
        raise ValueError("N32_SATURATION_HEADER")
    # All lane values, envelopes, phase, wave, gain, output, identities and
    # source-clock edges are independently verified BEFORE counting coverage.
    # Observed PCM never feeds the expected PCM of this oracle.
    result = reference_check(raw)
    coverage = result["coverage"]
    if not coverage.get("positive_clips") or not coverage.get("negative_clips"):
        raise ValueError("BOTH_SATURATION_SIGNS_REQUIRED")
    slots = set()
    totals, live = [], {}
    exact_outputs = {"positive": 0, "negative": 0, "unclipped_nonzero": 0,
                     "silence": 0}
    for line in raw.decode("ascii").splitlines()[1:]:
        row = line.split()
        if row[0] in ("C", "R", "X"):
            live = {}
        elif row[0] == "L":
            slot, pcm = int(row[3]), int(row[9])
            live[slot] = pcm
            if pcm:
                slots.add(slot)
        elif row[0] == "O":
            total = sum(live.values())
            totals.append(total)
            key = ("positive" if total > 8388607 else "negative" if total < -8388608
                   else "unclipped_nonzero" if total else "silence")
            exact_outputs[key] += 1
    if slots != set(range(32)) or not all(exact_outputs.values()):
        raise ValueError("ALL32_AND_UNCLIPPED_SILENT_REQUIRED")
    if exact_outputs["positive"] != coverage["positive_clips"] or exact_outputs["negative"] != coverage["negative_clips"]:
        raise ValueError("SATURATION_COVERAGE_DISAGREES")
    result.update(status=STATUS, verified_output_classes=exact_outputs,
                  verified_accumulator_min=min(totals),
                  verified_accumulator_max=max(totals), nonzero_slots=sorted(slots),
                  sample_deadline_qualified=result["over_833_results"] == 0,
                  coverage_counting="only after independent reference accepts full capture",
                  N32_event_router_integration="NOT_RUN_IN_THIS_STAGE",
                  N32_long_ADSR_retirement="NOT_RUN_IN_THIS_STAGE")
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
