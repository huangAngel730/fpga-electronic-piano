#!/usr/bin/env python3
"""Capture hashes of the actual 1/4 ADSR scale experiment."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
from check_t016_adsr_scale import parse  # noqa: E402


def capture(out: Path):
    cases = {str(n): parse(out, n) for n in (1, 4)}
    if (cases["1"]["tool"], cases["1"]["part"]) != (cases["4"]["tool"], cases["4"]["part"]):
        raise ValueError("Tool/device changed across probe variants")
    watched = [ROOT / "code/rtl/audio/adsr_piano_envelope.sv",
               ROOT / "code/rtl/board/adsr_scale_probe.sv",
               ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem",
               ROOT / "code/scripts/run_t016_adsr_scale.ps1"]
    for n in (1, 4):
        root = out / f"voice_{n}/impl/pnr"
        watched += [root / f"adsr_probe_{n}.rpt.txt",
                    root / f"adsr_probe_{n}_tr_content.html",
                    root / f"adsr_probe_{n}.fs"]
    digests = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in watched}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return {"purpose": "one/four independent ADSR wrappers, not the complete voice",
            "source_commit": head, "variants": cases,
            "delta_four_minus_one": {key: cases["4"]["resource"][key] - cases["1"]["resource"][key]
                                     for key in cases["1"]["resource"]},
            "sha256": digests,
            "limitations": ["No DDS, allocator, mixer, PCM handshake, UART or HDMI",
                            "No CST or clocked upstream sample request timing",
                            "Fixed 50 MHz SDC constrains sys_clk registers only",
                            "Does not validate four simultaneous audible voices or board audio"]}


def main():
    try:
        result = capture(ROOT / "code/output/t016_adsr_scale")
        dest = ROOT / "code/docs/evidence/t016_adsr_scale_20260927.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        print(f"PASS T016 evidence: {len(result['sha256'])} matching source/report hashes in {dest}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("FAIL T016 evidence:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
