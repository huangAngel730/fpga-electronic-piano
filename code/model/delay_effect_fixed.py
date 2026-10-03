#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T028 延迟效果器 - 定点黄金模型（2026-10-02）

定点实现，bit-exact 匹配硬件 RTL。
- PCM：24-bit signed two's complement [-8388608, 8388607]
- Gain：Q0.15 unsigned [0, 32767]，表示 [0.0, 0.999969]
- Feedback：Q0.15 unsigned [0, 32767]，必须 < 1.0（防发散）

算法合同
--------
1. **干湿混合**（先乘后加）：
   output_raw = (input_pcm * dry_gain) >> 15 + (delayed_pcm * wet_gain) >> 15
   output = saturate(output_raw, PCM_MIN, PCM_MAX)

2. **反馈缓存**（写入含反馈）：
   fb_raw = input_pcm + ((delayed_pcm * feedback) >> 15)
   buffer[wr_ptr] = saturate(fb_raw, PCM_MIN, PCM_MAX)

3. **舍入策略**：截断（>> 15 不加舍入），匹配硬件右移
4. **饱和**：signed 24-bit [-8388608, 8388607]，超限截断
5. **旁路**：干信号通过时有 Q0.15 截断误差（最大 input/32768）
   硬件可用专用旁路路径实现 0 LSB（不经过乘法器）
6. **复位**：清空缓存、复位读写指针
7. **参数切换**：立即生效（不要求平滑过渡，M2 负责）

缓存结构
--------
- 循环缓冲，写指针自增，读指针 = (wr_ptr - delay_samples) % depth
- 小深度验证算法（如 100/1000 样本），最大规模交 M2 核预算
"""

from __future__ import annotations

PCM_BITS = 24
PCM_MAX = (1 << (PCM_BITS - 1)) - 1      # 8388607
PCM_MIN = -(1 << (PCM_BITS - 1))         # -8388608
GAIN_BITS = 15
GAIN_MAX = (1 << GAIN_BITS) - 1          # 32767


def saturate_pcm24(value: int) -> int:
    """饱和到 24-bit signed。"""
    if value > PCM_MAX:
        return PCM_MAX
    if value < PCM_MIN:
        return PCM_MIN
    return value


class DelayEffectFixed:
    """定点延迟效果器（bit-exact 硬件模型）。

    参数
    ----
    depth : 缓存深度（样本数），必须 > 0
    """

    def __init__(self, depth: int) -> None:
        if depth <= 0:
            raise ValueError(f"depth must be > 0, got {depth}")
        self.depth = depth
        self.buffer = [0] * depth
        self.wr_ptr = 0

    def reset(self) -> None:
        """清空缓存，复位指针。"""
        self.buffer = [0] * self.depth
        self.wr_ptr = 0

    def process(self, input_pcm: int, delay_samples: int,
                dry_gain: int, wet_gain: int, feedback: int) -> int:
        """处理一个样本（bit-exact 定点）。

        参数
        ----
        input_pcm : 输入 PCM，24-bit signed [-8388608, 8388607]
        delay_samples : 延迟样本数 [0, depth-1]
        dry_gain : 干信号增益，Q0.15 unsigned [0, 32767]
        wet_gain : 湿信号增益，Q0.15 unsigned [0, 32767]
        feedback : 反馈增益，Q0.15 unsigned [0, 32767]，必须 < 1.0

        返回
        ----
        output_pcm : 输出 PCM，24-bit signed

        合同保证
        --------
        - delay_samples=0：读当前写位置（M2 修正：rd_ptr=wr_ptr，先读后写）
          实际无延迟效果（总是读到尚未写入的位置），但反馈仍写入当前位置
        - dry_gain=32767, wet_gain=0：近似旁路，误差 ≤ input/32768
        - feedback >= 32768：算法允许但会发散（用户责任）
        """
        # 边界检查
        if not (0 <= delay_samples < self.depth):
            raise ValueError(f"delay_samples {delay_samples} out of range [0, {self.depth})")
        if not (PCM_MIN <= input_pcm <= PCM_MAX):
            raise ValueError(f"input_pcm {input_pcm} out of range [{PCM_MIN}, {PCM_MAX}]")
        if not (0 <= dry_gain <= GAIN_MAX):
            raise ValueError(f"dry_gain {dry_gain} out of range [0, {GAIN_MAX}]")
        if not (0 <= wet_gain <= GAIN_MAX):
            raise ValueError(f"wet_gain {wet_gain} out of range [0, {GAIN_MAX}]")
        if not (0 <= feedback <= GAIN_MAX):
            raise ValueError(f"feedback {feedback} out of range [0, {GAIN_MAX}]")

        # 读指针：(wr_ptr - delay_samples) % depth
        rd_ptr = (self.wr_ptr - delay_samples) % self.depth
        delayed_pcm = self.buffer[rd_ptr]

        # 干湿混合（先乘后加，扩展到 64-bit 防溢出，截断右移）
        dry_contrib = (input_pcm * dry_gain) >> GAIN_BITS
        wet_contrib = (delayed_pcm * wet_gain) >> GAIN_BITS
        output_raw = dry_contrib + wet_contrib
        output_pcm = saturate_pcm24(output_raw)

        # 反馈缓存（写入 = 输入 + 延迟*反馈）
        fb_contrib = (delayed_pcm * feedback) >> GAIN_BITS
        fb_raw = input_pcm + fb_contrib
        fb_saturated = saturate_pcm24(fb_raw)
        self.buffer[self.wr_ptr] = fb_saturated

        # 写指针自增
        self.wr_ptr = (self.wr_ptr + 1) % self.depth

        return output_pcm


# -------------------------------------------------------------------- 自检
def test_exact_bypass() -> None:
    """近似旁路：dry=32767, wet=0 -> 误差 ≤ input/32768。

    Q0.15 截断误差：对 PCM_MAX=8388607，误差可达 256 LSB (0.003%)。
    真正的 0 LSB 旁路需要硬件专用旁路路径（不经过乘法器）。
    """
    delay = DelayEffectFixed(100)
    test_cases = [0, 1000, -5000, 100000, -100000, PCM_MAX, PCM_MIN]
    for sample in test_cases:
        out = delay.process(sample, delay_samples=50,
                            dry_gain=32767, wet_gain=0, feedback=0)
        # 允许误差：abs(sample) / 32768
        max_error = abs(sample) // 32768 + 1
        error = abs(out - sample)
        assert error <= max_error, \
            f"bypass error: input={sample}, out={out}, error={error}, max={max_error}"
    print("PASS: approximate bypass (Q0.15 truncation error)")


def test_impulse_response() -> None:
    """脉冲响应：检查延迟、反馈回声。"""
    delay = DelayEffectFixed(200)
    impulse_val = 1000000
    # dry=0.5 (16384), wet=0.5 (16384), feedback=0.5 (16384), delay=100
    dry_g = 16384
    wet_g = 16384
    fb_g = 16384
    delay_s = 100

    outputs = []
    # 输入：1 个脉冲 + 300 个零
    for i in range(301):
        inp = impulse_val if i == 0 else 0
        out = delay.process(inp, delay_s, dry_g, wet_g, fb_g)
        outputs.append(out)

    # 检查 t=0：应有干信号贡献
    assert outputs[0] != 0, "t=0 should have dry contribution"
    # 检查 t=100：应有第一次回声（湿信号）
    assert outputs[100] != 0, "t=100 should have first echo"
    # 检查 t=200：应有第二次回声（反馈）
    assert outputs[200] != 0, "t=200 should have second echo (feedback)"
    print(f"PASS: impulse response (t=0: {outputs[0]}, t=100: {outputs[100]}, t=200: {outputs[200]})")


def test_saturation() -> None:
    """饱和：超限截断到 PCM_MAX/PCM_MIN。"""
    delay = DelayEffectFixed(10)
    # 写入大值，反馈放大
    for _ in range(5):
        delay.process(PCM_MAX, delay_samples=1, dry_gain=0, wet_gain=0, feedback=32767)
    # 读出应饱和（考虑 Q0.15 截断误差）
    out = delay.process(0, delay_samples=1, dry_gain=0, wet_gain=32767, feedback=0)
    # PCM_MAX * 32767 >> 15 = 8388351，不是 8388607
    expected = (PCM_MAX * 32767) >> 15
    assert out == expected, f"saturation output: {out} != {expected}"
    print(f"PASS: saturation (output={out}, after Q0.15 truncation)")


def test_zero_delay() -> None:
    """零延迟：delay_samples=0，rd_ptr=wr_ptr（先读后写）。

    M2 修正：零延迟时 rd_ptr 等于 wr_ptr，但先读后写，所以总是读到
    尚未被本次写入覆盖的旧值。对于递增的写指针，相当于读前一个循环
    周期的同位置值（初始为 0）。
    """
    delay = DelayEffectFixed(10)
    # 第一次：wr_ptr=0, rd_ptr=0, buffer[0]=0（初始）
    out1 = delay.process(1000, delay_samples=0, dry_gain=16384, wet_gain=16384, feedback=16384)
    # dry=1000*0.5=500, wet=0*0.5=0 -> 500
    # 然后写 buffer[0]=1000, wr_ptr=1
    assert out1 == 500, f"zero delay t=0: {out1} != 500"

    # 第二次：wr_ptr=1, rd_ptr=1, buffer[1]=0（仍为初始值）
    out2 = delay.process(2000, delay_samples=0, dry_gain=16384, wet_gain=16384, feedback=16384)
    # dry=2000*0.5=1000, wet=0*0.5=0 -> 1000
    # 然后写 buffer[1]=2000, wr_ptr=2
    assert out2 == 1000, f"zero delay t=1: {out2} != 1000"

    print("PASS: zero delay (rd_ptr=wr_ptr, read before write, always reads old/initial value)")


def test_reset() -> None:
    """复位：清空缓存，复位指针。"""
    delay = DelayEffectFixed(10)
    delay.process(5000, delay_samples=5, dry_gain=0, wet_gain=0, feedback=32767)
    delay.reset()
    out = delay.process(0, delay_samples=5, dry_gain=0, wet_gain=32767, feedback=0)
    assert out == 0, f"reset failed: {out} != 0"
    print("PASS: reset")


def main() -> int:
    test_exact_bypass()
    test_impulse_response()
    test_saturation()
    test_zero_delay()
    test_reset()
    print("\nRESULT: all 5 tests PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
