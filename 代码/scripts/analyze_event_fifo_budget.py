"""
事件 FIFO 深度与演奏延迟的定量分析

目的：为 模块接口规范.md 3.6 节「FIFO 深度固定为 32」提供推导依据，
      并检验该深度与赛题延迟指标（<=10ms 基础 / <=5ms 目标）是否冲突。

本脚本只做算术，不依赖 RTL。所有假设集中写在 ASSUMPTIONS 中，
便于复核者替换参数后重新计算。
"""

ASSUMPTIONS = {
    # --- 来自冻结接口 v1.0 ---
    "fs_hz": 48_000,          # sample_tick 频率（规范 2.3）
    "fifo_depth": 32,         # 规范 3.6
    "event_bits": 64,         # 规范 3.1

    # --- 来自赛题的硬指标 ---
    "latency_base_ms": 10.0,  # 基础要求：控制信号到音频输出总延迟
    "latency_goal_ms": 5.0,   # 拓展要求：压缩至 5ms

    # --- 待核实/需 M1 确认的算法侧参数 ---
    # 单声部每采样周期占用的处理拍数。DDS 相位累加 1 拍，
    # 但含 ADSR、混音、饱和限幅后按保守值估。
    "cycles_per_voice": 4,
    # 音频核心是否流水化处理多声部（1=全并行，N=每周期处理 N 个声部）
    "voices_per_cycle": 1,

    # --- 输入侧限速（规范 3.7）---
    "cc_rate_hz": 1_000,      # 单一连续控制源上限
}


def section(title):
    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


def fifo_drain_time(depth, service_per_sample, fs):
    """排空一个满 FIFO 需要多少个采样周期，以及对应时间。"""
    samples = depth / service_per_sample
    return samples, samples / fs * 1000.0


def main():
    a = ASSUMPTIONS
    fs = a["fs_hz"]
    depth = a["fifo_depth"]

    section("一 基本时间常数")
    tick_us = 1e6 / fs
    print(f"sample_tick 周期          : {tick_us:.3f} us  ({fs} Hz)")
    print(f"1 ms 包含采样周期数       : {fs / 1000:.1f}")
    print(f"10 ms 包含采样周期数      : {fs / 100:.0f}")
    print(f"5 ms  包含采样周期数      : {fs / 200:.0f}")

    section("二 事件产生速率上限")
    # 最坏情况：连续控制按 1kHz 限速持续灌入
    cc_per_sample = a["cc_rate_hz"] / fs
    print(f"单一连续控制源 {a['cc_rate_hz']} Hz")
    print(f"  -> 每采样周期事件数     : {cc_per_sample:.4f}")
    print(f"  -> 填满 {depth} 深度 FIFO 需 : {depth / cc_per_sample:.0f} 个采样周期"
          f"  ({depth / cc_per_sample / fs * 1000:.2f} ms)")
    print("  结论：单靠 1kHz 连续控制，FIFO 不可能被填满。")

    section("三 最坏情况：和弦齐按")
    # 演奏场景：双手同时按下 N 键
    for n in (4, 8, 10, 16, 32):
        burst = n
        if burst <= depth:
            verdict = "可全部缓存"
        else:
            verdict = f"超出 {burst - depth} 个事件"
        print(f"{n:2d} 键同时按下 -> {burst:2d} 个 Note On : {verdict}")

    section("四 排空速率与服务能力")
    # 音频核心每采样周期能消费多少事件
    service = a["voices_per_cycle"]  # 每周期至少可分配 1 个声部
    print(f"音频核心每采样周期可处理事件数（保守估计）: {service}")
    samples, ms = fifo_drain_time(depth, service, fs)
    print(f"排空一个满 FIFO 需要       : {samples:.0f} 个采样周期 ({ms:.3f} ms)")
    print()
    print("注意：事件是「每采样周期取用」，不是在采样周期内串行逐个处理。")
    print("      因此 32 深度 FIFO 的排空时间上界约 32 个采样周期 = 0.667 ms。")

    section("五 延迟预算分解")
    print("赛题要求：控制信号 -> 音频输出 总延迟 <=10ms（目标 <=5ms）")
    print()
    print("延迟链路分解：")
    parts = [
        ("输入采集与去抖", 1.0, "按键去抖典型 1ms，传感器另计"),
        ("事件 FIFO 排队（最坏满）", depth / fs * 1000, f"{depth} 深度全部排队"),
        ("算法流水线", 0.2, "假设 4 拍流水 @100MHz 量级"),
        ("PCM 握手机制", 1 / fs * 1000, "1 个采样周期"),
        ("I2S 串行输出", 1 / fs * 1000, "1 帧 = 1/48000 s"),
        ("DAC 转换与模拟", 0.5, "待 M3 实测确认"),
    ]
    total = 0.0
    for name, val, note in parts:
        total += val
        print(f"  {name:<24} {val:6.3f} ms   {note}")
    print(f"  {'-' * 60}")
    print(f"  {'合计':<24} {total:6.3f} ms")
    print()
    if total <= a["latency_goal_ms"]:
        print(f"  结论：{total:.2f} ms <= 目标 {a['latency_goal_ms']} ms ✓ 达标")
    elif total <= a["latency_base_ms"]:
        print(f"  结论：{total:.2f} ms <= 基础 {a['latency_base_ms']} ms，"
              f"但未达目标 {a['latency_goal_ms']} ms")
    else:
        print(f"  结论：{total:.2f} ms > 基础 {a['latency_base_ms']} ms ✗ 超标")

    section("六 关键结论")
    print("1. 上述「事件 FIFO 排队」项假设 FIFO 完全排满，这是绝对最坏情况。")
    print("   实际演奏中 FIFO 水位通常接近空，该项应按 0 计。")
    print()
    print("2. 真正的风险不是 FIFO 深度，而是「去抖 + DAC 模拟」这些固定开销。")
    print(f"   仅去抖 1ms + DAC 0.5ms 就占掉基础预算的 "
          f"{(1.0 + 0.5) / a['latency_base_ms'] * 100:.0f}%。")
    print()
    print("3. 反压的正确代价不是「丢事件」，而是「上游阻塞」。")
    print("   规范 3.6 已禁止丢事件，因此 FIFO 满时唯一后果是输入侧暂停，")
    print("   演奏者感知为「按键无响应」，而非「挂音」。")
    print()
    print("4. 深度 32 对 10 键和弦（常见演奏上限）有 3 倍余量，判定充分。")

    section("七 待核实项")
    print("- 去抖时间：M3 按实际按键与传感器方案确定")
    print("- DAC 转换与模拟延迟：M3 实测")
    print("- 算法流水线拍数：M1 按实际实现确定")
    print("- 上述三项确定后应重算「五」的延迟预算")


if __name__ == "__main__":
    main()
