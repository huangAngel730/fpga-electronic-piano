#!/usr/bin/env python3
"""M1 Pitch / Mod FCW golden model (2026-10-02).

Bit-exact reference for code/rtl/audio/pitch_mod_fcw.sv. Standard library only
(no numpy/scipy); works on any Python 3.9+.

Contract
--------
Pitch : semi_q10 = (bend * range) >>> 1        Q10 semitone, floor
        ratio    = 2 ** (semi_q10 / 1024 / 12)
        fcw      = round(base_fcw * ratio), saturated to [0, FCW_MAX]
Mod   : LFO phase (32-bit) advances exactly once per sample call
        depth_q10 = (mod * DEPTH_MAX_Q10) >> 12
        vib_q10   = (lfo_sine_q15 * depth_q10) >>> 15
        total_q10 = semi_q10 + vib_q10
Exact : bend == 0 and mod == 0  ->  fcw == base_fcw  (bit exact)
        range == 0              ->  fcw == base_fcw  (bit exact)
        mod   == 0              ->  pure Pitch path (bit exact)

Fixed-point realisation (what the RTL does, stage by stage)
-----------------------------------------------------------
    q = total_q10 >>> 10                     # arithmetic / floor
    r = total_q10 &  0x3FF                   # non-negative remainder
    factor_q16 = (OCT[q + 25] * SUB[r]) >>> 16      # truncating
    fcw        = (base_fcw * factor_q16 + 32768) >>> 16   # round half up
    fcw        = min(FCW_MAX, max(0, fcw))           # Nyquist policy

No LUT entry is rounded twice: OCT/SUB are rounded once at generation, the
intermediate product truncates, and the only explicit rounding is the final
round-half-up. That keeps the model and the RTL identical by construction.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------- constants
SAMPLE_RATE_HZ = 48_000
SEMI_Q = 10                       # sub-semitone resolution: 1/1024 semitone
SEMI_ONE = 1 << SEMI_Q            # 1024
Q_MIN, Q_MAX = -25, 24            # reachable integer-semitone range
OCT_BIAS = -Q_MIN                 # 25
OCT_SIZE = Q_MAX - Q_MIN + 1      # 50
SUB_SIZE = SEMI_ONE               # 1024
Q16 = 1 << 16
FCW_MAX = 1 << 31                 # 24 kHz @ 48 kHz = DDS Nyquist, see policy

LFO_SIZE = 1024
LFO_AMP_Q15 = 32767
MASK32 = 0xFFFF_FFFF

# PROPOSALS (M1 owns the constants, not yet frozen by the user).
# State them as numbers so M2 can wire, but they are proposals, not user law.
# M2 V0143: 改为函数参数或显式传递，避免硬编码导致 RTL 参数改动后测试漂移
MOD_DEPTH_MAX_Q10 = 512           # +/- 50 cents at mod = 4095 (default)
MOD_LFO_HZ = 5.0                  # vibrato rate
LFO_INC = round(MOD_LFO_HZ * (1 << 32) / SAMPLE_RATE_HZ)
FCW_MAX = 1 << 31                 # M2 V0147: 恢复 2^31 (24 kHz @48k)


# ------------------------------------------------------------------- tables
def build_oct_lut() -> list[int]:
    """2 ** (q / 12) for integer semitone q in [Q_MIN, Q_MAX], Q16."""
    return [round((2.0 ** (q / 12.0)) * Q16) for q in range(Q_MIN, Q_MAX + 1)]


def build_sub_lut() -> list[int]:
    """2 ** ((r / 1024) / 12) for r in [0, 1023], Q16."""
    return [round((2.0 ** (r / (12.0 * SEMI_ONE))) * Q16) for r in range(SUB_SIZE)]


def build_lfo_lut() -> list[int]:
    """Sine vibrato table, amplitude +/-32767 (Q15), 1024 points."""
    return [round(LFO_AMP_Q15 * math.sin(2.0 * math.pi * i / LFO_SIZE))
            for i in range(LFO_SIZE)]


OCT_LUT = build_oct_lut()
SUB_LUT = build_sub_lut()
LFO_LUT = build_lfo_lut()


# ------------------------------------------------------- combinational math
def pitch_semi_q10(bend: int, rng: int) -> int:
    """Signed12 bend x 0..24 range -> Q10 semitone offset. Floor divide."""
    return (bend * rng) >> 1


def mod_depth_q10(mod: int, depth_max_q10: int = MOD_DEPTH_MAX_Q10) -> int:
    """Unsigned12 mod -> Q10 semitone peak depth.

    Round-half-up so mod == 4095 reaches the full multiplier exactly, while
    mod == 0 stays exactly 0 (the strict bypass the contract requires).
    M2 V0143: depth_max_q10 改为参数，匹配 RTL MOD_DEPTH_MAX_Q10 参数。
    """
    return (mod * depth_max_q10 + (1 << 11)) >> 12


def lfo_vib_q10(sine_q15: int, depth_q10: int) -> int:
    """Current vibrato offset in Q10 semitone for one LFO sample."""
    return (sine_q15 * depth_q10) >> 15


def factor_q16(total_q10: int) -> int:
    """Q10 semitone offset -> Q16 frequency ratio, two-LUT decomposition."""
    q = total_q10 >> SEMI_Q
    r = total_q10 & (SEMI_ONE - 1)
    idx = q + OCT_BIAS
    if not 0 <= idx < OCT_SIZE:
        raise ValueError(
            f"semitone index {idx} out of range (total_q10={total_q10}); "
            f"the design must clamp before this point"
        )
    return (OCT_LUT[idx] * SUB_LUT[r]) >> 16


def final_fcw(base_fcw: int, total_q10: int, fcw_max: int = FCW_MAX) -> int:
    """Apply ratio and the Nyquist saturation policy.  Returns 0..fcw_max.

    M2 V0143: fcw_max 改为参数，匹配 RTL FCW_MAX 参数。
    """
    f = factor_q16(total_q10)
    value = (base_fcw * f + (Q16 >> 1)) >> 16
    if value < 0:
        return 0
    if value > fcw_max:
        return fcw_max
    return value


def ideal_fcw_float(base_fcw: int, bend: int, rng: int, mod: int = 0,
                    sine_q15: int = 0) -> float:
    """Unquantised reference, for error accounting only (never for output)."""
    semis = (bend * rng) / 2048.0
    semis += (mod_depth_q10(mod) / SEMI_ONE) * (sine_q15 / 32767.0)
    return base_fcw * (2.0 ** (semis / 12.0))


def cents_error(measured_fcw: float, reference_fcw: float) -> float:
    """Pitch error in cents between two FCW values (or frequencies)."""
    if reference_fcw <= 0 or measured_fcw <= 0:
        return 0.0
    return 1200.0 * math.log2(measured_fcw / reference_fcw)


# ---------------------------------------------------------------- oscillator
class PitchModVoice:
    """One voice's Pitch + Mod control path.  One step() call == one sample.

    M2 V0143: NoteOn 只复位 lfo_phase 到 0（不推进），下次 sample 读 0 后推进。
    """

    def __init__(self, lfo_inc: int = LFO_INC,
                 depth_max_q10: int = MOD_DEPTH_MAX_Q10,
                 fcw_max: int = FCW_MAX) -> None:
        self.lfo_inc = lfo_inc
        self.depth_max_q10 = depth_max_q10
        self.fcw_max = fcw_max
        self.lfo_phase = 0

    def reset(self) -> None:
        self.lfo_phase = 0

    def step(self, base_fcw: int, bend: int, rng: int, mod: int,
             note_on: bool = False) -> int:
        """Advance one audio sample and return the FCW for the DDS.

        M2 V0143: NoteOn 时序修正。
        - note_on 不伴 sample：仅复位 lfo_phase 到 0
        - 下次 sample：读 lfo_phase（此时为 0），然后推进
        - 同拍 note_on + sample（本函数）：读 0，推进到 INC
        """
        # note_on 优先：先复位 phase 到 0
        if note_on:
            self.lfo_phase = 0

        # 本拍读 lfo_phase（note_on 同拍时为 0）
        sine = LFO_LUT[(self.lfo_phase >> 22) & (LFO_SIZE - 1)]
        vib = lfo_vib_q10(sine, mod_depth_q10(mod, self.depth_max_q10))
        total = pitch_semi_q10(bend, rng) + vib
        out = final_fcw(base_fcw, total, self.fcw_max)

        # 每次 sample 推进一次（note_on 同拍也推进）
        self.lfo_phase = (self.lfo_phase + self.lfo_inc) & MASK32

        return out


def fcw_from_frequency(hz: float) -> int:
    """Convenience: 48 kHz, 32-bit phase accumulator, rounded FCW."""
    return int(round(hz * (1 << 32) / SAMPLE_RATE_HZ))


def freq_from_fcw(fcw: int) -> float:
    return fcw * SAMPLE_RATE_HZ / (1 << 32)


if __name__ == "__main__":                       # tiny smoke run
    base = fcw_from_frequency(440.0)
    v = PitchModVoice()
    print(f"A4 base_fcw = {base}")
    print(f"bend=0 range=2 mod=0  -> {v.step(base, 0, 2, 0)} (exact={base})")
    print(f"bend=2047 range=2     -> {v.step(base, 2047, 2, 0)}")
    print(f"bend=-2048 range=2    -> {v.step(base, -2048, 2, 0)}")
