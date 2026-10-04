#!/usr/bin/env python3
"""Exercise real four-lane Program 0/1 through PCM commit."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "code/output/t027_dynamic_core"
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
    ROOT / "code/rtl/board/polyphonic_pcm_commit.sv",
    ROOT / "code/rtl/mixer/pcm_mixer_4voice.sv",
    ROOT / "code/rtl/audio_out/pcm_result_hold.sv",
    ROOT / "code/rtl/audio_out/pcm_frame_buffer.sv",
    ROOT / "code/rtl/common/pcm_clip_counter.sv",
    ROOT / "code/rtl/common/system_status_counters.sv",
    ROOT / "code/rtl/board/voice_gain_q15_candidate.sv",
    ROOT / "code/rtl/board/polyphonic_audio_core.sv",
    ROOT / "code/tb/board/tb_t027_dynamic_core.sv",
]
commands = [
    f"{quoted(CAD / 'bin/yosys.exe')} -Q -T -s {quoted(YS)}",
    f"{quoted(CAD / 'bin/iverilog.exe')} -g2012 -I {quoted(ROOT / 'code/rtl/board')} "
    f"-s tb_t027_dynamic_core -o {quoted(STAGE / 'tb.vvp')} "
    + " ".join(map(quoted, files)),
    f"{quoted(CAD / 'bin/vvp.exe')} {quoted(STAGE / 'tb.vvp')} "
    f"+VELOCITY_ROM_PATH={quoted(STAGE / 'velocity_gain_rom.mem')} "
    f"+WAVETABLE_PATH={quoted(STAGE / 'piano_band_4x256_8191.mem')}",
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
nested = STAGE / "model/generated"
nested.mkdir(parents=True, exist_ok=True)
for table in ("sine_wavetable.hex", "triangle_wavetable.hex"):
    (nested / table).write_bytes((ROOT / "code/model/generated" / table).read_bytes())
(STAGE / "velocity_gain_rom.mem").write_bytes(
    (ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem").read_bytes()
)
proc = subprocess.run(
    ["cmd.exe", "/c", str(batch)], cwd=STAGE,
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
)
output = proc.stdout + proc.stderr
(STAGE / "run.log").write_text(output, encoding="utf-8", newline="\n")
for line in output.splitlines():
    if "PASS T027" in line or "FATAL" in line or "error:" in line:
        print(line)
print("Log:", STAGE / "run.log")
if "readmemh: Unable to open" in output or "ERROR:" in output:
    raise SystemExit("T027 ROM load or simulator error: see log")
raise SystemExit(proc.returncode or (0 if "PASS T027 dynamic PCM" in proc.stdout else 1))
