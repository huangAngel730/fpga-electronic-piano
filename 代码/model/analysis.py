# -*- coding: utf-8 -*-
"""波形分析工具：频率测量、信纳比与谐波失真。

只依赖 Python 标准库，不需要 numpy 或 scipy，保证三个人的机器和 CI 都能直接跑。
计算量按 O(N) 设计，48 kHz 下几万点在秒级完成。

本文件服务于 T002 的自动判定，后续 T032 的波形与频谱分析工具会在此基础上扩展。
"""

import cmath
import math
from dataclasses import dataclass
from typing import Sequence

from audio_defs import SAMPLE_RATE_HZ


def hann_window(length: int) -> list[float]:
    """汉宁窗。用于抑制截断泄漏，使谐波与基波之间互相干扰足够小。"""
    if length < 2:
        raise ValueError("窗长至少为 2")
    return [
        0.5 - 0.5 * math.cos(2.0 * math.pi * i / length) for i in range(length)
    ]


def _segment_phasor(
    samples: Sequence[float],
    start: int,
    count: int,
    freq_hz: float,
    sample_rate: int,
    window: Sequence[float] | None,
) -> complex:
    """对 samples[start:start+count] 在指定频率上做单点 DFT。"""
    omega = 2.0 * math.pi * freq_hz / sample_rate
    real = 0.0
    imag = 0.0
    for i in range(count):
        value = samples[start + i]
        if window is not None:
            value *= window[i]
        angle = omega * i
        real += value * math.cos(angle)
        imag -= value * math.sin(angle)
    return complex(real, imag)


def dft_at(
    samples: Sequence[float],
    freq_hz: float,
    sample_rate: int = SAMPLE_RATE_HZ,
    window: Sequence[float] | None = None,
) -> complex:
    """整段序列在任意频率上的单点 DFT。"""
    return _segment_phasor(samples, 0, len(samples), freq_hz, sample_rate, window)


def estimate_frequency(
    samples: Sequence[float],
    sample_rate: int = SAMPLE_RATE_HZ,
    freq_hint_hz: float = 440.0,
) -> float:
    """用两段相位差法测量实际输出频率。

    原理：把序列平均分成前后两段，同一个正弦分量在第二段中的相位比第一段
    超前 ``2*pi*f*m/fs``。由相位差反解频率，精度远高于直接找 DFT 峰值，
    因为它不受频率栅格限制。

    相位差有 ``2*pi`` 模糊，用 ``freq_hint_hz`` 选定分支，因此要求真实频率与
    提示频率的偏差小于 ``fs/(2m)``。本项目里偏差是微赫兹量级，余量极大。

    对方波和锯齿波同样可用：加汉宁窗后各次谐波离基波足够远，泄漏可忽略。
    """
    total = len(samples)
    half = total // 2
    if half < 64:
        raise ValueError(f"样本数 {total} 太少，无法可靠测频")
    window = hann_window(half)
    first = _segment_phasor(samples, 0, half, freq_hint_hz, sample_rate, window)
    second = _segment_phasor(
        samples, half, half, freq_hint_hz, sample_rate, window
    )
    if abs(first) == 0.0 or abs(second) == 0.0:
        raise ValueError("提示频率处没有能量，无法测频")
    delta_phase = cmath.phase(second) - cmath.phase(first)
    base = delta_phase * sample_rate / (2.0 * math.pi * half)
    branch = sample_rate / half
    offset = round((freq_hint_hz - base) / branch)
    return base + offset * branch


def _solve3(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """3 阶线性方程组高斯消元，带部分主元选择。"""
    size = 3
    augmented = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(augmented[r][col]))
        if abs(augmented[pivot][col]) < 1e-300:
            raise ValueError("拟合矩阵奇异，检查输入序列是否为常数")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        for row in range(col + 1, size):
            factor = augmented[row][col] / augmented[col][col]
            for k in range(col, size + 1):
                augmented[row][k] -= factor * augmented[col][k]
    solution = [0.0] * size
    for row in reversed(range(size)):
        acc = augmented[row][size]
        for k in range(row + 1, size):
            acc -= augmented[row][k] * solution[k]
        solution[row] = acc / augmented[row][row]
    return solution


@dataclass(frozen=True)
class SinusoidFit:
    """单频最小二乘拟合结果。"""

    freq_hz: float
    dc: float
    cos_coeff: float
    sin_coeff: float
    signal_power: float
    residual_power: float

    @property
    def amplitude(self) -> float:
        return math.hypot(self.cos_coeff, self.sin_coeff)

    @property
    def sinad_db(self) -> float:
        """基波功率与残差功率之比，单位 dB。残差包含全部谐波与杂散。"""
        if self.residual_power <= 0.0:
            return math.inf
        return 10.0 * math.log10(self.signal_power / self.residual_power)


def fit_sinusoid(
    samples: Sequence[float],
    freq_hz: float,
    sample_rate: int = SAMPLE_RATE_HZ,
) -> SinusoidFit:
    """在给定频率上做 直流 + cos + sin 的最小二乘拟合。

    残差里包含谐波失真、相位截断杂散和幅度量化噪声，因此
    :attr:`SinusoidFit.sinad_db` 是一个完整的信纳比指标，不会像只看谐波的
    THD 那样漏掉非谐波杂散。这一点对相位截断 DDS 很关键：它的主要杂散
    通常不落在谐波上。
    """
    count = len(samples)
    if count < 16:
        raise ValueError("样本数太少，无法拟合")
    omega = 2.0 * math.pi * freq_hz / sample_rate
    s_cc = s_ss = s_cs = s_c = s_s = 0.0
    s_xc = s_xs = s_x = 0.0
    for i in range(count):
        cos_i = math.cos(omega * i)
        sin_i = math.sin(omega * i)
        value = float(samples[i])
        s_cc += cos_i * cos_i
        s_ss += sin_i * sin_i
        s_cs += cos_i * sin_i
        s_c += cos_i
        s_s += sin_i
        s_xc += value * cos_i
        s_xs += value * sin_i
        s_x += value
    matrix = [
        [s_cc, s_cs, s_c],
        [s_cs, s_ss, s_s],
        [s_c, s_s, float(count)],
    ]
    cos_coeff, sin_coeff, dc = _solve3(matrix, [s_xc, s_xs, s_x])
    residual_power = 0.0
    signal_power = 0.0
    for i in range(count):
        model = (
            cos_coeff * math.cos(omega * i) + sin_coeff * math.sin(omega * i)
        )
        residual = float(samples[i]) - dc - model
        residual_power += residual * residual
        signal_power += model * model
    return SinusoidFit(
        freq_hz=freq_hz,
        dc=dc,
        cos_coeff=cos_coeff,
        sin_coeff=sin_coeff,
        signal_power=signal_power / count,
        residual_power=residual_power / count,
    )


def harmonic_levels_dbc(
    samples: Sequence[float],
    fundamental_hz: float,
    sample_rate: int = SAMPLE_RATE_HZ,
    max_harmonic: int = 20,
) -> dict[int, float]:
    """各次谐波相对基波的电平，单位 dBc。超过奈奎斯特的次数自动跳过。"""
    window = hann_window(len(samples))
    fundamental = abs(dft_at(samples, fundamental_hz, sample_rate, window))
    if fundamental == 0.0:
        raise ValueError("基波幅度为 0，无法计算谐波电平")
    levels: dict[int, float] = {}
    for order in range(2, max_harmonic + 1):
        freq = fundamental_hz * order
        if freq >= sample_rate / 2.0:
            break
        magnitude = abs(dft_at(samples, freq, sample_rate, window))
        levels[order] = (
            -math.inf
            if magnitude == 0.0
            else 20.0 * math.log10(magnitude / fundamental)
        )
    return levels


def thd_dbc(
    samples: Sequence[float],
    fundamental_hz: float,
    sample_rate: int = SAMPLE_RATE_HZ,
    max_harmonic: int = 20,
) -> float:
    """总谐波失真，单位 dBc。只统计谐波，非谐波杂散见 :func:`fit_sinusoid`。"""
    levels = harmonic_levels_dbc(
        samples, fundamental_hz, sample_rate, max_harmonic
    )
    power = sum(10.0 ** (level / 10.0) for level in levels.values())
    if power <= 0.0:
        return -math.inf
    return 10.0 * math.log10(power)
