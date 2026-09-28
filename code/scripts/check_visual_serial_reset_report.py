#!/usr/bin/env python3
"""Validate only the M2 serial reset placement/recovery experiment.

This is a sub-gate; full visual STA must also pass before any board image.
"""
import argparse
from pathlib import Path
import sys

from check_hdmi_link_report import ReportParser

EXPECTED_FROM = "u_serial_reset/sync_chain_1_s0/Q"
EXPECTED_TO = "u_video_tx/rgb2dvi_inst/u_OSER10_clk/RESET"
EXPECTED_LOCATION = "R49C101[1][B]"


def check(timing: str, cst: str) -> list[str]:
    parser = ReportParser()
    parser.feed(timing)
    errors = []
    constraints = (
        'INS_LOC "u_serial_reset/sync_chain_0_s0" R49C101[1][A];',
        'INS_LOC "u_serial_reset/sync_chain_1_s0" R49C101[1][B];',
    )
    for item in constraints:
        if cst.count(item) != 1:
            errors.append(f"missing or ambiguous physical constraint: {item}")
    paths = [r for section, r in parser.rows
             if section == "Recovery_Slack_Table" and len(r) >= 4
             and r[0].isdigit()]
    if not paths:
        errors.append("no recovery paths")
        return errors
    if min(float(r[1]) for r in paths) < 0:
        errors.append("negative recovery slack")
    match = [r for r in paths if r[2] == EXPECTED_FROM and r[3] == EXPECTED_TO]
    if not match or min(float(r[1]) for r in match) < 0:
        errors.append("measured OSER10 RESET path absent/negative")
    physical = [r for section, r in parser.rows
                if section == "Recovery_Analysis" and len(r) >= 7
                and EXPECTED_FROM in r[-1]
                and EXPECTED_LOCATION in r]
    if not physical:
        errors.append("launch FF not at reviewed R49C101[1][B]")
    removal = [r for section, r in parser.rows
               if section == "Removal_Slack_Table" and len(r) >= 4
               and r[0].isdigit()]
    if not removal or min(float(r[1]) for r in removal) < 0:
        errors.append("missing or negative removal slack")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("timing", type=Path)
    parser.add_argument("--cst", type=Path, required=True)
    args = parser.parse_args()
    errors = check(args.timing.read_text(encoding="utf-8"),
                   args.cst.read_text(encoding="ascii"))
    if errors:
        for error in errors:
            print("FAIL", error)
        return 1
    print("PASS M2 measured reset placement/recovery only; full visual gate required")
    return 0


if __name__ == "__main__":
    sys.exit(main())
