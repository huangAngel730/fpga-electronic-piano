#!/usr/bin/env python3
"""Fail closed on standalone Gowin ADSR report, including actual resource rows."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import re


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section = ""
        self.row = []
        self.cell = None
        self.rows = []

    def finish_cell(self):
        if self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "a" and "name" in dict(attrs):
            self.section = dict(attrs)["name"]
        if tag == "tr":
            self.finish_cell()
            self.row = []
        if tag in ("td", "th"):
            self.finish_cell()
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.finish_cell()
        if tag == "tr":
            self.finish_cell()
            self.rows.append((self.section, self.row))
            self.row = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def verify(timing: str, usage: str) -> tuple[list[str], dict]:
    parser = Rows()
    parser.feed(timing)
    errors = []
    summary = {r[0]: r[1] for name, r in parser.rows
               if name == "STA_Tool_Run_Summary" and len(r) == 2}
    for key in ("Numbers of Setup Violated Endpoints",
                "Numbers of Hold Violated Endpoints"):
        if summary.get(key) != "0":
            errors.append(f"{key}: {summary.get(key, 'missing')}")
    for key in ("Numbers of Paths Analyzed", "Numbers of Endpoints Analyzed"):
        if not summary.get(key, "").isdigit() or int(summary[key]) == 0:
            errors.append(f"No timing paths for {key}")
    clocks = [r for name, r in parser.rows if name == "Clock_Report"
              and len(r) >= 5 and r[1] == "sys_clk"]
    if len(clocks) != 1 or clocks[0][3:5] != ["20.000", "50.000"]:
        errors.append("Missing or incorrect 50 MHz sys_clk constraint")
    fmax = [r for name, r in parser.rows if name == "Max_Frequency_Report"
            and len(r) >= 4 and r[1] == "sys_clk"]
    if len(fmax) != 1:
        errors.append("No sys_clk Fmax evidence")
    else:
        try:
            if float(fmax[0][3].replace("(MHz)", "")) < 50:
                errors.append(f"Fmax under 50 MHz: {fmax[0][3]}")
        except ValueError:
            errors.append("Invalid Fmax")
    worst = {}
    for kind in ("Setup", "Hold", "Recovery", "Removal"):
        section = kind + "_Slack_Table"
        paths = [r for name, r in parser.rows if name == section
                 and len(r) >= 4 and r[0].isdigit()]
        if kind in ("Recovery", "Removal") and not paths:
            # No paths exist if a particular recovery/removal relationship is
            # absent in this standalone implementation. This is not a claim
            # that those paths were analyzed.
            worst[kind] = None
            continue
        if not paths:
            errors.append("Missing " + kind + " path table")
            continue
        try:
            lowest = min(paths, key=lambda r: float(r[1]))
            worst[kind] = float(lowest[1])
            if worst[kind] < 0:
                errors.append(f"{kind} negative slack: {lowest[1]} ns")
        except ValueError:
            errors.append("Invalid " + kind + " slack")
    if not re.search(r"<Part Number>:\s*GW5AT-LV60PG484AC1/I0", usage):
        errors.append("Wrong or missing GW5AT-60 part")
    resources = {}
    for name in ("Logic", "Register", "DSP", "BSRAM"):
        matches = re.findall(r"^\s*" + name + r"\s*\|\s*(\d+)/(\d+)", usage, re.M)
        if len(matches) != 1:
            errors.append("Missing resource: " + name)
        else:
            resources[name] = int(matches[0][0])
    latch = re.search(r"^\s*--Logic Register as Latch\s*\|\s*(\d+)/", usage, re.M)
    if latch is None or int(latch[1]) != 0:
        errors.append("Latch usage not proven zero")
    return errors, {"resources": resources, "worst_ns": worst,
                    "fmax_mhz": fmax[0][3] if len(fmax) == 1 else None,
                    "setup_hold_violated_endpoints": (
                        summary.get("Numbers of Setup Violated Endpoints"),
                        summary.get("Numbers of Hold Violated Endpoints"))}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("timing", type=Path)
    cli.add_argument("resources", type=Path)
    args = cli.parse_args()
    errors, info = verify(args.timing.read_text(encoding="utf-8"),
                          args.resources.read_text(encoding="utf-8"))
    for problem in errors:
        print("FAIL T009", problem)
    if errors:
        return 1
    print("PASS T009 standalone PnR", info)
    print("No top, stereo audio, MIDI or board validation implied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
