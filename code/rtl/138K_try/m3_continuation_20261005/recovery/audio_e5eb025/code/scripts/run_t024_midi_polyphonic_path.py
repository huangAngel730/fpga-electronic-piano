"""T024 formal GPRJ top: physical MIDI bytes to four voices and PT8211 pins.

This checks no UART STAT and does not resume the paused T025/T026 validation.
Allocator lowering only supplies Icarus-compatible code; algorithm is unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")
TOP = "tb_t024_midi_polyphonic_path"


def execute(command, stage, label):
    log = stage / f"{label}.log"
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        result = subprocess.run(command, cwd=stage, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=900)
    text = log.read_text(encoding="utf-8", errors="replace")
    return result.returncode, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast-only", action="store_true")
    parser.add_argument("--negative-tests", action="store_true")
    args = parser.parse_args()
    stage = ROOT / "code/output/t024_midi_polyphonic_path_20261001"
    stage.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + os.environ["PATH"]
    allocator = ROOT / "code/rtl/audio/voice_allocator_4.sv"
    net = stage / "allocator.v"
    ys = stage / "lower.ys"
    ys.write_text(f"read_slang --top voice_allocator_4 {allocator.as_posix()}\n"
                  f"proc\nopt\ntechmap\nopt\nwrite_verilog -noattr {net.as_posix()}\n",
                  encoding="ascii")
    code, text = execute([str(CAD / "bin/yosys.exe"), "-Q", "-T", "-s", str(ys)], stage, "lower")
    if code:
        print(text[-2000:])
        return code
    project = ROOT / "code/build/electronic_piano.gprj"
    original = [(project.parent / entry.attrib["path"]).resolve()
                for entry in ET.parse(project).findall(".//File")
                if entry.attrib["type"] == "file.verilog" and entry.attrib.get("enable", "1") == "1"]
    sources = [net if source.name == allocator.name else source for source in original]
    sources.sort(key=lambda source: 0 if source.name == "audio_defs_pkg.sv" else (1 if source.name == "sustain_control_contract_pkg.sv" else 2))
    tb = ROOT / f"code/tb/board/{TOP}.sv"
    sources.append(tb)
    evidence = {"scope": "Formal top GPRJ list; real 50MHz MIDI 31250 8N1. Fast Release run plus true-rate run. No force, no source modification, no STAT test.",
                "source_sha256": {str(source.relative_to(ROOT)): hashlib.sha256(source.read_bytes()).hexdigest()
                                  for source in original + [project, tb]}, "runs": []}
    modes = [1] if args.fast_only else [1, 0]
    for fast in modes:
        binary = stage / f"top_{fast}.vvp"
        snapshot = stage / f"tb_mode_{fast}.sv"
        snapshot.write_bytes(tb.read_bytes())
        command = [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", TOP,
                   "-P", f"{TOP}.FAST_AUDIO={fast}", "-I", str(ROOT / "code/rtl/common"),
                   "-I", str(ROOT / "code/rtl/board"), "-o", str(binary)] + list(map(str, sources[:-1])) + [str(snapshot)]
        code, text = execute(command, stage, f"compile_{fast}")
        if code:
            print(text[-3000:])
            return code
        command = [str(CAD / "bin/vvp.exe"), str(binary),
                   "+WAVETABLE_PATH=" + str(ROOT / "code/model/generated/wavetables/piano_band_4x256_8191.mem"),
                   "+VELOCITY_ROM_PATH=" + str(ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem")]
        code, text = execute(command, stage, f"run_{fast}")
        results = [line for line in text.splitlines() if line.startswith("PASS " + TOP)]
        for line in text.splitlines():
            if line.startswith(("PASS", "FATAL")):
                print(line)
        passed = code == 0 and len(results) == 1 and "FATAL" not in text
        evidence["runs"].append({"fast_audio": fast, "pass": passed, "exit_code": code, "result": results,
                                 "testbench_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                                 "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
        (stage / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
        if not passed:
            print(text[-3000:])
            return code or 1
        if fast and args.negative_tests:
            negative_code, negative_text = execute(command + ["+NEGATIVE_DATA"], stage, "negative_serial_lsb")
            rejected = negative_code != 0 and "PT8211 PCM mismatch" in negative_text
            evidence["negative_serial_lsb"] = {"rejected": rejected, "exit_code": negative_code}
            print("PT8211 corrupted LSB negative:", "REJECTED" if rejected else "FAIL")
            if not rejected:
                return 1
    evidence["passed"] = True
    (stage / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Evidence:", stage / "evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
