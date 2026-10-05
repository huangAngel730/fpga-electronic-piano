#!/usr/bin/env python3
"""Fail-closed gate for an isolated M2 full visual path, including CDC paths.

A Gowin SDC command marked Actived is not sufficient proof that its endpoint
collection is nonempty. Explicit numbered timing tables are required here.
"""
import argparse
from pathlib import Path
import sys

from check_hdmi_link_report import ReportParser, analyze_pins

FIRST_STAGES = (
    ("u_event_bridge", "ack_meta", "ack_sync"),
    ("u_event_bridge", "req_meta", "req_sync"),
    ("u_event_bridge", "desync_meta", "video_desync"),
    ("u_control/u_score_mailbox", "ack_meta", "ack_sync"),
    ("u_control/u_score_mailbox", "req_meta", "req_sync"),
    ("u_control/u_mode_mailbox", "ack_meta", "ack_sync"),
    ("u_control/u_mode_mailbox", "req_meta", "req_sync"),
)
BUSS = (
    ("u_event_bridge", "payload_hold", "video_data"),
    ("u_control/u_score_mailbox", "payload_hold", "dst_data"),
)
EXPECTED_CLOCKS = {
    "sys_clk": ["20.000", "50.000"],
    "video_pixel": ["40.000", "25.000"],
    "video_serial": ["8.000", "125.000"],
}


def check(timing: str, pins: str) -> tuple[list[str], dict]:
    parser = ReportParser()
    parser.feed(timing)
    rows = parser.rows
    errors = []
    summary = {r[0]: r[1] for section, r in rows
               if section == "STA_Tool_Run_Summary" and len(r) == 2}
    active = {r[2] for section, r in rows
              if section == "SDC_Report" and len(r) == 3
              and r[1] == "Actived"}
    clocks = {r[1]: r[3:5] for section, r in rows
              if section == "Clock_Report" and len(r) >= 5 and r[0].isdigit()}
    for name, expected in EXPECTED_CLOCKS.items():
        if clocks.get(name) != expected:
            errors.append(f"missing/mismatched {name}: {clocks.get(name)}")
    for key in ("Numbers of Setup Violated Endpoints",
                "Numbers of Hold Violated Endpoints"):
        if summary.get(key) != "0":
            errors.append(f"{key}: {summary.get(key, 'MISSING')}")
    for key in ("Numbers of Paths Analyzed", "Numbers of Endpoints Analyzed"):
        if not summary.get(key, "").isdigit() or int(summary[key]) < 1:
            errors.append(f"missing analyzed paths/endpoints: {key}")
    for kind in ("Recovery_Slack_Table", "Removal_Slack_Table"):
        matches = [r for section, r in rows if section == kind
                   and len(r) >= 4 and r[0].isdigit()]
        if not matches or min(float(r[1]) for r in matches) < 0:
            errors.append(f"missing/negative {kind}")
    _, pin_errors = analyze_pins(pins)
    errors.extend(pin_errors)

    expected_false = {"set_false_path -from [get_ports {sys_rst_n}]"}
    for prefix, first, second in FIRST_STAGES:
        exception = f"set_false_path -to [get_pins {{{prefix}/{first}_s0/D}}]"
        expected_false.add(exception)
        for kind in ("Setup", "Hold"):
            command = (f"report_timing -{kind.lower()} -from "
                       f"[get_regs {{{prefix}/{first}_s0}}] -to "
                       f"[get_regs {{{prefix}/{second}_s0}}] -max_paths 1")
            if command not in active:
                errors.append(f"inactive second-stage report: {prefix} {kind}")
            paths = [r for section, r in rows
                     if section.startswith(kind + "_Slack_Table")
                     and len(r) >= 4 and r[0].isdigit()
                     and r[2] == f"{prefix}/{first}_s0/Q"
                     and r[3] == f"{prefix}/{second}_s0/D"]
            if len(paths) != 1 or float(paths[0][1]) < 0:
                errors.append(f"missing/negative second-stage path: {prefix} {kind}")
    actual_false = {s for s in active if s.startswith("set_false_path")}
    if actual_false != expected_false:
        errors.append("unexpected or missing first-stage false-path exception")
    if any(s.startswith("set_clock_groups") for s in active):
        errors.append("clock groups are broadly cut")

    bus_count = {}
    for index, (prefix, source, sink) in enumerate(BUSS, start=1):
        command = (f"set_max_delay -from [get_regs {{{prefix}/{source}*}}] "
                   f"-to [get_regs {{{prefix}/{sink}*}}] 10.000")
        report = (f"report_timing -setup -from "
                  f"[get_regs {{{prefix}/{source}*}}] -to "
                  f"[get_regs {{{prefix}/{sink}*}}] "
                  f"-max_paths 128 -max_common_paths 1")
        if command not in active or report not in active:
            errors.append(f"inactive payload constraint/report: {prefix}")
        paths = [r for section, r in rows
                 if section == f"Setup_Slack_Table{index}"
                 and len(r) >= 4 and r[0].isdigit()]
        if not paths or len(paths) >= 128:
            errors.append(f"empty or truncated payload path table: {prefix}")
        if not all(r[2].startswith(f"{prefix}/{source}")
                   and r[3].startswith(f"{prefix}/{sink}")
                   and float(r[1]) >= 0 for r in paths):
            errors.append(f"unexpected/negative payload path: {prefix}")
        if len({r[3] for r in paths}) != len(paths):
            errors.append(f"duplicate destination payload endpoint: {prefix}")
        bus_count[prefix] = len(paths)
    return errors, {"summary": summary, "bus_path_count": bus_count}


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("timing", type=Path)
    argp.add_argument("--pin-report", type=Path, required=True)
    args = argp.parse_args()
    errors, facts = check(args.timing.read_text(encoding="utf-8"),
                          args.pin_report.read_text(encoding="utf-8"))
    if errors:
        for error in errors:
            print("FAIL", error)
        return 1
    print("PASS isolated full path: surviving payload paths are bounded; "
          f"counts={facts['bus_path_count']}; not full 64/98-bit coverage")
    return 0


if __name__ == "__main__":
    sys.exit(main())
