"""Single bounded software group for the R06 event calendar checker."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from event_calendar import CANONICAL_FIELDS, load_json, run_files
from fixtures import build_fixture, clone_rows, fixture_binding


PULSE_FIELDS = {
    "frame_tick", "event_valid", "event_ready", "apply_valid",
    "apply_event_seq", "apply_data", "note_on_mask", "note_off_mask",
    "retire_mask", "req_valid", "req_ready", "req_id", "advance_mask",
    "advance_frame_req_id", "result_valid", "result_ready", "result_id",
    "result_left", "result_right", "result_clip_mask", "commit",
    "commit_id", "commit_left", "commit_right", "commit_clip", "cancel",
    "config_valid", "config_ready", "effect_input_valid",
    "effect_input_ready", "effect_input_id", "effect_input_left",
    "effect_input_right", "effect_input_clip_mask", "tx_sample_valid",
    "finish",
}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps({key: row[key] for key in CANONICAL_FIELDS if key in row},
                                    separators=(",", ":")) + "\n")


def quiet_clone(rows: list[dict[str, Any]], cycle: int, epoch: int) -> dict[str, Any]:
    prior = [row for row in rows if row["cycle"] < cycle and row["epoch"] == epoch]
    if not prior:
        raise AssertionError(f"no prior row for {epoch}:{cycle}")
    row = copy.deepcopy(max(prior, key=lambda item: item["cycle"]))
    row["cycle"] = cycle
    for field in PULSE_FIELDS:
        row[field] = 0
    row["cancel_reason"] = None
    return row


def mutate(name: str, rows: list[dict[str, Any]], binding: dict[str, Any],
           frame_plan: dict[str, Any]) -> None:
    if name == "none":
        return
    if name == "untrusted_source":
        binding["trace_authority"] = "UNVERIFIED_METADATA"
        return
    if name == "missing_m1_semantics":
        binding["m1_semantics_authoritative"] = False
        return
    if name == "missing_frame_plan":
        frame_plan["authority"] = "MISSING_M2_CONTRACT"
        return
    if name == "missing_canonical_field":
        del rows[0]["apply_data"]
        return
    if name == "missing_actual_apply":
        target = next(row for row in rows
                      if row["apply_valid"] and row["apply_event_seq"] == 12)
        target["apply_valid"] = 0
        target["apply_event_seq"] = 0
        target["apply_data"] = 0
        return
    if name == "duplicate_actual_apply":
        target = next(row for row in rows
                      if row["apply_valid"] and row["apply_event_seq"] == 9)
        duplicate = copy.deepcopy(target)
        duplicate["cycle"] += 1
        rows.append(duplicate)
        rows.sort(key=lambda item: item["cycle"])
        return
    if name == "wrong_apply_data":
        target = next(row for row in rows
                      if row["apply_valid"] and row["apply_event_seq"] == 10)
        target["apply_data"] ^= 1
        return
    if name == "missing_post_cancel_frame":
        rows[:] = [row for row in rows if row["cycle"] not in {450_000, 450_005, 450_006}]
        return
    if name == "extra_idle_advance":
        row = quiet_clone(rows, 970_000, 0)
        row.update({"frame_tick": 1, "req_valid": 1, "req_ready": 1,
                    "req_id": 99, "advance_mask": 0xF,
                    "advance_frame_req_id": 99})
        rows.append(row)
        rows.sort(key=lambda item: item["cycle"])
        return
    if name == "wrong_common_mask":
        target = next(row for row in rows if row["frame_tick"] and row["req_id"] == 3
                      and row["epoch"] == 0)
        target["advance_mask"] = 0x7
        return
    if name == "commit_after_cancel":
        row = quiet_clone(rows, 350_010, 0)
        row["commit"] = 1
        row["commit_id"] = 4
        rows.append(row)
        rows.sort(key=lambda item: item["cycle"])
        return
    if name == "cross_epoch_commit":
        row = quiet_clone(rows, 1_010_000, 1)
        row["commit"] = 1
        row["commit_id"] = 10
        rows.append(row)
        rows.sort(key=lambda item: item["cycle"])
        return
    if name == "missing_finish":
        rows[:] = [row for row in rows if not row["finish"]]
        return
    raise AssertionError(name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = load_json(args.plan)
    case_spec = load_json(args.cases)
    if case_spec.get("schema") != "M3_R06_EVENT_CALENDAR_SELFTEST_CASES_V1":
        raise AssertionError("CASE_SCHEMA")
    base_rows, base_frame_plan = build_fixture(plan)
    base_binding = fixture_binding()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for case in case_spec["cases"]:
        case_dir = args.output / case["name"]
        case_dir.mkdir()
        rows = clone_rows(base_rows)
        binding = copy.deepcopy(base_binding)
        frame_plan = copy.deepcopy(base_frame_plan)
        mutate(case["mutation"], rows, binding, frame_plan)
        trace_path = case_dir / "trace.jsonl"
        binding_path = case_dir / "binding.json"
        frame_path = case_dir / "frame_plan.json"
        report_path = case_dir / "report.json"
        write_jsonl(trace_path, rows)
        write_json(binding_path, binding)
        write_json(frame_path, frame_plan)
        exit_code, report = run_files(args.plan, trace_path, binding_path,
                                      frame_path, report_path)
        assert exit_code == case["expected_exit"], (case["name"], exit_code, report)
        assert report["status"] == case.get("expected_status", "REJECT"), (
            case["name"], report
        )
        if "expected_error" in case:
            assert report.get("error") == case["expected_error"], (
                case["name"], report
            )
        results.append({"name": case["name"], "exit_code": exit_code,
                        "status": report["status"], "error": report.get("error")})

    valid = load_json(args.output / "valid_synthetic" / "report.json")
    assert valid["real_pro_calendar_pass"] is False
    assert valid["counts"]["accepted"] == 23
    assert valid["counts"]["applied"] == 23
    assert all(item["advance_mask"] == 0xF for item in valid["frame_ledger"])
    cancel_edge = [item for item in valid["same_edge_resolutions"]
                   if set(item["signals"]) == {"RESULT", "CANCEL"}]
    assert len(cancel_edge) == 1 and cancel_edge[0]["priority"][0] == "CANCEL"
    retire_after_hold = [len(item["active_notes"]) for item in valid["lifecycle"]
                         if item["retire_mask"] and 678_000 < item["cycle"] < 1_000_000]
    assert retire_after_hold == [3, 2, 1, 0], retire_after_hold
    summary = {
        "schema": "M3_R06_EVENT_CALENDAR_SELFTEST_SUMMARY_V1",
        "status": "PASS",
        "cases": len(results),
        "synthetic_passes": 1,
        "pending_cases": sum(item["exit_code"] == 3 for item in results),
        "rejected_cases": sum(item["exit_code"] == 2 for item in results),
        "real_trace_cases": 0,
        "hdl_sim_eda_hardware_calls": 0,
        "results": results,
    }
    write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
