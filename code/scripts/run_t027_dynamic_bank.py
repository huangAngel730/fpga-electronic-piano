#!/usr/bin/env python3
"""Exercise per-source MIDI Program 0/1 and four-lane waveform snapshots."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "code/output/t027_dynamic_bank"
STAGE.mkdir(parents=True, exist_ok=True)
CAD = Path("D:/Gowin/oss-cad-suite")
NET = STAGE / "allocator.v"
YS = STAGE / "lower.ys"
source = ROOT / "code/rtl/audio/voice_allocator_4.sv"
YS.write_text(
    f"read_slang --top voice_allocator_4 {source.as_posix()}\n"
    f"proc\nopt\ntechmap\nopt\nwrite_verilog -noattr {NET.as_posix()}\n",
    encoding="ascii",
)


def quoted(path: Path | str) -> str:
    return f'"{path}"'


files = [
    ROOT / "code/rtl/common/audio_defs_pkg.sv",
    NET,
    ROOT / "code/rtl/common/note_pitch.sv",
    ROOT / "code/rtl/board/sustain_control_contract_pkg.sv",
    ROOT / "code/rtl/input/sustain_control/sustain_controller.sv",
    ROOT / "code/rtl/board/polyphonic_event_router.sv",
    ROOT / "code/rtl/board/polyphonic_envelope_bank.sv",
    ROOT / "code/rtl/audio/dds_oscillator.sv",
    ROOT / "code/rtl/audio/piano_dds_oscillator.sv",
    ROOT / "code/rtl/audio/timbre_oscillator.sv",
    ROOT / "code/rtl/board/piano_triangle_voice.sv",
    ROOT / "code/rtl/audio/adsr_piano_envelope.sv",
    ROOT / "code/tb/board/tb_t027_dynamic_bank.sv",
]
commands = [
    f"{quoted(CAD / 'bin/yosys.exe')} -Q -T -s {quoted(YS)}",
    f"{quoted(CAD / 'bin/iverilog.exe')} -g2012 -I {quoted(ROOT / 'code/rtl/board')} "
    f"-s tb_t027_dynamic_bank -o {quoted(STAGE / 'tb.vvp')} "
    + " ".join(map(quoted, files)),
    f"{quoted(CAD / 'bin/vvp.exe')} {quoted(STAGE / 'tb.vvp')} "
    f"+VELOCITY_ROM_PATH={quoted(STAGE / 'velocity_gain_rom.mem')} "
    f"+WAVETABLE_PATH={quoted(STAGE / 'piano_band_4x256_8191.mem')} "
    f"+CAPTURE={quoted(STAGE / 'two_timbres.txt')}",
]
batch = STAGE / "run.bat"
batch.write_text(
    "@echo off\r\ncall " + quoted(CAD / "environment.bat") + " >nul\r\n"
    + "\r\nif errorlevel 1 exit /b 1\r\n".join(commands)
    + "\r\nexit /b %errorlevel%\r\n",
    encoding="ascii",
)
for table in ("sine_wavetable.hex", "triangle_wavetable.hex"):
    (STAGE / table).write_bytes((ROOT / "code/model/generated" / table).read_bytes())
# Existing ADSR uses this ROM even in standalone bank tests.
(STAGE / "piano_band_4x256_8191.mem").write_bytes(
    (ROOT / "code/model/generated/wavetables/piano_band_4x256_8191.mem").read_bytes()
)
(STAGE / "velocity_gain_rom.mem").write_bytes(
    (ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem").read_bytes()
)
proc = subprocess.run(
    ["cmd.exe", "/c", str(batch)], cwd=STAGE,
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
)
output = proc.stdout + proc.stderr
(STAGE / "run.log").write_text(output, encoding="utf-8", newline="\n")
for line in output.splitlines():
    if "PASS T027" in line or "FATAL" in line or "error:" in line:
        print(line)
print("Log:", STAGE / "run.log")
if "readmemh: Unable to open" in output or "ERROR:" in output:
    raise SystemExit("T027 ROM load or simulator error: see log")
if proc.returncode or "PASS T027 dynamic" not in proc.stdout:
    raise SystemExit(proc.returncode or 1)
# Independent DFT at the known 440/1320-Hz bins with Hann taper.
import cmath
import math
samples = [tuple(map(int, line.split())) for line in
           (STAGE / "two_timbres.txt").read_text(encoding="ascii").splitlines()]
if len(samples) != 2048:
    raise SystemExit(f"Expected 2048 paired samples, got {len(samples)}")

def harmonic_ratio(lane: int) -> float:
    def energy(hertz: float) -> float:
        total = sum(samples[n][lane] * (0.5 - 0.5 * math.cos(2 * math.pi * n / 2047))
                    * cmath.exp(-2j * math.pi * hertz * n / 48000)
                    for n in range(2048))
        return abs(total)
    return energy(1320.0) / max(energy(440.0), 1e-12)
triangle_ratio = harmonic_ratio(0)
piano_ratio = harmonic_ratio(1)
print(f"T027 captured A4 third/fundamental: triangle={triangle_ratio:.5f}, V1={piano_ratio:.5f}")
if not (0.06 < triangle_ratio < 0.16 and abs(piano_ratio - triangle_ratio) > 0.04):
    raise SystemExit("T027 live waveform spectra not distinguishable")
raise SystemExit(0)
