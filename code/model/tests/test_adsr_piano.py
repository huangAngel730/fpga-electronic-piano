#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T009 钢琴式ADSR包络边界测试

覆盖边界情况：
1. Velocity=0 的最小增益
2. Velocity=1023 的最大增益
3. Attack阶段立即Release
4. Decay阶段立即Release
5. Sustain长时间持续（验证自然衰减）
6. Release阶段重新Note On（重触发）
7. 连续快速Note On/Off（颤音）
8. 零样本输入的包络应用
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from adsr_piano import PianoADSREnvelope, apply_envelope, velocity_to_gain
from adsr_piano import ATTACK_SAMPLES, DECAY_SAMPLES, SUSTAIN_LEVEL, RELEASE_SAMPLES, ENVELOPE_MAX


def test_velocity_boundaries():
    """测试Velocity边界值"""
    print("测试1: Velocity边界值")

    # Velocity=0: 最小增益20%
    gain0 = velocity_to_gain(0)
    assert gain0 == 6553, f"Velocity=0增益错误: {gain0}"
    print(f"  Velocity=0: gain={gain0} (20%)")

    # Velocity=1023: 最大增益100%
    gain1023 = velocity_to_gain(1023)
    assert gain1023 == 32767, f"Velocity=1023增益错误: {gain1023}"
    print(f"  Velocity=1023: gain={gain1023} (100%)")

    # 验证单调性
    prev_gain = 0
    for v in range(0, 1024, 100):
        g = velocity_to_gain(v)
        assert g >= prev_gain, f"Velocity映射非单调: {v}"
        prev_gain = g

    print("  [PASS] Velocity边界正确")


def test_early_release():
    """测试Attack/Decay阶段提前Release"""
    print("\n测试2: Attack阶段提前Release")

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 在Attack中途（120样本，50%）Release
    for _ in range(120):
        env.step()

    level_before = env.step()
    env.note_off()
    level_after = env.step()

    # 验证平滑过渡
    assert abs(level_after - level_before) < 200, "Attack中途Release跳变过大"
    print(f"  Attack中途Release: {level_before} -> {level_after}, 差值={abs(level_after - level_before)}")

    # 验证能正常Release到0
    for _ in range(RELEASE_SAMPLES + 100):
        level = env.step()
    assert level == 0, "Release未完成"
    print("  [PASS] Attack中途Release正确")

    # 测试Decay阶段Release
    print("\n测试3: Decay阶段提前Release")
    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 完成Attack，进入Decay中途
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES // 2):
        env.step()

    level_before = env.step()
    env.note_off()
    level_after = env.step()

    assert abs(level_after - level_before) < 200, "Decay中途Release跳变过大"
    print(f"  Decay中途Release: {level_before} -> {level_after}")
    print("  [PASS] Decay中途Release正确")


def test_long_sustain():
    """测试长时间Sustain的自然衰减"""
    print("\n测试4: 长时间Sustain自然衰减")

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 完成Attack和Decay
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES):
        env.step()

    # 记录Sustain开始和多个时间点的电平
    sustain_start = env.step()
    samples_1s = []
    samples_2s = []

    for i in range(48000 * 2):  # 2秒
        level = env.step()
        if 47900 <= i < 48000:
            samples_1s.append(level)
        if 95900 <= i < 96000:
            samples_2s.append(level)

    avg_1s = sum(samples_1s) // len(samples_1s)
    avg_2s = sum(samples_2s) // len(samples_2s)

    # 验证衰减
    assert avg_2s < avg_1s * 0.95, "Sustain未自然衰减"
    decay_rate = (sustain_start - avg_2s) / sustain_start

    print(f"  Sustain开始: {sustain_start}")
    print(f"  1秒后平均: {avg_1s}")
    print(f"  2秒后平均: {avg_2s}")
    print(f"  总衰减率: {decay_rate:.1%}")
    print("  [PASS] Sustain自然衰减正确")


def test_retrigger():
    """测试Release阶段重新触发（修正版：保持当前电平）"""
    print("\n测试5: Release阶段重触发")

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 完整循环到Release中途
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 1000):
        env.step()
    env.note_off()

    for _ in range(RELEASE_SAMPLES // 2):
        env.step()

    # Release中途重新Note On（新规则：保持当前电平）
    level_before = env.step()
    env.note_on(velocity=512)  # 使用中等velocity
    level_after = env.step()

    # 应该保持当前电平，平滑过渡
    jump = abs(level_after - level_before)
    assert jump <= 138, f"重触发跳变过大: {jump} LSB"
    print(f"  Release中途电平: {level_before}")
    print(f"  重触发后电平: {level_after}, 跳变={jump} LSB")

    # 补充测试：Release更早阶段的重触发
    env2 = PianoADSREnvelope()
    env2.note_on(velocity=1023)
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 1000):
        env2.step()
    env2.note_off()

    # Release刚开始（约6530电平）
    for _ in range(2400):
        level = env2.step()

    level_before_early = level
    env2.note_on(velocity=768)
    level_after_early = env2.step()

    print(f"  Release早期电平: {level_before_early}")
    print(f"  重触发后电平: {level_after_early}")
    jump_early = abs(level_after_early - level_before_early)
    print(f"  电平跳变: {jump_early} LSB")

    # 验证跳变幅度满足 ≤138 LSB
    assert jump_early <= 138, f"Release早期重触发跳变过大: {jump_early} LSB"

    # 验证能达到新的velocity峰值
    for _ in range(ATTACK_SAMPLES + 100):
        level = env.step()

    expected_peak = velocity_to_gain(512)
    assert abs(level - expected_peak) < 500, "重触发峰值不正确"
    print(f"  重触发峰值: {level} (期望{expected_peak})")
    print("  [PASS] Release重触发正确")


def test_rapid_onoff():
    """测试快速Note On/Off（颤音）"""
    print("\n测试6: 快速连续Note On/Off")

    env = PianoADSREnvelope()

    # 模拟每10ms切换一次（快速颤音）
    levels = []
    for cycle in range(10):  # 10个周期
        env.note_on(velocity=768)
        for _ in range(240):  # 5ms
            levels.append(env.step())
        env.note_off()
        for _ in range(240):  # 5ms
            levels.append(env.step())

    # 验证无异常崩溃，电平在合理范围
    assert all(0 <= l <= 32767 for l in levels), "快速切换电平越界"
    print(f"  完成10个快速周期，电平范围: [{min(levels)}, {max(levels)}]")
    print("  [PASS] 快速切换无异常")


def test_envelope_application():
    """测试包络应用到波表样本"""
    print("\n测试7: 包络应用边界")

    # 最大样本 × 最大包络
    result = apply_envelope(32767, 32767)
    assert abs(result - 32767) <= 1, f"最大值计算错误: {result}"
    print(f"  32767 × 32767 = {result}")

    # 最小样本 × 最大包络
    result = apply_envelope(-32768, 32767)
    assert abs(result - (-32768)) <= 1, f"最小值计算错误: {result}"
    print(f"  -32768 × 32767 = {result}")

    # 任意样本 × 0包络
    result = apply_envelope(10000, 0)
    assert result == 0, "零包络应输出0"
    print(f"  10000 × 0 = {result}")

    # 任意样本 × 50%包络
    result = apply_envelope(16384, 16384)
    expected = 8192
    assert abs(result - expected) < 2, f"50%包络错误: {result}"
    print(f"  16384 × 16384 = {result} (期望≈{expected})")

    print("  [PASS] 包络应用正确")


def test_idle_state():
    """测试IDLE状态行为"""
    print("\n测试8: IDLE状态")

    env = PianoADSREnvelope()

    # 未触发时应保持IDLE和0电平
    for _ in range(100):
        level = env.step()
        assert level == 0, "IDLE状态电平非0"

    # IDLE时Note Off应无影响
    env.note_off()
    level = env.step()
    assert level == 0, "IDLE状态Note Off产生输出"

    print("  [PASS] IDLE状态正确")


if __name__ == "__main__":
    print("=" * 70)
    print("T009 钢琴式ADSR包络边界测试")
    print("=" * 70)

    test_velocity_boundaries()
    test_early_release()
    test_long_sustain()
    test_retrigger()
    test_rapid_onoff()
    test_envelope_application()
    test_idle_state()

    print("\n" + "=" * 70)
    print("[PASS] 全部边界测试通过")
    print("=" * 70)
