"""Prepare an independent V1+CC64 audio/visual probe from immutable Git audio.

Only generated output files are written. Production audio sources and contracts
are read-only; the diagnostic top is an exact top copy plus a display event tap.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
AUDIO_REF = "e5eb025ea37dfd7312b4a4e74e1a881c223dda1d"
PLL_HASH = "ededfd3e361c7e9b4523de6b3b50e00c98baed5b9900a361c606ab574376f9ba"
DVI_HASH = "b378c6a41d06a14215dc9ec54ed20bfc91309a0bb1543c589246717da3aee2ab"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(out, vendor):
    out = out.resolve()
    vendor = vendor.resolve()
    out.relative_to(ROOT / "code/output")
    out.mkdir(parents=True, exist_ok=True)
    snapshot = out / "audio_snapshot"
    if not snapshot.exists():
        blob = subprocess.check_output(["git", "-C", str(ROOT), "archive", AUDIO_REF, "code"])
        with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
            for entry in archive.getmembers():
                if entry.isdir():
                    continue
                if not entry.isfile() or ".." in Path(entry.name).parts:
                    raise ValueError("unsafe Git archive entry")
                path = snapshot / entry.name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(entry).read())
    project = snapshot / "code/build/electronic_piano.gprj"
    raw_project = subprocess.check_output(["git", "-C", str(ROOT), "show", AUDIO_REF + ":code/build/electronic_piano.gprj"])
    if project.read_bytes() != raw_project:
        raise ValueError("audio snapshot GPRJ changed")
    # This Git project has historical XML version=1; normalize only for parsing.
    tree = ET.fromstring(project.read_text(encoding="utf-8").replace('<?xml version="1"', '<?xml version="1.0"'))
    generated = out / "staged_sources"
    generated.mkdir(exist_ok=True)
    def verify_snapshot(path):
        rel = path.relative_to(snapshot).as_posix()
        original = subprocess.check_output(["git", "-C", str(ROOT), "show", AUDIO_REF + ":" + rel])
        if path.read_bytes() != original:
            raise ValueError("audio snapshot dependency changed: " + rel)
        return digest(path)

    original_hashes = {}
    staged_hashes = {}
    sources = []
    formal_top = None
    for file in tree.findall(".//File"):
        source = (project.parent / file.attrib["path"]).resolve()
        rel = source.relative_to(snapshot).as_posix()
        original = subprocess.check_output(["git", "-C", str(ROOT), "show", AUDIO_REF + ":" + rel])
        if source.read_bytes() != original:
            raise ValueError("audio snapshot changed: " + rel)
        original_hashes[rel] = digest(source)
        if file.attrib["type"] != "file.verilog":
            continue
        text = source.read_text(encoding="utf-8")
        for header, location in [("sustain_controller_ports.svh", "board"), ("sine_table.svh", "common")]:
            header_path = snapshot / ("code/rtl/" + location + "/" + header)
            text = text.replace('`include "' + header + '"', '`include "' + header_path.as_posix() + '"')
            if ('`include "' + header_path.as_posix() + '"') in text:
                original_hashes[header_path.relative_to(snapshot).as_posix()] = verify_snapshot(header_path)
        for name in ("sine_1024_8192.mem", "sine_1024_32767.mem", "velocity_gain_rom.mem", "piano_band_4x256_8191.mem"):
            rom = snapshot / ("code/model/generated/wavetables/" + name)
            if not rom.is_file():
                raise ValueError("missing official ROM " + name)
            original_hashes[rom.relative_to(snapshot).as_posix()] = verify_snapshot(rom)
            text = text.replace("model/generated/wavetables/" + name, rom.as_posix())
        if source.name == "electronic_piano_top.sv":
            formal_top = generated / "electronic_piano_top.sv"
            formal_top.write_text(text, encoding="utf-8", newline="\n")
            text = text.replace("ELECTRONIC_PIANO_TOP_SV", "AUDIO_VISUAL_COEXISTENCE_TOP_SV")
            text = text.replace("module electronic_piano_top #(", "module audio_visual_coexistence_top #(", 1)
            anchor = "output logic uart_tx      // U15  -> BL616"
            if text.count(anchor) != 1:
                raise ValueError("formal UART port anchor changed")
            text = text.replace(anchor, "output logic uart_tx,     // U15  -> BL616", 1)
            endport = text.index("\n);", text.index("module audio_visual"))
            text = text[:endport] + "\n    output wire tmds_clk_p,tmds_clk_n,\n    output wire [2:0] tmds_data_p,tmds_data_n" + text[endport:]
            addition = """
    // Display-only copy of events already accepted by the current audio core.
    // PLL/video resets never enter the audio reset or ready path.
    wire visual_pll_locked;
    audio_visual_display_probe u_visual (
        .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),
        .accepted_valid(shared_event_valid && shared_event_ready),
        .accepted_data(shared_event_data),
        .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
        .tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n),
        .visual_pll_locked(visual_pll_locked)
    );
"""
            if text.count("endmodule") != 1:
                raise ValueError("formal top boundary changed")
            text = text.replace("endmodule", addition + "\nendmodule", 1)
            dest = generated / "audio_visual_coexistence_top.sv"
        else:
            dest = generated / source.name
        dest.write_text(text, encoding="utf-8", newline="\n")
        sources.append(dest)
        staged_hashes[dest.relative_to(out).as_posix()] = digest(dest)
    # Package compilation order is explicit for simulation and synthesis.
    sources.sort(key=lambda f: 0 if f.name == "audio_defs_pkg.sv" else 1 if f.name == "sustain_control_contract_pkg.sv" else 2)
    for filename, expected in [("TMDS_PLL_800_600_60.v", PLL_HASH), ("DVI_TX_Top.v", DVI_HASH)]:
        path = vendor / filename
        if digest(path) != expected:
            raise ValueError("unreviewed vendor " + filename)
        sources.append(path)
    for file in ("visual_event_bridge.sv", "video_scan_timing.sv", "visual_mailbox_cdc.sv", "visual_control_bridge.sv"):
        sources.append(ROOT / ("code/rtl/common/" + file))
    for file in ("visual_live_state.sv", "visual_score_tracker.sv", "visual_scene_renderer.sv", "visual_hit_flash.sv", "m3_visualizer.sv"):
        sources.append(ROOT / ("code/rtl/input/visualizer/" + file))
    sources.append(ROOT / "code/rtl/board/audio_visual_display_probe.sv")
    cst = (snapshot / "code/constraints/electronic_piano.cst").read_text(encoding="utf-8")
    # Add only actual video pin/PLL declarations; shared clock/reset/PA remain
    # exactly the formal audio declarations, with no duplicate IO_LOC rows.
    for line in (ROOT / "code/constraints/hdmi_link_probe.cst").read_text(encoding="utf-8").splitlines():
        if '"tmds_' in line or line.startswith("INS_LOC"):
            cst += "\n" + line.replace("u_video_pll/", "u_visual/u_video_pll/")
    cst += '\nINS_LOC "u_visual/u_serial_reset/sync_chain_0_s0" R49C101[1][A];\n'
    cst += 'INS_LOC "u_visual/u_serial_reset/sync_chain_1_s0" R49C101[1][B];\n'
    cst_path = out / "audio_visual.cst"
    cst_path.write_text(cst, encoding="utf-8", newline="\n")
    sdc = (snapshot / "code/constraints/audio_timing.sdc").read_text(encoding="utf-8")
    video_sdc = (ROOT / "code/constraints/visual_full_path_probe.sdc").read_text(encoding="utf-8")
    lines = []
    for line in video_sdc.splitlines():
        if line.startswith("create_clock"):
            continue  # reuse the one formal 50MHz clock, including uncertainty
        lines.append(line.replace("u_video_pll/", "u_visual/u_video_pll/").replace("u_event_bridge/", "u_visual/u_event_bridge/").replace("u_control/", "u_visual/u_control/"))
    sdc += "\n# Independent audio+visual diagnostic: original audio constraints above.\n" + "\n".join(lines) + "\n"
    for clock in ("sys_clk", "video_pixel", "video_serial"):
        sdc += "report_timing -setup -from_clock [get_clocks {" + clock + "}] -to_clock [get_clocks {" + clock + "}] -max_paths 80 -max_common_paths 1\n"
        sdc += "report_timing -hold -from_clock [get_clocks {" + clock + "}] -to_clock [get_clocks {" + clock + "}] -max_paths 10 -max_common_paths 1\n"
    sdc_path = out / "audio_visual.sdc"
    sdc_path.write_text(sdc, encoding="utf-8", newline="\n")
    proj = ET.Element("Project")
    ET.SubElement(proj, "Template").text = "FPGA"
    ET.SubElement(proj, "Version").text = "5"
    ET.SubElement(proj, "Device", name="GW5AT-60B", pn="GW5AT-LV60PG484AC1/I0").text = "gw5at60b-002"
    listing = ET.SubElement(proj, "FileList")
    for file in sources + [cst_path, sdc_path]:
        typ = "file.verilog" if file.suffix in (".sv", ".v") else "file." + file.suffix[1:]
        ET.SubElement(listing, "File", path=file.as_posix(), type=typ, enable="1")
    gprj = out / "audio_visual_coexistence_top.gprj"
    ET.ElementTree(proj).write(gprj, encoding="utf-8", xml_declaration=True)
    (out / "run_build.tcl").write_text("open_project {" + gprj.as_posix() + "}\nset_option -top_module audio_visual_coexistence_top\nset_option -verilog_std sysv2017\nrun all\n", encoding="ascii")
    info = {"audio_commit": AUDIO_REF, "original_audio_sha256": original_hashes,
            "staged_audio_sha256": staged_hashes, "sources": [str(p) for p in sources],
            "input_sha256": {str(p): digest(p) for p in sources + [cst_path, sdc_path, gprj]},
            "formal_reference_top": str(formal_top), "snapshot": str(snapshot),
            "generated_top_changes": "rename/diagnostic HDMI ports plus accepted-event display tap only",
            "scope": "independent V1+CC64+8live+8score candidate; not production top or hardware acceptance"}
    (out / "inputs.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return info


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--output", type=Path, required=True)
    args.add_argument("--vendor", type=Path, required=True)
    cfg = args.parse_args()
    prepare(cfg.output, cfg.vendor)
    print("PASS prepared frozen audio + independent visual diagnostic")
