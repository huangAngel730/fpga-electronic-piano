# -*- coding: utf-8 -*-
"""公共音频常量与定点格式定义。

本文件是 M1 侧全部算法模型、生成脚本和测试的唯一常量来源，禁止在其他文件里
重复写死数值。

常量分两类：

- 标记「接口 v1.0」的来自 ``code/docs/模块接口规范.md``，属于冻结的公共接口。
  本目录内不得修改；确需变更时按该文档第八节流程，由 M2 发布新版本。
- 标记「M1 定义」的属于音频算法内部定点格式，由 M1 负责。变更时必须同步更新
  ``code/docs/test/DDS参考模型与波表格式说明.md`` 并通知 M2 与 M3。

对应任务：T002 Python DDS 参考模型、T003 波表和 FCW 生成脚本。
"""

import math

# --------------------------------------------------------------------------
# 采样率与相位（接口 v1.0 / M1 定义）
# --------------------------------------------------------------------------

#: 系统采样率，由 ``sample_tick`` 决定。接口 v1.0，固定 48 kHz。
SAMPLE_RATE_HZ = 48_000

#: 相位累加器位宽。M1 定义，取 32 位。
PHASE_BITS = 32

#: 相位累加器的模，累加溢出即回绕（无符号，天然 mod 2**32）。
PHASE_MODULO = 1 << PHASE_BITS

#: 频率分辨率 = fs / 2**32，约 1.1176e-5 Hz。
FREQ_RESOLUTION_HZ = SAMPLE_RATE_HZ / PHASE_MODULO

# --------------------------------------------------------------------------
# PCM 输出格式（接口 v1.0）
# --------------------------------------------------------------------------

#: 交付给 M2 的 PCM 位宽。接口 v1.0，24 位有符号二进制补码。
PCM_BITS = 24
PCM_MAX = (1 << (PCM_BITS - 1)) - 1  # 8388607
PCM_MIN = -(1 << (PCM_BITS - 1))  # -8388608

# --------------------------------------------------------------------------
# 波表格式（M1 定义）
# --------------------------------------------------------------------------

#: 波表样本位宽，16 位有符号，等效 Q1.15。
WT_SAMPLE_BITS = 16
WT_SAMPLE_MAX = (1 << (WT_SAMPLE_BITS - 1)) - 1  # 32767
WT_SAMPLE_MIN = -(1 << (WT_SAMPLE_BITS - 1))  # -32768

#: 波表满幅取 +32767 而不是 32768，使正负满幅对称，避免取反时溢出。
WT_AMPLITUDE = WT_SAMPLE_MAX

#: 波表地址位宽，1024 点单周期表。
WT_ADDR_BITS = 10
WT_LENGTH = 1 << WT_ADDR_BITS

#: 相位高 10 位做表地址，低 22 位为相位小数部分（插值用）。
PHASE_ADDR_SHIFT = PHASE_BITS - WT_ADDR_BITS  # 22
PHASE_FRAC_BITS = PHASE_ADDR_SHIFT
PHASE_FRAC_MASK = (1 << PHASE_FRAC_BITS) - 1

#: 16 位波表样本到 24 位 PCM 的定标：左移 8 位，等价于乘 256，无舍入误差。
WT_TO_PCM_SHIFT = PCM_BITS - WT_SAMPLE_BITS  # 8

#: 波表满幅经上述定标后的 PCM 值，32767 * 256 = 8388352，约 -0.0003 dBFS。
PCM_FULL_SCALE_FROM_WT = WT_AMPLITUDE << WT_TO_PCM_SHIFT

#: 增益定点格式 Q1.15，32768 表示 1.0。
GAIN_Q15_ONE = 1 << 15

# --------------------------------------------------------------------------
# 音高换算（M1 定义）
# --------------------------------------------------------------------------

#: 十二平均律基准音 A4。
A4_HZ = 440.0
A4_MIDI_NOTE = 69

#: 事件接口中 note_number 为 7 位，范围 0 至 127。接口 v1.0。
MIDI_NOTE_MIN = 0
MIDI_NOTE_MAX = 127

SEMITONES_PER_OCTAVE = 12
CENTS_PER_SEMITONE = 100
CENTS_PER_OCTAVE = SEMITONES_PER_OCTAVE * CENTS_PER_SEMITONE

# --------------------------------------------------------------------------
# 验收阈值（M1 定义，测试直接引用，不在测试里另写数值）
# --------------------------------------------------------------------------

#: 音高误差验收阈值。依据：受过训练的听音者对稳态音高的辨别阈约 5 音分，
#: 取 5 倍余量后定为 1 音分。整条链路（换算 + FCW 量化 + 波表）都必须满足。
FREQ_ERROR_SPEC_CENT = 1.0

#: 仅 FCW 量化引入的音高误差上限。用于证明 32 位相位累加器位宽足够。
#: 理论上界 = 半个 FCW LSB 折算到最低音 MIDI 0（8.1758 Hz）处的音分：
#:     0.5 * FREQ_RESOLUTION_HZ / 8.1758 * 1200 / ln2 ≈ 1.19e-3 音分
#: 误差随频率升高而变小，因此最低音就是最坏情况。取约 1.7 倍余量定为 0.002。
FCW_QUANT_ERROR_MAX_CENT = 0.002

#: 正弦波表 v1（相位截断，不插值）的信纳比下限。
#: 依据：相位截断无杂散动态范围 SFDR ≈ 6.02 * WT_ADDR_BITS - 3.92 = 56.3 dB，
#: 取约 6 dB 工程余量后定为 50 dB。测量方法见 analysis.sinad_db。
SINE_SINAD_SPEC_DB = 50.0

#: 正弦波表的谐波失真上限，作为附加检查（相位截断杂散多为非谐波，
#: 因此 THD 只作参考，主判据是上面的 SINAD）。
SINE_THD_SPEC_DBC = -40.0

#: 单声部输出允许的直流偏置上限，单位为 PCM LSB。
#: 16 LSB 相当于 24 位满量程的 -114 dB，远低于任何 DAC 的直流指标，
#: 目的是发现波表构造或舍入方向写错这类系统性偏置，而不是限制底噪。
PCM_DC_OFFSET_MAX_LSB = 16.0

# --------------------------------------------------------------------------
# 定点运算基元
# --------------------------------------------------------------------------


def round_half_away_from_zero(value: float) -> int:
    """按「四舍五入、半值远离零」取整。

    不使用 Python 内置 ``round``，因为它是银行家舍入（半值取偶），与 RTL 中
    常用的「加半个 LSB 再截断」行为不一致，会造成逐样本比较偶发失配。
    """
    if value >= 0.0:
        return int(value + 0.5)
    return -int(-value + 0.5)


def div_round_half_away_from_zero(numerator: int, denominator: int) -> int:
    """整数除法，半值远离零。全程整数运算，不引入浮点误差。"""
    if denominator <= 0:
        raise ValueError(f"denominator 必须为正整数，收到 {denominator}")
    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)
    return -((-2 * numerator + denominator) // (2 * denominator))


def saturate(value: int, low: int, high: int) -> tuple[int, bool]:
    """饱和限幅。返回 (限幅后的值, 是否发生削波)。

    禁止用低位截断或回绕代替本函数，见 ``code/rtl/audio/AGENTS.md``。
    """
    if value > high:
        return high, True
    if value < low:
        return low, True
    return value, False


def saturate_pcm24(value: int) -> tuple[int, bool]:
    """限幅到 24 位有符号 PCM 范围。"""
    return saturate(value, PCM_MIN, PCM_MAX)


def saturate_wt16(value: int) -> tuple[int, bool]:
    """限幅到 16 位有符号波表样本范围。"""
    return saturate(value, WT_SAMPLE_MIN, WT_SAMPLE_MAX)


def to_twos_complement(value: int, bits: int) -> int:
    """有符号整数转指定位宽的二进制补码无符号表示。"""
    low = -(1 << (bits - 1))
    high = (1 << (bits - 1)) - 1
    if not low <= value <= high:
        raise ValueError(f"{value} 超出 {bits} 位有符号范围 [{low}, {high}]")
    return value & ((1 << bits) - 1)


def from_twos_complement(raw: int, bits: int) -> int:
    """指定位宽的二进制补码无符号表示转有符号整数。"""
    if not 0 <= raw < (1 << bits):
        raise ValueError(f"0x{raw:x} 超出 {bits} 位无符号范围")
    if raw >= (1 << (bits - 1)):
        return raw - (1 << bits)
    return raw


def to_hex_word(value: int, bits: int) -> str:
    """有符号整数转定长小写十六进制字符串，供 $readmemh 使用。"""
    digits = (bits + 3) // 4
    return f"{to_twos_complement(value, bits):0{digits}x}"


def from_hex_word(text: str, bits: int) -> int:
    """定长十六进制字符串转有符号整数，用于回读校验生成文件。"""
    digits = (bits + 3) // 4
    token = text.strip()
    if len(token) != digits:
        raise ValueError(f"期望 {digits} 位十六进制，收到 {token!r}")
    return from_twos_complement(int(token, 16), bits)


def cents_between(actual_hz: float, reference_hz: float) -> float:
    """两个频率之间的音分差，正值表示 actual 偏高。"""
    if actual_hz <= 0.0 or reference_hz <= 0.0:
        raise ValueError("频率必须为正数才能换算音分")
    return CENTS_PER_OCTAVE * math.log2(actual_hz / reference_hz)
