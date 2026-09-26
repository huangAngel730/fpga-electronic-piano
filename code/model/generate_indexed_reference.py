#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""带帧序号的黄金向量生成器（D031逐帧规则）

生成逐帧PCM输出和DDS相位快照，供RTL逐帧对比验证。
对应M2要求的带帧序号黄金向量。
"""

import sys
from pathlib import Path
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import SAMPLE_RATE_HZ, PCM_BITS, PCM_MAX, PCM_MIN
from dds_model import freq_to_fcw, fcw_to_freq, WavetableOscillator, make_wavetable
from mixer import mix_voices

# T052测试频率
TEST_FREQUENCIES = [200, 400, 600, 800]  # Hz
DURATION_SECONDS = 2.0


def generate_indexed_reference():
    """生成带帧序号的黄金向量"""
    print("=" * 70)
    print("D031 逐帧黄金向量生成器")
    print("=" * 70)

    num_samples = int(SAMPLE_RATE_HZ * DURATION_SECONDS)
    print(f"采样率: {SAMPLE_RATE_HZ} Hz")
    print(f"总帧数: {num_samples}")
    print(f"时长: {DURATION_SECONDS} 秒")
    print()

    # 计算FCW
    fcws = []
    for freq in TEST_FREQUENCIES:
        fcw = freq_to_fcw(freq, SAMPLE_RATE_HZ)
        fcws.append(fcw)
        actual_freq = fcw_to_freq(fcw, SAMPLE_RATE_HZ)
        print(f"{freq} Hz -> FCW=0x{fcw:08x} (实际{actual_freq:.6f} Hz)")
    print()

    # 创建振荡器
    sine_table = make_wavetable('sine', 1024, 8192)
    oscillators = [WavetableOscillator(table=sine_table, fcw=fcw) for fcw in fcws]

    # 输出目录
    output_dir = SCRIPT_DIR / "generated" / "test_mode"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成逐帧数据
    indexed_file = output_dir / "indexed_reference.txt"
    compact_file = output_dir / "indexed_reference_compact.txt"

    print("生成逐帧向量...")

    with indexed_file.open('w', encoding='utf-8', newline='\n') as f_full, \
         compact_file.open('w', encoding='utf-8', newline='\n') as f_compact:

        # 完整文件头
        f_full.write("# D031 逐帧黄金向量\n")
        f_full.write(f"# 采样率: {SAMPLE_RATE_HZ} Hz\n")
        f_full.write(f"# 测试频率: {TEST_FREQUENCIES} Hz\n")
        f_full.write("# 格式: frame_idx pcm_hex pcm_dec phase0 phase1 phase2 phase3 voice0 voice1 voice2 voice3 clipped\n")
        f_full.write("#\n")

        # 精简文件头
        f_compact.write("# D031 精简逐帧向量（关键帧）\n")
        f_compact.write("# frame pcm_hex pcm_dec phase0 phase1 phase2 phase3\n")
        f_compact.write("#\n")

        # 关键帧索引
        key_frames = [0, 1, 10, 100, 240, 480, 2400, 4800, 24000, 48000, num_samples-1]

        for frame_idx in range(num_samples):
            # 生成4个声部
            voices = []
            phases = []
            for osc in oscillators:
                wt_sample = osc.step()
                voices.append(wt_sample << 8)  # 波表样本左移8位
                phases.append(osc.phase)

            # 混音
            mixed, clipped = mix_voices(voices)

            # 转为无符号hex
            if mixed < 0:
                pcm_unsigned = (1 << PCM_BITS) + mixed
            else:
                pcm_unsigned = mixed

            # 完整文件：每帧一行
            f_full.write(f"{frame_idx:6d} {pcm_unsigned:06x} {mixed:8d} ")
            f_full.write(f"{phases[0]:08x} {phases[1]:08x} {phases[2]:08x} {phases[3]:08x} ")
            f_full.write(f"{voices[0]:7d} {voices[1]:7d} {voices[2]:7d} {voices[3]:7d} ")
            f_full.write(f"{int(clipped)}\n")

            # 精简文件：只记录关键帧
            if frame_idx in key_frames:
                f_compact.write(f"{frame_idx:6d} {pcm_unsigned:06x} {mixed:8d} ")
                f_compact.write(f"{phases[0]:08x} {phases[1]:08x} {phases[2]:08x} {phases[3]:08x}\n")

    print(f"[完成] 已生成 {num_samples} 帧")
    print(f"  完整向量: {indexed_file}")
    print(f"  精简向量: {compact_file} ({len(key_frames)} 个关键帧)")
    print()

    # 生成关键帧说明
    print("关键帧选择说明:")
    print(f"  帧0: 初始状态，验证FCW加载和初始相位")
    print(f"  帧1: 首次相位累加，验证步进逻辑")
    print(f"  帧10: 早期稳定性")
    print(f"  帧100: 短期连续性")
    print(f"  帧240 (5ms): ADSR攻击段典型时间")
    print(f"  帧480 (10ms): 人耳可辨最短音符")
    print(f"  帧2400 (50ms): MIDI Note处理延迟上限")
    print(f"  帧4800 (100ms): 典型ADSR包络时间")
    print(f"  帧24000 (0.5s): 中期频率精度验证")
    print(f"  帧48000 (1.0s): 长期周期稳定性")
    print(f"  帧{num_samples-1}: 最后一帧，验证边界")
    print()

    # 统计信息
    print("=" * 70)
    print("验证指导")
    print("=" * 70)
    print("RTL验证建议:")
    print("1. 首先对比关键帧（compact文件），快速定位问题")
    print("2. 发现失配后，在完整向量中定位具体帧")
    print("3. 验证相位累加：phase[n+1] - phase[n] 应等于 FCW")
    print("4. 验证混音：sum(voices) 在 [-8388608, 8388607] 内")
    print("5. 验证削波：sum(voices) 超出范围时 clipped=1")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(generate_indexed_reference())
