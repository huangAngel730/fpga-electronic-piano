"""N16 checkpoint of the same independent event/audio reference, not new RTL.

R64 deliberately exceeds 833 cycles: correct late reporting is necessary but
does not qualify that configuration for the sample deadline or physical STA.
"""
import argparse
import json
from pathlib import Path

from b2c_check import check as reference_check


def check(raw):
    result = reference_check(raw, sizes=(16,), responses=(1, 3, 32, 64),
                             identity_controls=True, extra_long_events=1)
    result["status"] = "B2D_N16_EVENT_AUDIO_PASS_T061_PARTIAL"
    result["sample_deadline_qualified"] = result["deadline_misses"] == 0
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result, code = check(args.input.read_bytes()), 0
    except (ValueError, OSError, UnicodeError) as error:
        result, code = {"status": "REJECT", "reason": str(error)}, 1
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
