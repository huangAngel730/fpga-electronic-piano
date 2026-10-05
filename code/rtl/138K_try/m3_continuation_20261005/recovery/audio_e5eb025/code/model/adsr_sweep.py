#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADSR参数扫描工具 - 帮助调整包络参数"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from adsr import ADSREnvelope, SAMPLE_RATE_HZ
from analysis_tool import pcm_to_wav


def generate_adsr_sweep(param_name: str, values: list, output_dir: Path):
    """生成不同ADSR参数的音频对比"""
    from dds_model import WavetableOscillator, make_wavetable, freq_to_fcw

    sine_table = make_wavetable('sine', 1024, 32767)
    fcw = freq_to_fcw(440.0, SAMPLE_RATE_HZ)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"扫描参数: {param_name}")
    print(f"值范围: {values}")
    print()

    for val in values:
        # 创建包络
        env = ADSREnvelope()

        # 修改参数
        if param_name == 'attack':
            env.attack_slope = 32767 / val
        elif param_name == 'decay':
            env.decay_slope = (32767 - env.sustain_level) / val
        elif param_name == 'sustain':
            env.sustain_level = val
        elif param_name == 'release':
            pass  # release在note_off时计算

        # 生成音频
        osc = WavetableOscillator(sine_table, fcw)
        env.note_on()

        samples = []
        # 1秒Note On
        for _ in range(SAMPLE_RATE_HZ):
            wt = osc.step()
            e = env.step()
            samples.append((wt * e) >> 15 << 8)

        # Note Off + 1秒Release
        env.note_off()
        for _ in range(SAMPLE_RATE_HZ):
            wt = osc.step()
            e = env.step()
            samples.append((wt * e) >> 15 << 8)

        # 输出
        filename = f"adsr_{param_name}_{val}.wav"
        pcm_to_wav(samples, output_dir / filename)
        print(f"  生成: {filename}")

    print(f"\n[完成] 参数扫描完成，输出: {output_dir}")


if __name__ == "__main__":
    out_dir = SCRIPT_DIR / "generated" / "adsr_sweep"

    # 扫描Attack时间
    generate_adsr_sweep('attack', [240, 480, 960], out_dir)
