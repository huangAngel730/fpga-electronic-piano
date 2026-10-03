#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T028 延迟效果器 - 向量生成器（2026-10-02）

使用定点黄金模型生成 RTL 验证向量。
场景：旁路、脉冲响应、参数扫描、边界、复位。
"""

from __future__ import annotations
import sys
from pathlib import Path

# 添加模型路径
sys.path.insert(0, str(Path(__file__).resolve().parent))
from delay_effect_fixed import DelayEffectFixed, PCM_MAX, PCM_MIN, GAIN_MAX


def generate_vectors() -> list[tuple[int, int, int, int, int, int, int]]:
    """生成测试向量：(reset_before, input, delay, dry, wet, feedback, expected)

    M2 修正：场景间复位，避免缓存状态污染。
    """
    vectors = []
    reset_pending = True

    # 场景 1：精确旁路（dry=max, wet=0）
    delay = DelayEffectFixed(1024)
    for inp in [0, 1000, -5000, 100000, -100000, PCM_MAX, PCM_MIN]:
        out = delay.process(inp, delay_samples=100,
                           dry_gain=GAIN_MAX, wet_gain=0, feedback=0)
        vectors.append((int(reset_pending), inp, 100, GAIN_MAX, 0, 0, out))
        reset_pending = False

    # 场景 2：脉冲响应（检查延迟和反馈）
    delay.reset()  # M2 修正：场景复位
    reset_pending = True
    impulse_val = 1000000
    dry_g, wet_g, fb_g = 16384, 16384, 16384  # 0.5, 0.5, 0.5
    delay_s = 100

    for i in range(250):
        inp = impulse_val if i == 0 else 0
        out = delay.process(inp, delay_s, dry_g, wet_g, fb_g)
        vectors.append((int(reset_pending), inp, delay_s, dry_g, wet_g, fb_g, out))
        reset_pending = False

    # 场景 3：参数扫描（不同 dry/wet 组合）
    delay.reset()  # M2 修正：场景复位
    reset_pending = True
    test_input = 500000
    for dry in [0, 8192, 16384, 24576, 32767]:
        for wet in [0, 8192, 16384, 24576, 32767]:
            out = delay.process(test_input, delay_samples=50,
                               dry_gain=dry, wet_gain=wet, feedback=8192)
            vectors.append((int(reset_pending), test_input, 50, dry, wet, 8192, out))
            reset_pending = False

    # 场景 4：延迟时间扫描
    delay.reset()  # M2 修正：场景复位
    reset_pending = True
    for dly in [0, 1, 10, 50, 100, 500, 1000, 1023]:
        out = delay.process(test_input, delay_samples=dly,
                           dry_gain=16384, wet_gain=16384, feedback=16384)
        vectors.append((int(reset_pending), test_input, dly, 16384, 16384, 16384, out))
        reset_pending = False

    # 场景 5：反馈增益扫描（0 到接近 1.0）
    delay.reset()  # M2 修正：场景复位
    reset_pending = True
    for fb in [0, 8192, 16384, 24576, 32767]:
        for _ in range(5):  # 多次迭代观察反馈累积
            out = delay.process(test_input, delay_samples=20,
                               dry_gain=16384, wet_gain=16384, feedback=fb)
            vectors.append((int(reset_pending), test_input, 20, 16384, 16384, fb, out))
            reset_pending = False

    # 场景 6：边界值（PCM_MAX/MIN，饱和）
    delay.reset()  # M2 修正：场景复位
    reset_pending = True
    for inp in [PCM_MAX, PCM_MIN, 0]:
        for _ in range(10):
            out = delay.process(inp, delay_samples=5,
                               dry_gain=32767, wet_gain=32767, feedback=32767)
            vectors.append((int(reset_pending), inp, 5, 32767, 32767, 32767, out))
            reset_pending = False

    # 场景 7：零延迟（delay_samples=0）
    delay.reset()  # M2 修正：场景复位
    reset_pending = True
    for i in range(10):
        inp = (i + 1) * 10000
        out = delay.process(inp, delay_samples=0,
                           dry_gain=16384, wet_gain=16384, feedback=16384)
        vectors.append((int(reset_pending), inp, 0, 16384, 16384, 16384, out))
        reset_pending = False

    # 场景 8：正弦波输入（模拟真实音频）
    delay.reset()  # M2 修正：场景复位
    reset_pending = True
    import math
    for i in range(200):
        inp = int(5000000 * math.sin(2 * math.pi * i / 48))
        out = delay.process(inp, delay_samples=48,
                           dry_gain=22937, wet_gain=9830, feedback=16384)
        vectors.append((int(reset_pending), inp, 48, 22937, 9830, 16384, out))
        reset_pending = False

    return vectors


def main() -> int:
    vectors = generate_vectors()

    out_dir = Path(__file__).resolve().parent / "generated" / "delay_effect"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 写入向量文件
    vec_path = out_dir / "delay_effect_vectors.txt"
    lines = []
    for reset_before, inp, dly, dry, wet, fb, exp in vectors:
        # 格式：reset_before input delay dry wet feedback expected（显式场景复位）
        lines.append(f"{reset_before} {inp} {dly} {dry} {wet} {fb} {exp}")

    vec_path.write_text("\n".join(lines) + "\n", encoding="ascii")

    print(f"PASS: wrote {len(vectors)} vectors to {vec_path}")
    print(f"Scenarios: bypass, impulse, param sweep, delay sweep, feedback, "
          f"boundary, zero delay, sine wave")
    return 0


if __name__ == "__main__":
    sys.exit(main())
