#!/usr/bin/env python3
"""Write the three Pitch/Mod LUTs consumed by pitch_mod_fcw.sv.

Outputs (relative to this file):
    generated/pitch_mod/oct_ratio_q16.mem    50 x 20-bit  (integer semitone)
    generated/pitch_mod/sub_ratio_q16.mem  1024 x 20-bit  (1/1024 semitone)
    generated/pitch_mod/lfo_sine_q15.mem   1024 x 16-bit  (signed sine)

Values come from pitch_mod_model.py, so the .mem files and the golden model
can never drift: test_pitch_mod.py re-reads the .mem and compares.
"""

from __future__ import annotations

from pathlib import Path

import pitch_mod_model as m


def write_mem(path: Path, values: list[int], digits: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = (1 << (4 * digits)) - 1
    path.write_text("\n".join(f"{v & mask:0{digits}x}" for v in values) + "\n",
                    encoding="ascii")
    print(f"wrote {len(values):5d} x {digits * 4:2d}-bit -> {path}")


def main() -> None:
    out = Path(__file__).resolve().parent / "generated" / "pitch_mod"
    write_mem(out / "oct_ratio_q16.mem", m.OCT_LUT, 5)
    write_mem(out / "sub_ratio_q16.mem", m.SUB_LUT, 5)
    write_mem(out / "lfo_sine_q15.mem", m.LFO_LUT, 4)
    print(f"PASS: LUT generation complete (LFO_INC={m.LFO_INC} for "
          f"{m.MOD_LFO_HZ} Hz at {m.SAMPLE_RATE_HZ} Hz)")


if __name__ == "__main__":
    main()
