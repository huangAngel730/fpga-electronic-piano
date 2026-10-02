"""Actual installed GowinSynthesis CLI, new V3 output only; no PnR claim."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TOOL = Path("D:/program/gaoyunFPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/GowinSynthesis.exe")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=Path, required=True)
    args = p.parse_args()
    snap = args.snapshot.resolve()
    if not snap.is_relative_to(ROOT / "build"):
        p.error("owned build snapshot required")
    manifest = json.loads((snap / "frozen_input_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["staged_files"]:
        if hashlib.sha256((snap / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Changed build input " + item["path"])
    # Actual independent functional gates, not merely explanatory text.
    for path in (snap / "tests_oscillator/result.json", snap / "tests_lifecycle/v3_golden.json"):
        if json.loads(path.read_text(encoding="utf-8"))["status"] != "PASS":
            raise ValueError("Functional gate not passed")
    project = Path(manifest["project"])
    doc = ET.parse(project)
    files = [node.attrib["path"] for node in doc.findall(".//File") if node.attrib["type"] == "file.verilog"]
    work = snap / "gowin_synthesis"
    if work.exists():
        p.error("never overwrite reports")
    work.mkdir()
    out = work / "electronic_piano_v3.vg"
    command = [str(TOOL), "-p", "GW5AT-60B-PBGA484A-1", "-pn", "GW5AT-LV60PG484AC1/I0",
               "-top", "electronic_piano_top", "-verilog_language", "sysv-2017",
               "-inc", str(snap / "code/rtl/common"), str(snap / "code/rtl/board"), str(snap / "source/rtl"),
               "-sdc", str(snap / "code/constraints/audio_timing.sdc"), "-o", str(out), "-i", *files]
    (work / "command.json").write_text(json.dumps(command, indent=2)+"\n", encoding="utf-8")
    start = time.time()
    result = subprocess.run(command, cwd=work, capture_output=True, timeout=600)
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    (work / "actual_synthesis.log").write_text(output, encoding="utf-8")
    print(output[-5000:])
    report = {"exit_code":result.returncode,"elapsed_seconds":time.time()-start,
              "vg_created":out.is_file(),"command":command,"scope":"synthesis only; no PnR/STA/bitstream claim"}
    (work / "result.json").write_text(json.dumps(report,indent=2)+"\n", encoding="utf-8")
    if result.returncode or not out.is_file() or "ERROR (" in output or "EX3988" in output:
        raise RuntimeError("Actual Gowin synthesis failed; logs preserved")
    print("PASS actual Gowin synthesis; netlist", out)


if __name__ == "__main__":
    main()
