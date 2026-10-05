# -*- coding: utf-8 -*-
"""DDS 黄金参考模型（T002）。

本模型是 ``code/rtl/audio/`` 下 DDS RTL（T004）的判定基准：RTL 必须与本模型
逐样本一致，不允许反过来按 RTL 结果修改本模型。

模型约定（与 RTL 必须一一对应）：

1. 相位累加器为 32 位无符号，每个 ``sample_tick`` 累加一次频率控制字 FCW，
   溢出自然回绕，等价于 mod 2**32。
2. **先取样、后累加**。第 n 个输出样本对应累加 n 次之前的相位，即复位后的
   第 0 个样本相位为 0。这一条决定逐样本比较时的对齐，改动即失配。
3. 表地址取相位高 ``WT_ADDR_BITS`` 位，v1 使用相位截断，不做插值。
   模型同时提供线性插值模式，仅用于评估升级收益，不是 v1 的判定基准。
4. 16 位波表样本左移 8 位得到 24 位 PCM，再按 Q1.15 增益缩放、
   半值远离零舍入、饱和限幅，禁止低位截断。

定点格式的完整说明见 ``code/docs/test/DDS参考模型与波表格式说明.md``。
"""

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

from audio_defs import (
    A4_HZ,
    A4_MIDI_NOTE,
    GAIN_Q15_ONE,
    MIDI_NOTE_MAX,
    MIDI_NOTE_MIN,
    PHASE_BITS,
    PHASE_MODULO,
    SAMPLE_RATE_HZ,
    SEMITONES_PER_OCTAVE,
    WT_AMPLITUDE,
    WT_LENGTH,
    WT_TO_PCM_SHIFT,
    cents_between,
    div_round_half_away_from_zero,
    round_half_away_from_zero,
    saturate_pcm24,
)

# --------------------------------------------------------------------------
# 音高与频率控制字换算
# --------------------------------------------------------------------------


def midi_note_to_freq(note: int, a4_hz: float = A4_HZ) -> float:
    """MIDI 音符号转频率，十二平均律。

    note 必须是 0 至 127 的整数，与事件接口 v1.0 的 7 位 ``note_number`` 一致。
    60 为中央 C，69 为 A4。
    """
    if isinstance(note, bool) or not isinstance(note, int):
        raise TypeError(f"note 必须是整数，收到 {type(note).__name__}")
    if not MIDI_NOTE_MIN <= note <= MIDI_NOTE_MAX:
        raise ValueError(
            f"note 必须在 [{MIDI_NOTE_MIN}, {MIDI_NOTE_MAX}]，收到 {note}"
        )
    return a4_hz * 2.0 ** ((note - A4_MIDI_NOTE) / SEMITONES_PER_OCTAVE)


def freq_to_fcw(
    freq_hz: float,
    sample_rate: int = SAMPLE_RATE_HZ,
    allow_above_nyquist: bool = False,
) -> int:
    """频率转 32 位频率控制字。

    FCW = round(f * 2**32 / fs)，半值远离零。

    超过奈奎斯特频率的输入默认报错，因为直接合成会产生混叠。确实要做混叠
    实验时显式传 ``allow_above_nyquist=True``。
    """
    if freq_hz < 0.0:
        raise ValueError(f"频率不能为负，收到 {freq_hz}")
    nyquist = sample_rate / 2.0
    if not allow_above_nyquist and freq_hz >= nyquist:
        raise ValueError(
            f"{freq_hz} Hz 达到或超过奈奎斯特频率 {nyquist} Hz，会产生混叠"
        )
    fcw = round_half_away_from_zero(freq_hz * PHASE_MODULO / sample_rate)
    if fcw >= PHASE_MODULO:
        raise ValueError(f"FCW {fcw} 溢出 {PHASE_MODULO}，频率过高")
    return fcw


def fcw_to_freq(fcw: int, sample_rate: int = SAMPLE_RATE_HZ) -> float:
    """频率控制字转实际输出频率。"""
    if not 0 <= fcw < PHASE_MODULO:
        raise ValueError(f"FCW {fcw} 超出 32 位无符号范围")
    return fcw * sample_rate / PHASE_MODULO


def midi_note_to_fcw(
    note: int, sample_rate: int = SAMPLE_RATE_HZ, a4_hz: float = A4_HZ
) -> int:
    """MIDI 音符号直接转频率控制字。"""
    return freq_to_fcw(midi_note_to_freq(note, a4_hz), sample_rate)


# --------------------------------------------------------------------------
# 波表生成
# --------------------------------------------------------------------------


def make_sine_table(
    length: int = WT_LENGTH, amplitude: int = WT_AMPLITUDE
) -> list[int]:
    """单周期正弦波表，16 位有符号。

    只计算前半周期，后半周期按奇对称取反填充，保证 ``t[i + N/2] == -t[i]``
    在数值上严格成立，而不是依赖 ``sin(x + pi)`` 的浮点结果。
    RTL 侧可进一步利用四分之一周期对称，把 ROM 压到 N/4，见格式说明文档。
    """
    _check_table_length(length)
    half = length // 2
    table = [0] * length
    for i in range(half):
        value = round_half_away_from_zero(
            amplitude * math.sin(2.0 * math.pi * i / length)
        )
        table[i] = value
        table[i + half] = -value
    return table


def make_square_table(
    length: int = WT_LENGTH, amplitude: int = WT_AMPLITUDE
) -> list[int]:
    """单周期方波表，占空比 50%，前半周期为正。"""
    _check_table_length(length)
    half = length // 2
    return [amplitude] * half + [-amplitude] * half


def make_saw_table(
    length: int = WT_LENGTH, amplitude: int = WT_AMPLITUDE
) -> list[int]:
    """单周期上升锯齿波表。

    定义为 s(i) = round(A * (2i/N - 1))，相位 0 对应负满幅，单调上升到
    接近正满幅后回绕。RTL 上这条波形可以直接由相位高位取反符号位得到，
    不必真的占用 ROM，见格式说明文档。
    """
    _check_table_length(length)
    return [
        round_half_away_from_zero(amplitude * (2.0 * i / length - 1.0))
        for i in range(length)
    ]


WAVEFORM_BUILDERS: dict[str, Callable[[int, int], list[int]]] = {
    "sine": make_sine_table,
    "square": make_square_table,
    "saw": make_saw_table,
}

WAVEFORM_NAMES = tuple(WAVEFORM_BUILDERS)


def make_wavetable(
    name: str, length: int = WT_LENGTH, amplitude: int = WT_AMPLITUDE
) -> list[int]:
    """按名称生成波表。"""
    try:
        builder = WAVEFORM_BUILDERS[name]
    except KeyError:
        raise ValueError(
            f"未知波形 {name!r}，可选 {', '.join(WAVEFORM_NAMES)}"
        ) from None
    return builder(length, amplitude)


def _check_table_length(length: int) -> None:
    if length < 4 or length & (length - 1):
        raise ValueError(f"波表长度必须是不小于 4 的 2 的幂，收到 {length}")


# --------------------------------------------------------------------------
# 振荡器
# --------------------------------------------------------------------------


class WavetableOscillator:
    """单声部波表振荡器，行为对齐 DDS RTL。

    每调用一次 :meth:`step` 相当于 RTL 中来了一个 ``sample_tick``。
    """

    def __init__(
        self,
        table: Sequence[int],
        fcw: int = 0,
        interpolate: bool = False,
        start_phase: int = 0,
    ) -> None:
        length = len(table)
        _check_table_length(length)
        self._table = list(table)
        self._addr_shift = _addr_shift_for(length)
        self._frac_bits = self._addr_shift
        self._frac_mask = (1 << self._frac_bits) - 1
        self._length = length
        self.interpolate = interpolate
        self.set_fcw(fcw)
        self.reset(start_phase)

    # -- 状态 ---------------------------------------------------------------

    @property
    def phase(self) -> int:
        """当前 32 位相位累加器值。"""
        return self._phase

    @property
    def fcw(self) -> int:
        return self._fcw

    @property
    def table(self) -> list[int]:
        return list(self._table)

    def reset(self, start_phase: int = 0) -> None:
        """复位。对应 RTL 中 ``sys_rst_n`` 拉低后相位清零。"""
        if not 0 <= start_phase < PHASE_MODULO:
            raise ValueError(f"起始相位 {start_phase} 超出 32 位范围")
        self._phase = start_phase

    def set_fcw(self, fcw: int) -> None:
        if not 0 <= fcw < PHASE_MODULO:
            raise ValueError(f"FCW {fcw} 超出 32 位无符号范围")
        self._fcw = fcw

    def set_frequency(
        self, freq_hz: float, sample_rate: int = SAMPLE_RATE_HZ
    ) -> None:
        self.set_fcw(freq_to_fcw(freq_hz, sample_rate))

    def set_midi_note(
        self, note: int, sample_rate: int = SAMPLE_RATE_HZ, a4_hz: float = A4_HZ
    ) -> None:
        self.set_fcw(midi_note_to_fcw(note, sample_rate, a4_hz))

    # -- 取样 ---------------------------------------------------------------

    def lookup(self, phase: int) -> int:
        """按给定相位查表，返回 16 位有符号样本。"""
        addr = (phase >> self._addr_shift) & (self._length - 1)
        if not self.interpolate:
            return self._table[addr]
        frac = phase & self._frac_mask
        if frac == 0:
            return self._table[addr]
        s0 = self._table[addr]
        s1 = self._table[(addr + 1) & (self._length - 1)]
        delta = div_round_half_away_from_zero(
            (s1 - s0) * frac, 1 << self._frac_bits
        )
        return s0 + delta

    def step(self) -> int:
        """输出当前相位对应的样本，然后累加相位。先取样后累加。"""
        sample = self.lookup(self._phase)
        self._phase = (self._phase + self._fcw) % PHASE_MODULO
        return sample

    def render(self, num_samples: int) -> list[int]:
        """连续输出若干个 16 位波表样本。"""
        if num_samples < 0:
            raise ValueError("样本数不能为负")
        return [self.step() for _ in range(num_samples)]


def _addr_shift_for(length: int) -> int:
    bits = length.bit_length() - 1
    if bits > PHASE_BITS:
        raise ValueError("波表长度超过 32 位相位可寻址范围")
    return PHASE_BITS - bits


# --------------------------------------------------------------------------
# 16 位波表样本 -> 24 位 PCM
# --------------------------------------------------------------------------


def wt16_to_pcm24(sample: int, gain_q15: int = GAIN_Q15_ONE) -> tuple[int, bool]:
    """16 位波表样本转 24 位有符号 PCM，返回 (PCM, 是否削波)。

    步骤：左移 8 位定标 -> 乘 Q1.15 增益 -> 半值远离零舍入 -> 饱和限幅。
    ``gain_q15 == 32768`` 时为纯移位，无舍入误差。
    """
    if gain_q15 < 0:
        raise ValueError("增益不能为负")
    scaled = sample << WT_TO_PCM_SHIFT
    if gain_q15 != GAIN_Q15_ONE:
        scaled = div_round_half_away_from_zero(scaled * gain_q15, GAIN_Q15_ONE)
    return saturate_pcm24(scaled)


def db_to_gain_q15(db: float) -> int:
    """分贝转 Q1.15 增益整数，仅用于生成测试向量时给出可读的电平。"""
    if db > 0.0:
        raise ValueError("本函数只用于衰减，dB 必须小于等于 0")
    return round_half_away_from_zero(GAIN_Q15_ONE * (10.0 ** (db / 20.0)))


@dataclass
class RenderResult:
    """一次渲染的结果与统计。"""

    pcm: list[int] = field(default_factory=list)
    wavetable_samples: list[int] = field(default_factory=list)
    clip_count: int = 0
    fcw: int = 0
    actual_freq_hz: float = 0.0


def render_pcm24(
    waveform: str | Sequence[int],
    freq_hz: float,
    num_samples: int,
    sample_rate: int = SAMPLE_RATE_HZ,
    gain_q15: int = GAIN_Q15_ONE,
    interpolate: bool = False,
    table_length: int = WT_LENGTH,
    amplitude: int = WT_AMPLITUDE,
) -> RenderResult:
    """渲染一段单声部 24 位 PCM。

    ``waveform`` 可以是波形名，也可以直接传入一张波表。
    """
    table = (
        make_wavetable(waveform, table_length, amplitude)
        if isinstance(waveform, str)
        else waveform
    )
    fcw = freq_to_fcw(freq_hz, sample_rate)
    osc = WavetableOscillator(table, fcw=fcw, interpolate=interpolate)
    result = RenderResult(fcw=fcw, actual_freq_hz=fcw_to_freq(fcw, sample_rate))
    for _ in range(num_samples):
        wt_sample = osc.step()
        pcm, clipped = wt16_to_pcm24(wt_sample, gain_q15)
        result.wavetable_samples.append(wt_sample)
        result.pcm.append(pcm)
        result.clip_count += int(clipped)
    return result


# --------------------------------------------------------------------------
# 音高误差报告
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class NoteFrequencyReport:
    """单个 MIDI 音符的理想频率、FCW 与量化误差。"""

    note: int
    ideal_hz: float
    fcw: int
    actual_hz: float

    @property
    def error_hz(self) -> float:
        return self.actual_hz - self.ideal_hz

    @property
    def error_cent(self) -> float:
        return cents_between(self.actual_hz, self.ideal_hz)


def build_note_table(
    sample_rate: int = SAMPLE_RATE_HZ, a4_hz: float = A4_HZ
) -> list[NoteFrequencyReport]:
    """生成 MIDI 0 至 127 的频率与 FCW 全表。

    高音区可能超过奈奎斯特频率。第一版键盘不会用到那么高的音，但表要完整，
    因此这里允许超奈奎斯特，由使用方自行判断；混叠风险写在格式说明文档里。
    """
    reports = []
    for note in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX + 1):
        ideal = midi_note_to_freq(note, a4_hz)
        fcw = freq_to_fcw(ideal, sample_rate, allow_above_nyquist=True)
        reports.append(
            NoteFrequencyReport(
                note=note,
                ideal_hz=ideal,
                fcw=fcw,
                actual_hz=fcw_to_freq(fcw, sample_rate),
            )
        )
    return reports


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def midi_note_name(note: int) -> str:
    """MIDI 音符号转音名，60 为 C4。"""
    if not MIDI_NOTE_MIN <= note <= MIDI_NOTE_MAX:
        raise ValueError(f"note 超出范围：{note}")
    return f"{NOTE_NAMES[note % 12]}{note // 12 - 1}"
