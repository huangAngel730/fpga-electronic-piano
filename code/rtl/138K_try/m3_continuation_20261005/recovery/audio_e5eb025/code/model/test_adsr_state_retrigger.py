#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T009 各状态重触发的 Python 模型连续性测试

本文件只执行 PianoADSREnvelope，不执行或对照真实 RTL。
真实 RTL 验证入口：run_t009_adsr_sim.ps1 和 check_t009_zip_retrigger.py。
验证模型 "任何状态保留当前电平" 后的连续性：
- Attack 状态重触发
- Decay 状态重触发
- Sustain 状态重触发
- Release 状态重触发
- 各测试过渡窗口每样本跳变 ≤138 Q15 LSB
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from adsr_piano import PianoADSREnvelope, ATTACK_SAMPLES, DECAY_SAMPLES

# RTL 对照容差
MAX_ERROR_LSB = 2


def simulate_rtl_envelope(events):
    """生成 Python 模型采样序列（不是 RTL 仿真）

    Args:
        events: [(sample_index, event_type, velocity), ...]
                event_type: 'note_on' or 'note_off'

    Returns:
        list of (sample_index, level)
    """
    env = PianoADSREnvelope()
    results = []
    event_idx = 0
    sample_count = events[-1][0] + 500 if events else 1000

    for sample in range(sample_count):
        # 处理事件
        while event_idx < len(events) and events[event_idx][0] == sample:
            event_type = events[event_idx][1]
            if event_type == 'note_on':
                velocity = events[event_idx][2]
                env.note_on(velocity)
            elif event_type == 'note_off':
                env.note_off()
            event_idx += 1

        # 采样
        level = env.step()
        results.append((sample, level))

    return results


def test_attack_retrigger():
    """测试 Attack 状态重触发"""
    print("\n" + "=" * 70)
    print("测试1：Attack 状态重触发逐样本对照")
    print("=" * 70)

    events = [
        (0, 'note_on', 1023),
        (120, 'note_on', 768),  # Attack 中途重触发
    ]

    results = simulate_rtl_envelope(events)

    # 检查重触发点前后的样本
    retrigger_idx = 120
    level_before = results[retrigger_idx - 1][1]
    level_after = results[retrigger_idx][1]

    print(f"重触发前（样本{retrigger_idx-1}）: {level_before}")
    print(f"重触发后（样本{retrigger_idx}）: {level_after}")

    jump = abs(level_after - level_before)
    print(f"首样本跳变: {jump} LSB")

    # 检查后续 240 个样本的连续性
    max_jump = 0
    for i in range(retrigger_idx, retrigger_idx + ATTACK_SAMPLES - 1):
        if i + 1 >= len(results):
            break
        curr = results[i][1]
        next_val = results[i + 1][1]
        jump = abs(next_val - curr)
        max_jump = max(max_jump, jump)

    print(f"过渡期最大跳变: {max_jump} LSB")

    # 验收标准
    if max_jump <= 138:
        print(f"✓ PASS: Attack 重触发连续性满足 ≤138 LSB")
        return True
    else:
        print(f"✗ FAIL: Attack 重触发跳变过大 {max_jump} LSB")
        return False


def test_decay_retrigger():
    """测试 Decay 状态重触发"""
    print("\n" + "=" * 70)
    print("测试2：Decay 状态重触发逐样本对照")
    print("=" * 70)

    events = [
        (0, 'note_on', 1023),
        (ATTACK_SAMPLES + 2400, 'note_on', 512),  # Decay 中途重触发
    ]

    results = simulate_rtl_envelope(events)

    retrigger_idx = ATTACK_SAMPLES + 2400
    level_before = results[retrigger_idx - 1][1]
    level_after = results[retrigger_idx][1]

    print(f"重触发前（样本{retrigger_idx-1}）: {level_before}")
    print(f"重触发后（样本{retrigger_idx}）: {level_after}")

    jump = abs(level_after - level_before)
    print(f"首样本跳变: {jump} LSB")

    # 检查过渡期连续性
    max_jump = 0
    for i in range(retrigger_idx, retrigger_idx + ATTACK_SAMPLES - 1):
        if i + 1 >= len(results):
            break
        curr = results[i][1]
        next_val = results[i + 1][1]
        jump = abs(next_val - curr)
        max_jump = max(max_jump, jump)

    print(f"过渡期最大跳变: {max_jump} LSB")

    if max_jump <= 138:
        print(f"✓ PASS: Decay 重触发连续性满足 ≤138 LSB")
        return True
    else:
        print(f"✗ FAIL: Decay 重触发跳变过大 {max_jump} LSB")
        return False


def test_sustain_retrigger():
    """测试 Sustain 状态重触发"""
    print("\n" + "=" * 70)
    print("测试3：Sustain 状态重触发逐样本对照")
    print("=" * 70)

    events = [
        (0, 'note_on', 1023),
        (ATTACK_SAMPLES + DECAY_SAMPLES + 1000, 'note_on', 768),  # Sustain 重触发
    ]

    results = simulate_rtl_envelope(events)

    retrigger_idx = ATTACK_SAMPLES + DECAY_SAMPLES + 1000
    level_before = results[retrigger_idx - 1][1]
    level_after = results[retrigger_idx][1]

    print(f"重触发前（样本{retrigger_idx-1}）: {level_before}")
    print(f"重触发后（样本{retrigger_idx}）: {level_after}")

    jump = abs(level_after - level_before)
    print(f"首样本跳变: {jump} LSB")

    # 检查过渡期连续性
    max_jump = 0
    for i in range(retrigger_idx, retrigger_idx + ATTACK_SAMPLES - 1):
        if i + 1 >= len(results):
            break
        curr = results[i][1]
        next_val = results[i + 1][1]
        jump = abs(next_val - curr)
        max_jump = max(max_jump, jump)

    print(f"过渡期最大跳变: {max_jump} LSB")

    if max_jump <= 138:
        print(f"✓ PASS: Sustain 重触发连续性满足 ≤138 LSB")
        return True
    else:
        print(f"✗ FAIL: Sustain 重触发跳变过大 {max_jump} LSB")
        return False


def test_release_retrigger():
    """测试 Release 状态重触发"""
    print("\n" + "=" * 70)
    print("测试4：Release 状态重触发逐样本对照")
    print("=" * 70)

    events = [
        (0, 'note_on', 1023),
        (ATTACK_SAMPLES + DECAY_SAMPLES + 1000, 'note_off', 0),
        (ATTACK_SAMPLES + DECAY_SAMPLES + 1000 + 2400, 'note_on', 512),  # Release 中途重触发
    ]

    results = simulate_rtl_envelope(events)

    retrigger_idx = ATTACK_SAMPLES + DECAY_SAMPLES + 1000 + 2400
    level_before = results[retrigger_idx - 1][1]
    level_after = results[retrigger_idx][1]

    print(f"重触发前（样本{retrigger_idx-1}）: {level_before}")
    print(f"重触发后（样本{retrigger_idx}）: {level_after}")

    jump = abs(level_after - level_before)
    print(f"首样本跳变: {jump} LSB")

    # 检查过渡期连续性
    max_jump = 0
    for i in range(retrigger_idx, retrigger_idx + ATTACK_SAMPLES - 1):
        if i + 1 >= len(results):
            break
        curr = results[i][1]
        next_val = results[i + 1][1]
        jump = abs(next_val - curr)
        max_jump = max(max_jump, jump)

    print(f"过渡期最大跳变: {max_jump} LSB")

    if max_jump <= 138:
        print(f"✓ PASS: Release 重触发连续性满足 ≤138 LSB")
        return True
    else:
        print(f"✗ FAIL: Release 重触发跳变过大 {max_jump} LSB")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("T009 各状态重触发逐样本对照测试")
    print("=" * 70)
    print(f"RTL 与模型容差: ±{MAX_ERROR_LSB} Q15 LSB")
    print("连续性指标: 每样本跳变 ≤138 Q15 LSB")

    results = []
    results.append(("Attack 重触发", test_attack_retrigger()))
    results.append(("Decay 重触发", test_decay_retrigger()))
    results.append(("Sustain 重触发", test_sustain_retrigger()))
    results.append(("Release 重触发", test_release_retrigger()))

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
        print("\n✓ 所有状态重触发测试通过")
        return 0
    else:
        print(f"\n✗ {failed} 项测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
