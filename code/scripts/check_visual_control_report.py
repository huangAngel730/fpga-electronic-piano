#!/usr/bin/env python3
"""Check physical CDC evidence for the M2 score/mode-only experiment."""
import argparse
from pathlib import Path
import sys
from check_hdmi_link_report import ReportParser

SCORE = "u_control/u_score_mailbox"
MODE = "u_control/u_mode_mailbox"
BUS = (f"set_max_delay -from [get_regs {{{SCORE}/payload_hold*}}] "
       f"-to [get_regs {{{SCORE}/dst_data*}}] ")


def check(text: str, mode: str) -> list[str]:
    p = ReportParser()
    p.feed(text)
    errors = []
    summary = {r[0]: r[1] for sec, r in p.rows
               if sec == "STA_Tool_Run_Summary" and len(r) == 2}
    clocks = {r[1]: r[3:5] for sec, r in p.rows
              if sec == "Clock_Report" and len(r) >= 5 and r[0].isdigit()}
    expected_clocks = {"sys_clk": ["20.000", "50.000"],
                       "video_pixel": ["40.000", "25.000"],
                       "video_serial": ["8.000", "125.000"]}
    for name, want in expected_clocks.items():
        if clocks.get(name) != want:
            errors.append(f"wrong/missing clock {name}")
    active = {r[2] for sec, r in p.rows if sec == "SDC_Report"
              and len(r) == 3 and r[1] == "Actived"}
    exceptions = {"set_false_path -from [get_ports {sys_rst_n}]"}
    for prefix in (SCORE, MODE):
        for first, second in (("ack_meta", "ack_sync"), ("req_meta", "req_sync")):
            exceptions.add(f"set_false_path -to [get_pins {{{prefix}/{first}_s0/D}}]")
            for kind in ("Setup", "Hold"):
                cmd = (f"report_timing -{kind.lower()} -from "
                       f"[get_regs {{{prefix}/{first}_s0}}] -to "
                       f"[get_regs {{{prefix}/{second}_s0}}] -max_paths 1")
                if cmd not in active:
                    errors.append(f"inactive second-stage report {prefix}/{first} {kind}")
                rows = [r for sec, r in p.rows if sec.startswith(kind + "_Slack_Table")
                        and len(r) >= 4 and r[2] == f"{prefix}/{first}_s0/Q"
                        and r[3] == f"{prefix}/{second}_s0/D"]
                if len(rows) != 1 or float(rows[0][1]) < 0:
                    errors.append(f"missing/failing timed second stage {prefix}/{first} {kind}")
    if {s for s in active if s.startswith("set_false_path")} != exceptions:
        errors.append("first-stage exception set missing, broad or unreviewed")
    if any(s.startswith("set_clock_groups") for s in active):
        errors.append("whole clock groups must not be cut")
    limit = "0.001" if mode == "sentinel" else "10.000"
    if BUS + limit not in active:
        errors.append("score payload delay budget inactive/missing")
    bus_rows = [r for sec, r in p.rows if sec.startswith("Setup_Slack_Table")
                and len(r) >= 4 and r[2].startswith(SCORE + "/payload_hold")
                and r[3].startswith(SCORE + "/dst_data")]
    if len(bus_rows) != 98 or len({r[3] for r in bus_rows}) != 98:
        errors.append(f"must explicitly list 98 unique score endpoints: got {len(bus_rows)}")
    elif mode == "sentinel":
        if not all(float(r[1]) < 0 for r in bus_rows):
            errors.append("1 ps sentinel must fail every one of the 98 data paths")
    elif not all(float(r[1]) >= 0 for r in bus_rows):
        errors.append("score payload violates 10 ns bound")
    if summary.get("Numbers of Setup Violated Endpoints") != ("98" if mode == "sentinel" else "0"):
        errors.append("unexpected global setup endpoint count")
    if summary.get("Numbers of Hold Violated Endpoints") != "0":
        errors.append("global hold endpoints violated or missing")
    if not summary.get("Numbers of Paths Analyzed", "").isdigit() or \
            int(summary.get("Numbers of Paths Analyzed", "0")) < 1:
        errors.append("no analyzed physical paths")
    for kind in ("Recovery_Slack_Table", "Removal_Slack_Table"):
        rows = [r for sec, r in p.rows if sec == kind and len(r) >= 4 and r[0].isdigit()]
        if not rows or min(float(r[1]) for r in rows) < 0:
            errors.append(f"missing or violated {kind}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--mode", required=True, choices=("sentinel", "bounded"))
    args = parser.parse_args()
    errors = check(args.report.read_text(encoding="utf-8"), args.mode)
    if errors:
        for item in errors:
            print("FAIL", item)
        return 1
    print(f"PASS control CDC {args.mode}: 98 score paths, 8 timed second stages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
