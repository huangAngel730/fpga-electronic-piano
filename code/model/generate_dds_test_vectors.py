#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T004 DDS单声部测试向量生成器

生成DDS逐样本参考向量，用于RTL验证：
1. 单频率正弦波测试
2. MIDI音符覆盖测试
3. 相位连续性测试
4. 频率跳变测试
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import SAMPLE_RATE_HZ, WT_AMPLITUDE
from dds_model import (
    WavetableOscillator, make_wavetable,
    midi_note_to_fcw, fcw_to_freq, freq_to_fcw
)


def generate_single_tone_test():
    """生成单音测试向量 - A4 (440Hz) 正弦波"""
    print("=" * 70)
    print("测试1: 单音DDS测试 (A4 440Hz)")
    print("=" * 70)

    # A4音符 (MIDI 69)
    fcw = midi_note_to_fcw(69)
    actual_freq = fcw_to_freq(fcw)

    print(f"MIDI Note: 69 (A4)")
    print(f"目标频率: 440.000 Hz")
    print(f"FCW: 0x{fcw:08x} ({fcw})")
    print(f"实际频率: {actual_freq:.6f} Hz")
    print(f"误差: {(actual_freq - 440.0):.6f} Hz")
    print()

    # 创建振荡器
    sine_table = make_wavetable('sine', 1024, WT_AMPLITUDE)
    osc = WavetableOscillator(table=sine_table, fcw=fcw)

    # 生成1秒波形
    num_samples = SAMPLE_RATE_HZ
    output_dir = SCRIPT_DIR / "generated" / "dds_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 完整向量文件
    vector_file = output_dir / "dds_a4_440hz.txt"
    with vector_file.open('w', encoding='utf-8', newline='\n') as f:
        f.write("# T004 DDS单音测试向量 - A4 (440Hz)\n")
        f.write(f"# FCW: 0x{fcw:08x}\n")
        f.write("# 格式: sample_idx phase_hex wt_sample_dec wt_sample_hex\n")
        f.write("#\n")

        for i in range(num_samples):
            phase_before = osc.phase
            wt_sample = osc.step()

            # 转换为16位无符号hex
            if wt_sample < 0:
                wt_unsigned = (1 << 16) + wt_sample
            else:
                wt_unsigned = wt_sample

            f.write(f"{i:6d} {phase_before:08x} {wt_sample:6d} {wt_unsigned:04x}\n")

    print(f"已生成: {vector_file}")
    print(f"样本数: {num_samples}")
    print()

    return vector_file


def generate_midi_range_test():
    """生成MIDI音符范围测试 - 每个音符16个样本"""
    print("=" * 70)
    print("测试2: MIDI音符范围测试 (C0-C8)")
    print("=" * 70)

    sine_table = make_wavetable('sine', 1024, WT_AMPLITUDE)
    output_dir = SCRIPT_DIR / "generated" / "dds_test"

    vector_file = output_dir / "dds_midi_range.txt"
    summary_file = output_dir / "dds_midi_range_summary.txt"

    # 测试范围：C0(12) 到 C8(108)，每个八度的C
    test_notes = [12, 24, 36, 48, 60, 72, 84, 96, 108]

    with vector_file.open('w', encoding='utf-8', newline='\n') as f, \
         summary_file.open('w', encoding='utf-8', newline='\n') as fs:

        f.write("# T004 MIDI音符范围测试\n")
        f.write("# 每个音符16个样本\n")
        f.write("# 格式: note sample_idx phase wt_sample\n")
        f.write("#\n")

        fs.write("# MIDI音符频率对照表\n")
        fs.write("# note fcw_hex fcw_dec freq_hz\n")
        fs.write("#\n")

        for note in test_notes:
            fcw = midi_note_to_fcw(note)
            freq = fcw_to_freq(fcw)

            fs.write(f"{note:3d} {fcw:08x} {fcw:10d} {freq:10.3f}\n")

            osc = WavetableOscillator(table=sine_table, fcw=fcw)

            for i in range(16):
                phase = osc.phase
                wt_sample = osc.step()
                f.write(f"{note:3d} {i:2d} {phase:08x} {wt_sample:6d}\n")

    print(f"已生成: {vector_file}")
    print(f"已生成: {summary_file}")
    print(f"测试音符: {len(test_notes)} 个")
    print()


def generate_phase_continuity_test():
    """生成相位连续性测试 - 验证FCW切换"""
    print("=" * 70)
    print("测试3: 相位连续性测试 (FCW切换)")
    print("=" * 70)

    sine_table = make_wavetable('sine', 1024, WT_AMPLITUDE)
    output_dir = SCRIPT_DIR / "generated" / "dds_test"

    vector_file = output_dir / "dds_phase_continuity.txt"

    # 测试序列：200Hz -> 400Hz -> 200Hz
    test_sequence = [
        (200, 100),  # 200Hz持续100样本
        (400, 100),  # 切换到400Hz
        (200, 100),  # 切换回200Hz
    ]

    with vector_file.open('w', encoding='utf-8', newline='\n') as f:
        f.write("# T004 相位连续性测试\n")
        f.write("# 测试FCW切换时的相位连续性\n")
        f.write("# 序列: 200Hz(100) -> 400Hz(100) -> 200Hz(100)\n")
        f.write("# 格式: sample_idx freq_hz fcw phase_before phase_after wt_sample\n")
        f.write("#\n")

        osc = WavetableOscillator(table=sine_table, fcw=0)
        sample_idx = 0

        for freq, num_samples in test_sequence:
            fcw = freq_to_fcw(freq)
            # 使用set_fcw更新频率，相位自动保持连续
            osc.set_fcw(fcw)

            print(f"频率: {freq} Hz, FCW: 0x{fcw:08x}, 样本数: {num_samples}")

            for i in range(num_samples):
                phase_before = osc.phase
                wt_sample = osc.step()
                phase_after = osc.phase

                f.write(f"{sample_idx:6d} {freq:4d} {fcw:08x} {phase_before:08x} {phase_after:08x} {wt_sample:6d}\n")
                sample_idx += 1

    print(f"已生成: {vector_file}")
    print(f"总样本数: {sample_idx}")
    print()


def generate_edge_cases_test():
    """生成边界情况测试"""
    print("=" * 70)
    print("测试4: 边界情况测试")
    print("=" * 70)

    sine_table = make_wavetable('sine', 1024, WT_AMPLITUDE)
    output_dir = SCRIPT_DIR / "generated" / "dds_test"

    vector_file = output_dir / "dds_edge_cases.txt"

    # 边界测试：最低音、最高音、DC
    test_cases = [
        ("DC (0Hz)", 0),
        ("最低MIDI (C0 16.35Hz)", 12),
        ("最高MIDI (G9 12543Hz)", 127),
    ]

    with vector_file.open('w', encoding='utf-8', newline='\n') as f:
        f.write("# T004 边界情况测试\n")
        f.write("# 格式: case sample_idx phase wt_sample\n")
        f.write("#\n")

        for case_name, note_or_freq in test_cases:
            if isinstance(note_or_freq, int) and note_or_freq >= 12:
                # MIDI音符
                fcw = midi_note_to_fcw(note_or_freq)
                freq = fcw_to_freq(fcw)
            else:
                # 直接频率
                fcw = note_or_freq
                freq = 0.0

            print(f"{case_name}: FCW=0x{fcw:08x}, 频率={freq:.2f}Hz")

            osc = WavetableOscillator(table=sine_table, fcw=fcw)

            for i in range(32):  # 每个测试32样本
                phase = osc.phase
                wt_sample = osc.step()
                f.write(f"\"{case_name}\" {i:2d} {phase:08x} {wt_sample:6d}\n")

    print(f"已生成: {vector_file}")
    print()


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("T004 DDS测试向量生成器")
    print("=" * 70)
    print()

    # 生成各类测试向量
    generate_single_tone_test()
    generate_midi_range_test()
    generate_phase_continuity_test()
    generate_edge_cases_test()

    print("=" * 70)
    print("全部测试向量生成完成")
    print("=" * 70)
    print()
    print("输出目录: code/model/generated/dds_test/")
    print("文件列表:")
    print("  - dds_a4_440hz.txt          : A4单音完整1秒波形")
    print("  - dds_midi_range.txt        : MIDI音符范围测试")
    print("  - dds_midi_range_summary.txt: MIDI音符频率对照")
    print("  - dds_phase_continuity.txt  : FCW切换相位连续性")
    print("  - dds_edge_cases.txt        : 边界情况测试")
    print()
    print("RTL验证方法:")
    print("1. 单音测试：逐样本对比相位和波表输出")
    print("2. MIDI范围：验证所有音符的FCW正确")
    print("3. 相位连续：验证FCW切换时相位无跳变")
    print("4. 边界情况：验证极端频率的稳定性")

    return 0


if __name__ == "__main__":
    sys.exit(main())
