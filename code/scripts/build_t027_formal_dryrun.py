#!/usr/bin/env python3
"""Dry-run formal T027 top from exact source copies; never alter deployed GPRJ."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from check_t009_fusion_report import Rows, verify

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "code/output/t027_formal_dryrun"
STAGE.mkdir(parents=True, exist_ok=True)
source_project = ROOT / "code/build/electronic_piano.gprj"
root = ET.parse(source_project)
files = root.find("./FileList")
assert files is not None
roms = {
    "model/generated/wavetables/" + name:
        (ROOT / "code/model/generated/wavetables" / name).as_posix()
    for name in ("sine_1024_8192.mem", "sine_1024_32767.mem",
                 "velocity_gain_rom.mem", "piano_band_4x256_8191.mem")
}
for name in ("sine_wavetable.hex", "triangle_wavetable.hex"):
    roms["model/generated/" + name] = (ROOT / "code/model/generated" / name).as_posix()
    roms[name] = (ROOT / "code/model/generated" / name).as_posix()
port_header = (ROOT / "code/rtl/board/sustain_controller_ports.svh").as_posix()
for entry in files:
    source = (source_project.parent / entry.attrib["path"]).resolve()
    if entry.attrib.get("type") == "file.verilog":
        original = source.read_text(encoding="utf-8")
        code = original.replace('`include "sustain_controller_ports.svh"',
                                '`include "' + port_header + '"')
        for rel, absolute in roms.items():
            code = code.replace('"' + rel + '"', '"' + absolute + '"')
        if source.name == "electronic_piano_top.sv":
            needle = "polyphonic_audio_core u_audio_core("
            assert code.count(needle) == 1
            code = code.replace(needle,
                "polyphonic_audio_core #(.DYNAMIC_TIMBRE_ENABLE(1'b1)) u_audio_core(")
        if code != original:
            target = STAGE / source.name
            target.write_text(code, encoding="utf-8", newline="\n")
            source = target
    entry.set("path", source.as_posix())
for rel in ("code/rtl/audio/timbre_oscillator.sv",
            "code/rtl/board/piano_triangle_voice.sv"):
    ET.SubElement(files, "File", path=(ROOT / rel).as_posix(),
                  type="file.verilog", enable="1")
project = STAGE / "electronic_piano.gprj"
root.write(project, encoding="utf-8", xml_declaration=True)
tcl = STAGE / "run_all.tcl"
tcl.write_text(f"cd {{{STAGE.as_posix()}}}\nopen_project {{{project.as_posix()}}}\n"
               "set_option -verilog_std sysv2017\nrun all\n",
               encoding="ascii", newline="\n")
gw = Path("D:/Gowin/Gowin_V1.9.11.03_Education/"
          "Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe")
proc = subprocess.run([str(gw), str(tcl)], cwd=STAGE,
                      capture_output=True, text=True, encoding="utf-8",
                      errors="replace", timeout=480)
log = proc.stdout + proc.stderr
(STAGE / "build.log").write_text(log, encoding="utf-8", newline="\n")
if proc.returncode or re.search(r"EX3988|ERROR\s*\(|WARN\s*\(NL0002\).*timbre_oscillator", log):
    print(log[-3500:])
    raise SystemExit(f"T027 formal dry-run failed: {proc.returncode}")
report_dir = STAGE / "impl/pnr"
report = (report_dir / "electronic_piano.rpt.txt").read_text(encoding="utf-8")
timing = (report_dir / "electronic_piano_tr_content.html").read_text(encoding="utf-8")
errors, info = verify(timing, report)
rows = Rows(); rows.feed((report_dir / "electronic_piano.pin.html").read_text(encoding="utf-8"))
expected = {"sys_clk": "V22", "sys_rst_n": "AA13", "midi_rx": "R17",
            "uart_tx": "U15", "i2s_bclk": "Y17", "i2s_lrck": "AB17",
            "i2s_din": "AA16", "pa_en": "AB16"}
for name, ball in expected.items():
    found = [row for _,row in rows.rows if len(row) > 17 and row[0] == name]
    if len(found) != 1 or found[0][2].split("/")[0] != ball:
        errors.append(f"Physical pin mismatch: {name}/{ball}")
if not (report_dir / "electronic_piano.fs").is_file():
    errors.append("No bitstream output")
if info["resources"].get("BSRAM", 0) < 12:
    errors.append("Expected both waveform ROM banks retained (>=12 BSRAM)")
print("T027 full formal dry-run:", json.dumps(info, ensure_ascii=False))
print("Checked physical pins:", len(expected))
if errors:
    print("FAIL:", errors)
    raise SystemExit(1)
print("PASS isolated copy of formal top/CST/SDC; bitstream NOT for board")
