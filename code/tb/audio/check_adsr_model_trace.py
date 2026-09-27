#!/usr/bin/env python3
"""Compare T009 trace with the existing M1 Python ADSR model.

Tolerance is provisional: M1 still owns the final Q1.15 approximation bound.
Only Q1.15 amplitude is compared; debug state transitions may differ at boundaries.
Both successful comparison count and failure exit status are asserted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[2] / "model"
sys.path.insert(0, str(MODEL_DIR))
from adsr_piano import PianoADSREnvelope  # noqa: E402


class TraceError(ValueError):
    """Malformed or inconsistent trace."""


def check_trace(path: Path, tolerance: int, min_samples: int) -> tuple[int, int]:
    model: PianoADSREnvelope | None = None
    seen = 0
    max_error = 0
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = raw_line.split()
        if not fields:
            raise TraceError(f"empty line {line_no}")
        try:
            if fields == ["R"]:
                model = PianoADSREnvelope()
            elif len(fields) == 2 and fields[0] == "N" and model:
                model.note_on(int(fields[1]))
            elif fields == ["F"] and model:
                model.note_off()
            elif len(fields) == 3 and fields[0] == "S" and model:
                expected = model.step()
                actual = int(fields[1])
                observed_error = abs(expected - actual)
                max_error = max(max_error, observed_error)
                seen += 1
                if observed_error > tolerance:
                    raise TraceError(
                        f"line {line_no} sample {seen}: RTL={actual} "
                        f"model={expected} delta={observed_error} state={model.state}"
                    )
            else:
                raise TraceError(f"malformed event on line {line_no}: {raw_line!r}")
        except ValueError as exc:
            if isinstance(exc, TraceError):
                raise
            raise TraceError(f"bad integer on line {line_no}: {raw_line!r}") from exc
    if seen < min_samples:
        raise TraceError(f"only {seen} samples compared; require {min_samples}")
    return seen, max_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--tolerance", type=int, default=2)
    parser.add_argument("--min-samples", type=int, default=70000)
    args = parser.parse_args()
    if args.tolerance < 0 or args.min_samples < 1:
        parser.error("tolerance and min-samples must be nonnegative/positive")
    try:
        count, max_error = check_trace(args.trace, args.tolerance, args.min_samples)
    except (OSError, TraceError) as exc:
        print(f"FAIL T009 Python model comparison: {exc}", file=sys.stderr)
        return 1
    print(f"PASS T009 Python model comparison: samples={count} "
          f"max_delta={max_error} tolerance={args.tolerance} Q15 LSB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
