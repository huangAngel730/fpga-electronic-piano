#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钢琴式ADSR包络生成器 - Python参考实现（T009增强版）

解决问题：
1. 按住时恒幅持续 -> 改为自然衰减（Decay到较低的Sustain后继续慢衰减）
2. 松键"啪"声 -> 从当前包络值平滑Release，而非立即跳变
3. 轻重弹音量相同 -> 增加Velocity到幅度的映射

钢琴包络特性：
- Attack: 快速起音（5-10ms）
- Decay: 快速衰减到中等电平（50-100ms）
- Sustain: 较低电平（0.3-0.5）并缓慢继续衰减
- Release: 从当前电平平滑释放（50-200ms）
"""

import sys
from pathlib import Path
from typing import Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import SAMPLE_RATE_HZ

# 钢琴式ADSR参数
ATTACK_SAMPLES = 240       # 5ms @ 48kHz，钢琴快速起音
DECAY_SAMPLES = 4800       # 100ms，快速衰减到sustain
SUSTAIN_LEVEL = 13107      # 0.4 in Q1.15，钢琴持续音较弱
SUSTAIN_DECAY_RATE = 0.15  # Sustain阶段每秒衰减15%的相对幅度
RELEASE_SAMPLES = 4800     # 100ms，平滑释放

ENVELOPE_MAX = 32767       # Q1.15 的 1.0

# Velocity映射参数
VELOCITY_MIN = 0.2         # 最轻触键的相对幅度（20%）
VELOCITY_MAX = 1.0         # 最重触键的相对幅度（100%）


def velocity_to_gain(velocity: int) -> int:
    """将MIDI Velocity (0-1023) 映射到增益 (Q1.15)

    使用平方律响应曲线，更符合人耳感知：
    gain = VELOCITY_MIN + (VELOCITY_MAX - VELOCITY_MIN) * (velocity / 1023)^2

    Args:
        velocity: MIDI velocity值 (0-1023，接口规范10位)

    Returns:
        Q1.15增益 (0-32767)
    """
    if velocity <= 0:
        return int(ENVELOPE_MAX * VELOCITY_MIN)
    if velocity >= 1023:
        return ENVELOPE_MAX

    # 归一化到0-1
    norm = velocity / 1023.0
    # 平方律曲线
    curve = norm * norm
    # 映射到VELOCITY_MIN到VELOCITY_MAX
    gain_float = VELOCITY_MIN + (VELOCITY_MAX - VELOCITY_MIN) * curve

    return int(ENVELOPE_MAX * gain_float)


class PianoADSREnvelope:
    """钢琴式ADSR包络生成器"""

    def __init__(self):
        self.state = 'IDLE'
        self.level = 0.0        # 浮点内部计算，提高精度
        self.counter = 0
        self.velocity_gain = ENVELOPE_MAX  # 默认最大增益

        # Sustain阶段的衰减率（每采样）
        self.sustain_decay_per_sample = 1.0 - (SUSTAIN_DECAY_RATE / SAMPLE_RATE_HZ)

    def note_on(self, velocity: int = 1023):
        """触发Note On

        Args:
            velocity: MIDI velocity (0-1023)

        Release重触发平滑过渡（修正版）：
            - 保持当前电平作为起点（包括 Release 和非零 Sustain）
            - 新目标高于当前：平滑上升
            - 新目标低于当前：平滑下降
            - 240 采样过渡时间，最大跳变 ≤138 LSB
        """
        # 保存重触发起点（任何状态下的当前电平）
        retrigger_start_level = self.level

        # 计算新目标电平
        target_gain = velocity_to_gain(velocity)

        self.state = 'ATTACK'
        self.level = retrigger_start_level
        self.counter = 0
        self.velocity_gain = target_gain

        # 计算从当前电平到目标的步长（上升或下降）
        self.attack_delta = (target_gain - retrigger_start_level) / ATTACK_SAMPLES

    def note_off(self):
        """触发Note Off - 从当前电平平滑释放"""
        if self.state != 'IDLE':
            self.state = 'RELEASE'
            # Release斜率基于当前电平，避免突变
            self.release_slope = self.level / RELEASE_SAMPLES
            self.counter = 0

    def step(self) -> int:
        """更新包络，返回当前电平（Q1.15）"""
        if self.state == 'ATTACK':
            # 线性过渡到目标电平（上升、下降或零斜率）
            self.level += self.attack_delta
            self.counter += 1

            # 240 采样后精确结束过渡（包括零斜率）
            if self.counter >= ATTACK_SAMPLES:
                self.level = self.velocity_gain
                self.state = 'DECAY'
                self.counter = 0

        elif self.state == 'DECAY':
            # 衰减到Sustain电平
            target_sustain = SUSTAIN_LEVEL * (self.velocity_gain / ENVELOPE_MAX)
            decay_slope = (self.velocity_gain - target_sustain) / DECAY_SAMPLES
            self.level -= decay_slope

            if self.level <= target_sustain:
                self.level = target_sustain
                self.state = 'SUSTAIN'
                self.counter = 0

        elif self.state == 'SUSTAIN':
            # 缓慢指数衰减，模拟钢琴弦自然衰减
            self.level *= self.sustain_decay_per_sample

            # 如果衰减到极低，切换到IDLE（防止浮点误差累积）
            if self.level < 1.0:
                self.level = 0.0
                self.state = 'IDLE'

        elif self.state == 'RELEASE':
            # 线性释放到0
            self.level -= self.release_slope
            if self.level <= 0:
                self.level = 0.0
                self.state = 'IDLE'

        return int(self.level)  # 返回整数Q1.15

    def get_state(self) -> Tuple[str, int, int]:
        """获取当前状态（用于调试和验证）

        Returns:
            (state_name, level_q15, counter)
        """
        return (self.state, int(self.level), self.counter)


def apply_envelope(sample_s16: int, envelope_q15: int) -> int:
    """应用包络到波表样本

    Args:
        sample_s16: 波表样本（16位有符号）
        envelope_q15: 包络电平（Q1.15格式）

    Returns:
        调制后的样本（16位有符号）
    """
    return (sample_s16 * envelope_q15) >> 15


# 自检和测试
if __name__ == "__main__":
    print("=" * 70)
    print("钢琴式ADSR包络测试")
    print("=" * 70)

    # 测试1: 完整ADSR循环
    print("\n测试1: 完整ADSR循环（velocity=1023）")
    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 采集: Attack(240) + Decay(4800) + Sustain(24000，0.5秒) + Release(4800)
    samples = []
    for i in range(33840):
        if i == 29040:  # 持续0.5秒后Note Off
            env.note_off()
        level = env.step()
        samples.append(level)

    attack_peak = max(samples[:ATTACK_SAMPLES + 100])
    decay_end = samples[ATTACK_SAMPLES + DECAY_SAMPLES]
    sustain_start = samples[ATTACK_SAMPLES + DECAY_SAMPLES + 100]
    sustain_end = samples[29040]  # Note Off前
    release_end = samples[-1]

    print(f"  Attack峰值: {attack_peak} (期望≈32767)")
    print(f"  Decay结束: {decay_end} (期望≈13107)")
    print(f"  Sustain开始: {sustain_start}")
    print(f"  Sustain结束(0.5s后): {sustain_end} (应<{sustain_start}，自然衰减)")
    print(f"  Release结束: {release_end} (期望0)")

    assert attack_peak >= 32500, "Attack未达峰值"
    assert 12000 <= decay_end <= 14000, "Decay电平不正确"
    assert sustain_end < sustain_start * 0.95, "Sustain未自然衰减"
    assert release_end == 0, "Release未归零"
    print("  [PASS]")

    # 测试2: Velocity响应
    print("\n测试2: Velocity响应曲线")
    test_velocities = [0, 256, 512, 768, 1023]
    for vel in test_velocities:
        gain = velocity_to_gain(vel)
        relative = gain / ENVELOPE_MAX
        print(f"  Velocity={vel:4d} -> Gain={gain:5d} ({relative:.2%})")

    # 测试3: 不同velocity的峰值
    print("\n测试3: 不同Velocity的Attack峰值")
    for vel in [256, 512, 768, 1023]:
        env = PianoADSREnvelope()
        env.note_on(velocity=vel)
        peaks = []
        for _ in range(ATTACK_SAMPLES + 100):
            peaks.append(env.step())
        peak = max(peaks)
        expected = velocity_to_gain(vel)
        print(f"  Velocity={vel:4d}: 峰值={peak:5d} (期望{expected:5d})")
        assert abs(peak - expected) < 100, f"Velocity {vel} 峰值不匹配"
    print("  [PASS]")

    # 测试4: 平滑Release（从不同电平）
    print("\n测试4: 平滑Release（避免啪声）")
    env = PianoADSREnvelope()
    env.note_on(velocity=1023)

    # 在Sustain中途释放
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 1000):
        env.step()

    level_before = env.step()
    env.note_off()
    level_after = env.step()

    # Release首个样本应接近Note Off前的电平
    diff = abs(level_after - level_before)
    print(f"  Note Off前电平: {level_before}")
    print(f"  Release首样本: {level_after}")
    print(f"  电平变化: {diff} (期望<100，平滑过渡)")
    assert diff < 100, "Release起点跳变过大，会产生啪声"
    print("  [PASS]")

    print("\n" + "=" * 70)
    print("[PASS] 钢琴式ADSR包络全部测试通过")
    print("=" * 70)
