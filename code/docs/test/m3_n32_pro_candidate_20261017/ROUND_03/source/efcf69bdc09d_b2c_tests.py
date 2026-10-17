"""Exact N4 semantic trace comparison and complete N8 capture counterexamples."""
import argparse
import json
from pathlib import Path

from b2c_check import check


def rows(raw):
    return [line for line in raw.decode("ascii").splitlines()[1:]
            if "$finish called" not in line]


def main():
    parser = argparse.ArgumentParser()
    for name in ("n4", "n8", "prior", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    n4, n8 = args.n4.read_bytes(), args.n8.read_bytes()
    check(n4)
    check(n8)
    # Extra U transitions fixed by full-width observation are checked by the
    # independent router oracle. All old U transitions must still be identical.
    old = rows(args.prior.read_bytes())
    new = rows(n4)
    old_u = {line for line in old if line.startswith("U ")}
    new_u = {line for line in new if line.startswith("U ")}
    if not old_u <= new_u or [x for x in old if not x.startswith("U ")] != [x for x in new if not x.startswith("U ")]:
        raise ValueError("N4_PRIOR_TRACE_CHANGED")
    original = n8.decode("ascii").splitlines()
    tests = []
    specifications = (("A", 1, 1, "ADVANCE_EDGE_OR_MISSING"),
                      ("F", 1, -1, "FIRST_VALID_CLOCK_OR_MISSING"),
                      ("L", 1, 1, "LANE_CLOCK_OR_MISSING"),
                      ("G", 2, 8, "B1_FULL_TAG_CONTEXT_CONTROL_PEDAL"),
                      ("U", 9, 1, "ROUTER_LIFECYCLE_OR_IDENTITY"),
                      ("C", 3, 1, "BACKEND_FULL_SNAPSHOT"),
                      ("P", 3, 1, "OUTPUT_BACKPRESSURE_STABILITY"),
                      ("Y", 3, 1, "BANK_COMMIT_READBACK"))
    for tag, field, change, reason in specifications:
        damaged = original.copy()
        index = next(i for i, line in enumerate(damaged) if line.startswith(tag + " "))
        row = damaged[index].split()
        hexadecimal = (tag, field) in (("G", 2), ("U", 9), ("C", 3), ("Y", 3))
        value = int(row[field], 16 if hexadecimal else 10)
        row[field] = format(value ^ change, "x") if hexadecimal else str(value + change)
        damaged[index] = " ".join(row)
        if field == 1:
            # Preserve complete, well-ordered capture/END; only change edge.
            body = damaged[1:]
            finish = [x for x in body if "$finish called" in x]
            body = [x for x in body if "$finish called" not in x]
            body.sort(key=lambda line: int(line.split()[1]))
            damaged = damaged[:1] + body + finish
        raw = ("\n".join(damaged) + "\n").encode("ascii")
        (args.output / (tag + "_negative.txt")).write_bytes(raw)
        try:
            check(raw)
        except ValueError as error:
            if not str(error).startswith(reason):
                raise ValueError(f"WRONG_REJECTION:{tag}:{error}") from error
            tests.append({"tag": tag, "expected": reason, "actual": str(error)})
        else:
            raise ValueError("MUTANT_ACCEPTED:" + tag)
    result = {"N4_prior_semantic_trace_equal": True, "N4_extra_complete_route_observation": len(new_u-old_u),
              "complete_N8_negatives": tests, "exit_code": 0}
    (args.output / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
