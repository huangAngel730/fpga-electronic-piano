"""Fixed R06 software fixture. It is not an HDL, EDA, or hardware tool."""

import sys
import time


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"stream", "error"}:
        print("FIXTURE_MODE_REFUSED", file=sys.stderr, flush=True)
        return 9
    mode = sys.argv[1]
    for index in range(3):
        print(f"FIXTURE_STDOUT_{index}", flush=True)
        print(f"FIXTURE_STDERR_{index}", file=sys.stderr, flush=True)
        time.sleep(0.08)
    return 7 if mode == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
