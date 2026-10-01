"""Create independent Gowin SYNTHESIS-ONLY control-state probe.
No production GPRJ/CST/clock changes, no PnR/FS or board instructions.
"""
from pathlib import Path
import json
import hashlib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def main():
    stage = ROOT / "code/output/performance_control_state_20261001/gowin_probe"
    stage.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / rel for rel in ["code/rtl/common/audio_defs_pkg.sv",
                                   "code/rtl/board/performance_control_state.sv",
                                   "code/tb/board/performance_control_probe.sv"]]
    project = ET.Element("Project")
    ET.SubElement(project, "Template").text = "FPGA"
    ET.SubElement(project, "Version").text = "5"
    ET.SubElement(project, "Device", name="GW5AT-60B",
                  pn="GW5AT-LV60PG484AC1/I0").text = "gw5at60b-002"
    listing = ET.SubElement(project, "FileList")
    for path in paths:
        ET.SubElement(listing, "File", path=path.as_posix(), type="file.verilog", enable="1")
    gprj = stage / "performance_control_probe.gprj"
    ET.ElementTree(project).write(gprj, encoding="utf-8", xml_declaration=True)
    commands = ["cd {" + stage.as_posix() + "}", "open_project {" + gprj.as_posix() + "}",
                "set_option -top_module performance_control_probe",
                "set_option -verilog_std sysv2017", "run syn"]
    (stage / "run_synth.tcl").write_text("\n".join(commands) + "\n", encoding="ascii", newline="\n")
    facts = {"stage": str(stage), "scope": "synthesis-only standalone probe, not formal timing",
             "sources_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in paths}}
    (stage / "inputs.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Prepared synth-only probe:", stage / "run_synth.tcl")


if __name__ == "__main__":
    main()
