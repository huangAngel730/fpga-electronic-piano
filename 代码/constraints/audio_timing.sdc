// -----------------------------------------------------------------------------
// audio_timing.sdc
// 音频链路时序约束。对应任务 T019 与 T005，接口规范 v1.1 第 2、5 节。
//
// 依据：代码/docs/模块接口规范.md 2.1 至 2.5 节
//      分析：代码/scripts/analyze_clock_50m.py
//      板卡：代码/docs/板级硬件事实.md 3.3、3.7 节
//      器件：代码/docs/PT8211_V1.7_E_数据手册.pdf（16 位 LSBJ DAC）
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// 一 sys_clk
//
// 板载晶振 50 MHz（2026-09-12 确认，见 板级硬件事实.md 3.3 节）。
// 引脚 V22，LVCMOS33，BANK_VCCIO = 3.3 V（依据 Sipeed 官方 .cst）。
//
// 50 MHz 周期 = 20.000 ns。
//
// 【为什么不倍频到 98.304 MHz】
// 50 MHz 无法精确倍频到音频标准频率。Gowin rPLL 的 IDIV/FBDIV 为整数，
// 在 IDIV<=64、FBDIV<=128 范围内最接近 98.304 MHz 的是
//   IDIV=59, FBDIV=116 -> 98.305085 MHz，误差 +11.03 ppm
// 精度反而不如 50 MHz 直接分频（+0.096 ppm），且多消耗一个 PLL 和 BUFG。
// 因此选择 50 MHz 直接驱动，不倍频。详见 analyze_clock_50m.py。
// -----------------------------------------------------------------------------
create_clock -name sys_clk -period 20.000 [get_ports sys_clk]

// -----------------------------------------------------------------------------
// 二 I2S 输出时钟
//
// 接口规范 2.4 节：BCLK = 48 kHz x 64 = 3.072 MHz；LRCLK = BCLK / 64 = 48 kHz。
//
// 【关键约束】BCLK 不能用整数分频产生。
//   50 MHz / 3.072 MHz = 16.276042，不是整数。
//   整数分频只能取 16 或 17：
//     50 / 16 = 3.125000 MHz，误差 +17253 ppm，音高偏高约 0.29 半音
//     50 / 17 = 2.941176 MHz，误差 -42586 ppm，音高偏低约 0.75 半音
//   +0.29 半音的走音人耳可直接察觉，因此整数分频方案不可用。
//
// 【实施方案】BCLK 用与 sample_tick 相同的相位累加结构产生：
//   PHASE_STEP = round(2^32 x 3.072e6 / 50e6) = 263882791 (0x0FBA8827)
//   实际 BCLK = 3.072000004 MHz，误差 +0.0013 ppm
//   LRCLK 由同一累加器加 6 位计数器产生，天然保证 64:1 整数关系。
//
// 【抖动说明】相位累加的 BCLK 周期不均匀，存在 +-1 个 sys_clk 周期
//   （20 ns）的抖动。对 PT8211 一类 I2S/LSBJ DAC，BCLK 抖动会直接调制
//   输出采样时刻，需在音频验收时评估 THD+N。若实测指标不达标，
//   备选方案是用 PLL 产生 98.304 MHz 后整数 32 分频，可获得无抖动 BCLK。
//
// BCLK 为内部生成时钟，实现已于 T005 落地（rtl/audio_out/i2s_tx.sv）。
//
// 【约束方式说明】BCLK/LRCLK 不是从专用时钟资源分频得到的，而是由
//   sys_clk 下的普通寄存器经时钟使能 bclk_ce 翻转产生。对这类信号，
//   用 create_generated_clock -divide_by N 描述是错的：它假定存在一个
//   与源时钟有整数分频关系的物理时钟网络，而 50e6/3.072e6 = 16.276042
//   并非整数，且该寄存器输出并未走时钟树。
//
//   正确做法是用 set_output_delay -clock <虚拟时钟> 约束数据输出路径，
//   虚拟时钟表达"片外接收器件看到的时钟"。PT8211 实际看到的是 FPGA
//   引脚上带抖动的 BCLK，因此虚拟时钟周期取名义值 325.520833 ns，
//   再用 set_clock_uncertainty 把 +-20 ns 的相位累加抖动算进去。
//
//   这样约束的意义是：报告 IO 时序时按片外 DAC 的真实时钟关系计算，
//   而不是按 sys_clk 的 20 ns 错误地宽松化。
// -----------------------------------------------------------------------------

// 片外 DAC 视角的 BCLK 虚拟时钟：3.072 MHz
create_clock -name i2s_bclk_virt -period 325.520833
// 片外 DAC 视角的 LRCLK 虚拟时钟：48 kHz
create_clock -name i2s_lrclk_virt -period 20833.333333

// BCLK 抖动上限 +-20 ns 计入不确定度，避免按理想 3.072 MHz 报虚假收敛。
set_clock_uncertainty -setup 20.000 [get_clocks i2s_bclk_virt]
set_clock_uncertainty -hold   5.000 [get_clocks i2s_bclk_virt]
set_clock_uncertainty -setup 20.000 [get_clocks i2s_lrclk_virt]
set_clock_uncertainty -hold   5.000 [get_clocks i2s_lrclk_virt]

// PT8211 手册（V1.7，Timing Characteristics）要求：
//   tH（数据保持）>= 25 ns，tR / tF <= 20 ns，Fbck <= 18.4 MHz。
// 实现上 BCLK 在 clk 下降沿更新、DIN 在 clk 上升沿更新，两者相差
// 半个 sys_clk 周期（10 ns），使 BCLK 两个边沿都落在 DIN 稳定窗口中央。
// 下面的输出延迟按引脚与走线确定后再用布局布线报告校正。
// TODO(引脚确定后)：替换占位数值并补齐 get_ports 的实际端口名。
set_output_delay -clock i2s_bclk_virt  -max 5.000 [get_ports i2s_bclk]
set_output_delay -clock i2s_bclk_virt  -min 0.000 [get_ports i2s_bclk]
set_output_delay -clock i2s_bclk_virt  -max 5.000 [get_ports i2s_din]
set_output_delay -clock i2s_bclk_virt  -min 0.000 [get_ports i2s_din]
set_output_delay -clock i2s_lrclk_virt -max 5.000 [get_ports i2s_lrclk]
set_output_delay -clock i2s_lrclk_virt -min 0.000 [get_ports i2s_lrclk]

// -----------------------------------------------------------------------------
// 三 异步输入
//
// MIDI 输入为异步串行信号（31.25 kbaud），相对 sys_clk 完全异步。
// 其同步处理在 rtl/input/ 内实现，由 M3 负责。
// 相关引脚需要设置输入延迟约束，待引脚确定后补充。
//
// 外部 rst_n 为异步复位（引脚 AA13），已在 reset_sync 中做同步释放处理。
// 注意：官方 .cst 中 sys_rst_n 的电平标准为 LVCMOS15 / BANK_VCCIO=1.5，
//       与 sys_clk 的 LVCMOS33 / 3.3 V 不同，接线时必须核对。
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// 四 待补充项
//
// 已完成：
//   [x] 板载晶振频率核实 -> 50 MHz
//   [x] sys_clk 的 create_clock 周期 -> 20.000 ns
//   [x] 确认不倍频到 98.304 MHz（精度反而更差）
//   [x] 确认 BCLK 必须用相位累加（整数分频误差 +17253 ppm 不可用）
//   [x] BCLK / LRCLK 相位累加器实现落地（T005，rtl/audio_out/i2s_tx.sv）
//   [x] 用虚拟时钟描述片外 DAC 视角的 BCLK / LRCLK（见第二节）
//
// 待完成：
//   [ ] 引脚约束（CST）确定后，把上面的 set_output_delay 占位值
//       换成按实际走线计算的数值，并核对 i2s_bclk / i2s_lrclk / i2s_din
//       三个端口名与顶层一致
//   [ ] 首次综合后，检查时序报告是否收敛
//   [ ] 上板实测 BCLK 频率与 I2S 波形，验证 DAC 输出 THD+N
//       （PT8211 手册 THD 典型值 0.13% 约 -57.7 dB，是整条音频链的上限；
//        评估算法优化收益前先确认瓶颈不在此处）
//
// 注意：以上未完成项均不影响约束本身的语法正确性，但影响时序收敛
//       判定的充分性。在引脚确定前，第二节的 set_output_delay 仅是占位。
// -----------------------------------------------------------------------------
