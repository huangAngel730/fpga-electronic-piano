"""Offline measurement capability and timebase checker."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


class ProfileReject(ValueError):
    pass


def _identity(value: Any, label: str) -> bool:
    return (isinstance(value, dict) and set(value) == {"path", "sha256"}
            and isinstance(value["path"], str) and bool(value["path"])
            and isinstance(value["sha256"], str) and len(value["sha256"]) == 64
            and all(char in "0123456789abcdef" for char in value["sha256"]))


def assess(value: dict[str, Any]) -> dict[str, Any]:
    required = {"instrument_id", "kind", "session_id", "timebase_id",
                "sample_interval_ns", "edge_resolution_ns", "range_min",
                "range_max", "calibration", "dropped_samples", "saturated",
                "required_resolution_ns", "raw_settings_identity", "trigger"}
    if set(value) != required:
        raise ProfileReject("PROFILE_SHAPE")
    for key in ("sample_interval_ns", "edge_resolution_ns", "required_resolution_ns"):
        if (type(value[key]) not in (int, float) or not math.isfinite(value[key])
                or value[key] <= 0):
            raise ProfileReject(f"{key.upper()}_INVALID")
    for key in ("range_min", "range_max"):
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]):
            raise ProfileReject(f"{key.upper()}_INVALID")
    if value["range_min"] >= value["range_max"]:
        raise ProfileReject("RANGE")
    if not isinstance(value["instrument_id"], str) or not value["instrument_id"]:
        raise ProfileReject("INSTRUMENT_ID")
    if not isinstance(value["session_id"], str) or not value["session_id"]:
        return {"schema": "M3_R08_MEASUREMENT_PROFILE_V1",
                "status": "PENDING_SESSION_ID", "device_called": False}
    if not isinstance(value["timebase_id"], str) or not value["timebase_id"]:
        return {"schema": "M3_R08_MEASUREMENT_PROFILE_V1",
                "status": "PENDING_TIMEBASE", "device_called": False}
    if not _identity(value["raw_settings_identity"], "SETTINGS"):
        return {"schema": "M3_R08_MEASUREMENT_PROFILE_V1",
                "status": "PENDING_SETTINGS_IDENTITY", "device_called": False}
    trigger = value["trigger"]
    if (not isinstance(trigger, dict)
            or set(trigger) != {"mode", "source", "rule_sha256"}
            or not trigger["mode"] or not trigger["source"]
            or not isinstance(trigger["rule_sha256"], str)
            or len(trigger["rule_sha256"]) != 64
            or any(char not in "0123456789abcdef"
                   for char in trigger["rule_sha256"])):
        return {"schema": "M3_R08_MEASUREMENT_PROFILE_V1",
                "status": "PENDING_TRIGGER", "device_called": False}
    if value["dropped_samples"]:
        raise ProfileReject("DROPPED_SAMPLES")
    if value["saturated"]:
        raise ProfileReject("SATURATED")
    if (value["sample_interval_ns"] > value["required_resolution_ns"]
            or value["edge_resolution_ns"] > value["required_resolution_ns"]):
        raise ProfileReject("RESOLUTION_INSUFFICIENT")
    calibration = value["calibration"]
    if (not isinstance(calibration, dict) or calibration.get("status") != "VALID"
            or not _identity(calibration.get("record_identity"), "CALIBRATION")):
        status = "PENDING_CALIBRATION"
        uncertainty = None
    else:
        uncertainty = calibration.get("uncertainty_ns")
        if (type(uncertainty) not in (int, float)
                or not math.isfinite(uncertainty) or uncertainty < 0):
            raise ProfileReject("CALIBRATION_UNCERTAINTY")
        status = "PROFILE_READY"
    return {"schema": "M3_R08_MEASUREMENT_PROFILE_V1", "status": status,
            "instrument_id": value["instrument_id"], "kind": value["kind"],
            "session_id": value["session_id"], "timebase_id": value["timebase_id"],
            "uncertainty_ns": uncertainty,
            "settings_sha256": value["raw_settings_identity"]["sha256"],
            "trigger_rule_sha256": trigger["rule_sha256"],
            "device_called": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = assess(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
