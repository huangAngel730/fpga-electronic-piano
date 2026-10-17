"""NOT_RUN case adapter for measurement profile."""

from __future__ import annotations

import json
from pathlib import Path

from measurement_profile import ProfileReject, assess


def _profile() -> dict:
    return {"instrument_id": "synthetic-la", "kind": "LOGIC_ANALYZER",
            "session_id": "s1", "timebase_id": "la-clock",
            "sample_interval_ns": 10, "edge_resolution_ns": 10,
            "range_min": 0, "range_max": 3.3,
            "calibration": {"status": "VALID", "uncertainty_ns": 5,
                            "record_identity": {"path": "cal.json",
                                                "sha256": "1" * 64}},
            "raw_settings_identity": {"path": "settings.json",
                                      "sha256": "2" * 64},
            "trigger": {"mode": "EDGE", "source": "MIDI_RX",
                        "rule_sha256": "3" * 64},
            "dropped_samples": 0, "saturated": False,
            "required_resolution_ns": 25}


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    value = _profile()
    if case_id == "SYNTHETIC_PROFILE_READY":
        report = assess(value)
        if report["status"] != "PROFILE_READY":
            raise AssertionError(report)
    elif case_id == "UNKNOWN_CALIBRATION_PENDING":
        value["calibration"] = {"status": "UNKNOWN"}
        report = assess(value)
        if report["status"] != "PENDING_CALIBRATION" or report["uncertainty_ns"] is not None:
            raise AssertionError(report)
    elif case_id == "MISSING_TIMEBASE_PENDING":
        value["timebase_id"] = None
        report = assess(value)
        if report["status"] != "PENDING_TIMEBASE":
            raise AssertionError(report)
    elif case_id == "SELF_DECLARED_CALIBRATION_PENDING":
        del value["calibration"]["record_identity"]
        report = assess(value)
        if report["status"] != "PENDING_CALIBRATION":
            raise AssertionError(report)
    elif case_id == "MISSING_TRIGGER_PENDING":
        value["trigger"] = None
        report = assess(value)
        if report["status"] != "PENDING_TRIGGER":
            raise AssertionError(report)
    else:
        changes = {"DROPPED_SAMPLE_REJECT": ("dropped_samples", 1, "DROPPED_SAMPLES"),
                   "SATURATION_REJECT": ("saturated", True, "SATURATED"),
                   "LOW_RATE_REJECT": ("sample_interval_ns", 100, "RESOLUTION_INSUFFICIENT"),
                   "NONFINITE_RANGE_REJECT": ("range_max", "NaN", "RANGE_MAX_INVALID")}
        if case_id not in changes:
            raise KeyError(case_id)
        key, changed, expected = changes[case_id]
        value[key] = changed
        try:
            assess(value)
        except ProfileReject as exc:
            if expected not in str(exc):
                raise
        else:
            raise AssertionError("BAD_PROFILE_ACCEPTED")
        report = {"status": "EXPECTED_REJECT", "reason": expected}
    (output_dir / "input.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"case_id": case_id, "status": "PASS"}
