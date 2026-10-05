#!/usr/bin/env python3
"""Capture actual 1/4 lane DDS+ADSR+mixer probe evidence with hashes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
from check_t024_voice_datapath import report  # noqa: E402


def capture(out):
    variants = {str(n): report(out, n) for n in (1, 4)}
    if (variants["1"]["tool"], variants["1"]["part"]) != (
            variants["4"]["tool"], variants["4"]["part"]):
        raise ValueError("Tool or part mismatch between probes")
    paths = [
        ROOT / "code/rtl/board/voice_datapath_probe.sv",
        ROOT / "code/rtl/audio/dds_oscillator.sv",
        ROOT / "code/rtl/audio/adsr_piano_envelope.sv",
        ROOT / "code/rtl/mixer/pcm_mixer_4voice.sv",
        ROOT / "code/model/generated/wavetables/sine_1024_32767.mem",
        ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem",
        ROOT / "code/scripts/run_t024_voice_datapath.ps1",
        ROOT / "code/scripts/check_t024_voice_datapath.py",
        ROOT / "code/scripts/run_t024_voice_datapath_sim.ps1",
        ROOT / "code/tb/board/tb_voice_datapath_probe.sv",
        ROOT / "code/tb/board/test_t024_voice_datapath.py",
    ]
    for n in (1, 4):
        p = out / f"lanes_{n}/impl/pnr"
        name = f"voice_datapath_probe_{n}"
        paths.extend([p / f"{name}.rpt.txt", p / f"{name}_tr_content.html",
                      p / f"{name}.fs"])
    digests = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in paths}
    return {
        "source_baseline_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": "synthetic independent DDS+ADSR+mixer datapath; excludes formal voice allocation/audio output",
        "variants": variants,
        "delta_four_minus_one": {key: variants["4"]["resources"][key] - variants["1"]["resources"][key]
                                 for key in variants["1"]["resources"]},
        "sha256": digests,
        "limitations": [
            "Prototype scales 32767 peak sine before PCM; not M1 D028 frozen wavetable/PCM truth",
            "No allocator, note ownership, request-ID, I2S, UART or speaker",
            "No board CST; only 50 MHz sys_clk, standalone PnR, no hardware download",
            "Expected voice result latency and frame deadline not demonstrated",
        ],
    }


def main():
    try:
        result = capture(ROOT / "code/output/t024_voice_datapath")
        target = ROOT / "code/docs/evidence/t024_voice_datapath_20260928.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        print(f"PASS T024 evidence {len(result['sha256'])} hashes; {target}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL T024 evidence: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
