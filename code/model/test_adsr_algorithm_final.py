#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T009 ADSR 算法终验和边界验证

验证范围：
1. 连续重触发（快速多次）
2. 极端力度切换（0↔1023）
3. 零斜率（velocity=0）
4. 阶段边界事件（同拍 Note On/Off）
5. 确认四个定案指标的适用范围
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from adsr_piano import PianoADSREnvelope, velocity_to_gain, ATTACK_SAMPLES, DECAY_SAMPLES

# 定案指标
MAX_TRANSITION_LSB = 138  # 每采样最大跳变
TRANSITION_SAMPLES = 240  # 过渡时间
MODEL_TOLERANCE_LSB = 2   # RTL 容差
ENVELOPE_MAX = 32767      # Q1.15 最大值


def test_rapid_retrigger():
    """测试1：连续快速重触发"""
    print("\n" + "=" * 70)
    print("测试1：连续快速重触发（验证连续性保持）")
    print("=" * 70)

    env = PianoADSREnvelope()

    # 场景：每 50 采样重触发一次，共 5 次
    retrigger_intervals = [0, 50, 100, 150, 200]
    velocities = [1023, 512, 768, 256, 896]

    max_jump_overall = 0
    sample_count = 0

    for i, (target_sample, vel) in enumerate(zip(retrigger_intervals, velocities)):
        # 走到重触发点
        level_before = 0
        while sample_count < target_sample:
            level_before = env.step()
            sample_count += 1

        # 重触发
        env.note_on(velocity=vel)
        level_after = env.step()
        sample_count += 1

        jump = abs(level_after - level_before)
        max_jump_overall = max(max_jump_overall, jump)

        print(f"  第{i+1}次重触发（样本{target_sample}，vel={vel}）：")
        print(f"    重触发前：{level_before}, 重触发后：{level_after}, 跳变={jump} LSB")

    print(f"\n  整体最大跳变: {max_jump_overall} LSB")

    # 验收标准
    if max_jump_overall <= MAX_TRANSITION_LSB:
        print(f"✓ PASS: 连续重触发最大跳变 {max_jump_overall} ≤ {MAX_TRANSITION_LSB} LSB")
        return True
    else:
        print(f"✗ FAIL: 连续重触发跳变过大 {max_jump_overall} LSB")
        return False


def test_extreme_velocity_switch():
    """测试2：极端力度切换（0↔1023）"""
    print("\n" + "=" * 70)
    print("测试2：极端力度切换（验证全范围平滑过渡）")
    print("=" * 70)

    env = PianoADSREnvelope()

    # 场景1：最大 → 最小
    env.note_on(velocity=1023)
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 500):
        env.step()

    level_high = env.step()
    env.note_on(velocity=0)
    level_after_low = env.step()

    jump_high_to_low = abs(level_after_low - level_high)
    target_low = velocity_to_gain(0)

    print(f"  最大→最小：{level_high} → {level_after_low}")
    print(f"  目标增益（velocity=0）：{target_low}")
    print(f"  首样本跳变：{jump_high_to_low} LSB")

    # 检查过渡期
    max_jump_down = jump_high_to_low
    prev = level_after_low
    for _ in range(TRANSITION_SAMPLES - 1):
        level = env.step()
        jump = abs(level - prev)
        max_jump_down = max(max_jump_down, jump)
        prev = level

    print(f"  下降过渡最大跳变：{max_jump_down} LSB")

    # 场景2：最小 → 最大
    env2 = PianoADSREnvelope()
    env2.note_on(velocity=0)
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 500):
        env2.step()

    level_low = env2.step()
    env2.note_on(velocity=1023)
    level_after_high = env2.step()

    jump_low_to_high = abs(level_after_high - level_low)

    print(f"\n  最小→最大：{level_low} → {level_after_high}")
    print(f"  首样本跳变：{jump_low_to_high} LSB")

    # 检查过渡期
    max_jump_up = jump_low_to_high
    prev = level_after_high
    for _ in range(TRANSITION_SAMPLES - 1):
        level = env2.step()
        jump = abs(level - prev)
        max_jump_up = max(max_jump_up, jump)
        prev = level

    print(f"  上升过渡最大跳变：{max_jump_up} LSB")

    # 验收标准
    max_jump_overall = max(max_jump_down, max_jump_up)

    if max_jump_overall <= MAX_TRANSITION_LSB:
        print(f"\n✓ PASS: 极端力度切换最大跳变 {max_jump_overall} ≤ {MAX_TRANSITION_LSB} LSB")
        return True
    else:
        print(f"\n✗ FAIL: 极端力度切换跳变过大 {max_jump_overall} LSB")
        return False


def test_zero_slope_retrigger():
    """测试3：零斜率重触发（velocity=0 重触发验证）"""
    print("\n" + "=" * 70)
    print("测试3：零斜率重触发（验证 velocity=0 重触发行为）")
    print("=" * 70)

    # 场景1：从高电平重触发到 velocity=0
    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 到达 Sustain
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 500):
        env.step()

    level_before = env.step()
    target_zero = velocity_to_gain(0)

    print(f"  场景1：高电平 → velocity=0")
    print(f"    重触发前电平：{level_before}")
    print(f"    velocity=0 目标增益：{target_zero}")

    env.note_on(velocity=0)
    level_after = env.step()

    jump = abs(level_after - level_before)
    print(f"    重触发后首样本：{level_after}")
    print(f"    跳变：{jump} LSB")

    # 断言：跳变应 ≤138 LSB
    assert jump <= MAX_TRANSITION_LSB, f"velocity=0 重触发跳变过大：{jump} LSB"

    # 走完 240 采样过渡
    for _ in range(ATTACK_SAMPLES - 1):
        level = env.step()

    final_level = level
    state = env.get_state()[0]

    print(f"    240 采样后电平：{final_level}")
    print(f"    240 采样后状态：{state}")

    # 断言：240 采样后应到达目标并进入 DECAY
    assert abs(final_level - target_zero) <= MODEL_TOLERANCE_LSB, f"未到达 velocity=0 目标，误差 {abs(final_level - target_zero)} LSB"
    assert state == 'DECAY', f"240 采样后状态错误：{state}，应为 DECAY"

    # 场景2：velocity=0 完整循环
    env2 = PianoADSREnvelope()
    env2.note_on(velocity=0)

    # Attack 峰值
    peak = 0
    for _ in range(ATTACK_SAMPLES):
        level = env2.step()
        peak = max(peak, level)

    print(f"\n  场景2：velocity=0 完整循环")
    print(f"    Attack 峰值：{peak}")
    print(f"    目标增益：{target_zero}")

    # 断言：峰值应精确
    assert abs(peak - target_zero) <= MODEL_TOLERANCE_LSB, f"velocity=0 峰值误差 {abs(peak - target_zero)} LSB"

    # Decay + Sustain
    for _ in range(DECAY_SAMPLES + 1000):
        env2.step()

    # Note Off
    env2.note_off()

    # Release 到零
    final = None
    for _ in range(5000):
        level = env2.step()
        if level == 0:
            final = 0
            break

    print(f"    Release 最终：{final}")

    # 断言：必须归零
    assert final == 0, f"velocity=0 Release 未归零：{final}"

    print(f"\n✓ PASS: 零斜率重触发验证通过")
    return True


def test_boundary_events():
    """测试4：阶段边界事件（240 采样与状态边界断言）"""
    print("\n" + "=" * 70)
    print("测试4：阶段边界事件（240 采样与状态边界断言）")
    print("=" * 70)

    # 场景1：Attack 结束边界（第 240 采样）
    env1 = PianoADSREnvelope()
    env1.note_on(velocity=1023)

    for i in range(ATTACK_SAMPLES):
        level = env1.step()
        state = env1.get_state()[0]

        if i == ATTACK_SAMPLES - 1:
            # 第 240 采样应为 Attack 最后一个或已进入 Decay
            print(f"  场景1：Attack 第 {i+1} 采样")
            print(f"    电平：{level}")
            print(f"    状态：{state}")

            # 断言：第 240 采样后状态必须为 DECAY
            next_state = env1.get_state()[0]
            assert next_state == 'DECAY', f"第 240 采样后状态错误：{next_state}，应为 DECAY"

    # 场景2：Attack 结束时立即 Note Off
    env2 = PianoADSREnvelope()
    env2.note_on(velocity=1023)

    for _ in range(ATTACK_SAMPLES - 1):
        env2.step()

    level_before = env2.step()
    state_before = env2.get_state()[0]

    env2.note_off()
    level_after = env2.step()
    state_after = env2.get_state()[0]

    jump = abs(level_after - level_before)

    print(f"\n  场景2：Attack 结束时 Note Off")
    print(f"    状态转换：{state_before} → {state_after}")
    print(f"    电平：{level_before} → {level_after}")
    print(f"    跳变：{jump} LSB")

    # 断言：状态应为 RELEASE，跳变应平滑
    assert state_after == 'RELEASE', f"Note Off 后状态错误：{state_after}，应为 RELEASE"
    assert jump <= 200, f"Note Off 跳变过大：{jump} LSB"

    # 场景3：Decay 结束边界
    env3 = PianoADSREnvelope()
    env3.note_on(velocity=1023)

    # 走完 Attack + Decay，再多走一个样本确保状态转换
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 1):
        level = env3.step()

    state_after_decay = env3.get_state()[0]
    level_after_decay = env3.get_state()[1]

    print(f"\n  场景3：Decay {DECAY_SAMPLES} 采样后")
    print(f"    电平：{level_after_decay}")
    print(f"    状态：{state_after_decay}")

    # 断言：Decay 结束后应进入 SUSTAIN
    assert state_after_decay == 'SUSTAIN', f"Decay 结束后状态错误：{state_after_decay}，应为 SUSTAIN"

    # 场景4：同拍事件（Note On 后立即 Note Off）
    env4 = PianoADSREnvelope()
    env4.note_on(velocity=1023)
    env4.note_off()

    level = env4.step()
    state = env4.get_state()[0]

    print(f"\n  场景4：Note On 后立即 Note Off")
    print(f"    首样本电平：{level}")
    print(f"    状态：{state}")

    # 注：Python 模型串行处理，此场景验证模型行为
    # 不声称验证同拍 RTL 事件

    print(f"\n✓ PASS: 边界事件断言验证通过")
    return True


def test_true_zero_slope_retrigger():
    """测试5：真正零斜率重触发（当前电平 = 目标电平）"""
    print("\n" + "=" * 70)
    print("测试5：真正零斜率重触发（同电平重触发）")
    print("=" * 70)

    # 场景：同力度连续重触发
    env = PianoADSREnvelope()
    env.note_on(1023)

    # 走完 Attack 到达峰值
    for _ in range(ATTACK_SAMPLES):
        env.step()

    level_before = env.level
    print(f"  重触发前电平：{level_before}")
    print(f"  重触发前状态：{env.get_state()[0]}")

    # 同力度重触发（零斜率）
    env.note_on(1023)

    print(f"  attack_delta：{env.attack_delta}")

    # 检查第 1 采样
    level_1 = env.step()
    state_1 = env.get_state()[0]
    print(f"\n  第 1 采样：状态={state_1}, 电平={level_1}")

    # 断言：第 1 采样必须为 ATTACK
    assert state_1 == 'ATTACK', f"第 1 采样状态错误：{state_1}，应为 ATTACK"

    # 检查第 239 采样
    for _ in range(237):
        env.step()

    level_239 = env.step()
    state_239 = env.get_state()[0]
    print(f"  第 239 采样：状态={state_239}, 电平={level_239}")

    # 断言：第 239 采样必须为 ATTACK
    assert state_239 == 'ATTACK', f"第 239 采样状态错误：{state_239}，应为 ATTACK"

    # 检查第 240 采样
    level_240 = env.step()
    state_240 = env.get_state()[0]
    print(f"  第 240 采样：状态={state_240}, 电平={level_240}")

    # 断言：第 240 采样后必须为 DECAY
    assert state_240 == 'DECAY', f"第 240 采样后状态错误：{state_240}，应为 DECAY"

    # 断言：电平应保持不变
    assert level_1 == level_before, f"零斜率重触发电平改变：{level_before} → {level_1}"
    assert level_239 == level_before, f"零斜率过渡期电平改变：{level_239}"
    assert level_240 == level_before, f"零斜率结束电平改变：{level_240}"

    print(f"\n✓ PASS: 零斜率重触发固定 240 采样，状态正确")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("T009 ADSR 算法终验和补充边界验证")
    print("=" * 70)
    print("验证范围：连续重触发、极端力度、零斜率重触发、边界事件、真零斜率")
    print(f"定案指标：240 采样过渡、≤{MAX_TRANSITION_LSB} LSB 跳变、±{MODEL_TOLERANCE_LSB} LSB 容差")

    results = []
    results.append(("连续快速重触发", test_rapid_retrigger()))
    results.append(("极端力度切换", test_extreme_velocity_switch()))
    results.append(("零斜率重触发", test_zero_slope_retrigger()))
    results.append(("阶段边界事件", test_boundary_events()))
    results.append(("真零斜率重触发", test_true_zero_slope_retrigger()))

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
        print("\n✓ 所有算法终验测试通过")
        return 0
    else:
        print(f"\n✗ {failed} 项测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
