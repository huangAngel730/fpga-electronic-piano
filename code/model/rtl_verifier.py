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
    """加载hex文件，转为有符号整数列表

    支持格式：
    1. 纯hex（6位）：000000 到 FFFFFF
    2. 带0x前缀：0x000000
    3. 注释行以#开头，空行忽略

    Returns:
        有符号24位PCM样本列表

    Raises:
        ValueError: 文件格式错误
        FileNotFoundError: 文件不存在
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 检测BOM
    raw_bytes = file_path.read_bytes()
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        raise ValueError(f"文件包含UTF-8 BOM标记。请使用无BOM编码保存: {file_path}")

    samples = []
    line_num = 0

    for line in raw_bytes.decode('utf-8').splitlines():
        line_num += 1
        line = line.strip()

        # 跳过空行和注释
        if not line or line.startswith('#'):
            continue

        # 移除0x前缀
        if line.startswith('0x') or line.startswith('0X'):
            line = line[2:]

        # 验证hex格式
        if len(line) != 6:
            raise ValueError(f"行{line_num}: hex长度必须为6位，实际{len(line)}位: {line}")

        try:
            val = int(line, 16)
        except ValueError:
            raise ValueError(f"行{line_num}: 非法hex字符: {line}")

        # 24位有符号转换
        if val >= (1 << (PCM_BITS - 1)):
            val -= (1 << PCM_BITS)

        samples.append(val)

    if not samples:
        raise ValueError(f"文件为空或无有效数据: {file_path}")

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


def load_clipped_flags(file_path: Path) -> List[bool]:
    """加载削波标志文件

    格式：每行一个字符 '0' 或 '1'
    0 = 未削波, 1 = 已削波

    Returns:
        布尔值列表，True表示削波
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    flags = []
    line_num = 0

    for line in file_path.read_text(encoding='utf-8').splitlines():
        line_num += 1
        line = line.strip()

        if not line or line.startswith('#'):
            continue

        if line not in ('0', '1'):
            raise ValueError(f"行{line_num}: 削波标志必须为'0'或'1'，实际: {line}")

        flags.append(line == '1')

    if not flags:
        raise ValueError(f"文件为空或无有效数据: {file_path}")

    return flags


def verify_mixer_rtl(rtl_output_dir: Path, reference_dir: Path,
                     tolerance: int = 0) -> bool:
    """验证混音器RTL输出（包含PCM样本和削波标志）

    Args:
        rtl_output_dir: RTL输出目录（包含mixer_rtl_outputs.txt和mixer_rtl_clipped.txt）
        reference_dir: Python参考目录（包含mixer_outputs.txt和mixer_clipped.txt）
        tolerance: 容差（LSB数）

    Returns:
        True: 验证通过（PCM和削波标志都匹配）
        False: 验证失败

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式错误
    """
    print("=" * 70)
    print("混音器RTL验证")
    print("=" * 70)

    # 加载PCM文件
    ref_pcm_file = reference_dir / "mixer_outputs.txt"
    rtl_pcm_file = rtl_output_dir / "mixer_rtl_outputs.txt"

    # 加载削波标志文件
    ref_clip_file = reference_dir / "mixer_clipped.txt"
    rtl_clip_file = rtl_output_dir / "mixer_rtl_clipped.txt"

    print(f"参考PCM: {ref_pcm_file}")
    print(f"RTL PCM: {rtl_pcm_file}")
    print(f"参考削波: {ref_clip_file}")
    print(f"RTL削波: {rtl_clip_file}")
    print()

    try:
        ref_pcm = load_hex_file(ref_pcm_file)
        rtl_pcm = load_hex_file(rtl_pcm_file)
        ref_clip = load_clipped_flags(ref_clip_file)
        rtl_clip = load_clipped_flags(rtl_clip_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}")
        return False

    print(f"参考PCM样本数: {len(ref_pcm)}")
    print(f"RTL PCM样本数: {len(rtl_pcm)}")
    print(f"参考削波标志数: {len(ref_clip)}")
    print(f"RTL削波标志数: {len(rtl_clip)}")
    print(f"容差: {tolerance} LSB")
    print()

    # 对比PCM
    pcm_passed, pcm_stats = compare_samples(ref_pcm, rtl_pcm, tolerance)

    # 对比削波标志
    clip_passed = True
    clip_mismatches = []

    if len(ref_clip) != len(rtl_clip):
        print(f"[错误] 削波标志长度不一致: 参考{len(ref_clip)}, RTL{len(rtl_clip)}")
        clip_passed = False
    elif len(ref_clip) != len(ref_pcm):
        print(f"[错误] 削波标志数({len(ref_clip)})与PCM样本数({len(ref_pcm)})不一致")
        clip_passed = False
    else:
        for i, (ref, rtl) in enumerate(zip(ref_clip, rtl_clip)):
            if ref != rtl:
                clip_mismatches.append({
                    'index': i,
                    'reference': ref,
                    'rtl': rtl
                })
        clip_passed = len(clip_mismatches) == 0

    print("=" * 70)
    print("验证结果")
    print("=" * 70)

    # PCM结果
    if 'error' in pcm_stats:
        print(f"PCM长度不一致: 参考{pcm_stats['ref_len']}, RTL{pcm_stats['rtl_len']}")
        pcm_passed = False
    else:
        print(f"PCM总样本数: {pcm_stats['total_samples']}")
        print(f"PCM失配数: {pcm_stats['mismatches']}")
        print(f"PCM通过率: {pcm_stats['pass_rate']:.2f}%")
        print(f"PCM最大误差: {pcm_stats['max_error']} LSB")

        if not pcm_passed and pcm_stats['first_mismatch']:
            print()
            print("首个PCM失配:")
            m = pcm_stats['first_mismatch']
            print(f"  索引: {m['index']}")
            print(f"  参考: {m['reference']:8d} (0x{m['reference'] & 0xFFFFFF:06x})")
            print(f"  RTL:  {m['rtl']:8d} (0x{m['rtl'] & 0xFFFFFF:06x})")
            print(f"  误差: {m['error']} LSB")

    print()

    # 削波标志结果
    print(f"削波标志失配数: {len(clip_mismatches)}")
    if clip_mismatches:
        print("首个削波标志失配:")
        m = clip_mismatches[0]
        print(f"  索引: {m['index']}")
        print(f"  参考: {m['reference']}")
        print(f"  RTL:  {m['rtl']}")

    print()
    overall_pass = pcm_passed and clip_passed
    if overall_pass:
        print("[PASS] RTL输出与Python参考完全一致（PCM + 削波标志）")
    else:
        print("[FAIL] RTL输出与参考不匹配")
        if not pcm_passed:
            print("  - PCM不匹配")
        if not clip_passed:
            print("  - 削波标志不匹配")

    return overall_pass


def verify_dds_rtl(rtl_output_file: Path, reference_file: Path,
                   tolerance: int = 1) -> bool:
    """验证DDS RTL输出（允许1 LSB舍入误差）"""
    print("=" * 70)
    print("DDS RTL验证")
    print("=" * 70)

    try:
        reference = load_hex_file(reference_file)
        rtl_output = load_hex_file(rtl_output_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}")
        return False

    passed, stats = compare_samples(reference, rtl_output, tolerance)

    if 'error' in stats:
        print(f"长度不一致: 参考{stats['ref_len']}, RTL{stats['rtl_len']}")
        return False

    print(f"总样本数: {stats['total_samples']}")
    print(f"失配数: {stats['mismatches']}")
    print(f"通过率: {stats['pass_rate']:.2f}%")
    print(f"最大误差: {stats['max_error']} LSB")
    print()

    if passed:
        print("[PASS] DDS RTL验证通过")
    else:
        print(f"[FAIL] 失配率 {100 - stats['pass_rate']:.2f}%")

    return passed


if __name__ == "__main__":
    # 示例：验证混音器
    ref_dir = SCRIPT_DIR / "generated" / "mixer"
    rtl_dir = Path("rtl_outputs")  # RTL输出目录（需M2提供）

    print("RTL验证工具")
    print()

    if not rtl_dir.exists():
        print(f"RTL输出目录不存在: {rtl_dir}")
        print("此工具需要M2提供RTL仿真输出后使用")
        print()
        print("使用方法:")
        print("  1. M2将RTL输出保存为:")
        print("     - rtl_outputs/mixer_rtl_outputs.txt (PCM样本)")
        print("     - rtl_outputs/mixer_rtl_clipped.txt (削波标志)")
        print("  2. 运行: python rtl_verifier.py")
        print()
        print("hex文件格式要求:")
        print("  - PCM: 每行6位hex（000000-FFFFFF）")
        print("  - 削波标志: 每行一个字符'0'或'1'")
        print("  - 可选0x前缀")
        print("  - #开头为注释行")
        print("  - 空行忽略")
        sys.exit(1)
    else:
        try:
            result = verify_mixer_rtl(rtl_dir, ref_dir, tolerance=0)
            sys.exit(0 if result else 1)
        except Exception as e:
            print(f"[错误] 验证失败: {e}")
            sys.exit(1)
