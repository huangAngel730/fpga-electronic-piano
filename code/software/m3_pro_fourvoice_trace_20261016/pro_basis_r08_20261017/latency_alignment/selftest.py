"""NOT_RUN case adapter for latency alignment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from latency_alignment import AlignmentReject, align


def _sha(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _profile(kind: str, uncertainty_ns: int) -> dict:
    document = {"schema": "M3_R08_MEASUREMENT_PROFILE_V1",
                "status": "PROFILE_READY", "instrument_id": f"synthetic-{kind}",
                "kind": kind.upper(), "session_id": "s1",
                "timebase_id": "common", "uncertainty_ns": uncertainty_ns,
                "settings_sha256": "3" * 64, "trigger_rule_sha256": "2" * 64,
                "device_called": False}
    return {"document": document, "sha256": _sha(document)}


def _reseal(profile: dict) -> None:
    profile["sha256"] = _sha(profile["document"])


def _input() -> dict:
    return {"session_ids": {"input": "s1", "digital": "s1", "analog": "s1"},
            "timebase_ids": {"input": "common", "digital": "common",
                             "analog": "common"},
            "input_edge_ns": 1000, "digital_tx_ns": 2000,
            "analog_response_ns": 8_001_000, "input_uncertainty_ns": 100,
            "analog_uncertainty_ns": 200,
            "threshold_rule": {"id": "threshold-v1", "sha256": "1" * 64,
                               "status": "FROZEN"},
            "trigger_rule": {"id": "trigger-v1", "sha256": "2" * 64,
                             "status": "FROZEN"},
            "measurement_profiles": {"input": _profile("input", 100),
                                     "digital": _profile("digital", 50),
                                     "analog": _profile("analog", 200)},
            "event_evidence": {
                "input": [{"time_ns": 1000, "sample_index": 10,
                           "source_line": 11, "trigger_rule_sha256": "2" * 64}],
                "digital": [{"time_ns": 2000, "sample_index": 20,
                             "source_line": 21}],
                "analog": [{"time_ns": 7_000_000, "sample_index": 70_000,
                            "source_line": 70_001,
                            "threshold_rule_sha256": "0" * 64,
                            "clipped": False},
                           {"time_ns": 8_001_000, "sample_index": 80_010,
                            "source_line": 80_011,
                            "threshold_rule_sha256": "1" * 64,
                            "clipped": False}]},
            "analog_clipped": False}


def _expect_reject(value: dict, expected: str) -> dict:
    try:
        align(value)
    except AlignmentReject as exc:
        if expected not in str(exc):
            raise
    else:
        raise AssertionError(f"{expected}_ACCEPTED")
    return {"status": "EXPECTED_REJECT", "reason": expected}


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    value = _input()
    if case_id == "KNOWN_SYNTHETIC_LATENCY":
        report = align(value)
        if (report["nominal_ns"] != 8_000_000 or not report["under_10ms"]
                or report["first_match"]["analog"]["sample_index"] != 80_010):
            raise AssertionError(report)
    elif case_id == "NO_COMMON_TIMEBASE_UNKNOWN":
        value["session_ids"]["analog"] = "s2"
        report = align(value)
        if report["status"] != "UNKNOWN_COMMON_TIMEBASE":
            raise AssertionError(report)
    elif case_id == "THRESHOLD_UNSET_UNKNOWN":
        value["threshold_rule"] = None
        report = align(value)
        if report["status"] != "UNKNOWN_THRESHOLD_RULE":
            raise AssertionError(report)
    elif case_id == "CLIPPED_UNKNOWN":
        value["analog_clipped"] = True
        value["event_evidence"]["analog"][1]["clipped"] = True
        report = align(value)
        if report["status"] != "UNKNOWN_ANALOG_CLIPPED":
            raise AssertionError(report)
    elif case_id == "EMPTY_IDENTITIES_UNKNOWN":
        value["session_ids"] = {"input": "", "digital": "", "analog": ""}
        value["timebase_ids"] = {"input": "", "digital": "", "analog": ""}
        report = align(value)
        if report["status"] != "UNKNOWN_COMMON_TIMEBASE":
            raise AssertionError(report)
    elif case_id == "TRIGGER_UNSET_UNKNOWN":
        value["trigger_rule"] = None
        report = align(value)
        if report["status"] != "UNKNOWN_TRIGGER_RULE":
            raise AssertionError(report)
    elif case_id == "PENDING_PROFILE_UNKNOWN":
        profile = value["measurement_profiles"]["analog"]
        profile["document"]["status"] = "PENDING_CALIBRATION"
        _reseal(profile)
        report = align(value)
        if report["status"] != "UNKNOWN_MEASUREMENT_PROFILE":
            raise AssertionError(report)
    elif case_id == "PROFILE_SHA_MISMATCH_UNKNOWN":
        value["measurement_profiles"]["input"]["sha256"] = "f" * 64
        report = align(value)
        if report["status"] != "UNKNOWN_MEASUREMENT_PROFILE":
            raise AssertionError(report)
    elif case_id == "LATER_MATCH_REJECT":
        value["event_evidence"]["analog"].insert(
            1, {"time_ns": 7_500_000, "sample_index": 75_000,
                "source_line": 75_001, "threshold_rule_sha256": "1" * 64,
                "clipped": False})
        report = _expect_reject(value, "NOT_FIRST_MATCH_EVIDENCE")
    elif case_id == "FIRST_THRESHOLD_CLIPPED_REJECT":
        value["event_evidence"]["analog"].insert(
            1, {"time_ns": 7_500_000, "sample_index": 75_000,
                "source_line": 75_001, "threshold_rule_sha256": "1" * 64,
                "clipped": True})
        report = _expect_reject(value, "ANALOG_CLIP_CONTRADICTION")
    elif case_id == "NEGATIVE_UNCERTAINTY_REJECT":
        value["analog_uncertainty_ns"] = -1
        report = _expect_reject(value, "TIME_VALUE")
    elif case_id == "NONFINITE_UNCERTAINTY_REJECT":
        value["analog_uncertainty_ns"] = "NaN"
        report = _expect_reject(value, "TIME_VALUE")
    elif case_id == "EVENT_ORDER_REJECT":
        value["digital_tx_ns"] = 9_000_000
        report = _expect_reject(value, "NOT_FIRST_MATCH_EVIDENCE")
    else:
        raise KeyError(case_id)
    (output_dir / "input.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"case_id": case_id, "status": "PASS"}
