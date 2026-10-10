"""Complete N16 time/tag/high-slot counterexamples, retaining original logs."""
import argparse
import hashlib
import json
from pathlib import Path

from b2d_check import check


def damaged_capture(raw, tag, field, change, *, slot=None):
    lines = raw.decode("ascii").splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(tag + " ")
                 and (slot is None or (int(line.split()[3]) == slot if tag == "L"
                                      else int(line.split()[2], 16) & 15 == slot)))
    row = lines[index].split()
    hexadecimal = (tag, field) in (("G", 2), ("U", 9), ("C", 3), ("Y", 3))
    value = int(row[field], 16 if hexadecimal else 10)
    row[field] = format(value ^ change, "x") if hexadecimal else str(value + change)
    lines[index] = " ".join(row)
    if field == 1:
        body = [x for x in lines[1:] if "$finish called" not in x]
        body.sort(key=lambda x: int(x.split()[1]))
        lines = lines[:1] + body + [x for x in lines[1:] if "$finish called" in x]
    return ("\n".join(lines) + "\n").encode("ascii")


def main():
    parser = argparse.ArgumentParser()
    for name in ("normal", "slow", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    normal, slow = args.normal.read_bytes(), args.slow.read_bytes()
    good, late = check(normal), check(slow)
    if not good["sample_deadline_qualified"] or late["sample_deadline_qualified"]:
        raise ValueError("DEADLINE_BOUNDARY_NOT_EXERCISED")
    specs = (
        ("advance_early", "A", 1, -1, None, "ADVANCE_EDGE_OR_MISSING"),
        ("advance_late", "A", 1, 1, None, "ADVANCE_EDGE_OR_MISSING"),
        ("first_early", "F", 1, -1, None, "FIRST_VALID_CLOCK_OR_MISSING"),
        ("first_late", "F", 1, 1, None, "FIRST_VALID_CLOCK_OR_MISSING"),
        ("last_lane_early", "L", 1, -1, 15, "LANE_CLOCK_OR_MISSING"),
        ("last_lane_late", "L", 1, 1, 15, "LANE_CLOCK_OR_MISSING"),
        ("high_slot_generation", "G", 2, 16, 15, "B1_FULL_TAG_CONTEXT_CONTROL_PEDAL"),
        ("route_source", "U", 9, 1, None, "ROUTER_LIFECYCLE_OR_IDENTITY"),
        ("snapshot_high_occupancy", "C", 3, 1 << 15, None, "BACKEND_FULL_SNAPSHOT"),
        ("publish_pcm", "P", 3, 1, None, "OUTPUT_BACKPRESSURE_STABILITY"),
        ("bank_context", "Y", 3, 1, None, "BANK_COMMIT_READBACK"),
        ("late_flag_false", "F", 5, -1, None, "PCM_OR_DEADLINE"),
    )
    reports = []
    for name, tag, field, delta, slot, reason in specs:
        raw = damaged_capture(slow if name == "late_flag_false" else normal,
                              tag, field, delta, slot=slot)
        (args.output / (name + ".txt")).write_bytes(raw)
        try:
            check(raw)
        except ValueError as error:
            if str(error) != reason:
                raise ValueError(f"WRONG_REJECTION:{name}:{error}") from error
            reports.append(dict(name=name, expected=reason, actual=str(error),
                                sha256=hashlib.sha256(raw).hexdigest()))
        else:
            raise ValueError("MUTANT_ACCEPTED:" + name)
    result = dict(exit_code=0, complete_N16_negatives=reports,
                  normal_sha256=hashlib.sha256(normal).hexdigest(),
                  slow_sha256=hashlib.sha256(slow).hexdigest())
    (args.output / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
