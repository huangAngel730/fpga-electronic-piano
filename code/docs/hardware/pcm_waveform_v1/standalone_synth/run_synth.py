"""One bounded T058 native Gowin synthesis only; no PnR/bitstream/pins."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
SOURCE = ROOT / "code/rtl/input/pcm_waveform_candidate/pcm_waveform_candidate.sv"
DEVICE = "GW5AST-138C"
PART = "GW5AST-LV138PG484AC1/I0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(path):
    spec = importlib.util.spec_from_file_location("gowin_rows", ROOT / "code/scripts/check_t009_fusion_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.Rows()
    parser.feed(path.read_text(encoding="utf-8"))
    about = {r[0]: r[1] for section, r in parser.rows if section == "about" and len(r) == 2}
    clocks = [r for section, r in parser.rows if section == "clock" and len(r) >= 5 and r[1] == "pixel_clk"]
    if about.get("Part Number") != PART or about.get("Device Version") != "C":
        raise ValueError("REPORT_TARGET")
    if len(clocks) != 1 or clocks[0][3:5] != ["40.000", "25.000"]:
        raise ValueError("REPORT_CLOCK")
    resources = {key: "unknown" for key in ("Logic", "Register", "BSRAM", "DSP")}
    for key in resources:
        hits = [r[1] for section, r in parser.rows if section == "utilization" and len(r) > 1 and r[0] == key]
        if len(hits) == 1:
            match = re.fullmatch(r"(\d+)(?:\([^)]*\))?\s*/\s*(\d+)", hits[0])
            if match:
                resources[key] = {"used": int(match[1]), "available": int(match[2])}
    if any(resources[k] == "unknown" for k in ("Logic", "Register", "BSRAM")):
        raise ValueError("MISSING_RESOURCES")
    return {"resources": resources, "tool": about, "actual_clock": clocks,
            "estimated_performance": [r for section, r in parser.rows if section == "performance"],
            "primitive_usage": [r for section, r in parser.rows if section == "usage"],
            "PnR_STA": "not executed; synthesis estimates are not STA"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tool", type=Path, default=Path("D:/program/gaoyunFPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/GowinSynthesis.exe"))
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to((ROOT / "code/output").resolve()) or not out.name.startswith("m3_pcm_waveform_"):
        parser.error("require new code/output/m3_pcm_waveform_* output")
    if not args.tool.is_file() or args.tool.name.lower() != "gowinsynthesis.exe":
        parser.error("require existing native GowinSynthesis.exe")
    out.mkdir(parents=True)
    receipt = {"passed": False, "attempts": 0, "scope": "standalone synthesis only", "source_sha256": sha(SOURCE)}
    try:
        local = out / SOURCE.name
        shutil.copyfile(SOURCE, local)
        sdc = out / "waveform.sdc"
        sdc.write_text("create_clock -name pixel_clk -period 40.000 [get_ports {pixel_clk}]\n", encoding="ascii")
        project = ET.Element("Project")
        ET.SubElement(project, "Template").text = "FPGA"
        ET.SubElement(project, "Version").text = "5"
        ET.SubElement(project, "Device", name=DEVICE, pn=PART).text = "gw5ast138c-007"
        files = ET.SubElement(project, "FileList")
        for path, kind in [(local, "file.verilog"), (sdc, "file.sdc")]:
            ET.SubElement(files, "File", path=path.as_posix(), type=kind, enable="1")
        ET.ElementTree(project).write(out / "waveform.gprj", encoding="utf-8", xml_declaration=True)
        command = [str(args.tool), "-p", DEVICE, "-pn", PART, "-i", str(local),
                   "-top", "pcm_waveform_candidate", "-verilog_language", "sysv-2017",
                   "-sdc", str(sdc), "-global_freq", "25", "-o", str(out / "waveform.vg")]
        receipt["command"] = command
        receipt["tool_sha256"] = sha(args.tool)
        receipt["attempts"] = 1
        with (out / "synthesis.stdout.log").open("wb") as stdout, (out / "synthesis.stderr.log").open("wb") as stderr:
            process = subprocess.Popen(command, cwd=out, stdout=stdout, stderr=stderr)
            try:
                code = process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30, check=False)
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=30)
                code = 124
        receipt["exit"] = code
        log = (out / "synthesis.stdout.log").read_text(encoding="utf-8", errors="replace")
        if code or re.search(r"(?:ERROR|FATAL)\s*[:(]", log):
            raise ValueError("SYNTHESIS_FAILED")
        report = out / "waveform_syn.rpt.html"
        receipt["report"] = review(report)
        receipt["report_sha256"] = sha(report)
        receipt["warnings"] = [line for line in log.splitlines() if "WARN" in line]
        if sha(SOURCE) != receipt["source_sha256"] or sha(local) != receipt["source_sha256"]:
            raise ValueError("SOURCE_CHANGED")
        if list(out.glob("*.fs")):
            raise ValueError("UNEXPECTED_BITSTREAM")
        receipt["passed"] = True
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        receipt["error"] = str(error)
        print("FAIL", error, flush=True)
    finally:
        receipt["artifacts_sha256"] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print("EVIDENCE", out, flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
