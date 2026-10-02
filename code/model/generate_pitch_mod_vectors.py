#!/usr/bin/env python3
"""补充真正饱和场景的向量生成器（M2 V0143 修正版，2026-10-02）.

修正内容：
  - 补充 MIDI127 + bend±2047/2048 + range24 的真实饱和场景
  - 补充人工 base_fcw 超大值场景
  - 原 62273 条向量保持，追加饱和场景

M2 证据显示 C8 最大组合不会饱和（1541004284 < FCW_MAX），需要 MIDI127。
"""

from __future__ import annotations

from pathlib import Path

import pitch_mod_model as m

# (label, base_fcw, [(bend, range, mod, note_on), ...])
BASE_A4 = m.fcw_from_frequency(440.0)
BASE_A0 = m.fcw_from_frequency(27.5)
BASE_C8 = m.fcw_from_frequency(4186.0)

# M2 V0143: MIDI127 真实饱和
# MIDI 127 = 12543.854 Hz (A9)
BASE_MIDI127 = m.fcw_from_frequency(440.0 * 2 ** ((127 - 69) / 12.0))


def sweep(bend: int, rng: int, mod: int, n: int, note_on_first: bool) -> list:
    return [(bend, rng, mod, note_on_first and i == 0) for i in range(n)]


def build_cases() -> list[tuple[str, int, list[tuple[int, int, int, bool]]]]:
    cases = []
    # 1. exact bypass, every note, centre bend and mod 0
    for note in range(0, 128):
        hz = 440.0 * 2.0 ** ((note - 69) / 12.0)
        cases.append((f"bypass_n{note}", m.fcw_from_frequency(hz),
                      [(0, 2, 0, True), (0, 0, 0, False), (0, 2, 0, False),
                       (500, 0, 0, False), (-2048, 0, 0, False)]))
    # 2. full bend sweep at default range, plus extremes at range 24
    cases.append(("bend_sweep_2", BASE_A4, sweep_step(-2048, 2048, 2, 0)))
    cases.append(("bend_sweep_24", BASE_A4, sweep_step(-2048, 2048, 24, 0)))
    # 3. vibrato: full depth for two LFO periods
    cases.append(("vibrato_full", BASE_A4, sweep(0, 2, 4095, 19200, True)))
    cases.append(("vibrato_half", BASE_A4, sweep(0, 2, 2048, 9600, True)))
    # 4. pitch + mod combined, at the top of the range
    cases.append(("combined_hi", BASE_A4, sweep(2047, 24, 4095, 9600, True)))
    cases.append(("combined_lo", BASE_A4, sweep(-2048, 24, 4095, 9600, True)))
    # 5. every range value 0..24 at both bend extremes
    for rng in range(0, 25):
        cases.append((f"range{rng}", BASE_A4,
                      [(2047, rng, 0, True), (-2048, rng, 0, False)]))
    # 6. Nyquist / boundary: highest note driven to the top of the range
    cases.append(("nyquist_c8", BASE_C8, sweep(2047, 24, 4095, 4800, True)))
    cases.append(("low_a0", BASE_A0, sweep(2047, 24, 0, 240, True)))
    # 7. note_on restart mid-vibrato must return to exact base pitch
    seq = sweep(0, 2, 4095, 300, True)
    seq += [(0, 2, 4095, True)]           # retrigger
    seq += sweep(0, 2, 4095, 50, False)
    cases.append(("retrigger", BASE_A4, seq))

    # M2 V0143: 补充真正饱和场景
    # MIDI127 + bend+2047 + range24 -> 饱和到 FCW_MAX
    cases.append(("saturation_midi127_pos", BASE_MIDI127,
                  [(2047, 24, 0, True), (2047, 24, 4095, False)]))
    # MIDI127 + bend-2048 + range24 + 最大 mod -> 验证负向不回绕
    cases.append(("saturation_midi127_neg", BASE_MIDI127,
                  [(-2048, 24, 0, True), (-2048, 24, 4095, False)]))
    # 人工超大 base_fcw（模拟错误配置），验证饱和不回绕
    cases.append(("saturation_artificial_base", 0x70000000,
                  [(0, 2, 0, True), (2047, 24, 0, False)]))

    return cases


def sweep_step(start: int, stop: int, rng: int, mod: int) -> list:
    return [(bend, rng, mod, bend == start) for bend in range(start, stop)]


def main() -> None:
    out = Path(__file__).resolve().parent / "generated" / "pitch_mod"
    out.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    total = 0
    for label, base, seq in build_cases():
        voice = m.PitchModVoice()
        for bend, rng, mod, note_on in seq:
            fcw = voice.step(base, bend, rng, mod, note_on)
            lines.append(f"{base:08x} {bend & 0xFFF:03x} {rng & 0x1F:02x} "
                         f"{mod & 0xFFF:03x} {1 if note_on else 0} {fcw:08x}")
            total += 1
    path = out / "pitch_mod_vectors.txt"
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"PASS: wrote {total} vectors ({len(build_cases())} cases, "
          f"including M2 V0143 saturation scenarios) -> {path}")


if __name__ == "__main__":
    main()
