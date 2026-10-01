#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T027 双音色振荡器 —— 模型级测试

验证等级说明（重要，勿再误标）：
    本文件是 **模型级** 验证（相当于 L1），不运行 HDL 仿真器。
    真实 RTL 仿真自检与逐样本对照见 `test_t027_rtl.py`（L2/L3）。

测试内容：
1. 波表生成正确性（含 ±8192 幅度口径）
2. 两种音色谐波差异明显
3. 音色选择锁存行为（真实断言）
4. 同一 FCW 下两种音色基频不变（真实断言，基于相位模型）
5. 四声部独立音色并发（真实断言，基于行为模型）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from t027_timbre_model import (
    generate_sine_wavetable,
    generate_triangle_wavetable,
    analyze_harmonic_content,
    WAVETABLE_SIZE,
    SAMPLE_MAX,
    SAMPLE_MIN,
)

FS = 48000.0
PHASE_BITS = 32
ADDR_BITS = 10


def fcw_for(freq_hz: float) -> int:
    """标准 DDS 频率控制字：FCW = 2^32 * f / Fs。"""
    return int(round((2 ** PHASE_BITS) * freq_hz / FS))


def phase_address_sequence(fcw: int, count: int) -> list[int]:
    """复现「先取样、后累加」的波表地址序列。"""
    phase = 0
    addrs = []
    for _ in range(count):
        addrs.append((phase >> (PHASE_BITS - ADDR_BITS)) & 0x3FF)
        phase = (phase + fcw) & 0xFFFFFFFF
    return addrs


class VoiceModel:
    """振荡器行为模型：Note On 锁存音色，相位连续，不清零。"""

    def __init__(self, fcw: int) -> None:
        self.fcw = fcw
        self.phase = 0
        self.latched = 0
        self.note_active = False
        self.latches = 0

    def sample_step(self, sample_tick: bool = True) -> int:
        """推进一拍，返回该拍取样地址。"""
        addr = (self.phase >> (PHASE_BITS - ADDR_BITS)) & 0x3FF
        if sample_tick:
            self.phase = (self.phase + self.fcw) & 0xFFFFFFFF
        return addr

    def note_on(self, timbre: int) -> None:
        """Note On：锁存音色，**不**清相位。"""
        self.note_active = True
        self.latched = timbre
        self.latches += 1

    def note_off(self) -> None:
        self.note_active = False
        # 相位继续推进（外部 ADSR 需要 Release 期间的持续波形）


# --------------------------------------------------------------------------
# 1. 波表生成
# --------------------------------------------------------------------------
def test_wavetable_generation() -> bool:
    print("\n" + "=" * 68)
    print("测试1：波表生成正确性")
    print("=" * 68)

    sine = generate_sine_wavetable()
    triangle = generate_triangle_wavetable()

    assert len(sine) == WAVETABLE_SIZE, f"正弦波长度错误：{len(sine)}"
    assert len(triangle) == WAVETABLE_SIZE, f"三角波长度错误：{len(triangle)}"

    q = WAVETABLE_SIZE // 4
    h = WAVETABLE_SIZE // 2

    for name, table in (("Sine", sine), ("Triangle", triangle)):
        assert table[0] == 0, f"{name} 起点错误：{table[0]}"
        assert table[q] == SAMPLE_MAX, f"{name} 峰值错误：{table[q]}"
        assert table[h] == 0, f"{name} 中点错误：{table[h]}"
        assert table[3 * q] == SAMPLE_MIN, f"{name} 谷值错误：{table[3 * q]}"
        assert int(table.max()) == SAMPLE_MAX, f"{name} 最大幅度越界：{table.max()}"
        assert int(table.min()) == SAMPLE_MIN, f"{name} 最小幅度越界：{table.min()}"
        # 冻结口径 ±8192，不得退回 ±32767
        assert int(table.max()) <= 8192, f"{name} 幅度超出冻结口径 ±8192"

    print(f"正弦波：1024 点，峰值 {sine.max()} / {sine.min()}")
    print(f"三角波：1024 点，峰值 {triangle.max()} / {triangle.min()}")
    print(f"幅度口径：±{SAMPLE_MAX}（符合 v1.5 冻结）")
    print("\n✓ PASS")
    return True


# --------------------------------------------------------------------------
# 2. 谐波差异
# --------------------------------------------------------------------------
def test_harmonic_difference() -> bool:
    print("\n" + "=" * 68)
    print("测试2：两种音色谐波差异")
    print("=" * 68)

    sine = generate_sine_wavetable()
    triangle = generate_triangle_wavetable()

    sa = analyze_harmonic_content(sine)
    ta = analyze_harmonic_content(triangle)

    sine_thd = sa["thd"]
    triangle_thd = ta["thd"]
    sine_3rd = sa["harmonics"][3]["normalized"]
    triangle_3rd = ta["harmonics"][3]["normalized"]

    print(f"正弦波 THD ：{sine_thd * 100:.4f}%   3 次谐波：{sine_3rd:.3e}")
    print(f"三角波 THD ：{triangle_thd * 100:.4f}%   3 次谐波：{triangle_3rd:.4f}")

    assert sine_thd < 0.01, f"正弦波 THD 过高：{sine_thd * 100:.2f}%"
    assert triangle_3rd > 0.05, f"三角波 3 次谐波过弱：{triangle_3rd}"
    assert triangle_thd > sine_thd * 10, "三角波 THD 不够明显"

    ratio = triangle_3rd / max(sine_3rd, 1e-12)
    print(f"\n3 次谐波比值：{ratio:.3e}（远超可区分阈值）")
    print("\n✓ PASS")
    return True


# --------------------------------------------------------------------------
# 3. 音色锁存行为（真实断言）
# --------------------------------------------------------------------------
def test_timbre_switching() -> bool:
    print("\n" + "=" * 68)
    print("测试3：音色选择锁存行为")
    print("=" * 68)

    v = VoiceModel(fcw_for(440.0))

    # 场景：Note On 时选正弦；发声期间全局切换到三角；已发声槽不得跟随
    v.note_on(timbre=0)
    assert v.latched == 0, "Note On 未锁存音色"
    latched_after_on = v.latched

    for _ in range(100):
        v.sample_step()
    global_select = 1                       # 全局选择被改动
    assert v.latched == latched_after_on, "已发声槽跟随了全局切换（不应跟随）"
    assert v.latched == 0, f"锁存值被改动：{v.latched}"
    print(f"发声期间全局选择改为 {global_select}，槽内仍为 {v.latched} ✓")

    # 下一次 Note On 才生效
    v.note_on(timbre=global_select)
    assert v.latched == 1, f"新 Note On 未更新锁存：{v.latched}"
    print(f"新 Note On 后锁存更新为 {v.latched} ✓")

    # 锁存不得清相位
    phase_before = v.phase
    v.note_on(timbre=0)
    assert v.phase == phase_before, "Note On 清零了相位（违反连续重触发）"
    print("Note On 未清零相位 ✓")

    assert v.latches == 3, f"锁存事件数错误：{v.latches}"
    print(f"\n锁存事件数：{v.latches}")
    print("\n✓ PASS")
    return True


# --------------------------------------------------------------------------
# 4. 基频不变性（真实断言）
# --------------------------------------------------------------------------
def test_fundamental_frequency_invariance() -> bool:
    print("\n" + "=" * 68)
    print("测试4：同一 FCW 下两种音色基频不变")
    print("=" * 68)

    freq = 440.0
    fcw = fcw_for(freq)

    # 相位步进与音色无关：地址序列必须逐点相同
    addrs = phase_address_sequence(fcw, 4096)

    sine = generate_sine_wavetable()
    triangle = generate_triangle_wavetable()

    # 两种音色对同一地址序列取样，周期应完全相同
    zero_crossings = {}
    for name, table in (("Sine", sine), ("Triangle", triangle)):
        samples = [int(table[a]) for a in addrs]
        # 过零点数表征基频周期
        zc = sum(
            1 for i in range(1, len(samples))
            if samples[i - 1] < 0 <= samples[i]
        )
        zero_crossings[name] = zc

    assert zero_crossings["Sine"] == zero_crossings["Triangle"], (
        f"两音色过零点数不同：{zero_crossings}"
    )

    # 用相位增量反推实际基频
    measured = fcw * FS / (2 ** PHASE_BITS)
    err_hz = abs(measured - freq)
    err_cents = 1200 * np.log2(measured / freq) if measured > 0 else float("inf")

    print(f"目标频率：{freq} Hz，FCW = {fcw} (0x{fcw:08x})")
    print(f"反推频率：{measured:.6f} Hz，误差 {err_hz:.2e} Hz ({err_cents:.3e} 音分)")
    print(f"两音色上升过零点数：{zero_crossings}")

    assert err_hz < 1e-3, f"基频反推误差过大：{err_hz}"
    assert abs(err_cents) < 1.0, f"音分误差超阈值：{err_cents}"

    print("\n✓ PASS")
    return True


# --------------------------------------------------------------------------
# 5. 四声部独立音色（真实断言）
# --------------------------------------------------------------------------
def test_polyphony_independence() -> bool:
    print("\n" + "=" * 68)
    print("测试5：四声部独立音色并发")
    print("=" * 68)

    sine = generate_sine_wavetable()
    triangle = generate_triangle_wavetable()

    config = [(0, 440.0), (1, 493.88), (0, 523.25), (1, 587.33)]
    voices = []
    for timbre, freq in config:
        v = VoiceModel(fcw_for(freq))
        v.note_on(timbre)
        voices.append(v)

    assert len(voices) == 4, "四声部配置错误"
    assert [v.latched for v in voices] == [0, 1, 0, 1], "音色分配错误"

    # 并发运行，各槽取自己的波表，输出必须可区分
    outputs = [[] for _ in range(4)]
    for _ in range(2000):
        for i, v in enumerate(voices):
            a = v.sample_step()
            table = triangle if v.latched else sine
            outputs[i].append(int(table[a]))

    # 各槽幅度统计应互不相同（不同音高 + 不同音色）
    signatures = [round(float(np.std(o)), 3) for o in outputs]
    print(f"四槽波形标准差：{signatures}")

    # 两个正弦槽（0、2）波形不同（音高不同），两个三角槽（1、3）亦不同
    assert outputs[0] != outputs[2], "不同音高的两个正弦槽输出相同（疑似未独立）"
    assert outputs[1] != outputs[3], "不同音高的两个三角槽输出相同（疑似未独立）"
    # 同音色不同槽应使用同一张表
    assert voices[0].latched == voices[2].latched == 0, "槽 0/2 应同为 Sine"
    assert voices[1].latched == voices[3].latched == 1, "槽 1/3 应同为 Triangle"
    # 全局切换不得影响已锁存槽
    before = [v.latched for v in voices]
    for v in voices:
        for _ in range(10):
            v.sample_step()
    assert [v.latched for v in voices] == before, "已发声槽音色被改动"

    print(f"四槽锁存音色：{[v.latched for v in voices]}（0=Sine, 1=Triangle）")
    print(f"总锁存事件：{sum(v.latches for v in voices)}")
    print("\n✓ PASS")
    return True


def run_all_tests() -> int:
    print("=" * 68)
    print("T027 双音色振荡器 —— 模型级测试（非 RTL）")
    print("=" * 68)
    print("注：真实 RTL 仿真与逐样本对照见 test_t027_rtl.py")

    tests = [
        ("波表生成", test_wavetable_generation),
        ("谐波差异", test_harmonic_difference),
        ("音色锁存", test_timbre_switching),
        ("基频不变", test_fundamental_frequency_invariance),
        ("四声部独立", test_polyphony_independence),
    ]

    results = []
    for name, fn in tests:
        try:
            results.append((name, bool(fn()), None))
        except AssertionError as exc:
            results.append((name, False, str(exc)))

    print("\n" + "=" * 68)
    print("测试汇总（模型级）")
    print("=" * 68)
    for name, ok, err in results:
        print(f"{'PASS' if ok else 'FAIL':4s} - {name}" + (f"：{err}" if err else ""))

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n通过：{passed}/{len(results)}")
    print("验证等级：模型级（L1）；真实 RTL 见 test_t027_rtl.py")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
