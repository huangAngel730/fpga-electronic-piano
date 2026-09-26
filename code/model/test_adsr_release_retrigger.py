#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试ADSR Release阶段重触发的幅度连续性"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from adsr_piano import PianoADSREnvelope

print("=" * 70)
print("测试: Release阶段重触发的幅度连续性")
print("=" * 70)

env = PianoADSREnvelope()
env.note_on(velocity=1023)

# 完整循环到Release中途
for _ in range(240 + 4800 + 1000):  # Attack + Decay + Sustain部分
    env.step()

env.note_off()

# Release到约6530电平
for _ in range(2400):  # Release约一半
    level = env.step()

print(f"Release中途电平: {level}")

# 重触发Note On
env.note_on(velocity=512)
level_after = env.step()

print(f"重触发后首样本: {level_after}")
print(f"电平跳变: {level} -> {level_after}")
print(f"跳变幅度: {abs(level_after - level)}")

# M2关注的问题：6530 -> 54 跳变过大
if abs(level_after - level) > 100:
    print(f"\n[WARNING] 电平跳变过大: {abs(level_after - level)}")
    print("建议: Release重触发应从当前电平开始新Attack")
else:
    print("\n[PASS] 电平连续")
