"""
T019 时钟方案分析与 sample_tick 参数计算

目的：为 code/rtl/common/sample_tick_gen.sv 提供参数依据，
      并验证各候选 sys_clk 频率下的 sample_tick 生成精度。

背景：板载晶振频率尚未核实（见 板级硬件事实.md），本脚本对多个
      候选频率分别计算，使 RTL 可参数化而不依赖单一未知值。
"""

FS_HZ = 48_000  # 接口规范 2.3 节

# 候选 sys_clk 频率（Hz）。前四个为音频标准频率，可整数分频到 48 kHz。
# 最后一个为常见 FPGA 板载晶振频率，作为对照。
CANDIDATES = [
    (24_576_000, "24.576 MHz", "音频标准，÷512 = 48 kHz"),
    (49_152_000, "49.152 MHz", "音频标准，÷1024 = 48 kHz"),
    (98_304_000, "98.304 MHz", "音频标准，÷2048 = 48 kHz"),
    (12_288_000, "12.288 MHz", "音频标准，÷256 = 48 kHz"),
    (50_000_000, "50.000 MHz", "常见板载晶振，不能整除 48 kHz"),
    (100_000_000, "100.000 MHz", "常见 PLL 输出，不能整除 48 kHz"),
]


def section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def analyze_divide(fclk):
    """整数分频方案：检查能否整除，给出分频比。"""
    if fclk % FS_HZ == 0:
        return fclk // FS_HZ
    return None


def phase_accum_error(fclk, acc_bits, sample_cycles=48_000 * 60):
    """
    相位累加方案误差分析。

    相位累加器 acc_bits 位，每 sys_clk 周期累加 step，
    step = round(2^acc_bits * FS_HZ / fclk)。
    溢出时产生一个 sample_tick。当 step 不是精确值时产生长期频率误差。
    """
    import math
    full = 1 << acc_bits
    exact_step = full * FS_HZ / fclk
    step = round(exact_step)

    if step == 0:
        return None

    # 长期平均频率
    actual_fs = step * fclk / full
    err_ppm = (actual_fs - FS_HZ) / FS_HZ * 1e6

    # step 量化误差（相对）
    step_err = abs(step - exact_step) / exact_step

    return {
        "acc_bits": acc_bits,
        "exact_step": exact_step,
        "step": step,
        "actual_fs": actual_fs,
        "err_ppm": err_ppm,
        "step_err": step_err,
    }


def jitter_analysis(fclk, acc_bits):
    """相位累加方案的 tick 间隔抖动。"""
    full = 1 << acc_bits
    exact_step = full * FS_HZ / fclk
    step = round(exact_step)

    # 间隔（以 sys_clk 周期计）在 floor(1/x) 和 ceil(1/x) 之间交替
    nominal = full / step  # 平均间隔，单位 sys_clk 周期
    lo = int(nominal)      # 下取整
    hi = lo + 1            # 上取整

    # 两种间隔的比例
    frac = nominal - lo
    n_hi = round(frac * step)   # ？

    period_ns = 1e9 / fclk
    jitter_ns = (hi - lo) * period_ns
    jitter_pct = (hi - lo) / nominal * 100

    return {
        "nominal_cycles": nominal,
        "lo": lo,
        "hi": hi,
        "jitter_ns": jitter_ns,
        "jitter_pct": jitter_pct,
        "period_ns": period_ns,
    }


def main():
    section("一 整数分频可行性")
    print(f"{'sys_clk':<16}{'分频比':>10}{'是否可整除':>14}{'说明':<34}")
    print("-" * 72)
    for fclk, name, note in CANDIDATES:
        div = analyze_divide(fclk)
        if div:
            print(f"{name:<16}{div:>10}{'是':>14}  {note:<34}")
        else:
            print(f"{name:<16}{'—':>10}{'否':>14}  {note:<34}")

    section("二 相位累加方案（32 位累加器）")
    print(f"{'sys_clk':<16}{'step(理想)':>14}{'step(取整)':>12}{'实际频率':>16}{'误差ppm':>12}")
    print("-" * 72)
    for fclk, name, note in CANDIDATES:
        r = phase_accum_error(fclk, 32)
        if r is None:
            print(f"{name:<16}{'—':>14}")
            continue
        print(f"{name:<16}{r['exact_step']:>14.4f}{r['step']:>12}"
              f"{r['actual_fs']:>16.6f}{r['err_ppm']:>12.4f}")

    section("三 音频标准频率的整数分频方案抖动")
    print("（整数分频无量化误差，但 tick 间隔仍可能有量化抖动）")
    print()
    print(f"{'sys_clk':<16}{'分频比':>8}{'标称间隔':>10}{'实际间隔':>10}"
          f"{'抖动':>12}{'相对':>10}")
    print("-" * 72)
    for fclk, name, note in CANDIDATES:
        div = analyze_divide(fclk)
        if not div:
            continue
        # 整数分频：每 div 个周期产生一个 tick，无抖动
        print(f"{name:<16}{div:>8}{'—':>10}{f'{div} 周期':>10}"
              f"{'0':>12}{'0%':>10}")

    section("四 非整除频率的相位累加抖动")
    print(f"{'sys_clk':<16}{'标称周期数':>14}{'间隔取值':>14}{'抖动(ns)':>12}{'相对':>10}")
    print("-" * 72)
    for fclk, name, note in CANDIDATES:
        if analyze_divide(fclk):
            print(f"{name:<16}{'整数分频，无抖动':>14}")
            continue
        j = jitter_analysis(fclk, 32)
        rng = f"{j['lo']}~{j['hi']}"
        print(f"{name:<16}{j['nominal_cycles']:>14.4f}{rng:>14}"
              f"{j['jitter_ns']:>12.3f}{j['jitter_pct']:>9.3f}%")

    section("五 关键发现：相位累加在整除时退化为整数分频")
    print("观察上表：音频标准频率下，32 位相位累加的 step 是精确整数")
    print("（24.576 MHz -> 8388608，49.152 MHz -> 4194304，98.304 MHz -> 2097152），")
    print("量化误差与 tick 抖动均为 0。")
    print()
    print("这意味着相位累加器与整数分频器在整除时行为完全等价：")
    print("累加器每次加 2^n，溢出周期恰好为 2^32 / 2^n = 2^(32-n) 个时钟，")
    print("结果就是分频比 2^(32-n) 的整数分频器。")
    print()
    print("结论：RTL 只需实现相位累加一个模块，无需分支。")
    print("      整除时自动获得整数分频的无抖动特性；")
    print("      非整除时自动获得最接近的长期平均频率。")

    section("六 结论与建议")
    print("1. 推荐 sys_clk 取音频标准频率，可整数分频到 48 kHz，")
    print("   无量化误差、无 tick 抖动。优先 98.304 MHz（分频比 2048，时序余量大），")
    print("   资源或时序紧张时退回 49.152 MHz（分频比 1024）或 24.576 MHz。")
    print()
    print("2. 若板载晶振不是音频标准频率，用 PLL 倍频到 98.304 MHz。")
    print("   不做此步时，相位累加仍能工作，但有 tick 间隔抖动，见第四节。")
    print()
    print("3. sample_tick_gen 用单一相位累加结构，参数化 ACC_BITS 与 PHASE_STEP，")
    print("   晶振频率核实后只需改参数，不需重写 RTL。")

    section("七 待核实")
    print("- 板载晶振频率：必须查原理图或实测，不得猜测")
    print("- PLL 可用性与输出范围：查 Gowin 器件手册与工具报告")
    print("- 98.304 MHz 下后续模块的时序收敛能力：需综合与时序分析")


if __name__ == "__main__":
    main()
