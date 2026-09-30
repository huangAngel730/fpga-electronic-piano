#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T009 ADSR 包络跳变量验收测试

验收指标：
1. Release后极轻力度重触发：保持当前电平作为起点，平滑过渡
2. 每采样最大跳变量：≤138 Q15 LSB（Attack/重触发过渡）
3. RTL与模型容差：±2 Q15 LSB（本测试不涉及RTL，只验证模型）

测试覆盖：
- 高电平Release + 极轻力度重触发（下降过渡）
- 低电平Release + 高力度重触发（上升过渡）
- Attack阶段最大跳变
- Release阶段最大跳变
- 满力度峰值精确性
- Release归零精确性
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from adsr_piano import PianoADSREnvelope, ATTACK_SAMPLES, RELEASE_SAMPLES

# 定案指标
MAX_TRANSITION_LSB = 138  # 每采样最大跳变量
MODEL_TOLERANCE_LSB = 2   # RTL与模型容差（本测试中用于精确性检查）

def test_release_retrigger_light_velocity():
    """测试1：高电平Release后极轻力度重触发（下降过渡）

    真正的下降场景：起点电平高于目标增益
    验证 M2 提到的 13063 → velocity=1(6553) 下降重触发
    """
    print("\n" + "=" * 70)
    print("测试1：高电平Release后极轻力度重触发（下降过渡）")
    print("=" * 70)

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 走完 Attack + Decay + 少量 Sustain，到达约 13000+ 电平
    for _ in range(240 + 4800 + 100):
        env.step()

    level_in_sustain = env.step()
    print(f"Sustain中电平: {level_in_sustain}")

    env.note_off()

    # Release 少量，保持较高电平
    for _ in range(10):
        env.step()

    level_before = env.step()
    print(f"Release高电平: {level_before}")

    # 极轻力度重触发（velocity=1 -> 目标 6553）
    from adsr_piano import velocity_to_gain
    target = velocity_to_gain(1)
    print(f"velocity=1 目标增益: {target}")

    # 断言：起点必须高于目标（真正的下降）
    assert level_before > target, f"测试前提错误：起点 {level_before} 应高于目标 {target}"
    print(f"✓ 确认下降场景：{level_before} > {target}")

    env.note_on(velocity=1)

    # 检查过渡期间的跳变量
    max_jump = 0
    prev_level = level_before
    transition_levels = []
    state_at_240 = None

    for i in range(ATTACK_SAMPLES + 1):
        level = env.step()
        transition_levels.append(level)
        jump = abs(level - prev_level)
        max_jump = max(max_jump, jump)
        prev_level = level

        if i == ATTACK_SAMPLES:
            state_at_240 = env.get_state()[0]

    print(f"过渡期间最大跳变: {max_jump} LSB")
    print(f"过渡起点: {level_before}")
    print(f"过渡终点: {transition_levels[ATTACK_SAMPLES - 1]}")
    print(f"第240采样后电平: {transition_levels[ATTACK_SAMPLES]}")
    print(f"第240采样后状态: {state_at_240}")

    # 验收标准
    success = True

    if max_jump <= MAX_TRANSITION_LSB:
        print(f"✓ PASS: 最大跳变 {max_jump} ≤ {MAX_TRANSITION_LSB} LSB")
    else:
        print(f"✗ FAIL: 最大跳变 {max_jump} > {MAX_TRANSITION_LSB} LSB")
        success = False

    # 检查第240采样后状态必须为DECAY
    if state_at_240 == 'DECAY':
        print(f"✓ PASS: 第240采样后状态为 DECAY")
    else:
        print(f"✗ FAIL: 第240采样后状态为 {state_at_240}，应为 DECAY")
        success = False

    return success


def test_release_retrigger_heavy_velocity():
    """测试2：低电平Release后高力度重触发（上升过渡）"""
    print("\n" + "=" * 70)
    print("测试2：低电平Release后高力度重触发（上升过渡）")
    print("=" * 70)

    env = PianoADSREnvelope()
    env.note_on(velocity=128)  # 中低力度

    # 走完 Attack + Decay + 部分 Sustain
    for _ in range(240 + 4800 + 500):
        env.step()

    env.note_off()

    # Release 大部分
    for _ in range(4000):
        env.step()

    level_before = env.step()
    print(f"Release末期电平: {level_before}")

    # 高力度重触发
    env.note_on(velocity=1023)

    # 检查过渡期间的跳变量
    max_jump = 0
    prev_level = level_before
    transition_levels = []

    for i in range(ATTACK_SAMPLES):
        level = env.step()
        transition_levels.append(level)
        jump = abs(level - prev_level)
        max_jump = max(max_jump, jump)
        prev_level = level

    print(f"过渡期间最大跳变: {max_jump} LSB")
    print(f"过渡起点: {level_before}")
    print(f"过渡终点: {transition_levels[-1]}")

    # 验收标准
    if max_jump <= MAX_TRANSITION_LSB:
        print(f"✓ PASS: 最大跳变 {max_jump} ≤ {MAX_TRANSITION_LSB} LSB")
        return True
    else:
        print(f"✗ FAIL: 最大跳变 {max_jump} > {MAX_TRANSITION_LSB} LSB")
        return False


def test_normal_attack_transition():
    """测试3：正常Attack阶段最大跳变"""
    print("\n" + "=" * 70)
    print("测试3：正常Attack阶段最大跳变")
    print("=" * 70)

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    max_jump = 0
    prev_level = 0

    for _ in range(ATTACK_SAMPLES):
        level = env.step()
        jump = abs(level - prev_level)
        max_jump = max(max_jump, jump)
        prev_level = level

    print(f"Attack期间最大跳变: {max_jump} LSB")

    # 验收标准
    if max_jump <= MAX_TRANSITION_LSB:
        print(f"✓ PASS: 最大跳变 {max_jump} ≤ {MAX_TRANSITION_LSB} LSB")
        return True
    else:
        print(f"✗ FAIL: 最大跳变 {max_jump} > {MAX_TRANSITION_LSB} LSB")
        return False


def test_release_transition():
    """测试4：Release阶段最大跳变"""
    print("\n" + "=" * 70)
    print("测试4：Release阶段最大跳变")
    print("=" * 70)

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 走完 Attack + Decay + 部分 Sustain
    for _ in range(240 + 4800 + 1000):
        env.step()

    level_before = env.step()
    env.note_off()

    # 检查Release第一个样本
    level_after = env.step()
    first_jump = abs(level_after - level_before)

    print(f"Note Off前电平: {level_before}")
    print(f"Release首样本: {level_after}")
    print(f"首次跳变: {first_jump} LSB")

    # 检查整个Release期间
    max_jump = first_jump
    prev_level = level_after

    for _ in range(RELEASE_SAMPLES - 1):
        level = env.step()
        if level == 0:
            break
        jump = abs(level - prev_level)
        max_jump = max(max_jump, jump)
        prev_level = level

    print(f"Release期间最大跳变: {max_jump} LSB")

    # 验收标准：Release斜率应小于Attack
    expected_max = (level_before / RELEASE_SAMPLES) + 1
    print(f"预期最大跳变: {expected_max:.1f} LSB")

    if max_jump <= expected_max + MODEL_TOLERANCE_LSB:
        print(f"✓ PASS: 最大跳变在预期范围内")
        return True
    else:
        print(f"✗ FAIL: 最大跳变超出预期")
        return False


def test_peak_accuracy():
    """测试5：满力度峰值精确性"""
    print("\n" + "=" * 70)
    print("测试5：满力度峰值精确性")
    print("=" * 70)

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 走完Attack
    peak_level = 0
    for _ in range(ATTACK_SAMPLES):
        level = env.step()
        peak_level = max(peak_level, level)

    # 第一个Decay样本应该是峰值
    first_decay = env.step()

    print(f"峰值电平: {peak_level}")
    print(f"期望峰值: 32767")

    # 验收标准：满力度峰值必须精确
    if peak_level == 32767:
        print(f"✓ PASS: 峰值精确")
        return True
    else:
        print(f"✗ FAIL: 峰值偏差 {32767 - peak_level} LSB")
        return False


def test_release_zero_accuracy():
    """测试6：Release归零精确性"""
    print("\n" + "=" * 70)
    print("测试6：Release归零精确性")
    print("=" * 70)

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 走完 Attack + Decay + 部分 Sustain
    for _ in range(240 + 4800 + 1000):
        env.step()

    env.note_off()

    # Release全程
    final_level = None
    for _ in range(RELEASE_SAMPLES + 100):
        level = env.step()
        if level == 0:
            final_level = 0
            break

    print(f"Release最终电平: {final_level}")

    # 验收标准：必须精确归零
    if final_level == 0:
        print(f"✓ PASS: 精确归零")
        return True
    else:
        print(f"✗ FAIL: 未归零，残余 {final_level} LSB")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("T009 ADSR 包络跳变量验收测试")
    print("=" * 70)
    print(f"最大跳变量指标: {MAX_TRANSITION_LSB} Q15 LSB")
    print(f"模型精确性容差: ±{MODEL_TOLERANCE_LSB} Q15 LSB")

    results = []

    results.append(("高电平Release+极轻力度重触发", test_release_retrigger_light_velocity()))
    results.append(("低电平Release+高力度重触发", test_release_retrigger_heavy_velocity()))
    results.append(("正常Attack跳变", test_normal_attack_transition()))
    results.append(("Release跳变", test_release_transition()))
    results.append(("满力度峰值精确性", test_peak_accuracy()))
    results.append(("Release归零精确性", test_release_zero_accuracy()))

    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)

    passed = 0
    failed = 0

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status:5s} - {name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n通过: {passed}/{len(results)}")
    print(f"失败: {failed}/{len(results)}")

    if failed == 0:
        print("\n✓ 所有测试通过")
        return 0
    else:
        print(f"\n✗ {failed} 项测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
