"""Fail-closed checker for independent control snapshot internal STA.
Does not approve external unconstrained scan ports or board downloads.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from check_t009_fusion_report import Rows


def check(folder):
    folder = Path(folder)
    pnr = folder / "impl/pnr"
    name = "control_snapshot_timing_probe"
    report = pnr / (name + "_tr_content.html")
    usage_path = pnr / (name + ".rpt.txt")
    timing = report.read_text(encoding="utf-8")
    usage = usage_path.read_text(encoding="utf-8")
    parser = Rows();parser.feed(timing)
    rows = parser.rows
    errors = []
    summary = {r[0]: r[1] for section, r in rows if section == "STA_Tool_Run_Summary" and len(r) == 2}
    for field in ["Numbers of Setup Violated Endpoints", "Numbers of Hold Violated Endpoints"]:
        if summary.get(field) != "0":
            errors.append(field + "=" + summary.get(field, "missing"))
    for field in ["Numbers of Paths Analyzed", "Numbers of Endpoints Analyzed"]:
        if not summary.get(field, "").isdigit() or int(summary[field]) <= 0:
            errors.append("nonvacuous analysis not proven: " + field)
    clocks = [r for section, r in rows if section == "Clock_Report" and len(r) >= 5 and r[1] == "sys_clk"]
    if len(clocks) != 1 or clocks[0][3:5] != ["20.000", "50.000"]:
        errors.append("actual50MHz clock constraint missing")
    active = {r[2] for section, r in rows if section == "SDC_Report" and len(r) == 3 and r[1] == "Actived"}
    for typ, value in [("setup", "1.000"), ("hold", "0.500")]:
        wanted = f"set_clock_uncertainty -{typ} {value} -from [get_clocks {{sys_clk}}] -to [get_clocks {{sys_clk}}]"
        if wanted not in active:
            errors.append("clock uncertainty weakened/missing: " + typ)
    for command in active:
        if command.startswith("set_false_path") and "sys_rst_n" not in command:
            errors.append("unexpected internal false path: " + command)
        if "set_multicycle_path" in command:
            errors.append("unexpected multicycle exception")
    fmax = [r for section, r in rows if section == "Max_Frequency_Report" and len(r) >= 4 and r[1] == "sys_clk"]
    if len(fmax) != 1 or float(fmax[0][3].replace("(MHz)", "")) < 50:
        errors.append("Fmax50MHz not met")
    slack = {}
    worst_paths = {}
    for typ in ["Setup", "Hold", "Recovery", "Removal"]:
        candidates = [r for section, r in rows if section.startswith(typ + "_Slack_Table") and len(r) >= 4 and r[0].isdigit()]
        if not candidates:
            errors.append("missing " + typ + " paths");slack[typ] = None;continue
        worst = min(candidates, key=lambda r: float(r[1]))
        slack[typ] = float(worst[1]);worst_paths[typ] = worst
        if slack[typ] < 0:
            errors.append("negative " + typ + "=" + str(slack[typ]))
    hierarchy_file = folder / "impl/gwsynthesis" / (name + "_syn_rsc.xml")
    tree = ET.parse(hierarchy_file).getroot()
    resources = {}
    for kind in ["Logic", "Register"]:
        matches = re.findall(r"^\s*" + kind + r"\s*\|\s*(\d+)/(\d+)", usage, re.M)
        if len(matches) != 1:
            errors.append("missing physical resource " + kind)
        else:
            resources[kind] = int(matches[0][0])
    # Gowin omits zero DSP/BSRAM rows. Cross-check the synthesis hierarchy too,
    # never call a nonempty missing resource zero without this independent fact.
    for physical, attrs in [("DSP", ["Dsp", "T_Dsp"]), ("BSRAM", ["Bsram", "T_Bsram"])]:
        matches = re.findall(r"^\s*" + physical + r"\s*\|\s*(\d+)/(\d+)", usage, re.M)
        used = any(int(re.match(r"\d+", node.attrib.get(attr, "0")).group()) > 0
                   for node in tree.iter() for attr in attrs)
        if matches:
            resources[physical] = int(matches[0][0])
        elif not used:
            resources[physical] = 0
        else:
            errors.append("missing nonzero physical resource " + physical)
    distributed = re.search(r"--SSRAM\(RAM16\)\s*\|\s*(\d+)", usage)
    resources["RAM16"] = int(distributed[1]) if distributed else 0
    latch = re.search(r"--Logic Register as Latch\s*\|\s*(\d+)/", usage)
    if not latch or latch[1] != "0":
        errors.append("latch-free not proven")
    if "GW5AT-LV60PG484AC1/I0" not in usage or "V1.9.11.03 Education" not in usage:
        errors.append("wrong device/tool")
    build_log = (folder / "build.log").read_text(encoding="utf-8", errors="replace")
    if "ERROR  (" in build_log or "Bitstream generation completed" not in build_log:
        errors.append("build failure/incomplete")
    facts = {"resources": resources, "fmax_mhz": float(fmax[0][3].replace("(MHz)", "")) if len(fmax) == 1 else None,
             "summary": summary, "minimum_slack_ns": slack, "worst_paths": worst_paths,
             "scope": "standalone wrapper internal50MHz timing only; no external IO timing or board proof",
             "report_sha256": {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in [report, usage_path, hierarchy_file]}}
    return errors, facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    cfg = parser.parse_args()
    errors, facts = check(cfg.folder)
    (cfg.folder / "checked_summary.json").write_text(json.dumps({"errors": errors, "facts": facts}, indent=2) + "\n", encoding="utf-8", newline="\n")
    for error in errors:
        print("FAIL control snapshot", error)
    print(json.dumps(facts, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, ET.ParseError) as exc:
        print("FAIL report unavailable/invalid:", exc);raise SystemExit(1)
