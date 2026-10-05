#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多声部混音器与饱和限幅 - Python参考实现（T023）

本模块提供混音算法的Python参考实现，用于：
1. 定义混音的数学规格（M1算法定义权）
2. 为RTL实现提供逐样本对比的黄金参考
3. 生成测试向量供M2的RTL验证

对应任务：T023 宽位混音器与饱和限幅
主负责人：M1
验收标准：满量程不溢出且逐样本PASS
"""

import sys
from pathlib import Path
from typing import List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import PCM_BITS, PCM_MAX, PCM_MIN, saturate_pcm24

# --------------------------------------------------------------------------
# 混音器参数（M1定义）
# --------------------------------------------------------------------------

#: 默认最大声部数（对应T010的4复音）
DEFAULT_MAX_VOICES = 4

#: 混音中间结果位宽（接口规范v1.2要求：不少于32位）
MIXER_ACCUM_BITS = 32

#: Python实现使用Python int（无位宽限制），但规格要求RTL必须用≥32位累加器
# 数学分析：4声部峰值 2097152 * 4 = 8388608 < 2^24，26位足够
# 但接口规范v1.2明确要求：累加器不少于32位
# RTL实现示例：logic signed [31:0] accumulator;
MIXER_ACCUM_MIN = -(1 << 31)  # -2147483648，32位有符号下界
MIXER_ACCUM_MAX = (1 << 31) - 1  # 2147483647，32位有符号上界


# --------------------------------------------------------------------------
# 核心混音函数
# --------------------------------------------------------------------------

def mix_voices(voice_samples: List[int]) -> Tuple[int, bool]:
    """多声部混音与饱和限幅

    这是T023的核心算法，定义混音的数学规格。RTL实现必须与本函数逐样本一致。

    算法：
        1. 将所有声部PCM相加（使用≥32位累加器，接口规范v1.2要求）
        2. 饱和限幅到24位PCM范围 [-8388608, 8388607]
        3. 返回混音结果和削波标志

    RTL实现要求：
        - 累加器位宽：不少于32位（logic signed [31:0] 或更宽）
        - Python用Python int（无限精度），等价于足够宽的累加器
        - 饱和比较在累加完成后进行

    参数：
        voice_samples: 声部输出列表，每个元素是24位有符号PCM
                      长度可变（0到任意值），但设计目标是4声部

    返回：
        (mixed_pcm, clipped)
        - mixed_pcm: 混音后的24位有符号PCM，保证在[PCM_MIN, PCM_MAX]内
        - clipped: 是否发生削波（True=发生削波，False=未削波）

    异常：
        ValueError: 如果任何输入样本超出24位PCM范围

    示例：
        >>> mix_voices([0, 0, 0, 0])
        (0, False)

        >>> mix_voices([8388352, 8388352])  # 双声部满幅
        (8388607, True)  # 限幅到PCM_MAX

        >>> mix_voices([4000000, -3000000, 2000000, -1000000])
        (2000000, False)  # 相加后在范围内
    """
    # 输入验证
    for i, sample in enumerate(voice_samples):
        if not isinstance(sample, int):
            raise TypeError(f"声部{i}样本必须是整数，收到 {type(sample)}")
        if not (PCM_MIN <= sample <= PCM_MAX):
            raise ValueError(
                f"声部{i}样本 {sample} 超出24位PCM范围 "
                f"[{PCM_MIN}, {PCM_MAX}]"
            )

    # 空输入返回静音
    if not voice_samples:
        return 0, False

    # 求和（Python的int类型无溢出，自动扩展）
    mix_sum = sum(voice_samples)

    # 饱和限幅到24位PCM范围
    mixed_pcm, clipped = saturate_pcm24(mix_sum)

    return mixed_pcm, clipped


def mix_voices_batch(
    voice_samples_array: List[List[int]]
) -> Tuple[List[int], List[bool], int]:
    """批量混音（用于测试和向量生成）

    参数：
        voice_samples_array: 每个元素是一组声部样本列表
                            例如：[[v0_s0, v1_s0], [v0_s1, v1_s1], ...]

    返回：
        (mixed_pcm_list, clipped_list, clip_count)
        - mixed_pcm_list: 每个时刻的混音输出
        - clipped_list: 每个时刻的削波标志
        - clip_count: 总削波次数
    """
    mixed_pcm_list = []
    clipped_list = []
    clip_count = 0

    for voice_samples in voice_samples_array:
        mixed_pcm, clipped = mix_voices(voice_samples)
        mixed_pcm_list.append(mixed_pcm)
        clipped_list.append(clipped)
        if clipped:
            clip_count += 1

    return mixed_pcm_list, clipped_list, clip_count


# --------------------------------------------------------------------------
# 辅助函数
# --------------------------------------------------------------------------

def estimate_headroom_db(num_voices: int, per_voice_peak: int = None) -> float:
    """估算给定声部数和单声部峰值下的余量

    参数：
        num_voices: 声部数
        per_voice_peak: 单声部峰值（默认为2097152，即D028冻结工作点）

    返回：
        余量（dB），正值表示不会削波
    """
    import math

    if per_voice_peak is None:
        # D028冻结工作点：8192 * 256 = 2097152
        per_voice_peak = 8192 << 8  # 2097152

    # 所有声部同时满幅的总和
    worst_case_sum = num_voices * per_voice_peak

    # 与24位满量程的比值
    headroom_linear = PCM_MAX / worst_case_sum

    # 转为dB
    headroom_db = 20 * math.log10(headroom_linear)

    return headroom_db


def calculate_required_bits(num_voices: int, per_voice_bits: int = 24) -> int:
    """计算N声部混音所需的累加器位宽

    参数：
        num_voices: 声部数
        per_voice_bits: 单声部位宽

    返回：
        所需的有符号位宽

    示例：
        >>> calculate_required_bits(4, 24)
        26  # 需要26位有符号
    """
    import math

    # 单声部最大绝对值
    per_voice_max = (1 << (per_voice_bits - 1)) - 1

    # N声部相加的最大绝对值
    total_max = num_voices * per_voice_max

    # 需要的位数（含符号位）
    required_bits = math.ceil(math.log2(total_max + 1)) + 1

    return required_bits


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------

def _self_check():
    """混音器自检，验证核心功能"""
    print("=" * 70)
    print("T023 混音器自检")
    print("=" * 70)
    print()

    test_cases = [
        # (输入, 期望输出, 期望削波, 描述)
        ([0, 0, 0, 0], 0, False, "全零输入"),
        ([8388352], 8388352, False, "单声部满幅"),
        ([8388352, 8388352], PCM_MAX, True, "双声部满幅（削波）"),
        ([8388352, 8388352, 8388352, 8388352], PCM_MAX, True, "4声部正满幅（削波）"),
        ([-8388352, -8388352, -8388352, -8388352], PCM_MIN, True, "4声部负满幅（削波）"),
        ([8388352, -8388352], 0, False, "正负抵消"),
        ([4000000, -3000000, 2000000, -1000000], 2000000, False, "混合符号"),
        ([1000000, 2000000, 3000000], 6000000, False, "三声部无削波"),
    ]

    passed = 0
    failed = 0

    for i, (inputs, expected_out, expected_clip, desc) in enumerate(test_cases, 1):
        try:
            actual_out, actual_clip = mix_voices(inputs)

            if actual_out == expected_out and actual_clip == expected_clip:
                status = "PASS"
                passed += 1
            else:
                status = "FAIL"
                failed += 1
                print(f"  [{status}] 用例{i}: {desc}")
                print(f"    输入: {inputs}")
                print(f"    期望: out={expected_out}, clip={expected_clip}")
                print(f"    实际: out={actual_out}, clip={actual_clip}")
                print()
        except Exception as e:
            status = "ERROR"
            failed += 1
            print(f"  [{status}] 用例{i}: {desc}")
            print(f"    异常: {e}")
            print()

    # 位宽计算验证
    print("-" * 70)
    print("位宽计算验证")
    print("-" * 70)
    for n in [2, 4, 8, 16]:
        required = calculate_required_bits(n, 24)
        headroom = estimate_headroom_db(n)
        print(f"  {n}声部: 需要{required}位, 余量{headroom:+.2f} dB")
    print()

    # 总结
    print("=" * 70)
    print(f"自检结果: {passed} PASS, {failed} FAIL")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    import sys
    success = _self_check()
    sys.exit(0 if success else 1)
