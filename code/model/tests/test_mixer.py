#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T023 混音器单元测试

完整的测试套件，包括：
1. 边界条件测试
2. 随机输入测试
3. 对称性测试
4. 信号质量测试
5. RTL对比向量生成

对应任务：T023 宽位混音器与饱和限幅
"""

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from mixer import mix_voices, mix_voices_batch, calculate_required_bits, estimate_headroom_db
from audio_defs import PCM_MAX, PCM_MIN, PCM_BITS
from dds_model import WavetableOscillator, make_wavetable, freq_to_fcw, SAMPLE_RATE_HZ


class TestMixerBoundary(unittest.TestCase):
    """边界条件测试"""

    def test_empty_input(self):
        """空输入应返回静音"""
        out, clipped = mix_voices([])
        self.assertEqual(out, 0)
        self.assertFalse(clipped)

    def test_single_voice_full_scale(self):
        """单声部满幅不应削波"""
        # 波表定标后的满幅值
        full_scale = 32767 << 8  # 8388352
        out, clipped = mix_voices([full_scale])
        self.assertEqual(out, full_scale)
        self.assertFalse(clipped)

    def test_two_voices_full_scale_clips(self):
        """双声部满幅应削波"""
        full_scale = 32767 << 8
        out, clipped = mix_voices([full_scale, full_scale])
        self.assertEqual(out, PCM_MAX)
        self.assertTrue(clipped)

    def test_four_voices_positive_full_scale(self):
        """4声部正满幅应削波到PCM_MAX"""
        full_scale = 32767 << 8
        out, clipped = mix_voices([full_scale] * 4)
        self.assertEqual(out, PCM_MAX)
        self.assertTrue(clipped)

    def test_four_voices_negative_full_scale(self):
        """4声部负满幅应削波到PCM_MIN"""
        full_scale = -(32767 << 8)
        out, clipped = mix_voices([full_scale] * 4)
        self.assertEqual(out, PCM_MIN)
        self.assertTrue(clipped)

    def test_opposite_signs_cancel(self):
        """正负相等应抵消"""
        value = 5000000
        out, clipped = mix_voices([value, -value])
        self.assertEqual(out, 0)
        self.assertFalse(clipped)

    def test_all_zeros(self):
        """全零输入"""
        out, clipped = mix_voices([0, 0, 0, 0])
        self.assertEqual(out, 0)
        self.assertFalse(clipped)

    def test_mixed_signs_no_clip(self):
        """混合符号但不削波"""
        out, clipped = mix_voices([4000000, -3000000, 2000000, -1000000])
        self.assertEqual(out, 2000000)
        self.assertFalse(clipped)

    def test_pcm_max_boundary(self):
        """边界：刚好等于PCM_MAX"""
        out, clipped = mix_voices([PCM_MAX])
        self.assertEqual(out, PCM_MAX)
        self.assertFalse(clipped)

    def test_pcm_min_boundary(self):
        """边界：刚好等于PCM_MIN"""
        out, clipped = mix_voices([PCM_MIN])
        self.assertEqual(out, PCM_MIN)
        self.assertFalse(clipped)

    def test_just_over_max(self):
        """刚超过PCM_MAX应削波"""
        out, clipped = mix_voices([PCM_MAX - 1, 2])
        self.assertEqual(out, PCM_MAX)
        self.assertTrue(clipped)

    def test_just_under_min(self):
        """刚低于PCM_MIN应削波"""
        out, clipped = mix_voices([PCM_MIN + 1, -2])
        self.assertEqual(out, PCM_MIN)
        self.assertTrue(clipped)


class TestMixerRandom(unittest.TestCase):
    """随机输入测试"""

    def test_random_inputs_no_wraparound(self):
        """随机输入：验证无回绕，只有饱和"""
        import random
        random.seed(42)

        num_tests = 1000
        for _ in range(num_tests):
            # 生成4个随机PCM样本
            voices = [random.randint(PCM_MIN, PCM_MAX) for _ in range(4)]
            out, clipped = mix_voices(voices)

            # 验证输出在范围内
            self.assertGreaterEqual(out, PCM_MIN, f"输出{out}低于PCM_MIN，输入={voices}")
            self.assertLessEqual(out, PCM_MAX, f"输出{out}高于PCM_MAX，输入={voices}")

            # 验证削波标志的正确性
            expected_sum = sum(voices)
            should_clip = (expected_sum > PCM_MAX) or (expected_sum < PCM_MIN)
            self.assertEqual(clipped, should_clip,
                           f"削波标志错误：sum={expected_sum}, clipped={clipped}, 输入={voices}")

    def test_random_small_values_never_clip(self):
        """小幅度随机值不应削波"""
        import random
        random.seed(123)

        # 每路最多25%满幅，4路相加不会超过100%
        max_per_voice = PCM_MAX // 4

        for _ in range(100):
            voices = [random.randint(-max_per_voice, max_per_voice) for _ in range(4)]
            out, clipped = mix_voices(voices)
            self.assertFalse(clipped, f"小幅度不应削波，输入={voices}")


class TestMixerProperties(unittest.TestCase):
    """数学性质测试"""

    def test_commutative(self):
        """交换律：mix(A,B) = mix(B,A)"""
        samples = [1000000, 2000000, 3000000, 4000000]
        import itertools

        # 测试几种排列
        permutations = list(itertools.permutations(samples))[:10]
        results = set()

        for perm in permutations:
            out, _ = mix_voices(list(perm))
            results.add(out)

        # 所有排列应该得到相同结果
        self.assertEqual(len(results), 1, "不同排列应得到相同结果")

    def test_identity(self):
        """单位元：mix(x, 0) = x"""
        value = 3000000
        out, _ = mix_voices([value, 0])
        self.assertEqual(out, value)

    def test_inverse(self):
        """逆元：mix(x, -x) = 0"""
        value = 5000000
        out, _ = mix_voices([value, -value])
        self.assertEqual(out, 0)


class TestMixerSignalQuality(unittest.TestCase):
    """信号质量测试"""

    def test_four_sine_waves_no_clip(self):
        """4路正弦波混音，幅度设置为不削波"""
        # 每路25%满幅，4路相加刚好100%
        amplitude = (32767 << 8) // 4  # 约2097088

        # 生成4路440Hz正弦波，相位均匀分布
        freqs = [440.0] * 4
        phases = [0, 256, 512, 768]  # 相位均匀分布（对于1024点表）

        oscillators = []
        sine_table = make_wavetable('sine', 1024, 32767)

        for freq, phase in zip(freqs, phases):
            fcw = freq_to_fcw(freq, SAMPLE_RATE_HZ)
            osc = WavetableOscillator(table=sine_table, fcw=fcw, start_phase=phase << 22)
            oscillators.append(osc)

        # 生成100个样本
        num_samples = 100
        clip_count = 0

        for _ in range(num_samples):
            voices = []
            for osc in oscillators:
                sample = osc.step()
                # 定标到24位并缩放到25%
                pcm = (sample << 8) // 4
                voices.append(pcm)

            out, clipped = mix_voices(voices)
            if clipped:
                clip_count += 1

        # 25%幅度不应削波
        self.assertEqual(clip_count, 0, "25%幅度4路正弦不应削波")

    def test_four_sine_waves_with_clip(self):
        """4路满幅同相正弦波应削波"""
        amplitude = 32767 << 8  # 满幅

        oscillators = []
        sine_table = make_wavetable('sine', 1024, 32767)
        fcw = freq_to_fcw(440.0, SAMPLE_RATE_HZ)

        # 使用相同相位（同相）使其相加而不是抵消
        for phase in [0, 0, 0, 0]:  # 所有声部同相
            osc = WavetableOscillator(table=sine_table, fcw=fcw, start_phase=phase << 22)
            oscillators.append(osc)

        # 生成100个样本
        num_samples = 100
        clip_count = 0

        for _ in range(num_samples):
            voices = []
            for osc in oscillators:
                sample = osc.step()
                pcm = sample << 8  # 满幅定标
                voices.append(pcm)

            out, clipped = mix_voices(voices)
            if clipped:
                clip_count += 1

        # 同相满幅正弦应该有削波
        self.assertGreater(clip_count, 0, "满幅4路同相正弦应削波")


class TestMixerInputValidation(unittest.TestCase):
    """输入验证测试"""

    def test_reject_out_of_range_positive(self):
        """拒绝超出正向范围的输入"""
        with self.assertRaises(ValueError):
            mix_voices([PCM_MAX + 1])

    def test_reject_out_of_range_negative(self):
        """拒绝超出负向范围的输入"""
        with self.assertRaises(ValueError):
            mix_voices([PCM_MIN - 1])

    def test_reject_non_integer(self):
        """拒绝非整数输入"""
        with self.assertRaises(TypeError):
            mix_voices([1.5, 2.7])


class TestMixerUtilities(unittest.TestCase):
    """辅助函数测试"""

    def test_calculate_required_bits(self):
        """位宽计算正确性"""
        self.assertEqual(calculate_required_bits(2, 24), 25)
        self.assertEqual(calculate_required_bits(4, 24), 26)
        self.assertEqual(calculate_required_bits(8, 24), 27)
        self.assertEqual(calculate_required_bits(16, 24), 28)

    def test_estimate_headroom(self):
        """余量估算合理性"""
        # 4声部满幅相加会溢出4倍，对应-12dB
        headroom = estimate_headroom_db(4)
        self.assertAlmostEqual(headroom, -12.04, places=1)


# --------------------------------------------------------------------------
# 测试向量生成（供M2 RTL对比）
# --------------------------------------------------------------------------

def generate_test_vectors(output_dir: Path, num_vectors: int = 1000):
    """生成RTL对比测试向量

    生成格式：
    - inputs.txt: 每行4个十六进制数（4声部输入）
    - outputs.txt: 每行1个十六进制数（混音输出）
    - clipped.txt: 每行1个0/1（削波标志）
    """
    import random
    random.seed(2026)

    output_dir.mkdir(parents=True, exist_ok=True)

    input_lines = []
    output_lines = []
    clipped_lines = []

    # 生成测试向量
    for _ in range(num_vectors):
        # 随机生成4个声部
        voices = [random.randint(PCM_MIN, PCM_MAX) for _ in range(4)]
        out, clipped = mix_voices(voices)

        # 转为十六进制（24位）
        voices_hex = [f"{v & 0xFFFFFF:06x}" for v in voices]
        out_hex = f"{out & 0xFFFFFF:06x}"

        input_lines.append(" ".join(voices_hex))
        output_lines.append(out_hex)
        clipped_lines.append("1" if clipped else "0")

    # 写入文件
    (output_dir / "mixer_inputs.txt").write_text("\n".join(input_lines) + "\n", encoding="utf-8")
    (output_dir / "mixer_outputs.txt").write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    (output_dir / "mixer_clipped.txt").write_text("\n".join(clipped_lines) + "\n", encoding="utf-8")

    print(f"已生成{num_vectors}个测试向量到 {output_dir}")
    print(f"  - mixer_inputs.txt: 4声部输入")
    print(f"  - mixer_outputs.txt: 混音输出")
    print(f"  - mixer_clipped.txt: 削波标志")


# --------------------------------------------------------------------------
# 主函数
# --------------------------------------------------------------------------

if __name__ == "__main__":
    # 运行单元测试
    print("=" * 70)
    print("T023 混音器单元测试")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 70)
    print(f"测试结果: {result.testsRun} 运行, {len(result.failures)} 失败, {len(result.errors)} 错误")
    print("=" * 70)

    # 生成RTL对比向量
    if result.wasSuccessful():
        print()
        output_dir = SCRIPT_DIR.parent / "generated" / "mixer"
        generate_test_vectors(output_dir, num_vectors=1000)
        print()
        print("[PASS] 所有测试通过，RTL对比向量已生成")
    else:
        print()
        print("[FAIL] 部分测试失败，请修复后再生成向量")

    sys.exit(0 if result.wasSuccessful() else 1)
