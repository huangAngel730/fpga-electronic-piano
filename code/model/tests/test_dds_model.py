# -*- coding: utf-8 -*-
"""T002 DDS 参考模型自检。

覆盖 ``code/docs/测试验收标准.md`` 要求的四类场景：复位过程、正常流程、
边界条件和异常场景。全部断言自动判定，不依赖看波形。

运行方式见 ``code/model/README.md``；推荐用 ``tests/run_all.py`` 一次跑完。
"""

import sys
import unittest
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1]
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from analysis import (  # noqa: E402
    estimate_frequency,
    fit_sinusoid,
    thd_dbc,
)
from audio_defs import (  # noqa: E402
    FCW_QUANT_ERROR_MAX_CENT,
    FREQ_ERROR_SPEC_CENT,
    GAIN_Q15_ONE,
    MIDI_NOTE_MAX,
    MIDI_NOTE_MIN,
    PCM_BITS,
    PCM_DC_OFFSET_MAX_LSB,
    PCM_FULL_SCALE_FROM_WT,
    PCM_MAX,
    PCM_MIN,
    PHASE_BITS,
    PHASE_MODULO,
    SAMPLE_RATE_HZ,
    SINE_SINAD_SPEC_DB,
    SINE_THD_SPEC_DBC,
    WT_ADDR_BITS,
    WT_AMPLITUDE,
    WT_LENGTH,
    WT_SAMPLE_BITS,
    WT_SAMPLE_MAX,
    WT_SAMPLE_MIN,
    cents_between,
    div_round_half_away_from_zero,
    round_half_away_from_zero,
)
from dds_model import (  # noqa: E402
    WavetableOscillator,
    build_note_table,
    fcw_to_freq,
    freq_to_fcw,
    make_saw_table,
    make_sine_table,
    make_square_table,
    make_wavetable,
    midi_note_to_fcw,
    midi_note_to_freq,
    midi_note_name,
    render_pcm24,
    wt16_to_pcm24,
)

#: 频谱类测试的样本数。341 ms，440 Hz 下约 150 个周期，
#: 两段相位差法的分支间隔 fs/8192 = 5.86 Hz，远大于任何可能的频率偏差。
ANALYSIS_SAMPLE_COUNT = 16384

#: THD 统计到第几次谐波。10 次谐波在 440 Hz 下到 4.4 kHz，覆盖听感敏感区。
THD_MAX_HARMONIC = 10


def _report(label: str, text: str) -> None:
    """打印实测值。测试不只给 PASS，还要留下可以写进报告和验证记录的数据。"""
    print(f"    [数据] {label}: {text}")


class TestFrozenConstants(unittest.TestCase):
    """接口 v1.0 冻结项不得被本目录改动。"""

    def test_interface_v1_values(self):
        self.assertEqual(SAMPLE_RATE_HZ, 48_000)
        self.assertEqual(PCM_BITS, 24)
        self.assertEqual(PCM_MAX, 8_388_607)
        self.assertEqual(PCM_MIN, -8_388_608)
        self.assertEqual(MIDI_NOTE_MIN, 0)
        self.assertEqual(MIDI_NOTE_MAX, 127)

    def test_m1_fixed_point_format(self):
        self.assertEqual(PHASE_BITS, 32)
        self.assertEqual(PHASE_MODULO, 1 << 32)
        self.assertEqual(WT_SAMPLE_BITS, 16)
        self.assertEqual(WT_ADDR_BITS, 10)
        self.assertEqual(WT_LENGTH, 1024)
        self.assertEqual(WT_AMPLITUDE, 32_767)
        self.assertEqual(PCM_FULL_SCALE_FROM_WT, 8_388_352)


class TestFixedPointPrimitives(unittest.TestCase):
    """舍入与限幅基元。写错方向会让后面所有逐样本比较系统性偏一个 LSB。"""

    def test_round_half_away_from_zero(self):
        cases = {
            0.0: 0,
            0.4: 0,
            0.5: 1,
            1.5: 2,
            2.5: 3,  # 内置 round 会给 2，这正是不能用内置 round 的原因
            -0.5: -1,
            -1.5: -2,
            -2.5: -3,
            -0.4: 0,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(round_half_away_from_zero(value), expected)

    def test_div_round_half_away_from_zero(self):
        cases = {
            (1, 2): 1,
            (-1, 2): -1,
            (3, 2): 2,
            (-3, 2): -2,
            (5, 2): 3,
            (-5, 2): -3,
            (0, 7): 0,
            (7, 7): 1,
        }
        for (num, den), expected in cases.items():
            with self.subTest(num=num, den=den):
                self.assertEqual(
                    div_round_half_away_from_zero(num, den), expected
                )

    def test_div_rejects_non_positive_denominator(self):
        with self.assertRaises(ValueError):
            div_round_half_away_from_zero(1, 0)


class TestNoteToFrequency(unittest.TestCase):
    """MIDI 音符号到频率的换算。"""

    def test_reference_points(self):
        self.assertEqual(midi_note_to_freq(69), 440.0)
        self.assertAlmostEqual(midi_note_to_freq(57), 220.0, places=9)
        self.assertAlmostEqual(midi_note_to_freq(81), 880.0, places=9)
        self.assertAlmostEqual(midi_note_to_freq(60), 261.625565300599, places=9)

    def test_octave_relation_holds_for_all_notes(self):
        for note in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX + 1 - 12):
            with self.subTest(note=note):
                self.assertAlmostEqual(
                    midi_note_to_freq(note + 12) / midi_note_to_freq(note),
                    2.0,
                    places=12,
                )

    def test_note_names(self):
        self.assertEqual(midi_note_name(60), "C4")
        self.assertEqual(midi_note_name(69), "A4")
        self.assertEqual(midi_note_name(21), "A0")

    def test_rejects_out_of_range_and_wrong_type(self):
        for bad in (-1, 128, 1000):
            with self.subTest(note=bad), self.assertRaises(ValueError):
                midi_note_to_freq(bad)
        for bad in (60.0, "60", None, True):
            with self.subTest(note=bad), self.assertRaises(TypeError):
                midi_note_to_freq(bad)


class TestFrequencyControlWord(unittest.TestCase):
    """FCW 换算与量化误差。这一项直接决定 T002 的验收条件。"""

    def test_known_values(self):
        self.assertEqual(freq_to_fcw(0.0), 0)
        self.assertEqual(freq_to_fcw(SAMPLE_RATE_HZ / 4), 1 << 30)
        self.assertEqual(freq_to_fcw(440.0), 39_370_534)

    def test_round_trip(self):
        for fcw in (0, 1, 39_370_534, (1 << 30), PHASE_MODULO - 1):
            with self.subTest(fcw=fcw):
                self.assertEqual(
                    freq_to_fcw(
                        fcw_to_freq(fcw), allow_above_nyquist=True
                    ),
                    fcw,
                )

    def test_all_midi_notes_within_quantisation_spec(self):
        reports = build_note_table()
        self.assertEqual(len(reports), 128)
        worst = max(reports, key=lambda item: abs(item.error_cent))
        _report(
            "FCW 量化最坏音分误差",
            f"MIDI {worst.note} {midi_note_name(worst.note)} "
            f"{worst.ideal_hz:.6f} Hz -> {worst.actual_hz:.6f} Hz，"
            f"{worst.error_cent:+.3e} 音分（阈值 {FCW_QUANT_ERROR_MAX_CENT} 音分）",
        )
        for report in reports:
            with self.subTest(note=report.note):
                self.assertLessEqual(
                    abs(report.error_cent), FCW_QUANT_ERROR_MAX_CENT
                )

    def test_a4_fcw_matches_hand_calculation(self):
        fcw = midi_note_to_fcw(69)
        expected = round_half_away_from_zero(440.0 * (1 << 32) / 48_000)
        self.assertEqual(fcw, expected)
        _report(
            "A4 频率控制字",
            f"0x{fcw:08x} = {fcw}，实际频率 {fcw_to_freq(fcw):.9f} Hz，"
            f"误差 {cents_between(fcw_to_freq(fcw), 440.0):+.3e} 音分",
        )

    def test_rejects_negative_and_nyquist(self):
        with self.assertRaises(ValueError):
            freq_to_fcw(-1.0)
        with self.assertRaises(ValueError):
            freq_to_fcw(SAMPLE_RATE_HZ / 2)
        with self.assertRaises(ValueError):
            freq_to_fcw(SAMPLE_RATE_HZ)
        # 显式允许时不报错，用于混叠实验
        self.assertGreater(
            freq_to_fcw(SAMPLE_RATE_HZ / 2 + 1.0, allow_above_nyquist=True), 0
        )

    def test_rejects_out_of_range_fcw(self):
        for bad in (-1, PHASE_MODULO):
            with self.subTest(fcw=bad), self.assertRaises(ValueError):
                fcw_to_freq(bad)


class TestWavetables(unittest.TestCase):
    """波表内容与边界。"""

    def test_common_properties(self):
        for name in ("sine", "square", "saw"):
            with self.subTest(waveform=name):
                table = make_wavetable(name)
                self.assertEqual(len(table), WT_LENGTH)
                self.assertTrue(all(isinstance(v, int) for v in table))
                self.assertGreaterEqual(min(table), WT_SAMPLE_MIN)
                self.assertLessEqual(max(table), WT_SAMPLE_MAX)

    def test_sine_shape_and_symmetry(self):
        table = make_sine_table()
        self.assertEqual(table[0], 0)
        self.assertEqual(table[WT_LENGTH // 4], WT_AMPLITUDE)
        self.assertEqual(table[WT_LENGTH // 2], 0)
        self.assertEqual(table[3 * WT_LENGTH // 4], -WT_AMPLITUDE)
        half = WT_LENGTH // 2
        for i in range(half):
            with self.subTest(index=i):
                self.assertEqual(table[i + half], -table[i])

    def test_square_shape(self):
        table = make_square_table()
        half = WT_LENGTH // 2
        self.assertTrue(all(v == WT_AMPLITUDE for v in table[:half]))
        self.assertTrue(all(v == -WT_AMPLITUDE for v in table[half:]))
        self.assertEqual(sum(table), 0)

    def test_saw_shape(self):
        table = make_saw_table()
        self.assertEqual(table[0], -WT_AMPLITUDE)
        self.assertEqual(table[WT_LENGTH // 2], 0)
        for i in range(WT_LENGTH - 1):
            with self.subTest(index=i):
                self.assertLessEqual(table[i], table[i + 1])
        self.assertLess(table[-1], WT_AMPLITUDE)

    def test_rejects_unknown_waveform_and_bad_length(self):
        with self.assertRaises(ValueError):
            make_wavetable("triangle")
        with self.assertRaises(ValueError):
            make_sine_table(length=1000)  # 不是 2 的幂
        with self.assertRaises(ValueError):
            make_sine_table(length=2)  # 太短


class TestOscillator(unittest.TestCase):
    """相位累加器行为，含复位过程。"""

    def setUp(self):
        self.table = make_sine_table()

    def test_reset_clears_phase_and_first_sample(self):
        osc = WavetableOscillator(self.table, fcw=freq_to_fcw(440.0))
        self.assertEqual(osc.phase, 0)
        self.assertEqual(osc.step(), self.table[0])
        osc.render(100)
        self.assertNotEqual(osc.phase, 0)
        osc.reset()
        self.assertEqual(osc.phase, 0)
        self.assertEqual(osc.step(), self.table[0])

    def test_sample_taken_before_phase_increment(self):
        """先取样后累加。这一条错了，逐样本比较会整体错一拍。"""
        fcw = freq_to_fcw(440.0)
        osc = WavetableOscillator(self.table, fcw=fcw)
        first = osc.step()
        self.assertEqual(first, self.table[0])
        self.assertEqual(osc.phase, fcw)

    def test_phase_accumulates_and_wraps(self):
        fcw = 0x4000_0001
        osc = WavetableOscillator(self.table, fcw=fcw)
        for step_index in range(1, 9):
            osc.step()
            with self.subTest(step=step_index):
                self.assertEqual(osc.phase, (step_index * fcw) % PHASE_MODULO)
        self.assertLess(osc.phase, PHASE_MODULO)
        # 8 * 0x40000001 已经绕过 2**32 两次，确认确实发生了回绕
        self.assertLess(osc.phase, 8 * fcw)

    def test_zero_fcw_holds_dc(self):
        osc = WavetableOscillator(self.table, fcw=0)
        self.assertEqual(set(osc.render(64)), {self.table[0]})

    def test_start_phase_and_range_check(self):
        osc = WavetableOscillator(self.table, fcw=0, start_phase=1 << 31)
        self.assertEqual(osc.step(), self.table[WT_LENGTH // 2])
        with self.assertRaises(ValueError):
            WavetableOscillator(self.table, start_phase=PHASE_MODULO)
        with self.assertRaises(ValueError):
            WavetableOscillator(self.table, fcw=-1)

    def test_interpolation_matches_truncation_on_table_grid(self):
        """相位小数部分为 0 时，插值与截断必须给出同一个样本。"""
        fcw = 1 << 22  # 每步正好走一个表地址
        trunc = WavetableOscillator(self.table, fcw=fcw, interpolate=False)
        interp = WavetableOscillator(self.table, fcw=fcw, interpolate=True)
        self.assertEqual(trunc.render(WT_LENGTH), interp.render(WT_LENGTH))


class TestPcmConversion(unittest.TestCase):
    """16 位波表样本到 24 位 PCM，含限幅异常场景。"""

    def test_unity_gain_is_exact_shift(self):
        for sample in (0, 1, -1, WT_SAMPLE_MAX, WT_SAMPLE_MIN):
            with self.subTest(sample=sample):
                pcm, clipped = wt16_to_pcm24(sample)
                self.assertEqual(pcm, sample * 256)
                self.assertFalse(clipped)

    def test_full_scale_stays_in_range(self):
        pcm, clipped = wt16_to_pcm24(WT_SAMPLE_MAX)
        self.assertEqual(pcm, PCM_FULL_SCALE_FROM_WT)
        self.assertFalse(clipped)
        self.assertLessEqual(pcm, PCM_MAX)
        pcm, clipped = wt16_to_pcm24(WT_SAMPLE_MIN)
        self.assertEqual(pcm, -8_388_608)
        self.assertEqual(pcm, PCM_MIN)
        self.assertFalse(clipped)

    def test_gain_rounds_half_away_from_zero(self):
        # 增益 1/32768 时，输入 128 对应 128*256/32768 = 1.0
        self.assertEqual(wt16_to_pcm24(128, gain_q15=1)[0], 1)
        # 输入 64 对应 0.5，半值远离零应得 1 而不是 0
        self.assertEqual(wt16_to_pcm24(64, gain_q15=1)[0], 1)
        self.assertEqual(wt16_to_pcm24(-64, gain_q15=1)[0], -1)

    def test_half_gain_is_exact(self):
        for sample in (WT_SAMPLE_MAX, -12_345, 7):
            with self.subTest(sample=sample):
                full = wt16_to_pcm24(sample)[0]
                half = wt16_to_pcm24(sample, gain_q15=GAIN_Q15_ONE // 2)[0]
                self.assertEqual(half * 2, full)

    def test_overdrive_saturates_and_counts_clipping(self):
        """异常场景：增益 2.0 让满幅正弦超出 24 位范围。

        必须饱和限幅并计数，绝不允许回绕。回绕在音频上表现为剧烈爆音，
        是这条链路最危险的失效模式。
        """
        result = render_pcm24(
            "sine", 440.0, 2048, gain_q15=GAIN_Q15_ONE * 2
        )
        self.assertGreater(result.clip_count, 0)
        self.assertLessEqual(max(result.pcm), PCM_MAX)
        self.assertGreaterEqual(min(result.pcm), PCM_MIN)
        _report(
            "增益 2.0 满幅正弦削波",
            f"2048 个样本中削波 {result.clip_count} 个，"
            f"输出范围 [{min(result.pcm)}, {max(result.pcm)}]，无回绕",
        )

    def test_rejects_negative_gain(self):
        with self.assertRaises(ValueError):
            wt16_to_pcm24(100, gain_q15=-1)


class TestRenderedWaveformQuality(unittest.TestCase):
    """对生成的 PCM 做实测：频率、信纳比、谐波失真、直流偏置。"""

    @classmethod
    def setUpClass(cls):
        cls.sine = render_pcm24("sine", 440.0, ANALYSIS_SAMPLE_COUNT)
        cls.sine_interp = render_pcm24(
            "sine", 440.0, ANALYSIS_SAMPLE_COUNT, interpolate=True
        )

    def _measure(self, pcm, label):
        measured = estimate_frequency(pcm, SAMPLE_RATE_HZ, 440.0)
        error_cent = cents_between(measured, 440.0)
        _report(
            f"{label} 实测频率",
            f"{measured:.6f} Hz，相对 440 Hz 误差 {error_cent:+.5f} 音分"
            f"（阈值 {FREQ_ERROR_SPEC_CENT} 音分）",
        )
        self.assertLessEqual(abs(error_cent), FREQ_ERROR_SPEC_CENT)
        return measured

    def test_440hz_sine_frequency(self):
        self._measure(self.sine.pcm, "正弦 440 Hz")

    def test_square_and_saw_frequency(self):
        for name in ("square", "saw"):
            with self.subTest(waveform=name):
                result = render_pcm24(name, 440.0, ANALYSIS_SAMPLE_COUNT)
                self._measure(result.pcm, f"{name} 440 Hz")

    def test_low_and_high_note_frequency(self):
        """边界条件：最低可用音与高音区各测一个。"""
        for note in (21, 108):  # 钢琴 88 键的两端 A0 与 C8
            with self.subTest(note=note):
                ideal = midi_note_to_freq(note)
                result = render_pcm24("sine", ideal, ANALYSIS_SAMPLE_COUNT)
                measured = estimate_frequency(
                    result.pcm, SAMPLE_RATE_HZ, ideal
                )
                error_cent = cents_between(measured, ideal)
                _report(
                    f"MIDI {note} {midi_note_name(note)} 实测频率",
                    f"理想 {ideal:.4f} Hz，实测 {measured:.4f} Hz，"
                    f"误差 {error_cent:+.5f} 音分",
                )
                self.assertLessEqual(abs(error_cent), FREQ_ERROR_SPEC_CENT)

    def test_sine_sinad_and_thd(self):
        measured = estimate_frequency(self.sine.pcm, SAMPLE_RATE_HZ, 440.0)
        fit = fit_sinusoid(self.sine.pcm, measured)
        thd = thd_dbc(
            self.sine.pcm, measured, SAMPLE_RATE_HZ, THD_MAX_HARMONIC
        )
        _report(
            "正弦 v1（相位截断）",
            f"SINAD {fit.sinad_db:.2f} dB（阈值 {SINE_SINAD_SPEC_DB} dB，"
            f"理论 6.02*{WT_ADDR_BITS}-3.92 = 56.3 dB），"
            f"THD {thd:.2f} dBc（阈值 {SINE_THD_SPEC_DBC} dBc），"
            f"直流偏置 {fit.dc:+.3f} LSB",
        )
        self.assertGreaterEqual(fit.sinad_db, SINE_SINAD_SPEC_DB)
        self.assertLessEqual(thd, SINE_THD_SPEC_DBC)
        self.assertLessEqual(abs(fit.dc), PCM_DC_OFFSET_MAX_LSB)

    def test_interpolation_gain_is_recorded(self):
        """记录线性插值的收益，作为 T004 是否上插值的决策依据。

        断言只要求插值不比截断差，具体数值打印出来供资源与音质权衡。
        """
        base = fit_sinusoid(
            self.sine.pcm,
            estimate_frequency(self.sine.pcm, SAMPLE_RATE_HZ, 440.0),
        )
        interp = fit_sinusoid(
            self.sine_interp.pcm,
            estimate_frequency(self.sine_interp.pcm, SAMPLE_RATE_HZ, 440.0),
        )
        _report(
            "线性插值收益",
            f"截断 SINAD {base.sinad_db:.2f} dB -> "
            f"插值 SINAD {interp.sinad_db:.2f} dB，"
            f"提升 {interp.sinad_db - base.sinad_db:.2f} dB",
        )
        self.assertGreater(interp.sinad_db, base.sinad_db)

    def test_no_clipping_at_unity_gain(self):
        self.assertEqual(self.sine.clip_count, 0)
        self.assertLessEqual(max(self.sine.pcm), PCM_FULL_SCALE_FROM_WT)
        self.assertGreaterEqual(min(self.sine.pcm), -PCM_FULL_SCALE_FROM_WT)

    def test_rendering_is_deterministic(self):
        again = render_pcm24("sine", 440.0, 1024)
        self.assertEqual(again.pcm, self.sine.pcm[:1024])


if __name__ == "__main__":
    unittest.main(verbosity=2)
