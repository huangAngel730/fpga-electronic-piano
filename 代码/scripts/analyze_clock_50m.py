"""
50 MHz 晶振下的音频时钟方案分析。

背景：板载晶振实测为 50 MHz（T019 待核实项，2026-09-12 由用户查看板卡确认）。
50 MHz 不能被 48 kHz 整除，需要定量评估误差，并决定是否使用 PLL。

用法：
    python -X utf8 代码/scripts/analyze_clock_50m.py
"""

import math

FS = 48_000
FCLK = 50_000_000
ACC_BITS = 32
ACC_MOD = 1 << ACC_BITS


def fmt_ppm(ppm):
    return f"{ppm:+.4f} ppm"


print("=" * 74)
print("50 MHz 直接驱动相位累加器")
print("=" * 74)

# 精确分频比
ratio = FCLK / FS
print(f"FCLK / FS = {FCLK} / {FS} = {ratio}")
print(f"  整数部分 {int(ratio)}，小数部分 {ratio - int(ratio):.6f}")
print(f"  -> 不是整数，无法用固定分频比得到精确 48 kHz")
print()

step = (ACC_MOD * FS + FCLK // 2) // FCLK
print(f"相位步进 PHASE_STEP = round(2^32 x 48000 / 50000000) = {step}")
print(f"  ({step} = 0x{step:08X})")
print(f"  是 2 的整数次幂吗: {step & (step - 1) == 0}")
print()

f_actual = step * FCLK / ACC_MOD
err_hz = f_actual - FS
err_ppm = err_hz / FS * 1e6
print(f"实际平均采样率 = {step} x 50e6 / 2^32 = {f_actual:.6f} Hz")
print(f"频率误差 = {err_hz:+.6f} Hz = {fmt_ppm(err_ppm)}")
print()

# 溢出周期（非整数，需要抖动分析）
cycles_per_tick = ACC_MOD / step
print(f"平均溢出周期 = 2^32 / {step} = {cycles_per_tick:.6f} 时钟")
print(f"  即每隔 {cycles_per_tick:.4f} 个时钟产生一次 sample_tick")
print()

# 抖动：溢出周期在 floor 和 ceil 之间交替
lo = math.floor(cycles_per_tick)
hi = math.ceil(cycles_per_tick)
frac = cycles_per_tick - lo
print(f"抖动模式：间隔在 {lo} 与 {hi} 个时钟之间交替")
print(f"  {lo} 的比例 = {1 - frac:.6f}")
print(f"  {hi} 的比例 = {frac:.6f}")
print(f"  峰峰抖动 = {hi - lo} 个时钟 = {(hi - lo) / FCLK * 1e9:.1f} ns")
print()

# 抖动对音频的影响：sample_tick 用于驱动音频采样
# 间隔抖动会导致采样时刻不均匀，产生边带
print("抖动对音频的影响：")
print(f"  采样周期标称 = 1/48000 = {1/FS*1e6:.3f} us")
print(f"  单次间隔偏差 = 1 个时钟 = {1/FCLK*1e9:.1f} ns")
print(f"  相对抖动 = {1/FCLK / (1/FS) * 100:.6f} %")
jitter_ppm = (1 / FCLK) / (1 / FS) * 1e6
print(f"            = {fmt_ppm(jitter_ppm)}")
print(f"  等效于采样时钟相位噪声，约 {20*math.log10(1/FCLK/(1/FS)):.1f} dBc 的边带")
print()

print("=" * 74)
print("方案对比")
print("=" * 74)
print()

# 方案 A：直接 50 MHz
print("方案 A：50 MHz 直接驱动（不改硬件，PLL 不用）")
print(f"  平均采样率误差 : {fmt_ppm(err_ppm)}  （优秀，远好于人耳分辨）")
print(f"  瞬时抖动       : +-1 时钟 = +-20.0 ns，峰峰 20 ns")
print(f"  资源           : 0 个 PLL / 0 个 BUFG，纯逻辑")
print(f"  风险           : 抖动注入音频链，需要评估对 THD+N 的影响")
print()

# 抖动的实际影响评估
# sample_tick 通常用于"每采样处理一次"，抖动会让相邻采样间隔不等
# 对于用 sample_tick 做节拍、而不是直接做 DAC 时钟的场景，影响很小
print("  关键判断：sample_tick 的用途决定抖动是否重要")
print("    - 若 sample_tick 只作为'处理节拍'（每 tick 算一个样点），")
print("      间隔抖动不改变数值结果，只改变算完的时刻，")
print("      只要平均速率精确、FIFO 深度够吸收，就完全可接受。")
print("    - 若 sample_tick 直接当 DAC 采样时钟，抖动会调制输出波形。")
print("      但本项目的音频出口是 I2S，BCLK 由独立分频产生，")
print("      采样率准确性由 BCLK/LRCLK 保证，不由 sample_tick 保证。")
print("    -> 本项目属于前者，抖动可接受。")
print()

# 方案 B：PLL 到 98.304 MHz
print("方案 B：rPLL 倍频到 98.304 MHz")
target = 98_304_000
print(f"  目标频率       : {target/1e6:.3f} MHz")
print(f"  50 MHz -> 98.304 MHz 需要倍频 {target/FCLK:.6f}")
print(f"  能否整数实现   : 需要 IDIV={FCLK//1000}kHz 级精度，Gowin rPLL 参数为整数")
# 检查是否可表示为 CLKOUT = FCLK * (FBDIV_SEL+1) / (IDIV_SEL+1)
found = None
for idiv in range(1, 64):
    for fbdiv in range(1, 128):
        f = FCLK * fbdiv / idiv
        if abs(f - target) < 1000:  # 1 kHz 容差
            found = (idiv, fbdiv, f)
            break
    if found:
        break
if found:
    idiv, fbdiv, f = found
    print(f"  可行参数       : IDIV={idiv} FBDIV={fbdiv} -> {f/1e6:.6f} MHz")
    print(f"  误差           : {fmt_ppm((f-target)/target*1e6)}")
else:
    print(f"  在 IDIV<=64, FBDIV<=128 范围内找不到误差 <1 kHz 的参数")
    print(f"  说明 50 MHz 难以精确倍频到 98.304 MHz")
    # 找最接近的
    best = None
    for idiv in range(1, 64):
        for fbdiv in range(1, 128):
            f = FCLK * fbdiv / idiv
            e = abs(f - target)
            if best is None or e < best[2]:
                best = (idiv, fbdiv, e, f)
    idiv, fbdiv, e, f = best
    print(f"  最接近         : IDIV={idiv} FBDIV={fbdiv} -> {f/1e6:.6f} MHz")
    print(f"  误差           : {e/1000:.3f} kHz = {fmt_ppm(e/target*1e6)}")
print()

# 方案 C：换晶振
print("方案 C：改用音频专用晶振（如 24.576 MHz）")
print(f"  24.576 MHz 分频比 = {24_576_000/FS}  (整数)")
print(f"  98.304 MHz 分频比 = {98_304_000/FS}  (整数)")
print(f"  误差           : 0 ppm，抖动 0")
print(f"  代价           : 需要改硬件（换晶振），竞赛周期内不现实")
print()

print("=" * 74)
print("结论")
print("=" * 74)
print(f"""
1. 50 MHz 下相位累加器的长期平均采样率误差仅 {err_ppm:.4f} ppm，
   完全满足音频要求（人耳可辨阈约 1000 ppm / 音分级别）。

2. 代价是 sample_tick 间隔存在 +-1 时钟（20 ns）抖动。
   但本项目 sample_tick 是"处理节拍"而非 DAC 时钟：
   音频输出的采样率由 I2S 的 BCLK/LRCLK 保证，而 BCLK 同样由
   相位累加器产生（见下方核对），其长期平均误差仅 +0.0013 ppm。
   因此该抖动不影响输出采样率的准确性。

3. 不需要 PLL。T019 现有 RTL 结构（相位累加器）无需修改，
   只需把 PHASE_STEP 改为 {step}，把约束里的时钟周期改为 20.000 ns。

4. 需要补充验证：BCLK 的相位累加器实现及其抖动，
   见下方的专项核对。50e6 / 3.072e6 = 16.276042，不能整数分频。
""")

print("=" * 74)
print("补充核对：50 MHz 下的 I2S 时钟")
print("=" * 74)
BCLK = 3_072_000
print(f"BCLK 目标 = {BCLK/1e6:.3f} MHz")
print(f"50e6 / 3.072e6 = {FCLK/BCLK:.6f}  （不是整数）")
# 用相位累加器产生 BCLK
bstep = (ACC_MOD * BCLK + FCLK // 2) // FCLK
bf = bstep * FCLK / ACC_MOD
print(f"相位累加器: step = {bstep} (0x{bstep:08X})")
print(f"  实际 BCLK = {bf/1e6:.9f} MHz")
print(f"  误差 = {(bf-BCLK)/BCLK*1e6:+.4f} ppm")
print(f"  是 2 的幂 = {bstep & (bstep-1) == 0}")
print()
print(f"LRCLK = BCLK / 64 = {bf/64/1000:.6f} kHz")
print(f"  vs 目标 48 kHz，误差 {(bf/64-FS)/FS*1e6:+.4f} ppm")
print()
print("注意：BCLK 与 LRCLK 必须严格 64:1，否则帧长不对。")
print("用同一个相位累加器 + 6 位计数器即可保证整数关系，")
print("但累加器抖动会让 BCLK 周期不均匀 —— 对 I2S 接收端")
print("（如 PCM5102）通常可容忍，但必须在约束和文档中注明。")
print()
print("建议：BCLK 直接用 50 MHz 整数分频到最接近的值，")
for div in [16, 17]:
    f = FCLK / div
    print(f"  50/{div} = {f/1e6:.6f} MHz，与 3.072 MHz 差 {(f-BCLK)/BCLK*1e6:+.1f} ppm")
print("  16 分频得 3.125 MHz（+1.7%，音高偏高约 0.3 半音，不可接受）")
print("  因此 BCLK 必须用相位累加器或 PLL，不能简单整数分频。")
