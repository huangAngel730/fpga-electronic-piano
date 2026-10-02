#!/usr/bin/env python3
"""RTL-semantics emulator for pitch_mod_fcw.sv, checked against the vectors.

This is NOT the golden model.  It re-implements the RTL exactly as written --
same bit widths, same truncation points, same clamp -- from the HDL source, so
a width mistake in the RTL (a 5-bit LUT index, truncating before saturation,
the wrong shift) shows up as a vector mismatch here even though the RTL and the
golden model were written from the same formula.

It is the strongest equivalence evidence obtainable without a simulator on this
machine.  It does not replace an Icarus/Vivado run: the TB source is shipped
for that (L2).  Reported level is L1/L3 as defined in the task book.

Run:  python -X utf8 check_rtl_equivalence.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pitch_mod_model as m

VECTORS = (Path(__file__).resolve().parent / "generated" / "pitch_mod"
           / "pitch_mod_vectors.txt")


def s(value: int, bits: int) -> int:
    """Two's-complement reinterpretation to `bits` width."""
    value &= (1 << bits) - 1
    if value >> (bits - 1):
        value -= 1 << bits
    return value


# --------------------------------------------------------------- RTL mirrors
def semi_q10_rtl(bend: int, pitch_range: int) -> int:
    # bend_x_range <== signed(bend) * unsigned(range)   (17-bit result)
    prod = s(bend, 12) * pitch_range
    return s(prod, 17) >> 1


def depth_q10_rtl(modulation: int) -> int:
    mod_x_depth = (modulation & 0xFFF) * 512
    return ((mod_x_depth + 2048) >> 12) & 0x3FF


def vib_q10_rtl(lfo_sine_q15: int, depth_q10: int) -> int:
    sine_x_depth = s(lfo_sine_q15, 16) * depth_q10
    return s(sine_x_depth, 26) >> 15


def factor_q16_rtl(total_q10: int) -> int:
    q_semi = total_q10 >> 10
    r_frac = total_q10 & 0x3FF
    if q_semi > 24:
        oct_idx = 49
    elif q_semi < -25:
        oct_idx = 0
    else:
        oct_idx = (q_semi + 25) & 0x3F
    oct_val = m.OCT_LUT[oct_idx]
    sub_val = m.SUB_LUT[r_frac]
    return ((oct_val * sub_val) >> 16) & 0x1FFFFFF


def fcw_rtl(base_fcw: int, total_q10: int, fcw_max: int) -> int:
    factor = factor_q16_rtl(total_q10)
    fcw_raw = (base_fcw * factor + 32768) >> 16
    return fcw_max if fcw_raw > fcw_max else fcw_raw


def step_rtl(lfo_phase: int, base_fcw: int, bend: int, pitch_range: int,
             modulation: int, note_on: bool):
    """One sample. Returns (fcw_out, next_lfo_phase)."""
    phase_now = 0 if note_on else lfo_phase
    sine = m.LFO_LUT[(phase_now >> 22) & 0x3FF]
    vib = vib_q10_rtl(sine, depth_q10_rtl(modulation))
    semi = semi_q10_rtl(bend, pitch_range)
    total = s(semi + vib, 18)
    fcw = fcw_rtl(base_fcw, total, 1 << 31)
    if note_on:
        nxt = m.LFO_INC
    else:
        nxt = (lfo_phase + m.LFO_INC) & 0xFFFFFFFF
    return fcw, nxt


def main() -> int:
    if not VECTORS.exists():
        print(f"FAIL: vectors missing: {VECTORS}")
        print("      run generate_pitch_mod_vectors.py first")
        return 1

    lines = VECTORS.read_text().split()
    rows = [lines[i:i + 6] for i in range(0, len(lines), 6)]
    errors = 0
    phase = 0
    for idx, (b, bd, rg, md, no, exp) in enumerate(rows):
        base = int(b, 16)
        bend = s(int(bd, 16), 12)
        rng = int(rg, 16)
        mod = int(md, 16)
        note_on = bool(int(no))
        expected = int(exp, 16)
        got, phase = step_rtl(phase, base, bend, rng, mod, note_on)
        if got != expected:
            if errors < 10:
                print(f"FAIL: sample {idx} base={b} bend={bend} rng={rng} "
                      f"mod={mod} no={int(note_on)} got={got:08x} exp={exp}")
            errors += 1

    print(f"{len(rows)} vectors, {errors} mismatches")
    if errors:
        print("RESULT: FAIL (RTL semantics differ from golden model)")
        return 1
    print("PASS: RTL semantics match the golden model on every vector")
    return 0


if __name__ == "__main__":
    sys.exit(main())
