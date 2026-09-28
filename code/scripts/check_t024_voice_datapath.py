#!/usr/bin/env python3
"""Fail closed on real 1/4-lane Gowin timing and resource reports."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
from check_t009_fusion_report import Rows  # noqa: E402


def one(text, pattern, label):
    matches = re.findall(pattern, text, re.M)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {label}, got {len(matches)}")
    return matches[0]


def report(out, lanes):
    p = out / f"lanes_{lanes}/impl/pnr"
    name = f"voice_datapath_probe_{lanes}"
    usage = (p / f"{name}.rpt.txt").read_text(encoding="utf-8")
    timing = (p / f"{name}_tr_content.html").read_text(encoding="utf-8")
    html = Rows()
    html.feed(timing)
    summary = {r[0]: r[1] for s, r in html.rows
               if s == "STA_Tool_Run_Summary" and len(r) == 2}
    for key in ("Numbers of Setup Violated Endpoints",
                "Numbers of Hold Violated Endpoints"):
        if summary.get(key) != "0":
            raise ValueError(f"{name}: {key}={summary.get(key)}")
    clocks = [r for s, r in html.rows if s == "Clock_Report"
              and len(r) >= 5 and r[1] == "sys_clk"]
    if len(clocks) != 1 or clocks[0][3:5] != ["20.000", "50.000"]:
        raise ValueError(f"{name}: expected 50 MHz sys_clk")
    fmax = [r for s, r in html.rows if s == "Max_Frequency_Report"
            and len(r) >= 4 and r[1] == "sys_clk"]
    if len(fmax) != 1:
        raise ValueError(f"{name}: no Fmax evidence")
    frequency = float(fmax[0][3].replace("(MHz)", ""))
    if frequency < 50:
        raise ValueError(f"{name}: Fmax {frequency} MHz below 50 MHz")
    worst = {}
    for kind in ("Setup", "Hold"):
        paths = [r for s, r in html.rows if s == f"{kind}_Slack_Table"
                 and len(r) >= 4 and r[0].isdigit()]
        if not paths:
            raise ValueError(f"{name}: no {kind} path")
        row = min(paths, key=lambda r: float(r[1]))
        worst[kind] = {"slack_ns": float(row[1]), "from": row[2], "to": row[3]}
        if worst[kind]["slack_ns"] < 0:
            raise ValueError(f"{name}: {kind} negative slack {row[1]} ns")
    part = one(usage, r"^  <Part Number>: (.+)$", "part")
    if part != "GW5AT-LV60PG484AC1/I0":
        raise ValueError(f"{name}: wrong device {part}")
    resources = {}
    for item in ("Logic", "Register", "BSRAM", "DSP"):
        resources[item] = int(one(usage, r"^  " + item + r"\s*\|\s*(\d+)/", item))
    latch = int(one(usage, r"^    --Logic Register as Latch\s*\|\s*(\d+)/", "latch"))
    if latch:
        raise ValueError(f"{name}: inferred latches")
    return {"fmax_mhz": frequency, "worst": worst, "resources": resources,
            "tool": one(usage, r"^  <Tool Version>: (.+)$", "tool"),
            "part": part}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_t024_voice_datapath.py BUILD_DIRECTORY")
    out = Path(sys.argv[1])
    try:
        results = {str(n): report(out, n) for n in (1, 4)}
        if [(results[n]["tool"], results[n]["part"]) for n in ("1", "4")][0] != \
           [(results[n]["tool"], results[n]["part"]) for n in ("1", "4")][1]:
            raise ValueError("Mismatched tool or part")
        delta = {key: results["4"]["resources"][key] - results["1"]["resources"][key]
                 for key in results["1"]["resources"]}
        if results["1"]["resources"]["BSRAM"] < 2 or results["4"]["resources"]["BSRAM"] < 8:
            raise ValueError("Expected four ADSR + four DDS ROM copies; check synthesis hierarchy")
        data = {"scope": "synthetic DDS+ADSR+mixer datapath only, not D028 PCM proof",
                "one": results["1"], "four": results["4"], "delta_four_minus_one": delta}
        (out / "summary.json").write_bytes((json.dumps(data, indent=2) + "\n").encode("utf-8"))
        print("T024 standalone PnR results:", json.dumps(data, indent=2))
        if results["1"]["fmax_mhz"] < 50 or results["4"]["fmax_mhz"] < 50:
            raise ValueError("At least one probe is below 50 MHz")
        if any(results[n]["worst"][k]["slack_ns"] < 0 for n in ("1", "4")
               for k in ("Setup", "Hold")):
            raise ValueError("Negative slack in at least one probe")
        print("PASS independent T024 probe timing; no full-piano claim")
        return 0
    except (OSError, ValueError) as exc:
        print("FAIL T024 timing/resource probe:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
