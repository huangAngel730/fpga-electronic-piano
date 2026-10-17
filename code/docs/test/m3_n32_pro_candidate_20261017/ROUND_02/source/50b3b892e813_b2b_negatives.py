"""Few complete-capture semantic counterexamples at the NEW integration boundary."""
import argparse
import json
from pathlib import Path

from b2b_check import check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    check(raw)
    args.output.mkdir(exist_ok=False)
    tests = (("router_identity", "U", 10, "ROUTER_LIFECYCLE_OR_IDENTITY"),
             ("full_tag", "G", 2, "B1_FULL_TAG_CONTEXT_CONTROL_PEDAL"),
             ("control_snapshot", "C", 5, "BACKEND_FULL_SNAPSHOT"),
             ("result_context", "W", 3, "B1_REAL_RESULT_TAG_OR_CONTEXT"),
             ("atomic_pcm", "P", 3, "OUTPUT_BACKPRESSURE_STABILITY"),
             ("committed_bank", "Y", 3, "BANK_COMMIT_READBACK"))
    results = []
    for name, tag, field, diagnostic in tests:
        lines = raw.decode("ascii").splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith(tag + " "))
        row = lines[index].split()
        row[field] = str(int(row[field])+1) if tag == "P" else format(int(row[field], 16) ^ 1, "x")
        lines[index] = " ".join(row)
        damaged = ("\n".join(lines) + "\n").encode("ascii")
        path = args.output / (name + ".capture")
        path.write_bytes(damaged)
        try:
            check(damaged)
            raise RuntimeError("FALSE_ACCEPT:" + name)
        except ValueError as error:
            if diagnostic not in str(error):
                raise RuntimeError("WRONG_REJECTION:" + name + ":" + str(error)) from error
            results.append({"name": name, "reason": str(error), "complete_capture_retained": True})
    (args.output / "receipt.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "B2B_SIX_BOUNDARY_COUNTEREXAMPLES_REJECTED", "tests": results}))


if __name__ == "__main__":
    main()
