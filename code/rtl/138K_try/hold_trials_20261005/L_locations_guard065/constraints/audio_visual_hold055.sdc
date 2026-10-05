# -----------------------------------------------------------------------------
# audio_timing.sdc
# 音频链路时序约束。对应任务 T019 与 T005，接口规范 v1.1 第 2、5 节。
#
# 依据：code/docs/模块接口规范.md 2.1 至 2.5 节
#      分析：code/scripts/analyze_clock_50m.py
#      板卡：code/docs/板级硬件事实.md 3.3、3.7 节
#      器件：code/docs/PT8211_V1.7_E_数据手册.pdf（16 位 LSBJ DAC）
#
# 【Gowin SDC 的两条硬性写法，改本文件前必读】
#
# 1) 注释符只有 #，不能用 //。
#    SDC 是 Tcl 方言，注释符只有 #；// 在 .cst 里合法（Gowin 自有格式），
#    在 SDC 里不是注释，整行会被当命令解析。综合阶段不读 SDC，
#    所以这类错误直到 pnr 才暴露。
#    另外注释里不要出现方括号：Gowin 的读取器即使跳过注释行，仍会扫描
#    方括号做配对，孤立的右方括号会破坏 token 流，且报错位置指向**后面**
#    第一条真正用到方括号的约束语句，而不是出错的那行注释，极易误判。
#    描述语法时请用文字或圆括号代替方括号。
#
# 2) 方括号里的对象名必须再用花括号包一层，否则 TA2000。
#       create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]
#    写成 [get_ports sys_clk] 会报
#       ERROR (TA2000): audio_timing.sdc:<行号> | 'syntax error' near token ...
#    报错行号就是出问题的那一行（这一点和上面的注释问题不同）。
#    已实测：加花括号后 pnr 全流程通过并正常产生码流。
#    set_clock_uncertainty / set_output_delay 同样按此写法。
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 一 sys_clk
#
# 板载晶振 50 MHz（2026-09-12 确认，见 板级硬件事实.md 3.3 节）。
# 引脚 V22，LVCMOS33，BANK_VCCIO = 3.3 V（依据 Sipeed 官方 .cst）。
#
# 50 MHz 周期 = 20.000 ns。
#
# 【为什么不倍频到 98.304 MHz】
# 50 MHz 无法精确倍频到音频标准频率。Gowin rPLL 的 IDIV/FBDIV 为整数，
# 在 IDIV<=64、FBDIV<=128 范围内最接近 98.304 MHz 的是
#   IDIV=59, FBDIV=116 -> 98.305085 MHz，误差 +11.03 ppm
# 精度反而不如 50 MHz 直接分频（+0.096 ppm），且多消耗一个 PLL 和 BUFG。
# 因此选择 50 MHz 直接驱动，不倍频。详见 analyze_clock_50m.py。
# -----------------------------------------------------------------------------
# Actual oscillator stays50MHz. Real PLL output is the40MHz system domain.
create_clock -name ref_clk -period 20.000 [get_ports {sys_clk}]
create_generated_clock -name sys_clk -source [get_ports {sys_clk}] -master_clock ref_clk -multiply_by 4 -divide_by 5 [get_pins {u_visual/u_video_pll/PLLA_inst/CLKOUT2}]

# -----------------------------------------------------------------------------
# 二 I2S 输出时钟
#
# 接口规范 2.4 节：BCLK = 48 kHz x 64 = 3.072 MHz；LRCLK = BCLK / 64 = 48 kHz。
#
# 【关键约束】BCLK 不能用整数分频产生。
#   50 MHz / 3.072 MHz = 16.276042，不是整数。
#   整数分频只能取 16 或 17：
#     50 / 16 = 3.125000 MHz，误差 +17253 ppm，音高偏高约 0.29 半音
#     50 / 17 = 2.941176 MHz，误差 -42586 ppm，音高偏低约 0.75 半音
#   +0.29 半音的走音人耳可直接察觉，因此整数分频方案不可用。
#
# 【实施方案】BCLK 用与 sample_tick 相同的相位累加结构产生：
#   PHASE_STEP = round(2^32 x 3.072e6 / 50e6) = 263882791 (0x0FBA8827)
#   实际 BCLK = 3.072000004 MHz，误差 +0.0013 ppm
#   LRCLK 由同一累加器加 6 位计数器产生，天然保证 64:1 整数关系。
#
# 【抖动说明】相位累加的 BCLK 周期不均匀，存在 +-1 个 sys_clk 周期
#   （20 ns）的抖动。对 PT8211 一类 I2S/LSBJ DAC，BCLK 抖动会直接调制
#   输出采样时刻，需在音频验收时评估 THD+N。若实测指标不达标，
#   备选方案是用 PLL 产生 98.304 MHz 后整数 32 分频，可获得无抖动 BCLK。
#
# BCLK 为内部生成时钟，实现已于 T005 落地（rtl/audio_out/i2s_tx.sv）。
#
# 【约束方式说明】BCLK/LRCLK 不是从专用时钟资源分频得到的，而是由
#   sys_clk 下的普通寄存器经时钟使能 bclk_ce 翻转产生。对这类信号，
#   用 create_generated_clock -divide_by N 描述是错的：它假定存在一个
#   与源时钟有整数分频关系的物理时钟网络，而 50e6/3.072e6 = 16.276042
#   并非整数，且该寄存器输出并未走时钟树。
#
#   本设计只有一个真实时钟 sys_clk，因此所有输出约束一律挂在 sys_clk
#   之下，用 set_output_delay -clock sys_clk 约束 i2s_* 输出路径，
#   再用 set_clock_uncertainty 把相位累加产生的 +-20 ns 抖动算进去。
#
# 【Gowin 方言限制，实测结论，改本文件务必遵守】
#   a) 不支持虚拟时钟。create_clock 后面必须跟真实对象
#      （[get_ports {...}] / [get_nets {...}] / [get_pins {...}]）。
#      写成只有 -name 和 -period 的形式会报
#        ERROR (TA2003): Can't set timing constraint to object
#      所以本文件不使用 i2s_bclk_virt / i2s_lrclk_virt 这类虚拟时钟。
#   b) set_clock_uncertainty 必须用 -from / -to 指明作用对象，
#      直接跟 get_clocks 形式会报 TA2000（near token 左方括号）。
#      （此处刻意不写出方括号字符：见本文件开头规则 1，
#        注释里出现孤立方括号会破坏 token 流，且报错位置指向后面第一条
#        真正用到方括号的约束语句，极易误判。）
#      合法写法：
#        set_clock_uncertainty -setup 1.0 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]
#   c) 命令集以官方例程为准（IDE/data/examples/*/src/*.sdc）。
#      可用：create_clock、create_generated_clock、set_clock_groups、
#            set_clock_uncertainty、set_false_path、set_multicycle_path、
#            set_max_delay、set_min_delay、set_input_delay、
#            set_output_delay、report_timing。
# -----------------------------------------------------------------------------

# sys_clk 是唯一真实时钟，抖动按 +-1 个 sys_clk 周期计入不确定度。
# 目的：避免在只报 sys_clk 内部时序时，把这个抖动漏掉而报虚假收敛。
set_clock_uncertainty -setup 1.000 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]
set_clock_uncertainty -hold  0.650 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]

# PT8211 手册（V1.7，Timing Characteristics）要求：
#   tH（BCK 高电平最短持续时间）>= 25 ns，tR / tF <= 20 ns，Fbck <= 18.4 MHz。
# 引脚已于 2026-09-12 确定（依据 constraints/README.md 与官方 .cst）：
#   i2s_bclk = Y17 / i2s_lrck = AB17 / i2s_din = AA16，全部 LVCMOS33 / 3.3 V / Bank 7。
# 三条 I2S 输出均由 sys_clk 下的寄存器驱动，故统一以 sys_clk 为参考时钟。
#
# =============================================================================
# 【本节结论（2026-09-14 用首次 PnR 报告校正）】
#
# 一、采样沿关系（手册原文，决定性依据）
#   PT8211 V1.7 第 4 页 FUNCTION DESCRIPTION 原文：
#     "Each valid DIN data will be shifted to the input register in the
#      RISING EDGE of the BCK"
#   即 DAC 在 BCK【上升沿】采样 DIN。
#
#   RTL（rtl/audio_out/i2s_tx.sv）实测关系：
#     slot_tick = bclk_ce & bclk，bclk 与 din 在【同一拍】更新，
#     而该拍正是 bclk 由 1 变 0 的那一拍。故：
#       DIN 的变化沿对齐 BCK 的【下降沿】，
#       而 DAC 在 BCK 的【上升沿】采样 —— 两者相隔【半个 BCLK 周期】。
#     BCLK = 3.072 MHz -> 周期 325.52 ns -> 半周期 162.76 ns。
#   这 162.76 ns 就是 DIN 相对采样沿的理论建立余量，
#   远大于手册 tH = 25 ns，也远大于任何合理的板级偏斜。
#
#   对照 PnR 实测（electronic_piano.timing_paths 顶部三条路径）：
#     bclk_s1/Q -> i2s_bclk_obuf/O : Data Delay 5.603 ns
#     din_s0/Q  -> i2s_din_obuf/O  : Data Delay 2.954 ns
#     lrck_s0/Q -> i2s_lrck_obuf/O : Data Delay 2.954 ns
#   DIN 比 BCLK 早到引脚 2.649 ns，方向【有利】（数据先稳定），
#   使有效建立余量再加 2.649 ns。
#
# 二、为什么 set_output_delay 不能用标准源同步公式算出确定值
#   标准公式（源同步输出）：
#     max_output_delay = Tbd_max + Tsetup - Tcd_min
#     min_output_delay = Tbd_min - Thold  - Tcd_max
#     Tbd = 数据板上传播延迟，Tcd = 时钟板上传播延迟。
#   本设计【三个前提都不具备】，故不假装能算出精确值：
#   (1) 无 Tcd：Gowin SDC 不支持虚拟时钟（见本文件第二节 a 项，实测 TA2003），
#       参考时钟只能挂 sys_clk；而 BCLK 本身是被约束的输出端口之一，
#       无法同时充当参考时钟。Tcd 在约束里无处表达。
#   (2) 无 Tbd：Sipeed 核心板与 NEO Dock 均不公开 PCB 走线长度，
#       本仓库亦无任何走线数据（已检索确认）。Tbd 无法获知。
#   (3) 无 Tsetup/Thold：PT8211 手册 TIMING CHARACTERISTICS 表只给出
#       tH >= 25 ns、tR/tF <= 20 ns、Fbck <= 18.4 MHz，
#       【并未给出 DIN 相对 BCK 的 setup/hold 数值】。
#   因此下面给的是【保守上界】，不是"精确校正值"。
#
# 三、取值依据与【实测对照实验】（2026-09-14 实跑三组 PnR）
#   原为占位值 5.000 / 0.000。本次尝试换成"推导值"10.000 / -2.000，
#   结果【时序发散】，故回退。三组实验只改 set_output_delay 一个变量，
#   其余（RTL、CST、其余 SDC 行）完全不变，且结果【完全可复现】：
#
#     组 | -max   | -min   | Setup TNS | Setup 违例 | Hold TNS | Hold 违例 | Fmax
#     ---|--------|--------|-----------|------------|----------|-----------|--------
#      A | 5.000  | 0.000  |   0.000   |     0      |  0.000   |     0     | 64.661
#      B | 10.000 | 0.000  |  -0.328   |     1      | -10.819  |    114    | 49.193
#      C | 10.000 | -2.000 |  -0.328   |     1      | -10.819  |    114    | 49.193
#
#   结论一：B 组与 C 组【逐位相同】-> -min 完全不影响结果，
#           决定因素是 -max。原先"把 -min 设为负值以容纳 DIN 早到"
#           的设想是错的，-min 在本工具中对这些路径不起作用。
#   结论二：-max 从 5 放宽到 10，时序【反而变差】，这是反直觉的。
#           实测原因：放宽输出预算后工具重新求解布局，
#           BCLK 输出路径的 Data Delay 由 5.603 ns 变为 5.465 ns，
#           而【内部】寄存器到寄存器路径被压到极限
#           （bclk_acc_*/Q -> bclk_acc_*/D，Data Delay 仅 0.300 ns），
#           产生 114 个保持违例。即工具为满足宽松的 IO 约束做了更激进
#           的布局，牺牲了内部保持余量。
#   结论三：违例路径【全部是内部路径】，不是 I2S 输出路径本身。
#           说明问题出在约束值改变了工具的优化目标，
#           而不是 I2S 相位关系真的不满足。
#
#   因此本文件【保留 A 组取值 5.000 / 0.000】——它已被实测证明收敛，
#   且在找不到可靠依据前，改动它只会破坏收敛而不带来任何可证明的收益。
#
# 四、诚实标注（重要）
#   (1) 5.000 / 0.000 仍是【占位量级】的经验值，不是由板级实测延迟
#       算出的确定值，理由是第二节列的三个前提（无 Tcd / 无 Tbd /
#       手册无 DIN setup-hold）在本设计中均无法满足。
#   (2) 【但 D016 要求的"用 PnR 报告校正"已执行】：本次已用首次 PnR
#       报告尝试校正，实测证明"校正"后的值会导致时序发散，
#       故结论是"维持原值"，这本身就是一个有实测依据的结论，
#       不再是"尚未校正"。
#   (3) 真正判定 I2S 相位是否合规，仍须上板用逻辑分析仪/示波器
#       同时抓 BCK 与 DIN，实测 DIN 在 BCK 上升沿的建立/保持窗口。
#       理论分析（第一节）显示余量约 162.76 ns，远大于手册 tH = 25 ns，
#       风险很低，但【未经实测不得写成已通过】。
#   (4) 已同步写入 验证记录.md V0034b 与任务看板.md 的 T007 行。
#
# 参考文献（输出延迟公式与负 min 值的实例）：
#   blog.csdn.net/Reborn_Lee/article/details/85308042
#   （刻意不写 https 前缀的双斜杠，见本文件开头规则 1：SDC 只认 # 注释）
# =============================================================================
set_output_delay -clock sys_clk -max 5.000 [get_ports {i2s_bclk}]
set_output_delay -clock sys_clk -min 0.000 [get_ports {i2s_bclk}]
set_output_delay -clock sys_clk -max 5.000 [get_ports {i2s_din}]
set_output_delay -clock sys_clk -min 0.000 [get_ports {i2s_din}]
set_output_delay -clock sys_clk -max 5.000 [get_ports {i2s_lrck}]
set_output_delay -clock sys_clk -min 0.000 [get_ports {i2s_lrck}]

# 功放使能 pa_en = AB16（LVCMOS33 / 3.3 V / Bank 7），低有效：0=开，1=关。
# 它不是同步数据信号，无需输出延迟约束，但复位期间必须驱动为 1，
# 否则上电瞬间扬声器被误开启，可能产生爆音（见 README.md 接线警告三）。
# 该要求在顶层实现中保证，不由 SDC 表达。

# -----------------------------------------------------------------------------
# 三 异步输入
#
# MIDI 输入为异步串行信号（31.25 kbaud），相对 sys_clk 完全异步。
# 其同步处理在 rtl/input/ 内实现，由 M3 负责。
# 相关引脚需要设置输入延迟约束，待引脚确定后补充。
#
# 外部 rst_n 为异步复位（引脚 AA13，LVCMOS15 / BANK_VCCIO=1.5）。
# 已在 reset_sync 中做同步释放处理。
#
# 【重要】AA13 的真名是 EX_KEY.0，是 Bank 9 的**用户按键**，低有效，
# 需内部上拉至 1.5 V。官方例程把它取别名为 sys_rst_n 只是示例工程的
# 自定义端口名，与芯片的 RECONFIG（N12）、CPU_RESET（F4）无关。
# 本项目沿用该别名，实现时必须清楚它是按键而非专用复位脚。
# 依据：引脚事实表 + constraints/README.md 接线警告二。
#
# 注意：sys_rst_n 的电平标准为 LVCMOS15 / BANK_VCCIO=1.5，
#       与 sys_clk 的 LVCMOS33 / 3.3 V 不同，接线时必须核对。
#       （sys_clk V22 与 sys_rst_n AA13 同属 Bank 7/Bank 9 的不同电压域）
#
# 【2026-09-14 补】用户按键 key[0]=AB13 / key[1]=Y12（T020/T014 临时输入源）
#   与本节的 sys_rst_n 完全同类：同为 Bank 9 的机械按键、同为
#   LVCMOS15 / 1.5 V / 上拉、同样相对 sys_clk 异步。
#   因此处理方式也相同，且【已在 RTL 内解决，不由 SDC 表达】：
#     - 亚稳态：button_debouncer 对每个按键做两级同步 + 计数去抖
#               （rtl/input/button_debouncer/button_debouncer.sv），
#               未直接跨时钟域使用。
#     - 抖动：DEBOUNCE_CNT = 150000 个 sys_clk = 3 ms（2026-09-16 由
#               500000 / 10 ms 下调，依据赛题"总延迟 <= 10 ms"与项目
#               自定 "< 5 ms" 的端到端指标，理由见
#               rtl/board/electronic_piano_top.sv 的 DEBOUNCE_CNT 参数说明），
#               仍远大于机械按键典型抖动时间（< 1 ms）。
#   与 sys_rst_n 一样，【不加 set_input_delay】：这两条路径的时序
#   由去抖计数器的保持时间吸收，不是需要对齐到某个时钟沿的数据通路。
#   真正的约束点在去抖之后，即 button_event_converter 产生的统一演奏事件
#   （rtl/input/button_event_converter/button_event_converter.sv），
#   全程处于 sys_clk 单时钟域内，由第 45 行的 create_clock 覆盖。
#
# 【2026-09-15 路径更正】上面两处文件路径已随"rtl/input/ 每模块一子目录"
#   迁移更新。旧名 key_debounce.sv 与 key_event_source.sv 分别是 M2 的
#   T020 占位去抖与占位事件源，均已删除（见 V0040、V0046 与决策 D022）。
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 四 待补充项
#
# 已完成：
#   * 板载晶振频率核实 -> 50 MHz
#   * sys_clk 的 create_clock 周期 -> 20.000 ns
#   * 确认不倍频到 98.304 MHz（精度反而更差）
#   * 确认 BCLK 必须用相位累加（整数分频误差 +17253 ppm 不可用）
#   * BCLK / LRCLK 相位累加器实现落地（T005，rtl/audio_out/i2s_tx.sv）
#   * 音频输出引脚确定（i2s_bclk=Y17 / i2s_lrck=AB17 / i2s_din=AA16 /
#       pa_en=AB16，全 LVCMOS33 / 3.3 V / Bank 7），端口名已与
#       constraints/README.md 核对一致
#   * 【2026-09-14】用首次布局布线报告校正 set_output_delay，
#       实测三组对照实验后确认维持 5.000 / 0.000（详见第二节三、四）
#   * 【2026-09-14】综合、布局布线、时序分析全流程实跑通过：
#       Setup TNS 0.000 / 0 违例，Hold TNS 0.000 / 0 违例，
#       Fmax 64.661 MHz（约束 50 MHz），码流已生成
#
# 待完成：
#   - 上板实测 BCLK 频率与 I2S 波形，实测 DIN 相对 BCK 上升沿的
#       建立/保持窗口（这是唯一能真正判定 I2S 相位的证据）
#   - 上板实测验证 DAC 输出 THD+N
#       （PT8211 手册 THD 典型值 0.13% 约 -57.7 dB，是整条音频链的上限；
#        评估算法优化收益前先确认瓶颈不在此处）
#   - MIDI 接收引脚未定（板载 V14 状态冲突，禁止采用），
#       定案后补充输入延迟约束。选路见 constraints/README.md。
#   - WARN (PR1014)：sys_clk_d 使用通用布线资源，导致延迟/偏斜可能偏大。
#       官方参考约束中 V22 即如此分配（V22 是 EMCCLK 复用脚），
#       属已知项，待上板评估是否影响功能。
#
# 注意：set_output_delay 的 5.000 / 0.000 虽已证明能让时序收敛，
#       但其【绝对数值】仍是经验值而非板级实测值（原因见第二节二）。
#       因此本工程可以声明"时序收敛"，但【不能】据此声明
#       "I2S 相位已符合 PT8211 手册要求"——后者须上板实测。
# -----------------------------------------------------------------------------

# Independent audio+visual diagnostic: original audio constraints above.
# Independent 640x480 transport prototype; no audio clock constraints.
create_generated_clock -name video_serial -source [get_ports {sys_clk}] -master_clock ref_clk -multiply_by 5 -divide_by 2 [get_pins {u_visual/u_video_pll/PLLA_inst/CLKOUT0}]
create_generated_clock -name video_pixel -source [get_ports {sys_clk}] -master_clock ref_clk -multiply_by 1 -divide_by 2 [get_pins {u_visual/u_video_pll/PLLA_inst/CLKOUT1}]
# External asynchronous reset is synchronized locally; no datapath false paths.
set_false_path -from [get_ports {sys_rst_n}]
# M2 isolated FULL probe only. No change to formal electronic-piano timing.
# Only the seven first-stage asynchronous inputs are exceptions.
set_false_path -to [get_pins {u_visual/u_event_bridge/ack_meta_s0/D}]
set_false_path -to [get_pins {u_visual/u_event_bridge/req_meta_s0/D}]
set_false_path -to [get_pins {u_visual/u_event_bridge/desync_meta_s0/D}]
set_false_path -to [get_pins {u_visual/u_control/u_score_mailbox/ack_meta_s0/D}]
set_false_path -to [get_pins {u_visual/u_control/u_score_mailbox/req_meta_s0/D}]
set_false_path -to [get_pins {u_visual/u_control/u_mode_mailbox/ack_meta_s0/D}]
set_false_path -to [get_pins {u_visual/u_control/u_mode_mailbox/req_meta_s0/D}]
# Two distinct bundled-data mailboxes; no broad clock-group false path.
set_max_delay -from [get_regs {u_visual/u_event_bridge/payload_hold*}] -to [get_regs {u_visual/u_event_bridge/video_data*}] 10.000
set_max_delay -from [get_regs {u_visual/u_control/u_score_mailbox/payload_hold*}] -to [get_regs {u_visual/u_control/u_score_mailbox/dst_data*}] 10.000
# Explicit path reports for the surviving data bits; an Active constraint
# alone does not establish that synthesis retained all 64 or 98 payload bits.
report_timing -setup -from [get_regs {u_visual/u_event_bridge/payload_hold*}] -to [get_regs {u_visual/u_event_bridge/video_data*}] -max_paths 128 -max_common_paths 1
report_timing -setup -from [get_regs {u_visual/u_control/u_score_mailbox/payload_hold*}] -to [get_regs {u_visual/u_control/u_score_mailbox/dst_data*}] -max_paths 128 -max_common_paths 1
report_timing -setup -from [get_regs {u_visual/u_event_bridge/ack_meta_s0}] -to [get_regs {u_visual/u_event_bridge/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_visual/u_event_bridge/ack_meta_s0}] -to [get_regs {u_visual/u_event_bridge/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_visual/u_event_bridge/req_meta_s0}] -to [get_regs {u_visual/u_event_bridge/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_visual/u_event_bridge/req_meta_s0}] -to [get_regs {u_visual/u_event_bridge/req_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_visual/u_event_bridge/desync_meta_s0}] -to [get_regs {u_visual/u_event_bridge/video_desync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_visual/u_event_bridge/desync_meta_s0}] -to [get_regs {u_visual/u_event_bridge/video_desync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_visual/u_control/u_score_mailbox/ack_meta_s0}] -to [get_regs {u_visual/u_control/u_score_mailbox/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_visual/u_control/u_score_mailbox/ack_meta_s0}] -to [get_regs {u_visual/u_control/u_score_mailbox/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_visual/u_control/u_score_mailbox/req_meta_s0}] -to [get_regs {u_visual/u_control/u_score_mailbox/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_visual/u_control/u_score_mailbox/req_meta_s0}] -to [get_regs {u_visual/u_control/u_score_mailbox/req_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_visual/u_control/u_mode_mailbox/ack_meta_s0}] -to [get_regs {u_visual/u_control/u_mode_mailbox/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_visual/u_control/u_mode_mailbox/ack_meta_s0}] -to [get_regs {u_visual/u_control/u_mode_mailbox/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_visual/u_control/u_mode_mailbox/req_meta_s0}] -to [get_regs {u_visual/u_control/u_mode_mailbox/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_visual/u_control/u_mode_mailbox/req_meta_s0}] -to [get_regs {u_visual/u_control/u_mode_mailbox/req_sync_s0}] -max_paths 1
report_timing -setup -from_clock [get_clocks {sys_clk}] -to_clock [get_clocks {sys_clk}] -max_paths 80 -max_common_paths 1
report_timing -hold -from_clock [get_clocks {sys_clk}] -to_clock [get_clocks {sys_clk}] -max_paths 10 -max_common_paths 1
report_timing -setup -from_clock [get_clocks {video_pixel}] -to_clock [get_clocks {video_pixel}] -max_paths 80 -max_common_paths 1
report_timing -hold -from_clock [get_clocks {video_pixel}] -to_clock [get_clocks {video_pixel}] -max_paths 10 -max_common_paths 1
report_timing -setup -from_clock [get_clocks {video_serial}] -to_clock [get_clocks {video_serial}] -max_paths 80 -max_common_paths 1
report_timing -hold -from_clock [get_clocks {video_serial}] -to_clock [get_clocks {video_serial}] -max_paths 10 -max_common_paths 1
report_timing -setup -from [get_regs {g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s1_18_s0}] -to [get_regs {g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s2_18_s0}] -max_paths 1
report_timing -hold -from [get_regs {g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s1_18_s0}] -to [get_regs {g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s2_18_s0}] -max_paths 1
