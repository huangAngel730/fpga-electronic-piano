"""NOT_RUN case adapter for FRAME coverage."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from frame_coverage_diff import CoverageReject, compare


def _plan() -> dict:
    value = {"schema": "M3_R06_UNIQUE_FRAME_PLAN_V1",
            "formula": "n_k=ceil(128*k*2**32/659706977); cycle_k=release_cycle+n_k-1; k>=1",
            "rules_sha256": "3c968a151b0b5369f9dd95465761b2d87449c29975b1fca914f81fc5cfd01560",
            "input_sha256": "1" * 64,
            "source_identities": [{"path": "frozen.json", "sha256": "2" * 64}],
            "parameters": {"acc_bits": 32, "phase_step": 659706977,
                           "core_hz_candidate": 40000000,
                           "half_bclk_toggles_per_frame": 128,
                           "initial_state": {"accumulator": 0, "bclk": 0,
                                             "slot_count": 0}},
            "epochs": [{"epoch": 0, "window_kind": "ACTIVE",
                        "reset_assert_cycle": 0, "release_cycle": 0,
                        "stop_cycle": 1666, "cycles": [833, 1666]},
                       {"epoch": 1, "window_kind": "RESET_ONLY",
                        "reset_assert_cycle": 1667, "release_cycle": None,
                        "stop_cycle": 1668, "cycles": []}],
            "finish": {"epoch": 1, "cycle": 1668},
            "independent_of_trace": True,
            "authority": "CANDIDATE_INDEPENDENT_PLAN_NOT_M2_ADMITTED"}
    payload = {key: value[key] for key in ("schema", "formula", "rules_sha256",
               "input_sha256", "source_identities", "parameters", "epochs", "finish")}
    digest = hashlib.sha256((json.dumps(payload, sort_keys=True,
        separators=(",", ":")) + "\n").encode()).hexdigest()
    value["canonical_identity_sha256"] = digest
    value["canonical_plan_id"] = f"sha256:{digest}"
    return value


def _reseal(value: dict) -> None:
    payload = {key: value[key] for key in ("schema", "formula", "rules_sha256",
               "input_sha256", "source_identities", "parameters", "epochs", "finish")}
    digest = hashlib.sha256((json.dumps(payload, sort_keys=True,
        separators=(",", ":")) + "\n").encode()).hexdigest()
    value["canonical_identity_sha256"] = digest
    value["canonical_plan_id"] = f"sha256:{digest}"


def _frames() -> list[dict]:
    return [{"epoch": 0, "cycle": 833, "source_line": 834},
            {"epoch": 0, "cycle": 1666, "source_line": 1667}]


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    plan, frames = _plan(), _frames()
    if case_id == "FULL_WINDOW_PASS":
        report = compare(plan, frames)
        if report["status"] != "PASS":
            raise AssertionError(report)
    elif case_id == "MISSING_LAST_FRAME":
        report = compare(plan, frames[:-1])
        if report["status"] != "FAIL" or report["missing"] != [(0, 1666)]:
            raise AssertionError(report)
    elif case_id == "DUPLICATE_REJECT":
        try:
            compare(plan, frames + [frames[-1]])
        except CoverageReject as exc:
            if "DUPLICATE_FRAME" not in str(exc):
                raise
        else:
            raise AssertionError("DUPLICATE_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "WRONG_SCHEMA_REJECT":
        plan["schema"] = "TRACE_DERIVED_PLAN"
        try:
            compare(plan, frames)
        except CoverageReject as exc:
            if "PLAN_SCHEMA" not in str(exc):
                raise
        else:
            raise AssertionError("WRONG_PLAN_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "WRONG_FIRST_PHASE_REJECT":
        frames[0]["cycle"] += 1
        report = compare(plan, frames)
        if report["first_difference_index"] != 0:
            raise AssertionError(report)
    elif case_id == "TRACE_DERIVED_SELF_HASH_REJECT":
        plan["derived_from_trace"] = True
        try:
            compare(plan, frames)
        except CoverageReject as exc:
            if "PLAN_NOT_INDEPENDENT" not in str(exc):
                raise
        else:
            raise AssertionError("TRACE_DERIVED_PLAN_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "CANONICAL_IDENTITY_TAMPER_REJECT":
        plan["epochs"][0]["cycles"] = [834, 1666]
        try:
            compare(plan, frames)
        except CoverageReject as exc:
            if "PLAN_CANONICAL_IDENTITY" not in str(exc):
                raise
        else:
            raise AssertionError("IDENTITY_TAMPER_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    elif case_id == "SELF_HASHED_ILLEGAL_WINDOW_REJECT":
        plan["epochs"][0]["reset_assert_cycle"] = 9999
        _reseal(plan)
        try:
            compare(plan, frames)
        except CoverageReject as exc:
            if "EPOCH_WINDOW_ORDER" not in str(exc):
                raise
        else:
            raise AssertionError("ILLEGAL_WINDOW_ACCEPTED")
        report = {"status": "EXPECTED_REJECT"}
    else:
        raise KeyError(case_id)
    (output_dir / "input.json").write_text(json.dumps({"plan": plan, "frames": frames}, indent=2) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"case_id": case_id, "status": "PASS"}
