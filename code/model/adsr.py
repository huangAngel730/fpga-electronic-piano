#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADSR包络生成器 - Python参考实现（T009）"""

import sys
from pathlib import Path
from typing import Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import SAMPLE_RATE_HZ

# ADSR参数（M1定义）
ATTACK_SAMPLES = 480      # 10ms @ 48kHz
DECAY_SAMPLES = 2400      # 50ms
SUSTAIN_LEVEL = 24575     # 0.75 in Q1.15
RELEASE_SAMPLES = 4800    # 100ms

ENVELOPE_MAX = 32767      # Q1.15 的 1.0


class ADSREnvelope:
    """ADSR包络生成器"""

    def __init__(self):
        self.state = 'IDLE'
        self.level = 0
        self.counter = 0

        # 预计算斜率（精确计算）
        self.attack_slope = ENVELOPE_MAX / ATTACK_SAMPLES  # 浮点暂存
        self.decay_slope = (ENVELOPE_MAX - SUSTAIN_LEVEL) / DECAY_SAMPLES
        self.release_slope = 0

    def note_on(self):
        """触发Note On"""
        self.state = 'ATTACK'
        self.level = 0
        self.counter = 0

    def note_off(self):
        """触发Note Off"""
        if self.state != 'IDLE':
            self.state = 'RELEASE'
            self.release_slope = self.level / RELEASE_SAMPLES
            self.counter = 0

    def step(self) -> int:
        """更新包络，返回当前电平（Q1.15）"""
        if self.state == 'ATTACK':
            self.level += self.attack_slope
            if self.level >= ENVELOPE_MAX:
                self.level = ENVELOPE_MAX
                self.state = 'DECAY'
                self.counter = 0

        elif self.state == 'DECAY':
            self.level -= self.decay_slope
            if self.level <= SUSTAIN_LEVEL:
                self.level = SUSTAIN_LEVEL
                self.state = 'SUSTAIN'

        elif self.state == 'SUSTAIN':
            self.level = SUSTAIN_LEVEL

        elif self.state == 'RELEASE':
            self.level -= self.release_slope
            if self.level <= 0:
                self.level = 0
                self.state = 'IDLE'

        self.counter += 1
        return int(self.level)  # 返回整数


def apply_envelope(sample_s16: int, envelope_q15: int) -> int:
    """应用包络到波表样本"""
    return (sample_s16 * envelope_q15) >> 15


# 自检
if __name__ == "__main__":
    env = ADSREnvelope()

    # 测试完整ADSR循环
    env.note_on()

    # 收集数据: Attack(480) + Decay(2400) + Sustain(2000) + Release(4800)
    samples = []
    for i in range(9680):
        if i == 4880:  # 持续一段时间后Note Off
            env.note_off()
        level = env.step()
        samples.append(level)

    attack_peak = max(samples[:ATTACK_SAMPLES + 100])
    sustain_level = samples[ATTACK_SAMPLES + DECAY_SAMPLES + 100]
    release_end = samples[-1]

    print(f"Attack峰值: {attack_peak} (期望≈32767)")
    print(f"Sustain电平: {sustain_level} (期望24575)")
    print(f"Release结束: {release_end} (期望0)")

    assert attack_peak >= 32500, "Attack未达峰值"
    assert 24400 <= sustain_level <= 24700, "Sustain电平不正确"
    assert release_end == 0, "Release未归零"

    print("[PASS] ADSR自检完成")
