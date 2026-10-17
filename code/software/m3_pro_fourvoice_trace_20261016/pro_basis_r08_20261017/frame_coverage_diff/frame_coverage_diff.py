"""Read-only FRAME coverage comparator for the unique R6-5 plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PLAN_SCHEMA = "M3_R06_UNIQUE_FRAME_PLAN_V1"
FORMULA = "n_k=ceil(128*k*2**32/659706977); cycle_k=release_cycle+n_k-1; k>=1"
RULES_SHA = "3c968a151b0b5369f9dd95465761b2d87449c29975b1fca914f81fc5cfd01560"


class CoverageReject(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def expected_from_plan(plan: dict[str, Any]) -> list[dict[str, int]]:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("formula") != FORMULA:
        raise CoverageReject("PLAN_SCHEMA_OR_FORMULA")
    if plan.get("rules_sha256") != RULES_SHA:
        raise CoverageReject("PLAN_RULES_SHA")
    if plan.get("independent_of_trace") is not True or any(key in plan for key in (
            "trace", "trace_path", "observed_frames", "derived_from_trace")):
        raise CoverageReject("PLAN_NOT_INDEPENDENT")
    identity_keys = ("schema", "formula", "rules_sha256", "input_sha256",
                     "source_identities", "parameters", "epochs", "finish")
    if any(key not in plan for key in identity_keys):
        raise CoverageReject("PLAN_IDENTITY_FIELDS")
    if not _is_sha256(plan["input_sha256"]):
        raise CoverageReject("PLAN_INPUT_SHA")
    sources = plan["source_identities"]
    if not isinstance(sources, list) or not sources:
        raise CoverageReject("PLAN_SOURCE_IDENTITIES")
    for index, source in enumerate(sources):
        if (not isinstance(source, dict) or set(source) != {"path", "sha256"}
                or not isinstance(source["path"], str) or not source["path"]
                or not _is_sha256(source["sha256"])):
            raise CoverageReject(f"PLAN_SOURCE_IDENTITY_{index}")
    payload = {key: plan[key] for key in identity_keys}
    identity = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    if (plan.get("canonical_identity_sha256") != identity
            or plan.get("canonical_plan_id") != f"sha256:{identity}"):
        raise CoverageReject("PLAN_CANONICAL_IDENTITY")
    params = plan.get("parameters", {})
    if params != {"acc_bits": 32, "phase_step": 659706977,
                  "core_hz_candidate": 40000000,
                  "half_bclk_toggles_per_frame": 128,
                  "initial_state": {"accumulator": 0, "bclk": 0,
                                    "slot_count": 0}}:
        raise CoverageReject("PLAN_PARAMETERS")
    result = []
    prior_stop = None
    for index, epoch in enumerate(plan.get("epochs", [])):
        if not isinstance(epoch, dict) or epoch.get("epoch") != index:
            raise CoverageReject("EPOCH_ORDER")
        reset = epoch.get("reset_assert_cycle")
        stop = epoch.get("stop_cycle")
        if (type(reset) is not int or type(stop) is not int
                or reset < 0 or stop < 0 or reset > stop):
            raise CoverageReject("EPOCH_WINDOW_ORDER")
        if prior_stop is not None and reset != prior_stop + 1:
            raise CoverageReject("EPOCH_GAP")
        calculated = []
        if epoch.get("window_kind") == "ACTIVE":
            release = epoch.get("release_cycle")
            if (type(release) is not int or release < 0
                    or not reset <= release <= stop):
                raise CoverageReject("EPOCH_WINDOW_ORDER")
            k = 1
            while True:
                edge = (128 * k * (1 << 32) + 659706977 - 1) // 659706977
                cycle = release + edge - 1
                if cycle > stop:
                    break
                calculated.append(cycle)
                result.append({"epoch": index, "cycle": cycle})
                k += 1
        elif epoch.get("window_kind") == "RESET_ONLY":
            if epoch.get("release_cycle") is not None:
                raise CoverageReject("WINDOW_KIND")
        else:
            raise CoverageReject("WINDOW_KIND")
        if epoch.get("cycles") != calculated:
            raise CoverageReject("PLAN_CYCLES_NOT_FORMULA")
        prior_stop = stop
    if not plan.get("epochs") or plan.get("finish") != {
            "epoch": plan["epochs"][-1]["epoch"],
            "cycle": plan["epochs"][-1]["stop_cycle"]}:
        raise CoverageReject("FINISH")
    return result


def compare(plan: dict[str, Any], observed: list[dict[str, Any]]) -> dict[str, Any]:
    expected = expected_from_plan(plan)
    actual = []
    seen = set()
    for row in observed:
        key = (row.get("epoch"), row.get("cycle"))
        if key in seen:
            raise CoverageReject(f"DUPLICATE_FRAME:{key}")
        seen.add(key)
        actual.append({"epoch": key[0], "cycle": key[1],
                       "source_line": row.get("source_line")})
    actual_keys = [(x["epoch"], x["cycle"]) for x in actual]
    expected_keys = [(x["epoch"], x["cycle"]) for x in expected]
    if actual_keys != expected_keys:
        first = next((index for index, pair in enumerate(zip(expected_keys, actual_keys))
                      if pair[0] != pair[1]), min(len(expected_keys), len(actual_keys)))
        return {"schema": "M3_R08_FRAME_COVERAGE_DIFF_V1", "status": "FAIL",
                "first_difference_index": first,
                "expected": expected_keys[first] if first < len(expected_keys) else None,
                "observed": actual[first] if first < len(actual) else None,
                "missing": [x for x in expected_keys if x not in actual_keys],
                "extra": [x for x in actual_keys if x not in expected_keys],
                "plan_reproduced": False}
    return {"schema": "M3_R08_FRAME_COVERAGE_DIFF_V1", "status": "PASS",
            "frame_count": len(expected), "first_difference_index": None,
            "plan_reproduced": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--frames", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = compare(json.loads(args.plan.read_text(encoding="utf-8")),
                     json.loads(args.frames.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
