#!/usr/bin/env python3
"""Fail closed on the M2 HDMI probe's Gowin timing report, including recovery.

Gowin HTML sometimes omits closing td tags. The parser handles new cells/rows
as implicit closes, avoiding a false PASS from per-clock TNS alone.
"""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section = ""
        self.rows = []
        self.row = []
        self.cell = None

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


def analyze(text):
    parser = ReportParser()
    parser.feed(text)
    errors = []
    summary = {r[0]: r[1] for s, r in parser.rows
               if s == "STA_Tool_Run_Summary" and len(r) == 2}
    for key in ("Numbers of Setup Violated Endpoints",
                "Numbers of Hold Violated Endpoints"):
        if summary.get(key) != "0":
            errors.append(f"{key}: {summary.get(key, 'MISSING')}")
    for key in ("Numbers of Paths Analyzed", "Numbers of Endpoints Analyzed"):
        if not summary.get(key, "").isdigit() or int(summary[key]) < 1:
            errors.append(f"No analyzed timing evidence: {key}")
    clocks = {r[1]: r[3:5] for s, r in parser.rows
              if s == "Clock_Report" and len(r) >= 5 and r[0].isdigit()}
    for name, expected in {"sys_clk": ["20.000", "50.000"],
                           "video_pixel": ["40.000", "25.000"],
                           "video_serial": ["8.000", "125.000"]}.items():
        if clocks.get(name) != expected:
            errors.append(f"Clock {name} period/frequency mismatch: {clocks.get(name)}")
    worst = {}
    for section in ("Setup_Slack_Table", "Hold_Slack_Table",
                    "Recovery_Slack_Table", "Removal_Slack_Table"):
        paths = [r for s, r in parser.rows if s == section and len(r) >= 4
                 and r[0].isdigit()]
        if not paths:
            errors.append(f"Missing path evidence: {section}")
            continue
        try:
            path = min(paths, key=lambda r: float(r[1]))
            worst[section] = {"slack_ns": float(path[1]), "from": path[2], "to": path[3]}
            if float(path[1]) < 0:
                errors.append(f"Negative {section}: {path[1]} ns -> {path[3]}")
        except ValueError:
            errors.append(f"Unparseable path slack: {section}")
    return {"summary": summary, "clocks": clocks, "worst": worst, "errors": errors}


EXPECTED_PINS = {
    "sys_clk": ("-", "V22/7", "LVCMOS33", "NONE", "3.3"),
    "sys_rst_n": ("-", "AA13/9", "LVCMOS15", "UP", "1.5"),
    "tmds_clk_p": ("tmds_clk_n", "G15,G16/4", "LVDS25", "NONE", "3.3"),
    "tmds_data_p[0]": ("tmds_data_n[0]", "J14,H14/4", "LVDS25", "NONE", "3.3"),
    "tmds_data_p[1]": ("tmds_data_n[1]", "J15,H15/4", "LVDS25", "NONE", "3.3"),
    "tmds_data_p[2]": ("tmds_data_n[2]", "K17,J17/5", "LVDS25", "NONE", "3.3"),
    "pa_en": ("-", "AB16/7", "LVCMOS33", "NONE", "3.3"),
}


def analyze_pins(text):
    start = text.find("7. Pinout by Port Name")
    end = text.find("8. All Package Pins", start + 1)
    if start < 0 or end < 0:
        return {}, ["Gowin port pinout section is missing"]
    rows = [list(map(str.strip, line.split("|")))
            for line in text[start:end].splitlines() if "|" in line]
    actual, errors = {}, []
    for name, expected in EXPECTED_PINS.items():
        matches = [row for row in rows if row[0] == name]
        if len(matches) != 1 or len(matches[0]) < 18:
            errors.append(f"Missing or duplicate pin row: {name}")
            continue
        row = matches[0]
        found = (row[1], row[2], row[7], row[9], row[17])
        actual[name] = {"diff_pair": row[1], "location": row[2],
                        "io_type": row[7], "pull_mode": row[9],
                        "bank_vccio": row[17]}
        if row[3] != "Y" or found != expected:
            errors.append(f"Pin mismatch: {name}: {found} constraint={row[3]}")
    return actual, errors


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("report", type=Path)
    args.add_argument("--json", type=Path)
    args.add_argument("--pin-report", type=Path)
    opt = args.parse_args()
    result = analyze(opt.report.read_text(encoding="utf-8"))
    if opt.pin_report:
        pins, pin_errors = analyze_pins(opt.pin_report.read_text(encoding="utf-8"))
        result["pins"] = pins
        result["errors"].extend(pin_errors)
    if opt.json:
        opt.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for error in result["errors"]:
        print("FAIL", error)
    if result["errors"]:
        return 1
    print("PASS timing: 50/125/25MHz clocks; setup/hold/recovery/removal nonnegative.")
    if opt.pin_report:
        print("PASS pinout: 7 ports / 11 balls, I/O types, pull and bank VCCIO checked.")
    print("Not a signal-integrity, PLL-lock, physical TMDS or monitor validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
