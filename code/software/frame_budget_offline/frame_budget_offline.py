#!/usr/bin/env python3
"""Offline checker for future R04 per-frame budget CSV exports.

This program never launches ModelSim.  It validates only a CSV file that a
separately approved simulation may produce in the future.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "frame_index",
    "frame_cycles",
    "max_processing_cycles",
    "underrun_count",
)
ALLOWED_FRAME_CYCLES = frozenset({833, 834})
PROCESSING_DEADLINE_CYCLES = 834


class CsvFormatError(ValueError):
    """Raised when the evidence CSV cannot be interpreted safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_nonnegative_int(raw: str | None, field: str, line: int) -> int:
    if raw is None or raw.strip() == "":
        raise CsvFormatError(f"line {line}: missing {field}")
    text = raw.strip()
    try:
        value = int(text, 10)
    except ValueError as exc:
        raise CsvFormatError(
            f"line {line}: {field} is not a base-10 integer: {text!r}"
        ) from exc
    if value < 0:
        raise CsvFormatError(f"line {line}: {field} must be nonnegative")
    return value


def analyze_csv(path: Path) -> dict[str, Any]:
    """Return an auditable summary.  Policy failures are listed in reasons."""

    if not path.is_file():
        raise CsvFormatError(f"input is not a regular file: {path}")

    rows: list[dict[str, int]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise CsvFormatError("CSV header is missing")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise CsvFormatError("CSV header contains duplicate fields")
        missing = [name for name in REQUIRED_FIELDS if name not in reader.fieldnames]
        if missing:
            raise CsvFormatError("CSV missing required fields: " + ", ".join(missing))

        for line, raw_row in enumerate(reader, start=2):
            if None in raw_row:
                raise CsvFormatError(f"line {line}: too many CSV columns")
            row = {
                name: _parse_nonnegative_int(raw_row.get(name), name, line)
                for name in REQUIRED_FIELDS
            }
            rows.append(row)

    if not rows:
        raise CsvFormatError("CSV contains no frame rows")

    reasons: list[str] = []
    previous_index = -1
    previous_max = -1
    previous_underrun = -1
    distribution: Counter[int] = Counter()

    for row in rows:
        index = row["frame_index"]
        frame_cycles = row["frame_cycles"]
        reported_max = row["max_processing_cycles"]
        underrun = row["underrun_count"]

        if index != previous_index + 1:
            reasons.append(
                f"FRAME_INDEX_NOT_CONTIGUOUS: expected {previous_index + 1}, got {index}"
            )
        previous_index = index

        distribution[frame_cycles] += 1
        if frame_cycles not in ALLOWED_FRAME_CYCLES:
            reasons.append(
                f"FRAME_CYCLES_OUT_OF_CONTRACT: frame {index} has {frame_cycles}"
            )

        if reported_max < previous_max:
            reasons.append(
                "MAX_PROCESSING_COUNTER_ROLLBACK: "
                f"frame {index} has {reported_max} after {previous_max}"
            )
        previous_max = reported_max

        if underrun < previous_underrun:
            reasons.append(
                f"UNDERRUN_COUNTER_ROLLBACK: frame {index} has {underrun} "
                f"after {previous_underrun}"
            )
        previous_underrun = underrun

    final_max = rows[-1]["max_processing_cycles"]
    final_underrun = rows[-1]["underrun_count"]
    if final_max >= PROCESSING_DEADLINE_CYCLES:
        reasons.append(
            "MAX_PROCESSING_DEADLINE_FAIL: "
            f"{final_max} is not less than {PROCESSING_DEADLINE_CYCLES}"
        )
    if final_underrun != 0:
        reasons.append(f"UNDERRUN_NONZERO: final cumulative count is {final_underrun}")

    return {
        "schema": "r04_frame_budget_offline_v1",
        "scope": "SYNTHETIC_OR_FUTURE_EXPORTED_CSV_ONLY",
        "input": {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        },
        "contract": {
            "required_fields": list(REQUIRED_FIELDS),
            "allowed_frame_cycles": sorted(ALLOWED_FRAME_CYCLES),
            "max_processing_cycles_must_be_less_than": (
                PROCESSING_DEADLINE_CYCLES
            ),
            "underrun_count_must_finish_at": 0,
        },
        "observed": {
            "rows": len(rows),
            "first_frame_index": rows[0]["frame_index"],
            "last_frame_index": rows[-1]["frame_index"],
            "frame_cycles_distribution": {
                str(cycles): count
                for cycles, count in sorted(distribution.items())
            },
            "final_max_processing_cycles": final_max,
            "final_underrun_count": final_underrun,
        },
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "limitations": [
            "No ModelSim, RTL, synthesis, PnR, STA, or device operation was run.",
            "A PASS validates the CSV contract only; it does not prove the R04 whole system.",
            "The cumulative max counter is checked for monotonicity and deadline only; "
            "the CSV does not independently reconstruct internal processing latency.",
        ],
    }


def write_summary(summary: dict[str, Any], path: Path | None) -> None:
    payload = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        sys.stdout.write(payload)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")
    sys.stdout.write(f"{summary['status']} summary={path}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate an R04 frame-budget CSV without launching a simulator."
    )
    parser.add_argument("csv", type=Path, help="CSV evidence to analyze")
    parser.add_argument("--summary", type=Path, help="write deterministic JSON summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = analyze_csv(args.csv)
    except (CsvFormatError, OSError) as exc:
        error_summary = {
            "schema": "r04_frame_budget_offline_v1",
            "scope": "SYNTHETIC_OR_FUTURE_EXPORTED_CSV_ONLY",
            "status": "ERROR",
            "reasons": [str(exc)],
        }
        write_summary(error_summary, args.summary)
        return 2
    write_summary(summary, args.summary)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
