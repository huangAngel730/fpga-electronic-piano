"""Independent integer oracle; never imports candidate model implementation.

Execute only on a verified frozen V3 snapshot. Outputs stay in owned build.
The above-220-Hz comparison uses an unchanged V1 RTL instance, not this oracle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CAD = Path("D:/Gowin/oss-cad-suite")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signed_mem(path):
    return [v if v < 32768 else v - 65536
            for v in (int(word, 16) for word in path.read_text().split())]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    snapshot = args.snapshot.resolve()
    if not snapshot.is_relative_to(ROOT / "build"):
        parser.error("snapshot must be in V3/build")
    lock = snapshot / "frozen_input_manifest.json"
    if not lock.is_file():
        parser.error("frozen-input manifest required")
    manifest = json.loads(lock.read_text(encoding="utf-8"))
    for item in manifest["staged_files"]:
        path = snapshot / item["path"]
        if sha(path) != item["sha256"]:
            parser.error("snapshot hash changed: " + str(path))
    source = snapshot / "source"
    work = snapshot / "tests_oscillator"
    if work.exists():
        parser.error("refuse to overwrite results")
    work.mkdir()
    constants = (source / "rtl/v3_constants.svh").read_text(encoding="utf-8")
    def values(name, width):
        match = re.search(name + r"\s*=\s*\{([^}]+)\}", constants)
        if not match:
            raise ValueError("missing coefficient contract " + name)
        return list(reversed([int(v) for v in re.findall(str(width)+r"'d(\d+)", match[1])]))
    initial = values("BASS_INITIAL", 16)
    floor = values("BASS_FLOOR", 16)
    shifts = values("PARTIAL_SHIFT", 5)
    assert len(initial) == len(floor) == len(shifts) == 12
    assert all(8191 >= a >= b > 0 for a, b in zip(initial, floor))
    rom_path = source / "rom/sine_v3_1024_32767.mem"
    sine = signed_mem(rom_path)
    assert len(sine) == 1024
    shutil.copy2(rom_path, work / "sine_rom.mem")
    shutil.copy2(source / "baseline/piano_band_4x256_8191.mem", work / "piano_rom.mem")
    # FCW from the unchanged formal semitone table, not floating tuning guesses.
    pitch_text = (snapshot / "code/rtl/common/note_pitch.sv").read_text(encoding="utf-8")
    packed = re.search(r"SEMITONE_TABLE\s*=\s*\{([^}]+)\}", pitch_text)
    base = list(reversed([int(v) for v in re.findall(r"32'd(\d+)", packed[1])]))
    assert len(base) == 12 and base[9] == 39370534
    def note_fcw(note):
        octave, semitone = divmod(note, 12)
        return base[semitone] << (octave-5) if octave >= 5 else base[semitone] >> (5-octave)
    rng = random.Random(30064)
    phase = 0
    amplitude = [v << 16 for v in floor]
    target = amplitude.copy()
    last = 0
    rows = []
    def vector(reset, strike, tick, fcw, velocity=900, idle=42):
        nonlocal phase, amplitude, target, last
        if reset:
            phase = 0
            amplitude = [v << 16 for v in floor]
            target = amplitude.copy()
            last = 0
        else:
            old_target = target.copy()
            if strike:
                target = [(b + ((a-b)//2 if velocity < 256 else
                           3*(a-b)//4 if velocity < 768 else a-b)) << 16
                          for a, b in zip(initial, floor)]
            if tick:
                phase = (phase + fcw) % (1 << 32)
                for k in range(12):
                    gap = old_target[k] - amplitude[k]
                    amplitude[k] += ((gap+63)//64 if gap >= 0 else -((-gap+63)//64))
                    if not strike and shifts[k]:
                        tail = old_target[k] - (floor[k] << 16)
                        target[k] = old_target[k] - (tail+(1 << shifts[k])-1)//(1 << shifts[k])
                total = sum(sine[((phase*(k+1)) % (1 << 32)) >> 22] * (amplitude[k] >> 16)
                            for k in range(12) if fcw*(k+1) <= 1789569706)
                last = min(8191, max(-8192, (total+16384)//32768))
        rows.append(f"{int(reset)} {int(strike)} {int(tick)} {fcw:08x} {velocity} {last} {int(fcw<=19685267)} {idle}\n")
    for note in range(21, 109):
        fcw = note_fcw(note)
        vector(True, False, False, fcw)
        vector(False, True, False, fcw)
        for index in range(160):
            if index in (31, 79, 120):
                vector(False, True, False, fcw, (1, 511, 1023)[(index+1) % 3])
            vector(False, index == 100, True, fcw, 256, 38 + rng.randrange(9))
    # Sustained decay, all velocity branches, FCW changes without phase resets.
    for note in (36, 37, 48, 49):
        fcw = note_fcw(note)
        vector(True, False, False, fcw)
        vector(False, True, False, fcw)
        for index in range(16000):
            vector(False, index % 4000 == 3999, True, fcw, (0, 255, 256, 767, 768, 1023)[index % 6])
    for index in range(512):
        fcw = note_fcw((36, 84, 37, 60)[index % 4])
        vector(False, index % 17 == 0, True, fcw, index % 1024)
    # Reset while the serialized renderer is busy is a separate real clock case.
    vector(False, False, True, note_fcw(36), idle=3)
    # The unfinished sample is intentionally not compared: reset aborts it.
    # Avoid checking either waveform mid-computation: represented below in TB skip flag.
    parts = rows[-1].split(); parts[6] = "2"; rows[-1] = " ".join(parts)+"\n"
    vector(True, False, False, note_fcw(36))
    for _ in range(128):
        vector(False, False, True, note_fcw(36))
    (work / "oscillator_vectors.txt").write_text("".join(rows), encoding="ascii")
    commands = [
        [str(CAD / "bin/iverilog.exe"), "-g2012", "-I", str(source / "rtl"),
         "-s", "tb_v3_oscillator", "-o", str(work / "tb.vvp"),
         str(source / "baseline/piano_dds_oscillator.sv"),
         str(source / "rtl/piano_dds_oscillator_v3.sv"),
         str(ROOT / "verification/tb_v3_oscillator.sv")],
        [str(CAD / "bin/vvp.exe"), str(work / "tb.vvp")]]
    for index, command in enumerate(commands):
        bat = work / f"step{index}.bat"
        bat.write_text('@echo off\r\ncall "'+str(CAD / "environment.bat")+'" >nul\r\n'+
                       " ".join('"'+part+'"' for part in command)+"\r\nexit /b %errorlevel%\r\n", encoding="ascii")
        result = subprocess.run(["cmd.exe", "/c", str(bat)], cwd=work,
                                capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr
        (work / f"step{index}.log").write_text(output, encoding="utf-8")
        print(output[-3000:])
        if result.returncode or re.search(r"ERROR:|FATAL|FAIL", output):
            raise RuntimeError("RTL test failed")
    if "PASS independent" not in output:
        raise RuntimeError("no actual PASS")
    (work / "result.json").write_text(json.dumps({"status":"PASS", "rows":len(rows),
        "scope":"independent bass integer oracle; high-note bit-identical V1 RTL comparator",
        "rom_sha256":sha(rom_path), "vectors_sha256":sha(work / "oscillator_vectors.txt"),
        "snapshot_manifest_sha256":sha(lock)}, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
