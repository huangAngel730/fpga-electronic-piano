"""Reproduce isolated M2 exact Pitch/Mod arithmetic and four-slot consumer.

Candidate sources live in tb/board/pitch_mod_pipeline_candidate, not formal
GPRJ. --physical runs a standalone50MHz internal probe NEVER TO BE PROGRAMMED;
it is not production I/O signoff or integrated piano timing/hardware evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "code/tb/board/pitch_mod_pipeline_candidate"
CAD = Path("D:/Gowin/oss-cad-suite")
GOWIN = Path("D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--physical", action="store_true")
    cfg = parser.parse_args()
    output = cfg.output.resolve()
    output.relative_to(ROOT / "code/output")
    if output.exists():
        parser.error("output exists; preserve previous evidence")
    output.mkdir(parents=True)
    manifest = json.loads((CANDIDATE / "source_manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["candidate_files_SHA"].items():
        if sha(CANDIDATE / name) != expected:
            raise ValueError("candidate source hash changed: " + name)
    for path, key in ((ROOT / "code/rtl/audio/pitch_mod_fcw.sv", "baseline_M1_module_SHA"),
                      (ROOT / "code/rtl/board/performance_control_snapshot.sv", "control_snapshot_SHA")):
        if sha(path) != manifest[key]:
            raise ValueError("accepted reference changed; re-review before replay")
    report = {"formal_audio_modified": False, "integrated_DDS_or_hardware_accepted": False,
              "source_sha256": manifest, "runs": {}}
    environment = dict(os.environ)
    environment["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + environment["PATH"]
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    def run(name, command, cwd=ROOT / "code", expect=True, timeout=180, marker=None):
        log = output / (name + ".log")
        with log.open("w", encoding="utf-8", newline="\n") as stream:
            result = subprocess.run(command, cwd=cwd, env=environment, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout, check=False)
        text = log.read_text(encoding="utf-8", errors="replace")
        report["runs"][name] = {"exit": result.returncode, "command": list(map(str, command)),
                                "log_sha256": sha(log), "expected_success": expect}
        if (result.returncode == 0) != expect or (expect and ("ERROR:" in text or "FATAL:" in text)):
            print(text[-3000:]);raise RuntimeError("unexpected result: " + name)
        if marker and marker not in text:
            raise RuntimeError("missing positive/negative evidence marker: " + name)
        print(name, "exit", result.returncode, flush=True)
        return text

    model = output / "model"
    model.mkdir()
    for name in ("pitch_mod_model.py", "generate_pitch_mod_luts.py", "generate_pitch_mod_vectors.py"):
        shutil.copy2(ROOT / "code/model" / name, model / name)
    for name in ("generate_pitch_mod_luts.py", "generate_pitch_mod_vectors.py"):
        run(name, [sys.executable, "-X", "utf8", str(model / name)], cwd=model)
    rom = model / "generated/pitch_mod"
    vectors = rom / "pitch_mod_vectors.txt"
    rows = vectors.read_text(encoding="ascii").splitlines()
    if len(rows) != 62279:
        raise ValueError("incomplete original model vectors")
    table = lambda key, name: "+" + key + "=" + str(rom / name)
    lut_args = [table("OCT_PATH", "oct_ratio_q16.mem"), table("SUB_PATH", "sub_ratio_q16.mem"), table("LFO_PATH", "lfo_sine_q15.mem")]
    pipeline = CANDIDATE / "pitch_mod_fcw_pipeline.sv"
    reference = ROOT / "code/rtl/audio/pitch_mod_fcw.sv"
    tb = CANDIDATE / "tb_pitch_mod_pipeline.sv"
    for label, depth, inc, golden in (("default", 512, 447392, 1), ("depth0", 0, 447392, 0),
                                     ("depth256", 256, 447392, 0), ("depth1023", 1023, 1073741824, 0)):
        binary = output / (label + ".vvp")
        run(label + "_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_pitch_mod_pipeline",
            "-P", f"tb_pitch_mod_pipeline.DEPTH={depth}", "-P", f"tb_pitch_mod_pipeline.INC={inc}",
            "-P", f"tb_pitch_mod_pipeline.RUN_VECTORS={golden}", "-o", str(binary), str(reference), str(pipeline), str(tb)])
        log = run(label, [str(CAD / "bin/vvp.exe"), str(binary), *lut_args, "+VECTORS=" + str(vectors)], marker="PASS pitchmod pipeline")
        report.setdefault("verdicts", {})[label] = next(line for line in log.splitlines() if line.startswith("PASS pitchmod pipeline"))
    consumer = CANDIDATE / "pitch_mod_snapshot_pipeline.sv"
    snapshot_tb = CANDIDATE / "tb_pitch_mod_snapshot_pipeline.sv"
    snapshot_sources = [ROOT / "code/rtl/common/audio_defs_pkg.sv", ROOT / "code/rtl/board/performance_control_snapshot.sv", reference, pipeline, consumer, snapshot_tb]
    snapshot_binary = output / "snapshot.vvp"
    run("snapshot_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_pitch_mod_snapshot_pipeline",
        "-o", str(snapshot_binary), *map(str, snapshot_sources)])
    log = run("snapshot", [str(CAD / "bin/vvp.exe"), str(snapshot_binary), *lut_args], marker="PASS actual control_snapshot")
    report["verdicts"]["snapshot"] = next(line for line in log.splitlines() if line.startswith("PASS actual"))
    bad_rows = rows.copy();fields = bad_rows[0].split();fields[-1] = f"{int(fields[-1],16)^1:08x}";bad_rows[0] = " ".join(fields)
    bad = output / "wrong_expected.txt";bad.write_text("\n".join(bad_rows) + "\n", encoding="ascii")
    run("wrong_expected", [str(CAD / "bin/vvp.exe"), str(output / "default.vvp"), *lut_args, "+VECTORS=" + str(bad)],
        expect=False, marker="accepted original matches Python vector")
    missing_args = [arg for arg in lut_args if not arg.startswith("+LFO_PATH=")] + ["+LFO_PATH=" + str(output / "missing.mem")]
    run("missing_ROM", [str(CAD / "bin/vvp.exe"), str(output / "default.vvp"), *missing_args, "+VECTORS=" + str(vectors)],
        expect=False, marker="missing requested LFO_PATH")
    wrong = output / "wrong_valid.sv"
    wrong.write_text(pipeline.read_text(encoding="utf-8").replace("fcw_valid<=valid_pipe[5];", "fcw_valid<=valid_pipe[4];"), encoding="utf-8", newline="\n")
    run("wrong_valid_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_pitch_mod_pipeline", "-P", "tb_pitch_mod_pipeline.RUN_VECTORS=0",
        "-o", str(output / "wrong_valid.vvp"), str(reference), str(wrong), str(tb)])
    run("wrong_valid", [str(CAD / "bin/vvp.exe"), str(output / "wrong_valid.vvp"), *lut_args], expect=False, marker="pipeline valid exactlyE+6")
    wrong_tag = output / "wrong_tag.sv"
    wrong_tag.write_text(consumer.read_text(encoding="utf-8").replace("result_generations<=held_generations;", "result_generations<=held_generations ^ 128'd1;"), encoding="utf-8", newline="\n")
    snapshot_sources[-2] = wrong_tag
    run("wrong_tag_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_pitch_mod_snapshot_pipeline", "-o", str(output / "wrong_tag.vvp"), *map(str, snapshot_sources)])
    run("wrong_tag", [str(CAD / "bin/vvp.exe"), str(output / "wrong_tag.vvp"), *lut_args], expect=False, marker="identity tags aligned")
    encoded = lambda x: x ^ (((x << 1) | (x >> 9)) & 1023) ^ (((x << 3) | (x >> 7)) & 1023)
    if len({encoded(value) for value in range(1024)}) != 1024:
        raise RuntimeError("fractional address layout not bijective")
    report["constant_ROM_address_bijection_entries"] = 1024
    if cfg.physical:
        folder = output / "fourlane_probe";folder.mkdir()
        def rom_relocate(original):
            text = original.read_text(encoding="utf-8")
            for name in ("oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem"):
                text = text.replace("model/generated/pitch_mod/" + name, (rom / name).as_posix())
            target = folder / original.name;target.write_text(text, encoding="utf-8", newline="\n");return target
        translated = [rom_relocate(pipeline), rom_relocate(consumer)]
        wrapper = folder / "timing_probe.sv";shutil.copy2(CANDIDATE / "pitch_mod_pipeline_timing_probe.sv", wrapper)
        cst = folder / "probe.cst";cst.write_text('IO_LOC "sys_clk" V22;\nIO_PORT "sys_clk" IO_TYPE=LVCMOS33;\nIO_LOC "sys_rst_n" AA13;\nIO_PORT "sys_rst_n" IO_TYPE=LVCMOS15 PULL_MODE=UP;\n', encoding="ascii")
        sdc = folder / "probe.sdc";sdc.write_text('create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]\nset_clock_uncertainty -setup -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}] 0.500\nset_clock_uncertainty -hold -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}] 0.200\nreport_timing -setup -from_clock [get_clocks {sys_clk}] -to_clock [get_clocks {sys_clk}] -max_paths 80\nreport_timing -hold -from_clock [get_clocks {sys_clk}] -to_clock [get_clocks {sys_clk}] -max_paths 25\nreport_timing -recovery -max_paths 25\nreport_timing -removal -max_paths 25\n', encoding="ascii")
        project = ET.Element("Project");ET.SubElement(project,"Template").text="FPGA";ET.SubElement(project,"Version").text="5"
        ET.SubElement(project,"Device",name="GW5AT-60B",pn="GW5AT-LV60PG484AC1/I0").text="gw5at60b-002"
        listing=ET.SubElement(project,"FileList")
        inputs=[ROOT / "code/rtl/common/audio_defs_pkg.sv",ROOT / "code/rtl/common/reset_sync.sv",ROOT / "code/rtl/board/performance_control_snapshot.sv",*translated,wrapper,cst,sdc]
        for file in inputs:
            ET.SubElement(listing,"File",path=file.as_posix(),type="file.verilog" if file.suffix==".sv" else "file."+file.suffix[1:],enable="1")
        gprj=folder/"fourlane_pipeline.gprj";ET.ElementTree(project).write(gprj,encoding="utf-8",xml_declaration=True)
        tcl=folder/"run.tcl";tcl.write_text(f"open_project {{{gprj.as_posix()}}}\nset_option -top_module pitch_mod_pipeline_timing_probe\nset_option -verilog_std sysv2017\nrun all\n",encoding="ascii")
        record={"scope":"internal fourlane+control state probe only; NEVER PROGRAM, autoassigned remainingI/O", "inputs":{str(file):sha(file) for file in inputs+list(rom.glob("*.mem"))}}
        (folder/"input_manifest.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
        run("actual_Gowin",[str(GOWIN),str(tcl)],cwd=ROOT,timeout=600)
        from check_hdmi_link_report import ReportParser
        parser=ReportParser();parser.feed((folder/"impl/pnr/fourlane_pipeline_tr_content.html").read_text(encoding="utf-8"))
        summary={row[0]:row[1] for section,row in parser.rows if section=="STA_Tool_Run_Summary" and len(row)==2}
        paths={}
        for kind in ("Setup","Hold","Recovery","Removal"):
            rows=[row for section,row in parser.rows if section.startswith(kind+"_Slack_Table") and len(row)>=4 and row[0].isdigit()]
            if not rows:
                raise RuntimeError("missing internal timing report class: "+kind)
            paths[kind]=min(rows,key=lambda row:float(row[1]))
            if float(paths[kind][1])<0:
                raise RuntimeError("negative internal "+kind)
        for key in ("Numbers of Setup Violated Endpoints","Numbers of Hold Violated Endpoints"):
            if summary.get(key)!="0":raise RuntimeError("internal timing violated: "+key)
        fmax={row[1]:row[3] for section,row in parser.rows if section=="Max_Frequency_Report" and row and row[0].isdigit()}
        usage=(folder/"impl/pnr/fourlane_pipeline.rpt.txt").read_text(encoding="utf-8")
        resources={key:float(re.search(r"^\s*"+key+r"\s*\|\s*([\d.]+)",usage,re.M).group(1)) for key in ("Logic","Register","DSP","BSRAM")}
        report["actual_fourlane_internal_STA"]={"summary":summary,"worst_paths":paths,"fmax":fmax,"resources":resources,"external_IOfullpiano_signoff":False}
    report["functional_candidate_pass"]=True
    (output/"review.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("Independent candidate passes; formal DDS/bank/board integration still NOT performed.",flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
