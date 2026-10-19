"""Pure R13 admission arithmetic; this file never launches or consumes."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import math
from pathlib import Path

from finalize import atomic_json
from stream_bridge import read_control, require

PLAN_SHA256 = "729cb21bd4b759f7d5738bdc14964bee1eaf5da053eee20b4a278acf651357d3"
CAPS = {"P0": 60, "K": 120, "V": 120, "B": 120, "W": 900,
        "P1": 60, "R": 120, "GATE_01": 900, "S1": 60,
        "GATE_02": 900, "S2": 60}
ORDER = ("P0", "K", "V", "B", "W", "GATE_01", "S1", "GATE_02", "S2")
INITIAL_CASES = {"K": 8, "V": 12, "B": 12, "W": 1}


def _time(value):
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None and result.utcoffset() is not None,
            "TIMEZONE_REQUIRED")
    return result


def _repair(snapshot):
    value = snapshot.get("repair")
    if value is None:
        return None
    require(type(value) is dict and
            value.get("located_own_software_defect") is True and
            value.get("changed_sources_frozen") is True,
            "REPAIR_NOT_LOCATED_OR_FROZEN")
    failure_group = value.get("failure_group")
    affected = value.get("affected_case_ids")
    require(failure_group in {"K", "V", "B"} and
            type(affected) is list and 0 < len(affected) <= 16 and
            len(set(affected)) == len(affected) and
            all(case.startswith(failure_group) for case in affected),
            "REPAIR_AFFECTED_CASES")
    for key in ("failure_receipt_sha256", "old_source_sha256",
                "new_source_sha256", "diff_sha256"):
        require(type(value.get(key)) is str and len(value[key]) == 64,
                "REPAIR_IDENTITY:" + key)
    require(value["old_source_sha256"] != value["new_source_sha256"],
            "REPAIR_SOURCE_UNCHANGED")
    return value


def _prior_satisfied(name, slots, repair):
    if slots[name]["state"] == "PASS":
        return True
    return bool(repair and name == repair["failure_group"] and
                slots[name]["state"] == "FAIL" and
                slots["P1"]["state"] == "PASS" and
                slots["R"]["state"] == "PASS")


def assess_start(group, snapshot, prerequisites, now_iso):
    issues = []
    try:
        require(group in CAPS and snapshot["plan_sha256"] == PLAN_SHA256,
                "PLAN_OR_GROUP")
        now, start = _time(now_iso), _time(snapshot["start"])
        ends = [start + timedelta(hours=5), _time(snapshot["member_end"])]
        if snapshot.get("explicit_cutoff"):
            ends.append(_time(snapshot["explicit_cutoff"]))
        deadline = min(ends)
        require(_time(snapshot["deadline"]) == deadline and now >= start,
                "DEADLINE_OR_START")
        slots = snapshot["slots"]
        require(set(slots) == set(CAPS), "EXACT_SLOT_SET")
        repair = _repair(snapshot)
        charged = 0
        for name, cap in CAPS.items():
            state = slots[name]["state"]
            require(state in {"NOT_STARTED", "RUNNING", "PASS", "FAIL"},
                    "SLOT_STATE")
            expected = 0 if state == "NOT_STARTED" else cap
            require(slots[name]["charged_cap_seconds"] == expected,
                    "FULL_CAP_NO_REFUND")
            charged += expected
        if slots[group]["state"] != "NOT_STARTED":
            issues.append("SLOT_ALREADY_CONSUMED")
        if any(item["state"] == "RUNNING" for item in slots.values()):
            issues.append("SAFE_CHECKPOINT_REQUIRED")
        if group in ORDER:
            for earlier in ORDER[:ORDER.index(group)]:
                if not _prior_satisfied(earlier, slots, repair):
                    issues.append("EARLIER_NOT_PASS:" + earlier)
        elif group == "P1":
            if repair is None:
                issues.append("REPAIR_NOT_DECLARED")
            else:
                failed = repair["failure_group"]
                if slots["P0"]["state"] != "PASS":
                    issues.append("P0_NOT_PASS")
                if slots[failed]["state"] != "FAIL":
                    issues.append("LOCATED_GROUP_NOT_FAILED:" + failed)
                if slots["R"]["state"] != "NOT_STARTED":
                    issues.append("R_ALREADY_CONSUMED")
        elif group == "R":
            if repair is None:
                issues.append("REPAIR_NOT_DECLARED")
            else:
                if slots["P1"]["state"] != "PASS":
                    issues.append("P1_NOT_PASS")
                if slots[repair["failure_group"]]["state"] != "FAIL":
                    issues.append("LOCATED_GROUP_NOT_FAILED")
        count = prerequisites.get("case_count")
        if group in INITIAL_CASES and count != INITIAL_CASES[group]:
            issues.append("CASE_COUNT")
        if group == "R" and repair is not None and count != len(
                repair["affected_case_ids"]):
            issues.append("R_CASE_COUNT")
        required = {"root_authorization", "source_frozen",
                    "deadline_snapshot_current", "tool_profile_unchanged"}
        if group != "P0":
            required.add("P0_identity_and_job_proof_pass")
        if group in {"P1", "R"}:
            required |= {"failure_original_preserved", "diff_identity_frozen",
                         "new_source_identity_frozen"}
        if group == "W":
            required |= {"A2_exact_all_output_geometry_pass",
                         "delivery_channel_confirmed",
                         "all_logical_originals_recoverable",
                         "actual_D4_no_stub", "fresh_free_space_pass",
                         "resources_strict_coverage_and_bound_pass",
                         "source_semantics_ready"}
        issues += ["MISSING:" + key for key in sorted(required)
                   if prerequisites.get(key) is not True]
        network = snapshot["network_charged_seconds"]
        git = snapshot["local_git_charged_seconds"]
        require(type(network) is int and 0 <= network <= 1260 and
                type(git) is int and 0 <= git <= 360,
                "BUDGET_COUNTER")
        remaining_names = {name for name in ORDER
                           if slots[name]["state"] == "NOT_STARTED"}
        if repair is not None:
            remaining_names |= {name for name in ("P1", "R")
                                if slots[name]["state"] == "NOT_STARTED"}
        remaining = sum(CAPS[name] for name in remaining_names)
        reserve = remaining + (1260 - network) + (360 - git) + 60
        seconds_left = (deadline - now).total_seconds()
        if not math.isfinite(seconds_left) or seconds_left < reserve:
            issues.append("FULL_CAPS_DO_NOT_FIT")
        if charged + network + git + CAPS[group] > 5040:
            issues.append("PACKAGE_5040_CAP")
        if group == "W" and prerequisites.get("resource_profile") != "PASS":
            issues.append("W_RESOURCE_PROFILE_NOT_PASS")
        return {"schema": "M3_R13_START_DECISION_V1",
                "decision": "NO_GO" if issues else "GO_FOR_ROOT_CONSUMPTION_ONLY",
                "issues": issues, "group": group,
                "cap_seconds": CAPS[group], "deadline": deadline.isoformat(),
                "consumption_written": False, "execution_started": False}
    except (KeyError, TypeError, ValueError) as error:
        return {"schema": "M3_R13_START_DECISION_V1", "decision": "NO_GO",
                "issues": [type(error).__name__ + ":" + str(error)],
                "consumption_written": False, "execution_started": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assess-one", action="store_true", required=True)
    parser.add_argument("--group", required=True, choices=CAPS)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--prerequisites", required=True, type=Path)
    parser.add_argument("--prerequisites-sha256", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    snapshot = read_control(args.snapshot, args.snapshot_sha256)["value"]
    prerequisites = read_control(args.prerequisites,
                                 args.prerequisites_sha256)["value"]
    result = assess_start(args.group, snapshot, prerequisites, args.now)
    atomic_json(args.output, result)
    return 0 if result["decision"].startswith("GO") else 2


if __name__ == "__main__":
    raise SystemExit(main())
