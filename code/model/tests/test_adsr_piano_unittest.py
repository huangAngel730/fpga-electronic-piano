#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T009 钢琴式ADSR包络边界测试（unittest格式）

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
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from adsr_piano import PianoADSREnvelope, apply_envelope, velocity_to_gain
from adsr_piano import ATTACK_SAMPLES, DECAY_SAMPLES, SUSTAIN_LEVEL, RELEASE_SAMPLES, ENVELOPE_MAX


class TestPianoADSREnvelope(unittest.TestCase):
    """T009钢琴式ADSR包络测试套件"""

    def test_velocity_boundaries(self):
        """测试Velocity边界值"""
        # Velocity=0: 最小增益20%
        gain0 = velocity_to_gain(0)
        self.assertEqual(gain0, 6553, "Velocity=0增益错误")

        # Velocity=1023: 最大增益100%
        gain1023 = velocity_to_gain(1023)
        self.assertEqual(gain1023, 32767, "Velocity=1023增益错误")

        # 验证单调性
        prev_gain = 0
        for v in range(0, 1024, 100):
            g = velocity_to_gain(v)
            self.assertGreaterEqual(g, prev_gain, f"Velocity映射非单调: {v}")
            prev_gain = g

    def test_early_release_attack(self):
        """测试Attack阶段立即Release"""
        env = PianoADSREnvelope()
        env.note_on(velocity=1023)

        # Attack进行一半
        for _ in range(ATTACK_SAMPLES // 2):
            env.step()

        level_before = env.step()
        env.note_off()
        level_after = env.step()

        # 应该平滑进入Release
        self.assertLess(level_after, level_before, "Release未下降")
        self.assertLess(abs(level_after - level_before), 200, "Release跳变过大")

    def test_early_release_decay(self):
        """测试Decay阶段立即Release"""
        env = PianoADSREnvelope()
        env.note_on(velocity=1023)

        # 完整Attack + Decay一半
        for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES // 2):
            env.step()

        level_before = env.step()
        env.note_off()
        level_after = env.step()

        self.assertLess(level_after, level_before, "Decay中Release未下降")
        self.assertLess(abs(level_after - level_before), 200, "Decay中Release跳变过大")

    def test_sustain_decay(self):
        """测试Sustain长时间持续"""
        env = PianoADSREnvelope()
        env.note_on(velocity=1023)

        # 完整Attack + Decay
        for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES):
            env.step()

        sustain_start = env.step()

        # 持续2秒（96000样本）
        for _ in range(96000):
            level = env.step()

        sustain_end = level

        # 验证自然衰减
        self.assertLess(sustain_end, sustain_start * 0.8, "Sustain未自然衰减")
        self.assertGreater(sustain_end, 0, "Sustain不应完全归零")

    def test_release_retrigger(self):
        """测试Release阶段重新Note On（重触发）"""
        env = PianoADSREnvelope()
        env.note_on(velocity=1023)

        # 完整循环到Release中途
        for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 1000):
            env.step()
        env.note_off()

        for _ in range(RELEASE_SAMPLES // 2):
            env.step()

        # Release中途重新Note On
        level_before = env.step()
        env.note_on(velocity=512)
        level_after = env.step()

        # 验证平滑过渡（跳变应小于Attack最大步长）
        max_attack_step = (32767 / ATTACK_SAMPLES) + 1
        self.assertLess(abs(level_after - level_before), max_attack_step * 2,
                       "Release重触发跳变过大")

        # 验证能达到新的velocity峰值
        for _ in range(ATTACK_SAMPLES + 100):
            level = env.step()

        expected_peak = velocity_to_gain(512)
        self.assertLess(abs(level - expected_peak), 500, "重触发峰值不正确")

    def test_fast_retrigger(self):
        """测试连续快速Note On/Off（10ms颤音）"""
        env = PianoADSREnvelope()

        for _ in range(10):
            env.note_on(velocity=768)
            for _ in range(480):  # 10ms
                env.step()
            env.note_off()
            for _ in range(480):  # 10ms
                env.step()

        # 应该不崩溃且状态正常
        state, level, counter = env.get_state()
        self.assertIn(state, ['IDLE', 'ATTACK', 'DECAY', 'SUSTAIN', 'RELEASE'])

    def test_envelope_application(self):
        """测试包络应用边界"""
        # 零样本
        result = apply_envelope(0, 32767)
        self.assertEqual(result, 0)

        # 最大样本 × 最大包络（允许1 LSB舍入误差）
        result = apply_envelope(32767, 32767)
        self.assertGreaterEqual(result, 32766)
        self.assertLessEqual(result, 32767)

        # 负样本
        result = apply_envelope(-32768, 16384)
        self.assertEqual(result, -16384)

    def test_idle_state(self):
        """测试IDLE状态"""
        env = PianoADSREnvelope()

        # 未触发应该输出0
        for _ in range(100):
            level = env.step()
            self.assertEqual(level, 0, "IDLE状态应该输出0")

        state, level, counter = env.get_state()
        self.assertEqual(state, 'IDLE')


if __name__ == "__main__":
    unittest.main()
