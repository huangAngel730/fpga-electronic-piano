"""M2 formal top real-rate R17-to-PT8211 digital causal latency selftest.
Not DAC analog/USB keyboard/mechanical input latency or physical timing proof.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")
TOP = "tb_t031_digital_latency"


def execute(command, stage, label, limit=900):
    path = stage / (label + ".log")
    with path.open("w", encoding="utf-8", newline="\n") as out:
        result = subprocess.run(command, cwd=stage, stdout=out, stderr=subprocess.STDOUT, timeout=limit)
    return result.returncode, path.read_text(encoding="utf-8", errors="replace")


def main():
    stage = ROOT / "code/output/t031_digital_latency_20261002"
    stage.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + os.environ["PATH"]
    allocator = ROOT / "code/rtl/audio/voice_allocator_4.sv"
    script = stage / "lower.ys"
    net = stage / "allocator.v"
    script.write_text("read_slang --top voice_allocator_4 " + allocator.as_posix() +
                      "\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr " + net.as_posix() + "\n", encoding="ascii")
    code, text = execute([str(CAD / "bin/yosys.exe"), "-Q", "-T", "-s", str(script)], stage, "lower", 120)
    if code:
        print(text[-3000:]);return code
    project = ROOT / "code/build/electronic_piano.gprj"
    original = [(project.parent / e.attrib["path"]).resolve() for e in ET.parse(project).findall(".//File")
                if e.attrib["type"] == "file.verilog" and e.attrib.get("enable", "1") == "1"]
    sources = [net if p.name == allocator.name else p for p in original]
    sources.sort(key=lambda p: 0 if p.name == "audio_defs_pkg.sv" else 1 if p.name == "sustain_control_contract_pkg.sv" else 2)
    tb = ROOT / "code/tb/board/tb_t031_digital_latency.sv"
    sources.append(tb)
    binary = stage / "tb.vvp"
    code, text = execute([str(CAD / "bin/iverilog.exe"), "-g2012", "-s", TOP,
                          "-I", str(ROOT / "code/rtl/common"), "-I", str(ROOT / "code/rtl/board"),
                          "-o", str(binary)] + list(map(str, sources)), stage, "compile", 120)
    if code:
        print(text[-3000:]);return code
    cmd = [str(CAD / "bin/vvp.exe"), str(binary),
           "+WAVETABLE_PATH=" + str(ROOT / "code/model/generated/wavetables/piano_band_4x256_8191.mem"),
           "+VELOCITY_ROM_PATH=" + str(ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem")]
    inputs = original + [project, tb, ROOT / "code/model/generated/wavetables/piano_band_4x256_8191.mem",
                         ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem",
                         ROOT / "code/rtl/common/sine_table.svh",
                         ROOT / "code/rtl/board/sustain_controller_ports.svh"]
    input_facts = {"scope": "unmodified production audio/V1+sustain top source list, real clocks/baud",
                   "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (stage / "inputs.json").write_text(json.dumps(input_facts, indent=2) + "\n", encoding="utf-8", newline="\n")
    code, text = execute(cmd + ["+CSV=" + str(stage / "latency.csv")], stage, "RTL")
    for line in text.splitlines():
        if line.startswith(("PASS latency", "PASS T031", "FATAL")):
            print(line)
    if code or "PASS T031 digital latency trials=11" not in text or "FATAL" in text:
        print(text[-3000:]);return code or 1
    code, text = execute(cmd + ["+CSV=" + str(stage / "negative.csv"), "+SUPPRESS_TARGET"], stage, "negative_no_target", 180)
    if code == 0 or "NO_TARGET_RESPONSE causal output missing" not in text:
        raise RuntimeError("suppressed target did not fail in causal detector: " + text[-2000:])
    print("PASS suppressed-target real RTL negative rejected")
    return subprocess.call([sys.executable, "-X", "utf8", str(ROOT / "code/scripts/check_t031_digital_latency.py"),
                            str(stage / "latency.csv"), "--output", str(stage / "analysis.json")])


if __name__ == "__main__":
    raise SystemExit(main())
