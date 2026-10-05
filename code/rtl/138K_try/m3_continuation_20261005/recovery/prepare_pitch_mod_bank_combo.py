"""Stage actual bank Pitch/Mod integration with frozen strict visual in isolation.

Only prepares files; never runs tools, overwrites an existing output, writes
production RTL/CST/SDC, programs hardware, or claims timing acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "code/tb/board/pitch_mod_bank_integration_candidate"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output, frozen_project):
    output = output.resolve()
    output.relative_to(ROOT / "code/output")
    if output.exists():
        raise ValueError("output already exists; preserve prior experiment")
    original = ET.parse(frozen_project)
    nodes = list(original.getroot().find("FileList"))
    for node in nodes:
        if not Path(node.attrib["path"]).is_file():
            raise ValueError("missing frozen input: " + node.attrib["path"])
    sdc = [Path(node.attrib["path"]) for node in nodes if node.attrib["type"] == "file.sdc"]
    if len(sdc) != 1:
        raise ValueError("expected one frozen SDC")
    hold_command = "set_clock_uncertainty -hold  0.550 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]"
    if hold_command not in sdc[0].read_text(encoding="utf-8"):
        raise ValueError("use the explicitly reviewed 0.550ns Hold project")
    output.mkdir(parents=True)
    sources = output / "sources"
    roms = output / "rom"
    sources.mkdir()
    roms.mkdir()
    replaces = {
        "polyphonic_envelope_bank.sv": CANDIDATE / "polyphonic_envelope_bank.sv",
        "polyphonic_event_router.sv": CANDIDATE / "polyphonic_event_router.sv",
        "midi_event_parser.sv": ROOT / "code/rtl/input/midi_input/midi_event_parser.sv",
        "midi_input.sv": ROOT / "code/rtl/input/midi_input/midi_input.sv",
        "button_tail_select.sv": ROOT / "code/rtl/input/button_event_converter/button_event_converter.sv",
    }
    extra = [ROOT / "code/rtl/board/performance_control_snapshot.sv",
             ROOT / "code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_fcw_pipeline.sv",
             ROOT / "code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_snapshot_pipeline.sv"]
    items = []

    def copy_source(source):
        text = source.read_text(encoding="utf-8")
        for name in set(re.findall(r'[A-Za-z]:/[^"\r\n]+\.(?:mem|hex)', text)):
            old = Path(name)
            if old.is_file():
                new = roms / old.name
                if new.exists() and digest(new) != digest(old):
                    raise ValueError("different ROMs share a basename")
                if not new.exists():
                    shutil.copyfile(old, new)
                text = text.replace(name, new.as_posix())
        for name in ("oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem"):
            original_rom = ROOT / "code/model/generated/pitch_mod" / name
            new = roms / name
            if not new.exists():
                shutil.copyfile(original_rom, new)
            if digest(new) != digest(original_rom):
                raise ValueError("control ROM changed")
            text = text.replace("model/generated/pitch_mod/" + name, new.as_posix())
        target = sources / source.name
        if target.exists():
            raise ValueError("duplicate staged source basename: " + source.name)
        target.write_text(text, encoding="utf-8", newline="\n")
        return target

    for node in nodes:
        old = Path(node.attrib["path"])
        source = replaces.get(old.name, old)
        target = copy_source(source) if node.attrib["type"] == "file.verilog" else source
        node.attrib["path"] = target.as_posix()
        items.append({"baseline": str(old), "input": str(source), "input_sha256": digest(source),
                      "actual": str(target), "actual_sha256": digest(target), "type": node.attrib["type"]})
    for source in extra:
        target = copy_source(source)
        ET.SubElement(original.getroot().find("FileList"), "File",
                      {"path": target.as_posix(), "type": "file.verilog", "enable": "1"})
        items.append({"input": str(source), "input_sha256": digest(source),
                      "actual": str(target), "actual_sha256": digest(target), "added": True})
    header = ROOT / "code/rtl/board/sustain_controller_ports.svh"
    shutil.copyfile(header, sources / header.name)
    project = output / "audio_visual_coexistence_top.gprj"
    original.write(project, encoding="utf-8", xml_declaration=True)
    (output / "run.tcl").write_text(
        "open_project {" + project.as_posix() + "}\nset_option -top_module audio_visual_coexistence_top\n"
        "set_option -verilog_std sysv2017\nrun all\n", encoding="ascii")
    record = {"scope": "isolated actual bank PitchMod/V1/CC64 plus frozen strict visual and latest input",
              "project": str(project), "frozen_project": str(frozen_project), "source_builds": items,
              "roms": {str(p): digest(p) for p in roms.iterdir()},
              "include_header_sha256": digest(header), "formal_modified": False,
              "hold_uncertainty_ns": 0.550, "Gowin_run_by_this_entry": False,
              "production_or_board_release": False}
    (output / "input_manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frozen-project", type=Path, required=True)
    cfg = parser.parse_args()
    info = prepare(cfg.output, cfg.frozen_project.resolve())
    print("Prepared isolated source/ROM hashes:", len(info["source_builds"]))
    print("Not timing or board acceptance:", info["project"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
