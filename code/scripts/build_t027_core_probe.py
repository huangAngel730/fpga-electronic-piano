#!/usr/bin/env python3
"""PnR an isolated full T027 PCM core at 50 MHz; never program it."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "code/output/t027_core_probe"
STAGE.mkdir(parents=True, exist_ok=True)
ROM = ROOT / "code/model/generated"
PROJECT = ROOT / "code/build/electronic_piano.gprj"
project_xml = ET.parse(PROJECT)
file_list = project_xml.find("./FileList")
assert file_list is not None
for entry in list(file_list):
    if entry.attrib.get("type") != "file.verilog":
        file_list.remove(entry)
        continue
    original = (PROJECT.parent / entry.attrib["path"]).resolve()
    if original.name == "electronic_piano_top.sv":
        file_list.remove(entry)
        continue
    entry.set("path", original.as_posix())

for source in ("code/rtl/audio/timbre_oscillator.sv",
               "code/rtl/board/piano_triangle_voice.sv",
               "code/tb/board/t027_audio_core_probe.sv"):

    ET.SubElement(file_list, "File", path=(ROOT / source).as_posix(),
                  type="file.verilog", enable="1")
source_text = (ROOT / "code/tb/board/t027_audio_core_probe.sv").read_text(encoding="utf-8")
assert '.WAVE_ROM_FILE("model/generated/wavetables/piano_band_4x256_8191.mem")' in source_text
source_text = source_text.replace(
    'model/generated/wavetables/piano_band_4x256_8191.mem',
    (ROM / "wavetables/piano_band_4x256_8191.mem").as_posix(),
)
probe_top = STAGE / "t027_audio_core_probe.sv"
probe_top.write_text(source_text, encoding="ascii", newline="\n")
for entry in file_list:
    if entry.attrib.get("path", "").endswith("t027_audio_core_probe.sv"):
        entry.set("path", probe_top.as_posix())
        break
velocity_source = ROOT / "code/rtl/audio/adsr_piano_envelope.sv"
velocity_text = velocity_source.read_text(encoding="utf-8")
needle = "model/generated/wavetables/velocity_gain_rom.mem"
assert needle in velocity_text
velocity_text = velocity_text.replace(needle, (ROM / "wavetables/velocity_gain_rom.mem").as_posix())
velocity_rtl = STAGE / "adsr_piano_envelope.sv"
velocity_rtl.write_text(velocity_text, encoding="utf-8", newline="\n")
for entry in file_list:
    if entry.attrib.get("path", "").endswith("rtl/audio/adsr_piano_envelope.sv"):
        entry.set("path", velocity_rtl.as_posix())
        break
# The M1 T027 ROM defaults also need absolute paths in the staged source.
rom_source = ROOT / "code/rtl/audio/timbre_oscillator.sv"
rom_text = rom_source.read_text(encoding="utf-8")
for rel in ("sine_wavetable.hex", "triangle_wavetable.hex"):
    needle = "model/generated/" + rel
    # The defaults in the original M1 module are plain filenames.
    rom_text = rom_text.replace('"' + rel + '"',
                                '"' + (ROM / rel).as_posix() + '"')
rom_rtl = STAGE / "timbre_oscillator.sv"
rom_rtl.write_text(rom_text, encoding="utf-8", newline="\n")
for entry in file_list:
    if entry.attrib.get("path", "").endswith("rtl/audio/timbre_oscillator.sv"):
        entry.set("path", rom_rtl.as_posix())
        break
# The bank passes its own two ROM parameter defaults into the wrapper;
# replace those defaults in a staged bank copy as well.
bank_source = ROOT / "code/rtl/board/polyphonic_envelope_bank.sv"
bank_text = bank_source.read_text(encoding="utf-8")
for rel in ("sine_wavetable.hex", "triangle_wavetable.hex"):
    old = '"model/generated/' + rel + '"'
    assert bank_text.count(old) == 1, old
    bank_text = bank_text.replace(old, '"' + (ROM / rel).as_posix() + '"')
bank_rtl = STAGE / "polyphonic_envelope_bank.sv"
bank_rtl.write_text(bank_text, encoding="utf-8", newline="\n")
for entry in file_list:
    if entry.attrib.get("path", "").endswith("rtl/board/polyphonic_envelope_bank.sv"):
        entry.set("path", bank_rtl.as_posix())
        break
sdc = STAGE / "probe.sdc"
sdc.write_text("create_clock -name sys_clk -period 20.000 [get_ports {clk}]\n",
               encoding="ascii", newline="\n")
ET.SubElement(file_list, "File", path=sdc.as_posix(), type="file.sdc", enable="1")
project = STAGE / "t027_core_probe.gprj"
project_xml.write(project, encoding="utf-8", xml_declaration=True)
tcl = STAGE / "run_all.tcl"
tcl.write_text(f"cd {{{STAGE.as_posix()}}}\nopen_project {{{project.as_posix()}}}\n"
               "set_option -verilog_std sysv2017\n"
               "set_option -top_module t027_audio_core_probe\nrun all\n",
               encoding="ascii", newline="\n")
gowin = Path("D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe")
result = subprocess.run([str(gowin), str(tcl)], cwd=STAGE,
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=480)
log = result.stdout + result.stderr
(STAGE / "build.log").write_text(log, encoding="utf-8", newline="\n")
if result.returncode or re.search(r"EX3988|ERROR\s*\(|WARN\s*\(NL0002\).*timbre_oscillator", log):
    print(log[-3000:])
    raise SystemExit(f"T027 standalone Gowin run all failed: {result.returncode}")
from check_t009_fusion_report import verify
report = (STAGE / "impl/pnr/t027_core_probe.rpt.txt").read_text(encoding="utf-8")
timing = (STAGE / "impl/pnr/t027_core_probe_tr_content.html").read_text(encoding="utf-8")
errors, info = verify(timing, report)
print("T027 standalone Gowin:", json.dumps(info, ensure_ascii=False))
if errors:
    print("T027 isolated timing or resource FAIL:", "; ".join(errors))
    raise SystemExit(1)
print("PASS T027 isolated four-lane PCM internal STA; no formal top/IO/board guarantee")
