"""Separate process for the frozen public-wire oracle, never RAM internals."""
from pathlib import Path
import argparse
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "code/tb/board/score_receive_integration_20261009"
sys.path.insert(0, str(BASE))
SPEC = importlib.util.spec_from_file_location("frozen_score_wire_oracle", BASE / "check_capture.py")
legacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(legacy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    try:
        oracle = json.loads(args.oracle.read_bytes())
        if (type(oracle.get("schema")) is not int or oracle["schema"] != 1
                or type(oracle.get("count")) is not int or oracle["count"] != 13
                or len(oracle["cases"]) != 13
                or [row["id"] for row in oracle["cases"]] != list(range(13))
                or any(type(row["id"]) is not int for row in oracle["cases"])):
            raise ValueError("EXACT13_ORACLE_IDENTITY")
        result = legacy.check(args.capture, oracle, args.negative)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("FAIL " + str(error), flush=True)
        return 1
    print("PASS " + json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
