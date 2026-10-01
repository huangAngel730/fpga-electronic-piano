"""Fail-closed independent audio+visual report gate; no board acceptance."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from check_hdmi_link_report import ReportParser
from check_visual_full_path_report import check as visual_gate

AUDIO_PINS = {
    "sys_clk": ("V22", "LVCMOS33", "3.3"),
    "sys_rst_n": ("AA13", "LVCMOS15", "1.5"),
    "key_n[0]": ("AB13", "LVCMOS15", "1.5"),
    "key_n[1]": ("Y12", "LVCMOS15", "1.5"),
    "midi_rx": ("R17", "LVCMOS33", "3.3"),
    "uart_tx": ("U15", "LVCMOS33", "3.3"),
    "i2s_bclk": ("Y17", "LVCMOS33", "3.3"),
    "i2s_lrck": ("AB17", "LVCMOS33", "3.3"),
    "i2s_din": ("AA16", "LVCMOS33", "3.3"),
    "pa_en": ("AB16", "LVCMOS33", "3.3"),
}


def check(folder):
    folder = Path(folder)
    pnr = folder / "impl/pnr"
    name = "audio_visual_coexistence_top"
    html = (pnr / (name + "_tr_content.html")).read_text(encoding="utf-8")
    usage = (pnr / (name + ".rpt.txt")).read_text(encoding="utf-8")
    # Reuse the exact bridge gate after normalizing ONLY instance root prefix.
    errors, visual = visual_gate(html.replace("u_visual/", ""), usage)
    parser = ReportParser()
    parser.feed(html)
    active = {row[2] for section, row in parser.rows if section == "SDC_Report"
              and len(row) == 3 and row[1] == "Actived"}
    for typ, value in (("setup", "1.000"), ("hold", "0.500")):
        command = "set_clock_uncertainty -" + typ + " " + value
        if not any(cmd.startswith(command) for cmd in active):
            errors.append("formal audio clock uncertainty missing: " + typ)
    for port in ("i2s_bclk", "i2s_lrck", "i2s_din"):
        for kind, value in (("max", "5.000"), ("min", "0.000")):
            cmd = "set_output_delay -clock sys_clk -" + kind + " " + value + " [get_ports {" + port + "}]"
            if cmd not in active:
                errors.append("formal audio output delay missing: " + port + kind)
    resources = {}
    for kind in ("Logic", "Register", "DSP", "BSRAM"):
        match = re.findall(r"^\s*" + kind + r"\s*\|\s*(\d+)/(\d+)", usage, re.M)
        if len(match) != 1:
            errors.append("resource missing: " + kind)
        else:
            resources[kind] = int(match[0][0])
    if resources.get("BSRAM") != 8:
        errors.append("audio ROM footprint is not 8 BSRAM")
    if "GW5AT-LV60PG484AC1/I0" not in usage or "V1.9.11.03 Education" not in usage:
        errors.append("tool/device mismatch")
    latch = re.search(r"--Logic Register as Latch\s*\|\s*(\d+)/", usage)
    if not latch or latch[1] != "0":
        errors.append("latch-free not proven")
    pins = ReportParser()
    pins.feed((pnr / (name + ".pin.html")).read_text(encoding="utf-8"))
    for port, expected in AUDIO_PINS.items():
        rows = [row for _, row in pins.rows if len(row) > 17 and row[0] == port]
        if len(rows) != 1 or (rows[0][2].split("/")[0], rows[0][7], rows[0][17]) != expected:
            errors.append("audio pin mismatch: " + port)
    hierarchy = ET.parse(folder / ("impl/gwsynthesis/" + name + "_syn_rsc.xml"))
    latency = [node for node in hierarchy.iter() if node.attrib.get("name") == "u_latency"]
    if len(latency) != 1 or int(latency[0].attrib.get("Register", "0")) < 65:
        errors.append("audio latency counter not retained")
    else:
        latency = int(latency[0].attrib["Register"])
    clocks = {row[1]: float(row[3].replace("(MHz)", "")) for section, row in parser.rows
              if section == "Max_Frequency_Report" and row[0].isdigit()}
    for clock, target in (("sys_clk", 50), ("video_pixel", 25), ("video_serial", 125)):
        if clocks.get(clock, 0) < target:
            errors.append("clock Fmax not met: " + clock)
    exported = {}
    for kind in ("Setup", "Hold", "Recovery", "Removal"):
        rows = [row for section, row in parser.rows if section.startswith(kind + "_Slack_Table")
                and len(row) >= 4 and row[0].isdigit()]
        exported[kind] = min(float(row[1]) for row in rows) if rows else None
        if not rows or exported[kind] < 0:
            errors.append("missing/negative exported " + kind)
    facts = {"visual_gate": visual, "audio_pins": len(AUDIO_PINS), "resources": resources,
             "fmax_mhz": clocks, "exported_min_slack_ns": exported,
             "latency_registers": latency,
             "scope": "independent audio/visual STA only; not production top, monitor or silicon acceptance"}
    return errors, facts


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("folder", type=Path)
    cfg = args.parse_args()
    errors, facts = check(cfg.folder)
    (cfg.folder / "gate.json").write_text(json.dumps({"errors": errors, "facts": facts}, indent=2) + "\n", encoding="utf-8")
    for error in errors:
        print("FAIL", error)
    print(json.dumps(facts, indent=2))
    raise SystemExit(1 if errors else 0)
