#!/usr/bin/env python3
"""Independent Gowin physical check for the current T010 allocator candidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "code/output/t010_allocator_gowin"
PART = "GW5AT-LV60PG484AC1/I0"


def run(source):
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"Missing T010 source: {source}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    input_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    local = OUTPUT / "voice_allocator_4.sv"
    local.write_bytes(source.read_bytes())
    sdc = OUTPUT / "allocator.sdc"
    sdc.write_text("create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]\n",
                   encoding="ascii")
    project = OUTPUT / "allocator.gprj"
    project.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<!DOCTYPE gowin-fpga-project>\n'
                       '<Project><Template>FPGA</Template><Version>5</Version>\n'
                       f'<Device name="GW5AT-60B" pn="{PART}">gw5at60b-002</Device>\n'
                       '<FileList><File path="voice_allocator_4.sv" type="file.verilog" enable="1"/>\n'
                       '<File path="allocator.sdc" type="file.sdc" enable="1"/></FileList></Project>\n',
                       encoding="ascii")
    driver = OUTPUT / "build.tcl"
    driver.write_text(f"open_project {{{project.as_posix()}}}\n"
                      "set_option -verilog_std sysv2017\n"
                      "set_option -top_module voice_allocator_4\nrun all\n", encoding="ascii")
    exe = (Path(os.environ.get("GOWIN_HOME",
              "D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64")) /
           "IDE/bin/gw_sh.exe")
    log = OUTPUT / "build.log"
    with log.open("w", encoding="utf-8") as stream:
        rc = subprocess.run([str(exe), str(driver)], cwd=OUTPUT,
                            stdout=stream, stderr=subprocess.STDOUT, check=False).returncode
    if rc != 0:
        raise ValueError(f"Gowin run all failed exit={rc}; see {log}")
    text = log.read_text(encoding="utf-8", errors="replace")
    if 'Current top module is "voice_allocator_4"' not in text or "Bitstream generation completed" not in text:
        raise ValueError("Gowin log lacks top or completed bitstream")
    timing = OUTPUT / "impl/pnr/allocator_tr_content.html"
    report = OUTPUT / "impl/pnr/allocator.rpt.txt"
    for path in (timing, report):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing Gowin report {path}")
    from check_t009_fusion_report import Rows
    parser = Rows()
    parser.feed(timing.read_text(encoding="utf-8"))
    pairs = {r[0]:r[1] for section,r in parser.rows if section=="STA_Tool_Run_Summary" and len(r)==2}
    for key in ("Numbers of Setup Violated Endpoints","Numbers of Hold Violated Endpoints"):
        if pairs.get(key) != "0":
            raise ValueError(f"Timing failure {key}: {pairs.get(key)}")
    clocks = [r for section,r in parser.rows if section=="Clock_Report" and len(r)>=5 and r[1]=="sys_clk"]
    if len(clocks)!=1 or clocks[0][3:5]!=["20.000","50.000"]:
        raise ValueError("Missing 50 MHz sys_clk")
    freq = [r for section,r in parser.rows if section=="Max_Frequency_Report" and len(r)>=4 and r[1]=="sys_clk"]
    if len(freq)!=1 or float(freq[0][3].replace("(MHz)","")) < 50:
        raise ValueError(f"Fmax below 50MHz: {freq}")
    values={}
    for kind in ("Setup","Hold","Recovery","Removal"):
        rows=[r for section,r in parser.rows if section==kind+"_Slack_Table" and len(r)>=4 and r[0].isdigit()]
        if rows:
            values[kind]=min(float(r[1]) for r in rows)
            if values[kind] < 0:
                raise ValueError(f"Negative {kind} slack {values[kind]}")
        else: values[kind]=None
    used={}
    raw=report.read_text(encoding="utf-8")
    if f"<Part Number>: {PART}" not in raw:
        raise ValueError("Target part mismatch")
    for name in ("Logic","Register","DSP","BSRAM"):
        match=re.findall(r"^\s*"+name+r"\s*\|\s*(\d+)/(\d+)",raw,re.M)
        if match:
            if len(match)!=1: raise ValueError(f"Duplicate resource {name}")
            used[name]={"used":int(match[0][0]),"capacity":int(match[0][1])}
    if not ("Logic" in used and "Register" in used):
        raise ValueError("Missing resource summary")
    if hashlib.sha256(source.read_bytes()).hexdigest()!=input_hash:
        raise ValueError("T010 source changed during build")
    info={"candidate_source_sha256":input_hash,"target_part":PART,
          "fmax_mhz":float(freq[0][3].replace("(MHz)","")),"worst_slack_ns":values,
          "resources":used,
          "report_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (log,timing,report)}}
    (OUTPUT/"summary.json").write_text(json.dumps(info,indent=2)+"\n",encoding="utf-8")
    return info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    args=parser.parse_args()
    try:
        print("PASS T010 standalone Gowin",json.dumps(run(args.source),indent=2))
    except (OSError,ValueError) as exc:
        print("FAIL T010 standalone Gowin:",exc,file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
