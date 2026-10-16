"""Software policy CLI; synthetic mode never attests real R05 execution."""
import argparse
from pathlib import Path
import json
import sys

from common import Refusal
from receipt_check import check_step


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--step", choices=("vlib", "vlog", "vsim"), required=True)
    p.add_argument("--stdout", type=Path, required=True)
    p.add_argument("--stderr", type=Path, required=True)
    p.add_argument("--exit-code", type=int, required=True)
    p.add_argument("--timeout", choices=("false", "true"), required=True)
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args()
    try:
        result = check_step(
            args.step, args.stdout.read_bytes(), args.stderr.read_bytes(),
            args.exit_code, args.timeout == "true", synthetic=args.synthetic,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (Refusal, OSError) as exc:
        print(json.dumps({
            "status": "REJECTED", "diagnostic": getattr(exc, "code", "MISSING_STREAM"),
            "detail": str(exc), "board_release_allowed": False,
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
