"""C v6 independent segmented plan after the retained C06 driver deadlock.

FULL changes only the missing pre-HOLD drain. SHORT starts from reset and
fresh four-voice input events, then exercises C05 through C09 independently.
Neither variant reads a DUT trace or inherits state from the retained prefix.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_v4 import FrameOracle, ROM_NAMES, FROZEN, build_v4_operations
from n32c_common import records_sha256, write_jsonl


def build_v6_operations(segment: str) -> list[dict]:
    if segment not in ("FULL", "SHORT_SUFFIX"):
        raise ValueError("C6_SEGMENT")
    original = build_v4_operations()
    if segment == "FULL":
        selected = original
    else:
        selected = [dict(case_id="C06_INDEPENDENT_SETUP", op="reset"),
                    dict(case_id="C06_INDEPENDENT_SETUP", op="wait_idle")]
        selected += [dict(case_id="C06_INDEPENDENT_SETUP", op="note_on",
                          source=6, channel=2, note=74+i, velocity=760+i,
                          expression=901) for i in range(4)]
        selected += [dict(case_id="C06_INDEPENDENT_SETUP", op="sample",
                          result_id=0x1005, disposition="PUBLISH"),
                     dict(case_id="C06_INDEPENDENT_SETUP", op="wait_idle")]
        selected += [op for op in original if op["case_id"].startswith(
            ("C05_", "C06_", "C07_", "C08_", "C09_"))]
    result = []
    for op in selected:
        # C09 is a fresh numerical-boundary case, not a cancellation case.
        # Preserve the C08 tail's promised publication before its reset.
        if op["case_id"] == "C09_EXACT_FULLSCALE_NOT_CLIPPED" and op["op"] == "reset":
            result.append(dict(case_id="C08_HIGH_DENSITY", op="wait_idle"))
        # A prior accepted frame must publish before lowering result_ready.
        # Otherwise the subsequent sample waits on an unconsumed HOLD result.
        if op["op"] == "set_result_ready" and op["value"] == 0:
            result.append(dict(case_id=op["case_id"], op="wait_idle"))
        result.append(dict(op))
    return result


def generate(segment: str = "SHORT_SUFFIX") -> tuple[list[dict], list[dict]]:
    operations = build_v6_operations(segment)
    body = [dict(record="PLAN", index=i, **op) for i, op in enumerate(operations)]
    meta = dict(record="META", schema="t061-n32c-plan-v6", n=32, response=1,
                clock_hz=40000000, segment=segment,
                independent_initial_state="RESET_FRESH_INPUT_EVENTS",
                b_review_key="T061-N32-B-RESULT-20261014-R01",
                b_snapshot_sha256="d475ed2acdd65037893cfc778ca7c99aa9c8d6c37c209a9217ce05e1174d3421")
    plan = [meta, *body, dict(record="END", operations=len(body),
                             body_sha256=records_sha256([meta, *body]))]
    oracle = FrameOracle()
    timeline = []
    for index, op in enumerate(operations):
        record = oracle.apply(index, op)
        if record is not None:
            timeline.append(record)
    expmeta = dict(record="META", schema="t061-n32c-expected-v6", segment=segment,
                   plan_sha256=records_sha256(plan), source="INPUT_ONLY_FROZEN_MATH",
                   rom_sha256={name: hashlib.sha256((FROZEN / "rom" / name).read_bytes()).hexdigest()
                               for name in ROM_NAMES})
    expected = [expmeta, *timeline, dict(record="END", events=oracle.event_serial,
                transactions=oracle.serial, reads=oracle.read_serial,
                retirements=oracle.retirements + oracle.router.counts["retirements"],
                body_sha256=records_sha256([expmeta, *timeline]))]
    return plan, expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--segment", choices=("FULL", "SHORT_SUFFIX"), default="SHORT_SUFFIX")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan, expected = generate(args.segment)
    write_jsonl(args.output / "plan_v6.jsonl", plan)
    write_jsonl(args.output / "expected_v6.jsonl", expected)
    print(json.dumps(dict(status="V6_INDEPENDENT_PLAN_MATH_GENERATED", segment=args.segment,
                          plan_records=len(plan), expected_records=len(expected))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
