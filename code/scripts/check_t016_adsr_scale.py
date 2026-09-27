#!/usr/bin/env python3
"""Fail-closed actual Gowin PnR comparison for 1 vs 4 independent ADSRs."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
from check_t009_fusion_report import Rows  # noqa: E402


def one(text: str, pattern: str, name: str):
    hits = re.findall(pattern, text, re.M)
    if len(hits) != 1:
        raise ValueError(f"Expected one {name}, got {len(hits)}")
    return hits[0]


def parse(out: Path, n: int):
    directory = out / f"voice_{n}/impl/pnr"
    prefix = f"adsr_probe_{n}"
    usage = (directory / (prefix + ".rpt.txt")).read_text(encoding="utf-8")
    timing = (directory / (prefix + "_tr_content.html")).read_text(encoding="utf-8")
    page = Rows()
    page.feed(timing)
    summary = {r[0]: r[1] for s, r in page.rows if s == "STA_Tool_Run_Summary" and len(r) == 2}
    if summary.get("Numbers of Setup Violated Endpoints") != "0" or summary.get("Numbers of Hold Violated Endpoints") != "0":
        raise ValueError(f"{prefix} has timing violated endpoints: {summary}")
    clocks = [r for s, r in page.rows if s == "Clock_Report" and len(r) >= 5 and r[1] == "sys_clk"]
    if len(clocks) != 1 or clocks[0][3:5] != ["20.000", "50.000"]:
        raise ValueError(f"{prefix} sys_clk constraint missing or incorrect")
    freq = [r for s, r in page.rows if s == "Max_Frequency_Report" and len(r) >= 4 and r[1] == "sys_clk"]
    if len(freq) != 1 or float(freq[0][3].replace("(MHz)", "")) < 50:
        raise ValueError(f"{prefix} Fmax less than 50 MHz or missing")
    worst = {}
    for kind in ("Setup", "Hold"):
        paths = [r for s, r in page.rows if s == kind + "_Slack_Table" and len(r) >= 4 and r[0].isdigit()]
        if not paths:
            raise ValueError(f"{prefix} no {kind} path evidence")
        row = min(paths, key=lambda r: float(r[1]))
        if float(row[1]) < 0:
            raise ValueError(f"{prefix} {kind} negative slack")
        worst[kind] = {"ns": float(row[1]), "start": row[2], "end": row[3]}
    resources = {name: int(one(usage, r"^  " + name + r"\s*\|\s*(\d+)/", name))
                 for name in ("Logic", "Register", "BSRAM", "DSP")}
    ff = int(one(usage, r"^    --Logic Register as FF\s*\|\s*(\d+)/", "FF"))
    latches = int(one(usage, r"^    --Logic Register as Latch\s*\|\s*(\d+)/", "latch"))
    if latches:
        raise ValueError(f"{prefix} inferred latches")
    resources["Logic_FF"] = ff
    return {"resource": resources, "fmax_mhz": float(freq[0][3].replace("(MHz)", "")),
            "worst": worst, "tool": one(usage, r"^  <Tool Version>: (.+)$", "tool"),
            "part": one(usage, r"^  <Part Number>: (.+)$", "part")}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_t016_adsr_scale.py BUILD_DIR")
    out = Path(sys.argv[1])
    try:
        cases = {str(n): parse(out, n) for n in (1, 4)}
        if cases["1"]["tool"] != cases["4"]["tool"] or cases["1"]["part"] != cases["4"]["part"]:
            raise ValueError("Different tool/part between comparisons")
        if cases["4"]["resource"]["BSRAM"] < 1:
            raise ValueError("Quad probe ROM optimized away")
        delta = {key: cases["4"]["resource"][key] - cases["1"]["resource"][key]
                 for key in cases["1"]["resource"]}
        if any(delta[key] < 0 for key in ("Logic", "Register", "DSP")):
            raise ValueError("Quad unexpectedly smaller; inspect optimization")
        result = {"scope": "isolated ADSR copies only, not a musical voice or full piano",
                  "one": cases["1"], "four": cases["4"], "four_minus_one": delta}
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.json").write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
        print("PASS independent 1/4 ADSR PnR", result)
        return 0
    except (OSError, ValueError) as exc:
        print("FAIL T016 ADSR resource comparison:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
