#!/usr/bin/env python3
"""Fail closed on six I2S output-path STA reports in an isolated Gowin project."""
from pathlib import Path
import sys
from capture_t034_formal_build import active_sdc_commands, cst_pins, placed_pins
from check_t009_fusion_report import Rows


def verify_paths(timing: str, pin_report: str, commands: list[str], sdc: str, cst: str):
    active_sdc_commands(timing, sdc)
    p = Rows()
    p.feed(timing)
    active = [row[2] for section, row in p.rows if section == "SDC_Report"
              and len(row) == 3 and row[1] == "Actived"]
    if len(commands) != 6 or len(set(commands)) != 6:
        raise ValueError("Expected six unique I2S report commands")
    missing = set(commands) - set(active)
    if missing or any(active.count(command) != 1 for command in commands):
        raise ValueError(f"Inactive or duplicate output path report commands: {missing}")
    for key in ("Numbers of Setup Violated Endpoints", "Numbers of Hold Violated Endpoints"):
        row = [r[1] for section, r in p.rows if section == "STA_Tool_Run_Summary"
               and len(r) == 2 and r[0] == key]
        if row != ["0"]:
            raise ValueError(f"STA global {key}: {row}")
    for kind in ("Recovery", "Removal"):
        entries = [r for section, r in p.rows if section == f"{kind}_Slack_Table"
                   and len(r) >= 4 and r[0].isdigit()]
        if not entries or min(float(row[1]) for row in entries) < 0:
            raise ValueError(f"Missing or negative {kind} slack")
    pins = placed_pins(pin_report)
    required = cst_pins(cst)
    if pins.keys() != required.keys():
        raise ValueError("Probe pinout and formal CST port sets differ")
    for port, fields in required.items():
        for key, value in fields.items():
            if pins[port][key] != value:
                raise ValueError(f"Probe pinout differs from formal CST: {port} {key}")
        if pins[port]["constrained"] != "Y":
            raise ValueError(f"Unconstrained formal pin: {port}")
    results = {}
    for index, port in enumerate(("i2s_bclk", "i2s_lrck", "i2s_din"), start=1):
        if port not in pins or pins[port]["constrained"] != "Y":
            raise ValueError(f"Missing constrained pin: {port}")
        results[port] = {}
        for kind in ("setup", "hold"):
            # Gowin reports the physical output-buffer node, not the port alias.
            section_name = f"{kind.capitalize()}_Slack_Table{index}"
            matches = [r for section, r in p.rows if section == section_name
                       and len(r) >= 4 and r[0].isdigit()
                       and r[3] == f"{port}_obuf/O"
                       and r[2].startswith("u_i2s_tx/") and r[2].endswith("/Q")]
            if len(matches) != 1:
                raise ValueError(f"Missing or ambiguous output path: {port} {kind}: {len(matches)}")
            try:
                slack = float(matches[0][1])
            except ValueError as error:
                raise ValueError(f"Invalid output slack {port} {kind}") from error
            if slack < 0:
                raise ValueError(f"Negative {port} {kind} slack: {slack}")
            results[port][kind] = {"slack_ns": slack, "from": matches[0][2], "to": matches[0][3]}
    return results


def main():
    if len(sys.argv) != 5:
        raise SystemExit("Usage: check_t034_output_paths.py TIMING_HTML PIN_REPORT PROBE_SDC FORMAL_CST")
    commands = [line.strip() for line in Path(sys.argv[3]).read_text(encoding="utf-8").splitlines()
                if line.lstrip().startswith("report_timing -")]
    try:
        print(verify_paths(Path(sys.argv[1]).read_text(encoding="utf-8"),
                           Path(sys.argv[2]).read_text(encoding="utf-8"), commands,
                           Path(sys.argv[3]).read_text(encoding="utf-8"),
                           Path(sys.argv[4]).read_text(encoding="utf-8")))
        return 0
    except (OSError, ValueError) as exc:
        print("FAIL T034 output paths:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
