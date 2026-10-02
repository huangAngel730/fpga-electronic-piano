#!/usr/bin/env python3
"""Self-checking tests for the M1 Pitch/Mod golden model.

Every check is a real assertion; the script exits non-zero on any failure so CI
or M2 can gate on the return code. Standard library only.

Run:  python -X utf8 test_pitch_mod.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pitch_mod_model as m

FAILURES: list[str] = []
CHECKS = 0


def check(condition: bool, name: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(f"{name}: {detail}")
        print(f"FAIL: {name} {detail}")


def approx(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


# --------------------------------------------------------------- 1. LUT files
def test_mem_files_match_model() -> dict:
    """The .mem files the RTL reads must equal the model tables exactly."""
    base = Path(__file__).resolve().parent / "generated" / "pitch_mod"

    def read(path: Path, signed_bits: int = 0) -> list[int]:
        vals = [int(line, 16) for line in path.read_text().split()]
        if signed_bits:
            sign = 1 << (signed_bits - 1)
            vals = [v - (1 << signed_bits) if v & sign else v for v in vals]
        return vals

    oct_mem = read(base / "oct_ratio_q16.mem")
    sub_mem = read(base / "sub_ratio_q16.mem")
    lfo_mem = read(base / "lfo_sine_q15.mem", signed_bits=16)

    check(oct_mem == m.OCT_LUT, "mem_oct", "oct .mem differs from model")
    check(sub_mem == m.SUB_LUT, "mem_sub", "sub .mem differs from model")
    check(lfo_mem == m.LFO_LUT, "mem_lfo", "lfo .mem differs from model")
    check(len(oct_mem) == m.OCT_SIZE, "oct_len", str(len(oct_mem)))
    check(len(sub_mem) == 1024, "sub_len", str(len(sub_mem)))
    check(len(lfo_mem) == 1024, "lfo_len", str(len(lfo_mem)))

    return {"oct": oct_mem, "sub": sub_mem, "lfo": lfo_mem}


# ------------------------------------------------- 2. exact-bypass invariants
def test_exact_bypass() -> dict:
    """Centre bend / mod 0 / range 0 must be bit-exact identity."""
    worst_mismatch = 0
    for note in range(0, 128):
        hz = 440.0 * 2.0 ** ((note - 69) / 12.0)
        base = m.fcw_from_frequency(hz)
        v = m.PitchModVoice()
        # (a) bend 0, range default 2, mod 0
        got = v.step(base, 0, 2, 0)
        worst_mismatch = max(worst_mismatch, abs(got - base))
        # (b) range 0 must remove all bend influence, any bend value
        for bend in (-2048, -1000, 0, 1, 1000, 2047):
            v2 = m.PitchModVoice()
            got2 = v2.step(base, bend, 0, 0)
            worst_mismatch = max(worst_mismatch, abs(got2 - base))
        # (c) mod 0 must remove all vibrato influence
        for rng in (0, 1, 2, 12, 24):
            v3 = m.PitchModVoice()
            got3 = v3.step(base, 0, rng, 0)
            worst_mismatch = max(worst_mismatch, abs(got3 - base))

    check(worst_mismatch == 0, "exact_bypass",
          f"centre/zero paths drifted by {worst_mismatch} LSB")
    return {"exact_bypass_max_lsb": worst_mismatch}


# --------------------------------------------------------- 3. pitch extremes
def test_pitch_extremes() -> dict:
    """+/- full bend at default range must be +/- 2 semitones, within budget."""
    base = m.fcw_from_frequency(440.0)
    v_hi = m.PitchModVoice().step(base, 2047, 2, 0)
    v_lo = m.PitchModVoice().step(base, -2048, 2, 0)
    hi_cents = m.cents_error(m.freq_from_fcw(v_hi), 440.0 * 2.0 ** (2 / 12))
    lo_cents = m.cents_error(m.freq_from_fcw(v_lo), 440.0 * 2.0 ** (-2 / 12))
    # 2047 is not 2048: expect ~ -0.85 cents on the positive end, 0 on neg.
    check(abs(hi_cents) < 1.0, "pitch_hi_2semi", f"{hi_cents:.3f} cents")
    check(abs(lo_cents) < 1.0, "pitch_lo_2semi", f"{lo_cents:.3f} cents")

    # full 24-semitone range: +/- 2 octaves
    v_hi24 = m.PitchModVoice().step(base, 2047, 24, 0)
    v_lo24 = m.PitchModVoice().step(base, -2048, 24, 0)
    hi24 = m.cents_error(m.freq_from_fcw(v_hi24), 440.0 * 4.0)
    lo24 = m.cents_error(m.freq_from_fcw(v_lo24), 440.0 / 4.0)
    check(abs(hi24) < 2.0, "pitch_hi_24semi", f"{hi24:.3f} cents")
    check(abs(lo24) < 2.0, "pitch_lo_24semi", f"{lo24:.3f} cents")
    return {"hi_2semi_cents": hi_cents, "lo_2semi_cents": lo_cents,
            "hi_24semi_cents": hi24, "lo_24semi_cents": lo24}


# ---------------------------------------------------- 4. monotonic + error
def test_monotonic_and_error_budget() -> dict:
    """Monotone in bend, and worst-case error over the whole legal grid."""
    worst = 0.0
    worst_where = None
    non_monotone = 0
    for note in (21, 48, 60, 72, 96, 108):
        base = m.fcw_from_frequency(440.0 * 2.0 ** ((note - 69) / 12.0))
        for rng in (0, 1, 2, 7, 12, 24):
            prev = -1
            for bend in range(-2048, 2048, 1):
                v = m.PitchModVoice().step(base, bend, rng, 0)
                if v < prev:
                    non_monotone += 1
                prev = v
                ideal = m.ideal_fcw_float(base, bend, rng)
                # cents is a ratio: compare FCW to FCW, not Hz to FCW.
                err = abs(m.cents_error(float(v), ideal))
                if err > worst:
                    worst = err
                    worst_where = (note, rng, bend)
    check(non_monotone == 0, "pitch_monotone", f"{non_monotone} inversions")
    # Floor of the Q10 semitone offset costs up to one quantum (1/1024 semi =
    # 0.098 cents) plus a little LUT truncation. Budget 0.2 cents: still ~50x
    # below the ~5-10 cent audible threshold the interface spec cites (V0006).
    check(worst < 0.20, "pitch_error_budget", f"{worst:.5f} cents")
    return {"worst_pitch_error_cents": worst, "worst_at": worst_where,
            "monotone_inversions": non_monotone}


# ------------------------------------------------------------- 5. LFO / mod
def test_lfo() -> dict:
    """Vibrato period, peak depth, one-advance-per-sample, depth 0 bypass."""
    base = m.fcw_from_frequency(440.0)
    v = m.PitchModVoice()
    n = m.SAMPLE_RATE_HZ // 2                     # 0.5 s, ~2.5 periods @5 Hz
    peaks = []
    for i in range(n):
        f = v.step(base, 0, 2, 4095)
        if i > m.SAMPLE_RATE_HZ // m.MOD_LFO_HZ:
            peaks.append(f)
    hi = max(peaks)
    lo = min(peaks)
    peak_cents = m.cents_error(m.freq_from_fcw(hi), 440.0)
    check(approx(peak_cents, 50.0, 0.5), "mod_depth_50cents",
          f"{peak_cents:.3f} cents at mod=4095")

    # period: count sample steps between rising mid-crossings
    crossings = []
    prev = None
    v2 = m.PitchModVoice()
    for i in range(m.SAMPLE_RATE_HZ):
        f = v2.step(base, 0, 2, 4095)
        if prev is not None and prev < base <= f:
            crossings.append(i)
        prev = f
    period = (crossings[1] - crossings[0]) if len(crossings) > 1 else 0
    expect = m.SAMPLE_RATE_HZ / m.MOD_LFO_HZ
    check(abs(period - expect) <= 2, "mod_period",
          f"{period} samples, expected {expect:.1f}")

    # one LFO advance per sample is enforced by construction; verify phase rate
    v3 = m.PitchModVoice()
    v3.step(base, 0, 2, 0)
    check(v3.lfo_phase == m.LFO_INC, "mod_one_advance_per_sample",
          f"phase={v3.lfo_phase}, expected {m.LFO_INC}")

    # depth 0 must be a strict bypass even with a large mod value
    v4 = m.PitchModVoice()
    got = v4.step(base, 0, 2, 0)
    check(got == base, "mod_zero_bypass", f"{got} != {base}")

    # full-peak amplitude must match the proposed depth exactly
    check(m.mod_depth_q10(4095) == m.MOD_DEPTH_MAX_Q10, "mod_depth_q10_full",
          str(m.mod_depth_q10(4095)))
    return {"mod_peak_cents": peak_cents, "mod_period_samples": period,
            "lfo_inc": m.LFO_INC}


# --------------------------------------------------- 6. combined + boundary
def test_combined_and_boundary() -> dict:
    """Pitch+Mod add; FCW stays inside [0, FCW_MAX]; no NaN on extreme notes."""
    base_hi = m.fcw_from_frequency(4186.0)         # C8
    v = m.PitchModVoice()
    max_seen = 0
    for i in range(m.SAMPLE_RATE_HZ // 2):
        f = v.step(base_hi, 2047, 24, 4095)
        max_seen = max(max_seen, f)
    check(max_seen <= m.FCW_MAX, "boundary_nyquist",
          f"fcw {max_seen} exceeded {m.FCW_MAX}")
    # saturated, not wrapped: never negative
    check(max_seen > 0, "boundary_positive", str(max_seen))

    # combined pitch + mod at a mid note: bounded and finite
    base = m.fcw_from_frequency(440.0)
    v2 = m.PitchModVoice()
    worst = 0.0
    for i in range(m.SAMPLE_RATE_HZ):
        f = v2.step(base, 2047, 2, 4095)
        worst = max(worst, abs(m.cents_error(m.freq_from_fcw(f),
                                             440.0 * 2.0 ** (2 / 12))))
    # +2 semi for pitch plus up to +0.5 semi vibrato = 2.5 semi peak
    check(worst < 55.0, "combined_bounded", f"{worst:.2f} cents")
    return {"boundary_max_fcw": max_seen, "combined_worst_cents": worst}


# --------------------------------------------------- 7. note_on / retrigger
def test_note_on_retrigger() -> dict:
    """note_on restarts the LFO, so a new note starts at exact base pitch."""
    base = m.fcw_from_frequency(440.0)
    v = m.PitchModVoice()
    for _ in range(100):                            # let the LFO wander off 0
        v.step(base, 0, 2, 4095)
    first = v.step(base, 0, 2, 4095, note_on=True)
    check(first == base, "note_on_exact_start",
          f"{first} != {base}, LFO not zeroed at note start")
    # without note_on the same call would NOT be exact (proves the flag works)
    v2 = m.PitchModVoice()
    for _ in range(100):
        v2.step(base, 0, 2, 4095)
    not_restarted = v2.step(base, 0, 2, 4095)
    check(not_restarted != base, "note_on_flag_effective",
          "LFO was zero anyway; test cannot distinguish")
    # same-tick note_on + step must advance the LFO exactly once
    v3 = m.PitchModVoice()
    v3.step(base, 0, 2, 4095, note_on=True)
    check(v3.lfo_phase == m.LFO_INC, "note_on_single_advance",
          str(v3.lfo_phase))
    return {"note_on_first_fcw": first, "restarted_equals_base": first == base}


# ---------------------------------------------------------------- 8. ranges
def test_range_values() -> dict:
    """Every legal range 0..24 gives the documented interval."""
    base = m.fcw_from_frequency(440.0)
    worst = 0.0
    for rng in range(0, 25):
        for bend in (-2048, 2047):
            got = m.PitchModVoice().step(base, bend, rng, 0)
            ideal = 440.0 * 2.0 ** ((bend * rng / 2048.0) / 12.0)
            worst = max(worst, abs(m.cents_error(m.freq_from_fcw(got), ideal)))
    # 24 semitones spans 4x frequency, so Q10 semitone quantisation dominates;
    # 0.1 cent is still two orders below the ~5 cent audible threshold.
    check(worst < 0.10, "range_all_values", f"{worst:.5f} cents")
    return {"range_worst_cents": worst}


def main() -> int:
    print("M1 Pitch/Mod golden-model self-check")
    print(f"  sample_rate={m.SAMPLE_RATE_HZ} LFO={m.MOD_LFO_HZ}Hz "
          f"depth_max={m.MOD_DEPTH_MAX_Q10} (Q10)")
    report: dict = {
        "model": "pitch_mod_model.py",
        "sample_rate_hz": m.SAMPLE_RATE_HZ,
        "mod_depth_max_q10": m.MOD_DEPTH_MAX_Q10,
        "mod_lfo_hz": m.MOD_LFO_HZ,
        "lfo_inc": m.LFO_INC,
    }
    test_mem_files_match_model()
    report["exact_bypass"] = test_exact_bypass()
    report["pitch_extremes"] = test_pitch_extremes()
    report["monotonic"] = test_monotonic_and_error_budget()
    report["lfo"] = test_lfo()
    report["combined"] = test_combined_and_boundary()
    report["note_on"] = test_note_on_retrigger()
    report["range"] = test_range_values()

    out = Path(__file__).resolve().parent / "generated" / "pitch_mod"
    out.mkdir(parents=True, exist_ok=True)
    (out / "model_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n{CHECKS} checks, {len(FAILURES)} failures")
    if FAILURES:
        for f in FAILURES:
            print(f"  FAIL {f}")
        print("RESULT: FAIL")
        return 1
    print("PASS: test_pitch_mod")
    return 0


if __name__ == "__main__":
    sys.exit(main())
