"""Offline common-timebase latency interval calculator."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


class AlignmentReject(ValueError):
    pass


def _canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _frozen_rule(rule: Any) -> bool:
    return (isinstance(rule, dict) and set(rule) == {"id", "sha256", "status"}
            and isinstance(rule["id"], str) and bool(rule["id"])
            and rule["status"] == "FROZEN"
            and isinstance(rule["sha256"], str) and len(rule["sha256"]) == 64
            and all(char in "0123456789abcdef" for char in rule["sha256"]))


def _profile_ready(entry: Any, session_id: str, timebase_id: str,
                   trigger_sha256: str) -> bool:
    if not isinstance(entry, dict) or set(entry) != {"document", "sha256"}:
        return False
    document = entry["document"]
    if (not isinstance(document, dict)
            or document.get("schema") != "M3_R08_MEASUREMENT_PROFILE_V1"
            or document.get("status") != "PROFILE_READY"
            or document.get("session_id") != session_id
            or document.get("timebase_id") != timebase_id
            or document.get("trigger_rule_sha256") != trigger_sha256
            or document.get("device_called") is not False
            or type(document.get("uncertainty_ns")) not in (int, float)
            or not math.isfinite(document["uncertainty_ns"])
            or document["uncertainty_ns"] < 0):
        return False
    digest = entry["sha256"]
    return (isinstance(digest, str) and len(digest) == 64
            and all(char in "0123456789abcdef" for char in digest)
            and digest == _canonical_sha256(document))


def _events(value: Any, kind: str) -> list[dict[str, Any]]:
    common = {"time_ns", "sample_index", "source_line"}
    extra = ({"trigger_rule_sha256"} if kind == "input" else
             {"threshold_rule_sha256", "clipped"} if kind == "analog" else set())
    if not isinstance(value, list) or not value:
        raise AlignmentReject(f"{kind.upper()}_EVENT_EVIDENCE")
    previous = -1.0
    for event in value:
        if not isinstance(event, dict) or set(event) != common | extra:
            raise AlignmentReject(f"{kind.upper()}_EVENT_EVIDENCE")
        if (type(event["time_ns"]) not in (int, float)
                or not math.isfinite(event["time_ns"]) or event["time_ns"] < 0
                or type(event["sample_index"]) is not int
                or event["sample_index"] < 0
                or type(event["source_line"]) is not int
                or event["source_line"] < 1
                or event["time_ns"] < previous):
            raise AlignmentReject(f"{kind.upper()}_EVENT_EVIDENCE")
        if kind == "input" and not isinstance(event["trigger_rule_sha256"], str):
            raise AlignmentReject("INPUT_EVENT_EVIDENCE")
        if kind == "analog" and (
                not isinstance(event["threshold_rule_sha256"], str)
                or type(event["clipped"]) is not bool):
            raise AlignmentReject("ANALOG_EVENT_EVIDENCE")
        previous = event["time_ns"]
    return value


def align(value: dict[str, Any]) -> dict[str, Any]:
    required = {"session_ids", "timebase_ids", "input_edge_ns", "digital_tx_ns",
                "analog_response_ns", "input_uncertainty_ns",
                "analog_uncertainty_ns", "threshold_rule", "trigger_rule",
                "measurement_profiles", "event_evidence", "analog_clipped"}
    if set(value) != required:
        raise AlignmentReject("INPUT_SHAPE")
    if not _frozen_rule(value["threshold_rule"]):
        return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1",
                "status": "UNKNOWN_THRESHOLD_RULE"}
    if not _frozen_rule(value["trigger_rule"]):
        return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1",
                "status": "UNKNOWN_TRIGGER_RULE"}
    sessions = value["session_ids"]
    timebases = value["timebase_ids"]
    if (not isinstance(sessions, dict) or not isinstance(timebases, dict)
            or set(sessions) != {"input", "digital", "analog"}
            or set(timebases) != {"input", "digital", "analog"}
            or any(not isinstance(item, str) or not item
                   for item in list(sessions.values()) + list(timebases.values()))
            or len(set(sessions.values())) != 1
            or len(set(timebases.values())) != 1):
        return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1",
                "status": "UNKNOWN_COMMON_TIMEBASE"}
    times = [value[name] for name in
             ("input_edge_ns", "digital_tx_ns", "analog_response_ns")]
    uncertainties = [value["input_uncertainty_ns"],
                     value["analog_uncertainty_ns"]]
    if (any(type(item) not in (int, float) or not math.isfinite(item)
            for item in times + uncertainties)
            or any(item < 0 for item in times + uncertainties)):
        raise AlignmentReject("TIME_VALUE")
    profiles = value["measurement_profiles"]
    if (not isinstance(profiles, dict)
            or set(profiles) != {"input", "digital", "analog"}
            or any(not _profile_ready(profiles[kind], sessions[kind],
                                      timebases[kind],
                                      value["trigger_rule"]["sha256"])
                   for kind in ("input", "digital", "analog"))):
        return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1",
                "status": "UNKNOWN_MEASUREMENT_PROFILE"}
    if (uncertainties[0] != profiles["input"]["document"]["uncertainty_ns"]
            or uncertainties[1]
            != profiles["analog"]["document"]["uncertainty_ns"]):
        raise AlignmentReject("PROFILE_UNCERTAINTY_MISMATCH")
    evidence = value["event_evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {"input", "digital", "analog"}:
        raise AlignmentReject("EVENT_EVIDENCE_SHAPE")
    input_events = _events(evidence["input"], "input")
    digital_events = _events(evidence["digital"], "digital")
    analog_events = _events(evidence["analog"], "analog")
    input_event = next((event for event in input_events
                        if event["trigger_rule_sha256"]
                        == value["trigger_rule"]["sha256"]), None)
    if input_event is None:
        return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1",
                "status": "UNKNOWN_INPUT_TRIGGER_EVIDENCE"}
    digital_event = next((event for event in digital_events
                          if event["time_ns"] >= input_event["time_ns"]), None)
    if digital_event is None:
        return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1",
                "status": "UNKNOWN_DIGITAL_EVENT"}
    analog_event = next((event for event in analog_events
                         if event["time_ns"] >= digital_event["time_ns"]
                         and event["threshold_rule_sha256"]
                         == value["threshold_rule"]["sha256"]), None)
    if analog_event is None:
        return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1",
                "status": "UNKNOWN_ANALOG_THRESHOLD_EVIDENCE"}
    if analog_event["clipped"] is not value["analog_clipped"]:
        raise AlignmentReject("ANALOG_CLIP_CONTRADICTION")
    if analog_event["clipped"]:
        return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1",
                "status": "UNKNOWN_ANALOG_CLIPPED"}
    selected = [input_event["time_ns"], digital_event["time_ns"],
                analog_event["time_ns"]]
    if times != selected:
        raise AlignmentReject("NOT_FIRST_MATCH_EVIDENCE")
    if not times[0] <= times[1] <= times[2]:
        raise AlignmentReject("EVENT_ORDER")
    uncertainty = sum(uncertainties)
    nominal = times[2] - times[0]
    return {"schema": "M3_R08_LATENCY_ALIGNMENT_V1", "status": "ALIGNED",
            "nominal_ns": nominal, "lower_ns": max(0, nominal - uncertainty),
            "upper_ns": nominal + uncertainty,
            "first_match": {"input": input_event, "digital": digital_event,
                            "analog": analog_event},
            "profile_sha256": {kind: profiles[kind]["sha256"]
                               for kind in ("input", "digital", "analog")},
            "threshold_rule_sha256": value["threshold_rule"]["sha256"],
            "trigger_rule_sha256": value["trigger_rule"]["sha256"],
            "under_10ms": nominal + uncertainty <= 10_000_000}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = align(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
