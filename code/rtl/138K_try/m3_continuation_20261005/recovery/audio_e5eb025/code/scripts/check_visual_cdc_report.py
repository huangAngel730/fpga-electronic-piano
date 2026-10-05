#!/usr/bin/env python3
"""Fail closed on the independent M2 mailbox CDC timing experiment."""
import argparse
from pathlib import Path
import sys

from check_hdmi_link_report import ReportParser, analyze


ACK = "set_false_path -to [get_pins {u_bridge/ack_meta_s0/D}]"
REQ = "set_false_path -to [get_pins {u_bridge/req_meta_s0/D}]"
DESYNC = "set_false_path -to [get_pins {u_bridge/desync_meta_s0/D}]"
BUS = "set_max_delay -from [get_regs {u_bridge/payload_hold*}] " \
      "-to [get_regs {u_bridge/video_data*}] "


def check(text: str, mode: str) -> list[str]:
    parser = ReportParser()
    parser.feed(text)
    analyzed = analyze(text)
    failures = []
    summary = analyzed["summary"]
    clocks = analyzed["clocks"]
    for name, expected in {"sys_clk": ["20.000", "50.000"],
                           "video_serial": ["8.000", "125.000"],
                           "video_pixel": ["40.000", "25.000"]}.items():
        if clocks.get(name) != expected:
            failures.append(f"clock {name}: {clocks.get(name)}")
    if summary.get("Numbers of Paths Analyzed", "0").isdigit() and \
            int(summary.get("Numbers of Paths Analyzed", "0")) > 0:
        pass
    else:
        failures.append("no analyzed timing paths")
    active = [r[2] for section, r in parser.rows
              if section == "SDC_Report" and len(r) == 3
              and r[1] == "Actived"]
    def constraint_present(command: str) -> bool:
        return command in active
    for command in (ACK, REQ, DESYNC):
        if not constraint_present(command):
            failures.append(f"inactive or missing synchronizer exception: {command}")
    limit = "0.001" if mode == "sentinel" else "10.000"
    if not constraint_present(BUS + limit):
        failures.append(f"inactive or missing payload max delay {limit} ns")
    for reg in ("ack_meta", "ack_sync", "req_meta", "req_sync",
                "desync_meta"):
        if f"u_bridge/{reg}_s0" not in text:
            failures.append(f"missing synchronizer register {reg}")
    # Keep the second synchronizer stages in the timing graph. An active
    # command alone is insufficient: every setup/hold report must contain
    # the expected Q -> D path with nonnegative slack.
    for first, second in (("ack_meta", "ack_sync"),
                          ("req_meta", "req_sync"),
                          ("desync_meta", "video_desync")):
        for kind in ("Setup", "Hold"):
            command = (f"report_timing -{kind.lower()} -from "
                       f"[get_regs {{u_bridge/{first}_s0}}] -to "
                       f"[get_regs {{u_bridge/{second}_s0}}] -max_paths 1")
            if not constraint_present(command):
                failures.append(f"inactive report command: {command}")
            matching = [r for section, r in parser.rows
                        if section.startswith(kind + "_Slack_Table")
                        and len(r) >= 4
                        and r[2] == f"u_bridge/{first}_s0/Q"
                        and r[3] == f"u_bridge/{second}_s0/D"]
            if len(matching) != 1 or float(matching[0][1]) < 0:
                failures.append(f"missing/failing second-stage {kind}: "
                                f"{first} -> {second}")
    # Explicit report_timing commands give numbered Setup/Hold tables, so
    # the generic checker cannot require an unnumbered Setup_Slack_Table.
    # The bus exception summary is a separate Setup_Analysis_Exceptions block.
    bus_summary = {row[0]: row[1] for section, row in parser.rows
                   if section == "Setup_Analysis_Exceptions" and len(row) == 2
                   and row[0] in ("Slack", "From", "To")}
    if "payload_hold." not in bus_summary.get("From", "") or \
            "video_data." not in bus_summary.get("To", ""):
        failures.append("bus exception lacks physical payload -> capture path")
    try:
        bus_slack = float(bus_summary["Slack"])
    except (KeyError, ValueError):
        failures.append("bus exception has no numeric slack")
        bus_slack = float("nan")
    if summary.get("Numbers of Hold Violated Endpoints") != "0":
        failures.append("hold endpoints violated")
    for kind in ("Recovery_Slack_Table", "Removal_Slack_Table"):
        rows = [row for section, row in parser.rows if section == kind
                and len(row) >= 4 and row[0].isdigit()]
        if not rows or min(float(row[1]) for row in rows) < 0:
            failures.append(f"missing or failing {kind}")
    if mode == "sentinel":
        if summary.get("Numbers of Setup Violated Endpoints") != "64":
            failures.append("1 ps sentinel must fail exactly 64 payload endpoints")
        if not bus_slack < 0:
            failures.append("1 ps sentinel did not fail the bus constraint")
    else:
        if summary.get("Numbers of Setup Violated Endpoints") != "0":
            failures.append("setup endpoints violated")
        if not bus_slack >= 0:
            failures.append("bounded payload slack negative")
    return failures


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("report", type=Path)
    argp.add_argument("--mode", choices=("sentinel", "bounded"), required=True)
    args = argp.parse_args()
    errors = check(args.report.read_text(encoding="utf-8"), args.mode)
    if errors:
        for error in errors:
            print("FAIL", error)
        return 1
    print(f"PASS independent CDC {args.mode} report (not full video timing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
