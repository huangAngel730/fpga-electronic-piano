#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T009 DDS×ADSR 输出口径定义和验证

明确：
1. 满包络 32767 时的输出口径
2. 舍入方法
3. PCM 保留的小数精度
4. 正、负峰值和零包络的参考结果
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def apply_envelope_truncate(sample_s16: int, envelope_q15: int) -> int:
    """方案1：截断法（当前实现）

    (sample × envelope) >> 15
    满包络 32767 时：8192 → 8191
    """
    return (sample_s16 * envelope_q15) >> 15


def apply_envelope_round(sample_s16: int, envelope_q15: int) -> int:
    """方案2：四舍五入（备选，不建议）

    正数：((sample × envelope) + 16384) >> 15
    负数：((sample × envelope) - 16384) >> 15

    注意：Python的整数除法向负无穷取整，需要调整舍入逻辑
    """
    product = sample_s16 * envelope_q15
    if product >= 0:
        return (product + 16384) >> 15
    else:
        # 负数四舍五入：向零方向舍入
        return (product - 16384) >> 15


def test_output_specs():
    """测试并明确输出口径"""
    print("=" * 70)
    print("T009 DDS×ADSR 输出口径定义")
    print("=" * 70)

    # 测试场景
    test_cases = [
        ("正峰值 × 满包络", 8192, 32767),
        ("负峰值 × 满包络", -8192, 32767),
        ("零样本 × 满包络", 0, 32767),
        ("正峰值 × 半包络", 8192, 16384),
        ("正峰值 × 零包络", 8192, 0),
        ("最大正样本 × 满包络", 32767, 32767),
        ("最大负样本 × 满包络", -32768, 32767),
    ]

    print("\n方案1：截断法（右移，当前实现）")
    print("-" * 70)
    print(f"{'场景':<25} {'波形':<8} {'包络':<8} {'结果':<8} {'精确值':<12}")
    print("-" * 70)

    for desc, wave, env in test_cases:
        result = apply_envelope_truncate(wave, env)
        exact = (wave * env) / 32768.0
        print(f"{desc:<25} {wave:<8} {env:<8} {result:<8} {exact:<12.3f}")

    print("\n方案2：四舍五入（+16384 后右移）")
    print("-" * 70)
    print(f"{'场景':<25} {'波形':<8} {'包络':<8} {'结果':<8} {'精确值':<12}")
    print("-" * 70)

    for desc, wave, env in test_cases:
        result = apply_envelope_round(wave, env)
        exact = (wave * env) / 32768.0
        print(f"{desc:<25} {wave:<8} {env:<8} {result:<8} {exact:<12.3f}")

    print("\n" + "=" * 70)
    print("关键对比")
    print("=" * 70)

    # 关键场景：正峰值 × 满包络
    wave_peak = 8192
    env_full = 32767

    truncate_result = apply_envelope_truncate(wave_peak, env_full)
    round_result = apply_envelope_round(wave_peak, env_full)
    exact_value = (wave_peak * env_full) / 32768.0

    print(f"\n正峰值波形 8192 × 满包络 32767：")
    print(f"  精确值：{exact_value:.6f}")
    print(f"  截断法：{truncate_result} (损失 {exact_value - truncate_result:.6f})")
    print(f"  四舍五入：{round_result} (误差 {round_result - exact_value:.6f})")

    # 负峰值
    wave_neg = -8192
    truncate_neg = apply_envelope_truncate(wave_neg, env_full)
    round_neg = apply_envelope_round(wave_neg, env_full)
    exact_neg = (wave_neg * env_full) / 32768.0

    print(f"\n负峰值波形 -8192 × 满包络 32767：")
    print(f"  精确值：{exact_neg:.6f}")
    print(f"  截断法：{truncate_neg} (损失 {abs(exact_neg - truncate_neg):.6f})")
    print(f"  四舍五入：{round_neg} (误差 {abs(round_neg - exact_neg):.6f})")


def define_output_specification():
    """明确输出口径定义"""
    print("\n" + "=" * 70)
    print("输出口径定义（M1 建议）")
    print("=" * 70)

    print("\n一、数学定义")
    print("  PCM_out = (DDS_sample × ADSR_envelope) / 32768")
    print("  其中：")
    print("    - DDS_sample: 16位有符号 [-32768, 32767]")
    print("    - ADSR_envelope: Q1.15 无符号 [0, 32767]")
    print("    - PCM_out: 16位有符号 [-32768, 32767]")

    print("\n二、舍入方法（建议：截断法）")
    print("  实现：(sample × envelope) >> 15")
    print("  理由：")
    print("    1. 硬件简单，无额外加法器")
    print("    2. 与现有 Python 模型一致")
    print("    3. 误差可接受（最大 1 LSB）")
    print("    4. 满包络时：8192 → 8191 可接受")

    print("\n三、关键场景参考结果（截断法）")
    print("  场景                        波形      包络      输出")
    print("  " + "-" * 60)
    print("  正峰值 × 满包络            8192     32767     8191")
    print("  负峰值 × 满包络           -8192     32767    -8192")
    print("  零样本 × 满包络               0     32767        0")
    print("  正峰值 × 半包络            8192     16384     4096")
    print("  正峰值 × 零包络            8192         0        0")
    print("  最大正样本 × 满包络       32767     32767    32766")
    print("  最大负样本 × 满包络      -32768     32767   -32767")

    print("\n四、精度说明")
    print("  - 满包络非完全归一：32767/32768 ≈ 0.999969")
    print("  - 正峰值损失：8191.9999... → 8191 (损失 ~1 LSB)")
    print("  - 此误差在音频应用中不可闻")
    print("  - 若需精确 8192，改用四舍五入（+16384 后右移）")

    print("\n五、M1 建议")
    print("  采用截断法（当前实现）：")
    print("    - 保持与现有模型一致")
    print("    - 满包络 32767 时，正峰值 8192 → 8191")
    print("    - 接受非完全归一，误差 ≤1 LSB")
    print("    - RTL 实现：wire signed [31:0] pcm_out = (dds_sample * envelope) >>> 15;")

    print("\n六、替代方案（若需精确归一）")
    print("  四舍五入法：")
    print("    product = dds_sample * envelope;")
    print("    pcm_out = (product + (product >= 0 ? 16384 : -16384)) >>> 15;")
    print("    - 满包络时正峰值精确到 8192")
    print("    - 需额外加法器")


def test_reference_results_with_assertions():
    """测试并断言七个关键场景的参考结果"""
    print("\n" + "=" * 70)
    print("七个关键场景断言测试（对照 apply_envelope）")
    print("=" * 70)

    from adsr_piano import apply_envelope

    # 七个关键场景及预期结果
    test_cases = [
        ("正峰值 × 满包络", 8192, 32767, 8191),
        ("负峰值 × 满包络", -8192, 32767, -8192),
        ("零样本 × 满包络", 0, 32767, 0),
        ("正峰值 × 半包络", 8192, 16384, 4096),
        ("正峰值 × 零包络", 8192, 0, 0),
        ("最大正样本 × 满包络", 32767, 32767, 32766),
        ("最大负样本 × 满包络", -32768, 32767, -32767),
    ]

    all_passed = True

    for desc, wave, env, expected in test_cases:
        actual = apply_envelope(wave, env)
        status = "✓ PASS" if actual == expected else "✗ FAIL"

        if actual != expected:
            all_passed = False

        print(f"{status} {desc:<25} wave={wave:<7} env={env:<7} 预期={expected:<7} 实际={actual}")

        # 断言
        assert actual == expected, f"{desc} 失败：预期 {expected}，实际 {actual}"

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ 所有七个关键场景断言通过")
        return 0
    else:
        print("✗ 部分场景断言失败")
        return 1


if __name__ == "__main__":
    test_output_specs()
    define_output_specification()

    # 运行断言测试
    exit_code = test_reference_results_with_assertions()

    print("\n" + "=" * 70)
    print("✓ 输出口径定义完成")
    print("=" * 70)

    sys.exit(exit_code)
