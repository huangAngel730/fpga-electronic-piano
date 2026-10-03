"""Assess one frozen Gowin Hold-guardband experiment without editing reports.

The actual experiment uses 0.550 ns system Hold uncertainty. The existing
production gate requires 0.500 ns, so only that exact expected diagnostic is
handled locally; every other original interface/timing gate is retained.
Original-condition same-clock system Hold is a constraint-delta inference,
NOT a second STA run. Tool reports and the baseline remain untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from check_audio_visual_probe import check as check_original
from check_hdmi_link_report import ReportParser


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_report(folder: Path) -> dict:
    timing = folder / "impl/pnr/audio_visual_coexistence_top_tr_content.html"
    parser = ReportParser()
    parser.feed(timing.read_text(encoding="utf-8"))
    active = {row[2] for section, row in parser.rows
              if section == "SDC_Report" and len(row) == 3 and row[1] == "Actived"}
    summary = {row[0]: row[1] for section, row in parser.rows
               if section == "STA_Tool_Run_Summary" and len(row) == 2}
    worst = {}
    for kind in ("Setup", "Hold", "Recovery", "Removal"):
        by_clock = {}
        for section, row in parser.rows:
            if (not section.startswith(kind + "_Slack_Table")
                    or len(row) < 9 or not row[0].isdigit()):
                continue
            launch = row[4].split(":")[0]
            capture = row[5].split(":")[0]
            if launch != capture:
                continue
            slack = float(row[1])
            if launch not in by_clock or slack < by_clock[launch]["slack_ns"]:
                by_clock[launch] = {
                    "slack_ns": slack, "from": row[2], "to": row[3],
                    "launch": row[4], "capture": row[5], "section": section,
                    "clock_skew_ns": float(row[7]), "data_path_ns": float(row[8]),
                }
        worst[kind] = by_clock
    tns = [row for section, row in parser.rows
           if section == "Total_Negative_Slack_Report" and len(row) == 4
           and row[0] in {"sys_clk", "video_pixel", "video_serial"}]
    pulse = [row for section, row in parser.rows
             if section == "MIN_PULSE_WIDTH_TABLE" and len(row) >= 7
             and row[0].isdigit()]
    errors, facts = check_original(folder)
    return {"per_clock_tns": tns,
            "min_pulse_width_slack_ns": min(float(row[1]) for row in pulse) if pulse else None,"active_sdc": sorted(active), "summary": summary,
            "per_clock_worst": worst, "original_gate_errors": errors,
            "facts": facts, "timing_report_sha256": digest(timing)}


def normalize_pnr_options(path: Path) -> list[str]:
    options = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if line.startswith(("-d ", "-cst ", "-cfg ", "-sdc ")):
            options.append(line.split(" ", 1)[0] + " <path>")
        else:
            options.append(line)
    return options


def assess(output: Path) -> dict:
    manifest = json.loads((output / "experiment_manifest.json").read_text(encoding="utf-8"))
    base = Path(manifest["baseline_project"]).parent
    trial = Path(manifest["trial_project"]).parent
    if manifest["planned_pnr_runs"] != 1 or not manifest["no_seed_search"]:
        raise ValueError("This entry only accepts the agreed one-run experiment")
    changed = [name for group in ("inputs_before", "roms_before", "baseline_artifacts")
               for name, expected in manifest[group].items()
               if not Path(name).is_file() or digest(Path(name)) != expected]
    if changed:
        raise ValueError("Frozen input/baseline changed: " + repr(changed))
    projects = [ET.parse(folder / "audio_visual_coexistence_top.gprj").getroot()
                for folder in (base, trial)]
    filelists = [list(project.find("FileList")) for project in projects]
    if len(filelists[0]) != len(filelists[1]):
        raise ValueError("File lists changed length")
    delta = [(a.attrib, b.attrib) for a, b in zip(*filelists) if a.attrib != b.attrib]
    if len(delta) != 1 or delta[0][0]["type"] != "file.sdc":
        raise ValueError("More than the experiment SDC changed")
    old_sdc = Path(delta[0][0]["path"]).read_bytes()
    new_sdc = Path(delta[0][1]["path"]).read_bytes()
    before = b"set_clock_uncertainty -hold  0.500 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]"
    if old_sdc.count(before) != 1 or old_sdc.replace(before, before.replace(b"0.500", b"0.550"), 1) != new_sdc:
        raise ValueError("SDC delta is not exactly the agreed +0.050ns Hold guardband")
    if int((trial / "build_exit.txt").read_text()) != 0:
        raise ValueError("Gowin flow returned a failure")
    reports = {"baseline": parse_report(base), "strict_trial": parse_report(trial)}
    baseline, candidate = reports["baseline"], reports["strict_trial"]
    expected = "formal audio clock uncertainty missing: hold"
    raw_errors = candidate["original_gate_errors"]
    strict_gate_errors = [error for error in raw_errors if error != expected]
    if baseline["original_gate_errors"]:
        raise ValueError("Original baseline no longer passes its own gates")
    old_command = "set_clock_uncertainty -hold 0.500 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]"
    new_command = old_command.replace("0.500", "0.550")
    old_active, new_active = set(baseline["active_sdc"]), set(candidate["active_sdc"])
    if old_command not in old_active or new_command not in new_active:
        strict_gate_errors.append("Expected exact active Hold command missing")
    if (old_active - {old_command}) != (new_active - {new_command}):
        strict_gate_errors.append("Other active constraints/report commands changed")
    if raw_errors.count(expected) != 1:
        strict_gate_errors.append("Original-gate expected constraint delta diagnostic missing/duplicated")
    opts = [normalize_pnr_options(folder / "impl/pnr/cmd.do") for folder in (base, trial)]
    if opts[0] != opts[1] or "-correct_hold 1" not in opts[1]:
        strict_gate_errors.append("PnR settings or automatic Hold repair changed")
    required_tns = {(clock, kind) for clock in ("sys_clk", "video_pixel", "video_serial")
                    for kind in ("Setup", "Hold")}
    tns_rows = candidate["per_clock_tns"]
    if (len(tns_rows) != 6 or {(row[0], row[1]) for row in tns_rows} != required_tns
            or any(float(row[2]) != 0 or row[3] != "0" for row in tns_rows)):
        strict_gate_errors.append("Per-clock TNS/violated endpoint evidence missing or negative")
    pulse = candidate["min_pulse_width_slack_ns"]
    if pulse is None or pulse < 0:
        strict_gate_errors.append("Minimum pulse-width evidence missing or negative")
    held = candidate["per_clock_worst"]["Hold"].get("sys_clk")
    setup = candidate["per_clock_worst"]["Setup"].get("sys_clk")
    if held is None or setup is None:
        strict_gate_errors.append("System worst Hold/Setup path evidence missing")
    # Only infer SAME-CLOCK sys_clk Hold. Do not adjust generated clocks, CDC,
    # report text or original-gate results. 0.0005ns allows displayed rounding.
    strict_sys_hold = held["slack_ns"] if held else None
    inferred_original = round(strict_sys_hold + 0.050, 6) if held else None
    conservative_lower = round(strict_sys_hold + 0.050 - 0.0005, 6) if held else None
    old_resources = baseline["facts"]["resources"]
    new_resources = candidate["facts"]["resources"]
    resource_delta = {key: new_resources[key] - old_resources[key] for key in old_resources}
    criteria = {
        "all_strict_timing_CDC_interface_gates_pass": not strict_gate_errors,
        "original_condition_system_hold_lower_bound_at_least0_050":
            conservative_lower is not None and conservative_lower >= 0.050,
        "system_setup_at_least0_500": setup is not None and setup["slack_ns"] >= 0.500,
        "no_resource_increase": all(value <= 0 for value in resource_delta.values()),
        "all_original_inputs_and_ROM_hashes_unchanged": True,
        "only_agreed_constraint_command_changed": True,
        "routing_options_unchanged": opts[0] == opts[1],
    }
    comparison = {
        "system_setup_delta_ns": round(setup["slack_ns"] - baseline["per_clock_worst"]["Setup"]["sys_clk"]["slack_ns"], 6) if setup else None,
        "pixel_setup_delta_ns": round(candidate["per_clock_worst"]["Setup"]["video_pixel"]["slack_ns"] - baseline["per_clock_worst"]["Setup"]["video_pixel"]["slack_ns"], 6),
        "system_hold_improvement_under_original_uncertainty_inferred_ns": round(inferred_original - baseline["per_clock_worst"]["Hold"]["sys_clk"]["slack_ns"], 6) if held else None,
        "actual_strict_removal_delta_ns": round(candidate["facts"]["exported_min_slack_ns"]["Removal"] - baseline["facts"]["exported_min_slack_ns"]["Removal"], 6),
        "actual_routes_compared": True,
        "power_not_measured": True,
        "functional_simulation_reused_only_by_exact_RTL_ROM_hash_identity": "V0158; no logic changes and no duplicate million-check regression claimed",
    }
    artifacts = {}
    for name in ("build.log", "impl/pnr/cmd.do", "impl/pnr/audio_visual_coexistence_top_tr_content.html",
                 "impl/pnr/audio_visual_coexistence_top.rpt.txt", "impl/pnr/audio_visual_coexistence_top.pin.html"):
        artifacts[name] = digest(trial / name)
    research_fs = trial / "impl/pnr/audio_visual_coexistence_top.fs"
    if research_fs.is_file():
        artifacts["research_only_fs"] = digest(research_fs)
    return {
        "date": "2026-10-03", "scope": manifest["scope"], "reports": reports,
        "strict_gate_errors": strict_gate_errors,
        "original_condition_hold": {
            "method": "inference on unchanged same routed sys_clk-to-sys_clk paths, not an independent STA run",
            "strict_tool_report_ns": strict_sys_hold, "uncertainty_delta_ns": 0.050,
            "inferred_original_condition_ns": inferred_original,
            "conservative_display_rounding_lower_bound_ns": conservative_lower,
            "generated_clock_and_CDC_reports_not_adjusted": True,
            "raw_reports_never_edited": True,
            "original_condition_STA_actually_run": False,
        },
        "resource_delta": resource_delta, "comparison": comparison, "criteria": criteria,
        "meets_numeric_screen": all(criteria.values()),
        "disposition": "eligible experimental routing candidate; formal adoption still requires exact accepted constraints and final integrated STA"
                       if all(criteria.values()) else "reject trial and retain previous approved version",
        "pnr_runs": 1, "no_second_PnR_or_seed_search": True,
        "formal_RTL_and_constraints_changed": False, "programmed": False,
        "trial_released_for_board_testing": False,
        "artifact_sha256": artifacts,
        "manifest_sha256": digest(output / "experiment_manifest.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = assess(args.output.resolve())
    (args.output / "assessment.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"criteria": result["criteria"], "disposition": result["disposition"],
                      "resource_delta": result["resource_delta"],
                      "original_condition_hold": result["original_condition_hold"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
