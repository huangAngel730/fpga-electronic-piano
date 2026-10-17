"""N32 short checkpoint of pinned N16 RTL; no long/physical acceptance."""
import argparse
import json
from pathlib import Path

from b2c_check import check as reference_check

STATUS = "B2E_N32_SHORT_EVENT_AUDIO_PASS_T061_PARTIAL"
RESPONSES = (1, 8, 16, 32)


def check(raw):
    # This stage does not claim long ADSR/retirement coverage. Reject a different
    # fixture rather than admitting it with the short-stage qualification.
    if raw.splitlines()[0:1] not in [[f"B2C 32 {r} 0".encode()] for r in RESPONSES]:
        raise ValueError("N32_SHORT_HEADER")
    result = reference_check(raw, sizes=(32,), responses=RESPONSES,
                             identity_controls=True)
    result.update(status=STATUS,
                  sample_deadline_qualified=result["deadline_misses"] == 0,
                  N32_long_ADSR_retirement="NOT_RUN",
                  N32_sustained_performance="NOT_VERIFIED",
                  source_clock_not_physical_STA=True)
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
