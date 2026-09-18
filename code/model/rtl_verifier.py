#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RTL对比验证工具 - 自动对比RTL输出与Python参考"""

import sys
from pathlib import Path
from typing import List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import PCM_BITS


def load_hex_file(file_path: Path) -> List[int]:
    """加载hex文件，转为有符号整数列表"""
    samples = []
    for line in file_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # 24位hex转有符号
        val = int(line, 16)
        if val >= (1 << (PCM_BITS - 1)):
            val -= (1 << PCM_BITS)
        samples.append(val)
    return samples


def compare_samples(reference: List[int], rtl_output: List[int],
                   tolerance: int = 0) -> Tuple[bool, dict]:
    """逐样本对比参考输出和RTL输出

    Args:
        reference: Python参考输出
        rtl_output: RTL仿真/上板输出
        tolerance: 容差（LSB数）

    Returns:
        (是否通过, 统计信息)
    """
    if len(reference) != len(rtl_output):
        return False, {
            'error': 'length_mismatch',
            'ref_len': len(reference),
            'rtl_len': len(rtl_output)
        }

    mismatches = []
    max_error = 0

    for i, (ref, rtl) in enumerate(zip(reference, rtl_output)):
        error = abs(ref - rtl)
        if error > max_error:
            max_error = error

        if error > tolerance:
            mismatches.append({
                'index': i,
                'reference': ref,
                'rtl': rtl,
                'error': error
            })

    passed = len(mismatches) == 0

    stats = {
        'total_samples': len(reference),
        'mismatches': len(mismatches),
        'max_error': max_error,
        'pass_rate': (1 - len(mismatches) / len(reference)) * 100,
        'first_mismatch': mismatches[0] if mismatches else None
    }

    return passed, stats


def verify_mixer_rtl(rtl_output_dir: Path, reference_dir: Path,
                     tolerance: int = 0) -> bool:
    """验证混音器RTL输出

    Args:
        rtl_output_dir: RTL输出目录（包含mixer_rtl_outputs.txt）
        reference_dir: Python参考目录（包含mixer_outputs.txt）
        tolerance: 容差
    """
    print("=" * 70)
    print("混音器RTL验证")
    print("=" * 70)

    # 加载文件
    ref_file = reference_dir / "mixer_outputs.txt"
    rtl_file = rtl_output_dir / "mixer_rtl_outputs.txt"

    if not ref_file.exists():
        print(f"[错误] 参考文件不存在: {ref_file}")
        return False

    if not rtl_file.exists():
        print(f"[错误] RTL输出文件不存在: {rtl_file}")
        return False

    print(f"参考文件: {ref_file}")
    print(f"RTL文件: {rtl_file}")
    print()

    # 加载数据
    reference = load_hex_file(ref_file)
    rtl_output = load_hex_file(rtl_file)

    print(f"参考样本数: {len(reference)}")
    print(f"RTL样本数: {len(rtl_output)}")
    print(f"容差: {tolerance} LSB")
    print()

    # 对比
    passed, stats = compare_samples(reference, rtl_output, tolerance)

    print("=" * 70)
    print("验证结果")
    print("=" * 70)
    print(f"总样本数: {stats['total_samples']}")
    print(f"失配数: {stats['mismatches']}")
    print(f"通过率: {stats['pass_rate']:.2f}%")
    print(f"最大误差: {stats['max_error']} LSB")

    if not passed:
        print()
        print("首个失配:")
        m = stats['first_mismatch']
        print(f"  索引: {m['index']}")
        print(f"  参考: {m['reference']:8d} (0x{m['reference'] & 0xFFFFFF:06x})")
        print(f"  RTL:  {m['rtl']:8d} (0x{m['rtl'] & 0xFFFFFF:06x})")
        print(f"  误差: {m['error']} LSB")

    print()
    if passed:
        print("[✓ PASS] RTL输出与Python参考完全一致")
    else:
        print("[✗ FAIL] RTL输出与参考不匹配")

    return passed


def verify_dds_rtl(rtl_output_file: Path, reference_file: Path,
                   tolerance: int = 1) -> bool:
    """验证DDS RTL输出（允许1 LSB舍入误差）"""
    print("=" * 70)
    print("DDS RTL验证")
    print("=" * 70)

    reference = load_hex_file(reference_file)
    rtl_output = load_hex_file(rtl_output_file)

    passed, stats = compare_samples(reference, rtl_output, tolerance)

    print(f"总样本数: {stats['total_samples']}")
    print(f"失配数: {stats['mismatches']}")
    print(f"通过率: {stats['pass_rate']:.2f}%")
    print(f"最大误差: {stats['max_error']} LSB")
    print()

    if passed:
        print("[✓ PASS] DDS RTL验证通过")
    else:
        print(f"[✗ FAIL] 失配率 {100 - stats['pass_rate']:.2f}%")

    return passed


if __name__ == "__main__":
    # 示例：验证混音器
    ref_dir = SCRIPT_DIR / "generated" / "mixer"
    rtl_dir = Path("rtl_outputs")  # RTL输出目录（需M2提供）

    if rtl_dir.exists():
        verify_mixer_rtl(rtl_dir, ref_dir, tolerance=0)
    else:
        print(f"RTL输出目录不存在: {rtl_dir}")
        print("此工具需要M2提供RTL仿真输出后使用")
        print()
        print("使用方法:")
        print("  python rtl_verifier.py")
        print()
        print("期望的RTL输出文件:")
        print("  rtl_outputs/mixer_rtl_outputs.txt")
