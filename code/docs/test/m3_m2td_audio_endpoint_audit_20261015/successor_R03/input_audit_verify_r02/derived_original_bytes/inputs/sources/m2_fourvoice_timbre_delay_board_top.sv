// -----------------------------------------------------------------------------
// electronic_piano_top.sv
// 顶层模块。对应任务 T007（上板点亮与硬件通路验证）。
//
// 板卡：Sipeed Tang Mega 60K 核心板 30354 + NEO Dock 31005
// 器件：GW5AT-LV60PG484AC1/I0（料号段写 PG484A），IDE 封装选 PBG484A，Device Version B
//   Sipeed 官方 Wiki 原文：select the package model PBG484A & Device Version: B in the IDE
//   注意：PG484A 是料号段、PBG484A 是 IDE 封装名，两个层级并存且均非笔误。
//   切勿依据 .gprj 器件数据库里的 PBGA484A 反推（该项曾导致一次误改，已改回）。
//
// -----------------------------------------------------------------------------
// 本顶层的定位：**最小可上板工程**
// -----------------------------------------------------------------------------
// 目的不是实现完整乐器，而是先把"硬件通路"验证通：
//   时钟 -> 复位 -> 音频节拍 -> I2S 发送 -> PT8211 -> 功放 -> 扬声器
//
// 当前保留按键/固定音诊断路径，另接入 31250 baud MIDI 输入、
// 双输入32项公共事件FIFO与四声部DDS/ADSR/混音核心。正常模式输出七字段STAT；
// 固定音模式保留DIAG。Pitch/Mod/Sustain音频效果仍待实现。
//
// 为什么需要一个能发声的测试音而不是直接输出静音：
//   静音无法区分"通路正常但没数据"和"通路某处断了"。
//   一个已知频率、已知幅度的正弦音可以同时验证：
//     1. BCLK/LRCK 频率是否正确（示波器/逻辑分析仪可测）；
//     2. LSBJ 相位是否正确（听感 + 波形）；
//     3. 左右声道是否都有输出；
//     4. 功放使能是否有效（能听到声音即证明 PA_EN 工作）。
//
// -----------------------------------------------------------------------------
// 【上电爆音防护】pa_en 低有效是本设计最关键的板级要求
// -----------------------------------------------------------------------------
//   事实表原文：PA_EN=0 时功放开启，PA_EN=1 时功放关闭；
//               "上电复位阶段应确保扬声器不会被误开启"。
//
//   本实现把 pa_en 直接由复位信号驱动，**不经过任何时钟域**：
//     assign pa_en = ~rst_sync_n;   // 复位期间 rst_sync_n=0 -> pa_en=1 -> 功放关
//
//   为什么不放在 always_ff 里用复位赋值：
//     如果写成 always_ff 里 `if (!rst_n) pa_en <= 1'b1;`，那么在 FPGA 完成
//     配置、时钟尚未稳定、复位尚未释放的这段时间里，pa_en 的实际电平取决于
//     寄存器的上电初值和 IO 的默认状态，不受该 always_ff 控制。
//     组合赋值则完全跟随 rst_sync_n，复位期间恒为 1，不依赖时钟。
//
//   代价：pa_en 与 rst_sync_n 之间是组合路径，会进入时序分析。
//   该路径无时序意义（功放使能的响应时间以毫秒计），但会被工具检查。
//   由于 rst_sync_n 是寄存器输出、pa_en 是直接输出到 IO，路径极短，
//   在 50 MHz 下不构成问题。
//
//   本设计在复位释放后**立即**使能功放。若实测有上电爆音，改进方向是
//   延迟使能并在开始时对输出做淡入，属于后续优化，不在最小工程范围内。
//
// -----------------------------------------------------------------------------
// 【测试音】用相位累加器 + 查表产生正弦
// -----------------------------------------------------------------------------
//   频率 = PHASE_STEP * FCLK / 2^ACC_BITS
//   本设计取 440 Hz（A4，标准音高）：
//     step = round(2^32 * 440 / 50000000) = 37796
//   实际频率 = 37796 * 50e6 / 2^32 = 439.99986 Hz，误差 -0.33 ppm
//
//   正弦表用参数化生成的 256 点、16 位有符号表。选择查表而非 CORDIC：
//   查表无流水线延迟、无收敛问题，且占用的 BRAM 极小（256 x 16 = 4 Kb）。
//
//   幅度取满量程的 1/4（16 位下 8192），留足余量避免任何中间运算溢出，
//   也避免上板第一次发声就满幅输出（安全考虑，见 AGENTS.md 电气安全一节）。
//
// -----------------------------------------------------------------------------
// 引脚（依据 code/constraints/electronic_piano.cst 与 D020）
// -----------------------------------------------------------------------------
//   sys_clk  V22  LVCMOS33 3.3 V  Bank 7  核心板 50 MHz 有源晶振
//   sys_rst_n AA13 LVCMOS15 1.5 V  Bank 9  EX_KEY.0 用户按键，低有效，需内部上拉
//   i2s_bclk Y17  LVCMOS33 3.3 V  Bank 7  接 PT8211-S BCK
//   i2s_lrck AB17 LVCMOS33 3.3 V  Bank 7  接 PT8211-S WS
//   i2s_din  AA16 LVCMOS33 3.3 V  Bank 7  接 PT8211-S DIN
//   pa_en    AB16 LVCMOS33 3.3 V  Bank 7  功放使能，低有效
//   uart_tx  U15  LVCMOS33 3.3 V  Bank 6  板载 USB-UART（BL616），调试输出
//   midi_rx  R17  LVCMOS33 3.3 V          PMOD0_IO5，经外部隔离模块输入
//
// 注意 sys_rst_n 与其余脚电压域不同（1.5 V vs 3.3 V）。
//
// -----------------------------------------------------------------------------
// 时钟域
// -----------------------------------------------------------------------------
//   全设计只有一个时钟域 sys_clk（50 MHz）。
//   bclk_ce / sample_tick 都是**时钟使能**，不是时钟，符合"不使用门控时钟"
//   的约束（接口规范 2.1 节、code/AGENTS.md）。
//   因此不需要任何 CDC 处理，也只需一个 reset_sync。
//
// -----------------------------------------------------------------------------
// 验证
// -----------------------------------------------------------------------------
//   tb/board/tb_electronic_piano_top.sv 自检，覆盖：
//     复位期间 pa_en 必须为 1、复位释放后 I2S 输出、正弦音频率与幅度、
//     BCLK/LRCK 的 64:1 关系、uart_tx 的空闲电平。
// -----------------------------------------------------------------------------

`ifndef M2_FOURVOICE_TIMBRE_DELAY_TOP_SV
`define M2_FOURVOICE_TIMBRE_DELAY_TOP_SV

`timescale 1ns / 1ps

// ISOLATED G: physical input remains 50MHz; all core logic uses PLL 40MHz.
// Video remains 25/125MHz. Legacy frozen-board comments below are not a pin change.
module m2_fourvoice_timbre_delay_board_top #(
    // 系统时钟频率（本板 50 MHz）
    parameter int unsigned CLK_HZ = 40_000_000,
    // 测试音频率（Hz）。用于 TEST_TONE_HZ_MODE 下的固定测试音。
    parameter int unsigned TEST_TONE_HZ = 440,
    // 正弦表深度（必须为 2 的幂，且与 SIN_TABLE 长度一致）
    parameter int unsigned SINE_DEPTH = 256,
    // 输出幅度（16 位有符号）。取满量程 32767 的约 1/4，
    // 既是安全音量，也避免任何中间运算溢出。
    parameter logic signed [15:0] TEST_AMPLITUDE = 16'sd8192,
    // -------------------------------------------------------------------------
    // 【T020 新增】骨架模式开关
    //
    //   SOURCE_MODE = 0（默认）：按键驱动。按 EX_KEY.1/EX_KEY.2 发声，
    //                            松开静音。这是集成骨架的验证目标。
    //   SOURCE_MODE = 1         ：固定测试音。与 T007 行为完全一致，
    //                            上电即持续发声，用于通路自检与回归对照。
    //
    //   为什么保留固定测试音模式：V0035 已用固定音验证过整条硬件通路，
    //   保留它就可以一键切回"已知良好"状态，在按键链路出问题时
    //   快速区分"硬件坏了"与"按键逻辑错了"。这是排障手段，不是冗余代码。
    // -------------------------------------------------------------------------
    parameter int unsigned SOURCE_MODE = 0,
    // 按键去抖门限（时钟周期数）。150000 @ 50 MHz = 3 ms。
    //
    // 【2026-09-16 由 500000（10 ms）下调，依据赛题延迟指标】
    // 赛题原文要求"控制信号到音频输出总延迟 <= 10 ms"（见
    // code/docs/赛题要求对照表.md L39/L45），项目自定目标为 < 5 ms
    // （code/docs/项目事实与范围.md L29）。去抖窗在按键路径上位于最前端，
    // 10 ms 一档就吃掉整个基础预算，端到端必然超标。
    // 机械按键的实际抖动通常在 1-2 ms，3 ms 是"够稳 + 留余量"的常见取值。
    // 改动后：按键路径端到端约 3 ms；MIDI 路径不经去抖，约 1 ms。
    // 两条路都落在项目自定的 5 ms 之内。
    parameter int unsigned DEBOUNCE_CNT = (CLK_HZ / 1000) * 3,
    // 去抖模块（button_debouncer）在换算"毫秒 -> 周期数"时使用的参考时钟频率。
    // 默认等于真实主频 CLK_HZ，此时上板行为与既有的周期数口径完全一致。
    // 仿真时可调小，使短去抖周期仍能精确表达，详见例化处的说明。
    // 该参数只影响去抖时间常数的换算，不改变任何端口或时钟。
    parameter int unsigned DEBOUNCE_CLK_HZ = CLK_HZ
) (
    input  logic sys_clk,     // V22, 50 MHz
    input  logic sys_rst_n,   // AA13, 低有效，1.5 V 域，EX_KEY.0
    // -------------------------------------------------------------------------
    // 【T020 新增】用户按键，低有效（按下 = 0）
    //   key_n[0] = AB13 = EX_KEY.1
    //   key_n[1] = Y12  = EX_KEY.2
    //
    //   【为什么没有 EX_KEY.0】EX_KEY.0 与 sys_rst_n 是同一个球 AA13。
    //   若把它也当音符键，按下时等于按住复位；而 pa_en = ~rst_sync_n，
    //   复位期间功放被关闭，结果是"按下就没声音"，无法作为音符使用。
    //   故 AA13 继续专用于 sys_rst_n，不参与演奏输入。
    //   复位本身不依赖按键：reset_sync 为上电异步复位、同步释放。
    // -------------------------------------------------------------------------
    input  logic [1:0] key_n,
    input  logic midi_rx, // R17, isolated 3.3 V MIDI data
    output logic i2s_bclk,    // Y17  -> PT8211-S BCK
    output logic i2s_lrck,    // AB17 -> PT8211-S WS
    output logic i2s_din,     // AA16 -> PT8211-S DIN
    output logic pa_en,       // AB16, 低有效：0=开，1=关
    output logic uart_tx,     // U15  -> BL616 板载 USB-UART
    output wire tmds_clk_p,tmds_clk_n,
    output wire [2:0] tmds_data_p,tmds_data_n
);

    // -------------------------------------------------------------------------
    // 导入公共定义
    // -------------------------------------------------------------------------
    import audio_defs_pkg::*;

    wire core_clk, visual_pll_locked;
    // Asynchronous assertion, local synchronous release in u_reset_sync.
    // PLL loss now mutes/reinitializes the audio core; unlike the original plan,
    // audio intentionally depends on PLL LOCK because its real clock is PLL-derived.
    wire core_async_rst_n = sys_rst_n && visual_pll_locked;
    localparam logic [TICK_ACC_BITS-1:0] CORE_BCLK_PHASE_STEP =
        phase_step_for(CLK_HZ, 2 * I2S_BCLK_HZ);

    // -------------------------------------------------------------------------
    // 参数计算
    // -------------------------------------------------------------------------

    // 测试音相位步进。
    //
    // 【关键：分母是采样率 Fs，不是系统时钟】
    //   累加器只在 sample_tick 上推进，即每秒推进 Fs = 48000 次，
    //   所以步进必须按采样率算：
    //     TONE_STEP = round(2^32 * TEST_TONE_HZ / SAMPLE_RATE_HZ)
    //   最初写成除以 CLK_HZ(50 MHz)，是把"每个系统时钟"和
    //   "每个采样节拍"混为一谈，结果音高偏低 50e6/48000 = 1041.67 倍，
    //   440 Hz 变成了 0.42 Hz —— 听感上就是没有声音，
    //   表现为 DIN 恒为 0。
    //
    // 用 64 位中间量避免左移溢出；不写位宽转换（见下方 cast 说明）。
    localparam logic [TICK_ACC_BITS-1:0] TONE_STEP =
        ( (64'd1 << TICK_ACC_BITS) * TEST_TONE_HZ + (SAMPLE_RATE_HZ >> 1) )
        / SAMPLE_RATE_HZ;

    // 正弦表索引位宽
    localparam int unsigned SINE_IDX_BITS = $clog2(SINE_DEPTH);

    // -------------------------------------------------------------------------
    // 正弦表（256 点，16 位有符号，幅度 +/-8192）
    //
    // 【表已移出本文件】表值定义在 code/rtl/common/sine_table.svh，
    // 本文件只 include，不再内联 256 个字面量。
    //
    // 为什么移出去：原先字面量直接内联在本文件里，导致
    //   (1) 任何新合成模块想复用这张表，只能复制粘贴 256 个数字，
    //       或者先重构本顶层；
    //   (2) 生成脚本要往本文件里回写，脚本与顶层相互耦合。
    // 现在表是 common/ 下的独立头文件，脚本只产出那一个文件，
    // 谁都能 include，与本顶层解耦。
    //
    // 【表的形状由两个工具限制共同决定，不是随意选的】
    //   - GowinSynthesis 不支持 real 与 $sin，报 ERROR (EX3956)，
    //     故表必须是预先算好的整数常量，不能在综合期算；
    //   - iverilog 不支持 unpacked array parameter，
    //     故表必须是打包向量（packed vector）。
    //   打包向量是纯 Verilog-2001，两个工具都接受。
    //
    // 【数值约定】第 i 项 = round(sin(2*pi*i/SINE_DEPTH) * TEST_AMPLITUDE)，
    // 四舍五入到最近整数（half away from zero），量程 +/-8192。
    // 表由 code/scripts/gen_sine_table.py 生成；改动后必须重跑
    //   python -X utf8 code/scripts/gen_sine_table.py --check
    // 因为表错不会让综合报错，只会让音高或幅度悄悄跑偏。
    //
    // 索引即相位，天然覆盖 0..2*pi 全周，不需要处理象限与符号。
    // -------------------------------------------------------------------------
    // -------------------------------------------------------------------------
    // 正弦查表
    //
    // 【正弦表定义在 simple_voice 里，本文件不再 include 头文件】
    //   sine_table.svh 的 ifndef 卫士是**全局**的：同一编译单元内第二次
    //   include 会被静默跳过，既不报重复定义、也不提供任何定义。
    //   之前顶层和 simple_voice 各 include 一次，iverilog 在 elaboration 报：
    //     error: Unable to bind parameter `SINE_TABLE_DEFAULT' in `...dut'
    //   故全设计只保留一个 include 点（simple_voice.sv），
    //   本文件通过层次化引用复用它已展开的查表函数。
    //   这样正弦表只有一份常量、一个 256 选 1 mux，不重复占资源。
    //
    // 【综合后是什么】入参是运行时信号（相位高位），不会折叠成常量，
    // 会综合成一个 256 选 1 的宽 mux。T007 单音测试音下可接受
    // （50 MHz 时序仍有裕量，见 V0031）；多声部时每个声部一份 mux
    // 会显著吃 LUT，T004 应改为 BRAM 查表 + 流水线寄存器，见任务看板 T004。
    // -------------------------------------------------------------------------
    // Local copy of generated constants for fixed-tone elaboration only.
// -----------------------------------------------------------------------------
// sine_table.svh  (GENERATED FILE -- DO NOT EDIT BY HAND)
// -----------------------------------------------------------------------------
// 256-point packed sine wavetable, 16-bit signed, amplitude +/-8192.
//
// Regenerate with:
//     python -X utf8 code/scripts/gen_sine_table.py --write
// Verify without touching the file (used by check_repo / regression):
//     python -X utf8 code/scripts/gen_sine_table.py --check
//
// Why a packed vector instead of an unpacked array
// ------------------------------------------------
// Two independent tool limits force this shape -- see gen_sine_table.py for
// the full story. Short version:
//   * `real` + `$sin` is rejected by GowinSynthesis (EX3956), so the table
//     MUST be precomputed integer constants;
//   * an unpacked array parameter is rejected by iverilog, so the table
//     MUST be a packed vector.
// A packed vector is plain Verilog-2001 and both tools accept it.
//
// Entry k occupies bits [16*k +: 16]; entry 0 is the LSB slice (rightmost).
//
// Guard: including this file twice is harmless, but a module that also
// defines its own SINE_TABLE_DEFAULT would collide. Do not redefine it.
// -----------------------------------------------------------------------------


// Number of entries in the table. Must be a power of two so that the DDS can
// slice the phase accumulator with a plain bit-select (no divider, no modulo).
localparam int unsigned SINE_TABLE_DEPTH = 256;

// Full table, packed. Total width = 16 * 256 = 4096 bits.
localparam logic signed [4096-1:0] SINE_TABLE_DEFAULT = {
        16'sd0, 16'sd201, 16'sd402, 16'sd603, 16'sd803, 16'sd1003, 16'sd1202, 16'sd1401,
        16'sd1598, 16'sd1795, 16'sd1990, 16'sd2185, 16'sd2378, 16'sd2570, 16'sd2760, 16'sd2948,
        16'sd3135, 16'sd3320, 16'sd3503, 16'sd3683, 16'sd3862, 16'sd4038, 16'sd4212, 16'sd4383,
        16'sd4551, 16'sd4717, 16'sd4880, 16'sd5040, 16'sd5197, 16'sd5351, 16'sd5501, 16'sd5649,
        16'sd5793, 16'sd5933, 16'sd6070, 16'sd6203, 16'sd6333, 16'sd6458, 16'sd6580, 16'sd6698,
        16'sd6811, 16'sd6921, 16'sd7027, 16'sd7128, 16'sd7225, 16'sd7317, 16'sd7405, 16'sd7489,
        16'sd7568, 16'sd7643, 16'sd7713, 16'sd7779, 16'sd7839, 16'sd7895, 16'sd7946, 16'sd7993,
        16'sd8035, 16'sd8071, 16'sd8103, 16'sd8130, 16'sd8153, 16'sd8170, 16'sd8182, 16'sd8190,
        16'sd8192, 16'sd8190, 16'sd8182, 16'sd8170, 16'sd8153, 16'sd8130, 16'sd8103, 16'sd8071,
        16'sd8035, 16'sd7993, 16'sd7946, 16'sd7895, 16'sd7839, 16'sd7779, 16'sd7713, 16'sd7643,
        16'sd7568, 16'sd7489, 16'sd7405, 16'sd7317, 16'sd7225, 16'sd7128, 16'sd7027, 16'sd6921,
        16'sd6811, 16'sd6698, 16'sd6580, 16'sd6458, 16'sd6333, 16'sd6203, 16'sd6070, 16'sd5933,
        16'sd5793, 16'sd5649, 16'sd5501, 16'sd5351, 16'sd5197, 16'sd5040, 16'sd4880, 16'sd4717,
        16'sd4551, 16'sd4383, 16'sd4212, 16'sd4038, 16'sd3862, 16'sd3683, 16'sd3503, 16'sd3320,
        16'sd3135, 16'sd2948, 16'sd2760, 16'sd2570, 16'sd2378, 16'sd2185, 16'sd1990, 16'sd1795,
        16'sd1598, 16'sd1401, 16'sd1202, 16'sd1003, 16'sd803, 16'sd603, 16'sd402, 16'sd201,
        16'sd0, -16'sd201, -16'sd402, -16'sd603, -16'sd803, -16'sd1003, -16'sd1202, -16'sd1401,
        -16'sd1598, -16'sd1795, -16'sd1990, -16'sd2185, -16'sd2378, -16'sd2570, -16'sd2760, -16'sd2948,
        -16'sd3135, -16'sd3320, -16'sd3503, -16'sd3683, -16'sd3862, -16'sd4038, -16'sd4212, -16'sd4383,
        -16'sd4551, -16'sd4717, -16'sd4880, -16'sd5040, -16'sd5197, -16'sd5351, -16'sd5501, -16'sd5649,
        -16'sd5793, -16'sd5933, -16'sd6070, -16'sd6203, -16'sd6333, -16'sd6458, -16'sd6580, -16'sd6698,
        -16'sd6811, -16'sd6921, -16'sd7027, -16'sd7128, -16'sd7225, -16'sd7317, -16'sd7405, -16'sd7489,
        -16'sd7568, -16'sd7643, -16'sd7713, -16'sd7779, -16'sd7839, -16'sd7895, -16'sd7946, -16'sd7993,
        -16'sd8035, -16'sd8071, -16'sd8103, -16'sd8130, -16'sd8153, -16'sd8170, -16'sd8182, -16'sd8190,
        -16'sd8192, -16'sd8190, -16'sd8182, -16'sd8170, -16'sd8153, -16'sd8130, -16'sd8103, -16'sd8071,
        -16'sd8035, -16'sd7993, -16'sd7946, -16'sd7895, -16'sd7839, -16'sd7779, -16'sd7713, -16'sd7643,
        -16'sd7568, -16'sd7489, -16'sd7405, -16'sd7317, -16'sd7225, -16'sd7128, -16'sd7027, -16'sd6921,
        -16'sd6811, -16'sd6698, -16'sd6580, -16'sd6458, -16'sd6333, -16'sd6203, -16'sd6070, -16'sd5933,
        -16'sd5793, -16'sd5649, -16'sd5501, -16'sd5351, -16'sd5197, -16'sd5040, -16'sd4880, -16'sd4717,
        -16'sd4551, -16'sd4383, -16'sd4212, -16'sd4038, -16'sd3862, -16'sd3683, -16'sd3503, -16'sd3320,
        -16'sd3135, -16'sd2948, -16'sd2760, -16'sd2570, -16'sd2378, -16'sd2185, -16'sd1990, -16'sd1795,
        -16'sd1598, -16'sd1401, -16'sd1202, -16'sd1003, -16'sd803, -16'sd603, -16'sd402, -16'sd201
};

// Look up entry `index` (0 .. SINE_TABLE_DEPTH-1).
//
// MUST be called with a constant or an elaborated-loop index: the for-loop
// below unrolls at compile time into a chain of bit-selects, which maps to
// pure combinational muxing. With a 256-entry table that is a wide mux;
// see the DDS module for the registered/pipelined usage that keeps timing.
function automatic logic signed [15:0] sine_lookup(
    input logic [31:0] index
);
    logic signed [15:0] value;
    integer k;
    begin
        value = 16'sd0;
        for (k = 0; k < SINE_TABLE_DEPTH; k = k + 1) begin
            if (index == k[31:0]) begin
                value = SINE_TABLE_DEFAULT[16*k +: 16];
            end
        end
    end
    return value;
endfunction

    function automatic logic signed [15:0] sine_sample(
        input logic [SINE_IDX_BITS-1:0] index
    );
        return sine_lookup({{(32-SINE_IDX_BITS){1'b0}}, index});
    endfunction

    // -------------------------------------------------------------------------
    // 1. 复位同步
    //
    // 全设计单一时钟域，因此只需一个同步器。
    // 注意 sys_rst_n 是 1.5 V 域的用户按键，不是专用复位脚。
    // -------------------------------------------------------------------------
    logic rst_sync_n;

    reset_sync #(
        .STAGES (2)
    ) u_reset_sync (
        .clk        (core_clk),
        .rst_n      (core_async_rst_n),
        .rst_sync_n (rst_sync_n)
    );

    // -------------------------------------------------------------------------
    // 2. 功放使能（低有效）—— 上电爆音防护
    //
    // 【关键】组合赋值，不经过时钟，复位期间恒为 1。
    // 见文件头"上电爆音防护"一节的详细说明。
    // -------------------------------------------------------------------------
    // Mute even before the PLL starts delivering any core clock edges.
    assign pa_en = ~rst_sync_n | ~core_async_rst_n;

    // -------------------------------------------------------------------------
    // 3. 48 kHz 采样节拍
    // -------------------------------------------------------------------------
    logic sample_tick, frame_sample_req, i2s_frame_tick;
    logic [31:0] sample_req_id;
    logic i2s_ready, pcm_valid_q, pcm_ready;
    logic [31:0] produced_req_id;
    logic signed [PCM_WIDTH-1:0] produced_left, produced_right;
    logic signed [PCM_WIDTH-1:0] buffered_left, buffered_right;
    logic pending_valid;
    logic [31:0] audio_frame_count, pcm_request_count;
    logic [31:0] pcm_commit_count, audio_underrun;
    logic [31:0] status_event_overflow, status_max_processing_cycles;
    assign sample_tick = frame_sample_req;

    // -------------------------------------------------------------------------
    // 4. 测试音参数（相位累加与查表移入下方 generate 的固定音分支）
    //
    // 【分母是采样率 Fs，不是系统时钟】
    //   累加器只在 sample_tick 上推进，即每秒推进 Fs = 48000 次，
    //   所以步进必须按采样率算。最初写成除以 CLK_HZ(50 MHz)，
    //   音高偏低 1041.67 倍（440 Hz -> 0.42 Hz），听感上就是没有声音。
    //   见文件头与 V0029 的缺陷三记录。
    // -------------------------------------------------------------------------
    localparam int unsigned SINE_SHIFT = TICK_ACC_BITS - SINE_IDX_BITS;

    // -------------------------------------------------------------------------
    // 5. 【T020】按键 -> 统一演奏事件 -> 单声部
    //
    // 数据流：
    //   key_n -> 去抖 -> 脉冲 -> 事件 -> 声部 -> PCM -> i2s_tx
    //
    // 这一节把 T007 的"固定测试音"升级为"事件驱动的骨架"。
    // 固定测试音路径保留（SOURCE_MODE=1），见下方 generate。
    // -------------------------------------------------------------------------
    logic [1:0] key_pressed;
    logic [1:0] key_press_pulse;
    logic [1:0] key_release_pulse;

    // 按键去抖：使用 M3 的 T021 正式实现
    // （rtl/input/button_debouncer/button_debouncer.sv）。
    // 它替换了本骨架原先的占位实现 rtl/common/key_debounce.sv（方案 A，2026-09-15）。
    //
    // 【为什么需要 DEBOUNCE_CLK_HZ】M3 的模块按"时钟频率 + 毫秒"参数化
    // （比周期数可读，换主频时不必手算），而本顶层的对外参数是 DEBOUNCE_CNT
    // （周期数）。两者之间只差一个时钟频率，所以这里把它显式参数化：
    //   真实硬件：DEBOUNCE_CLK_HZ = CLK_HZ = 50 MHz，DEBOUNCE_CNT = 150000
    //             -> 3 ms -> 150000 周期（2026-09-16 由 500000 / 10 ms 下调，
    //                理由见上方 DEBOUNCE_CNT 参数说明）。
    //   仿真时  ：testbench 把 DEBOUNCE_CLK_HZ 调小（如 16000），
    //             DEBOUNCE_CNT = 16 即对应 1 ms -> 16 周期，
    //             使快速仿真仍能得到与原实现完全相同的去抖窗口。
    // 这样既保留了毫秒参数化的可读性，又不改变任何既有的仿真与上板口径。
    localparam integer DEBOUNCE_MS_DIVISOR = (DEBOUNCE_CLK_HZ < 1000) ? 1 : (DEBOUNCE_CLK_HZ / 1000);
    localparam integer DEBOUNCE_TIME_MS_CALC =
        (DEBOUNCE_CNT + DEBOUNCE_MS_DIVISOR - 1) / DEBOUNCE_MS_DIVISOR;
    localparam integer DEBOUNCE_TIME_MS =
        (DEBOUNCE_TIME_MS_CALC < 1) ? 1 : DEBOUNCE_TIME_MS_CALC;

    button_debouncer #(
        .BUTTON_COUNT     (2),
        .CLK_FREQ_HZ      (DEBOUNCE_CLK_HZ),
        .DEBOUNCE_TIME_MS (DEBOUNCE_TIME_MS)
    ) u_button_debouncer (
        .clk                  (core_clk),
        .rst_n                (rst_sync_n),
        .button_n_async       (key_n),
        .button_down          (key_pressed),
        .button_press_pulse   (key_press_pulse),
        .button_release_pulse (key_release_pulse)
    );

    // 事件源：把按键脉冲翻译成统一演奏事件
    //
    // 【D022 / 2026-09-15】原 M2 占位模块 key_event_source 已删除，改用 M3 的
    // button_event_converter（依据 技术决策记录 D022，按 T021 先例走"取代占位"）。
    // 两者的端口名不同：新模块是 button_press_pulse / button_release_pulse，
    // 内部自带本地事件 FIFO。
    //
    // 音高映射：两个实体按键实测为 A4(69) 与 C5(72)，相差 3 个半音。模块默认的
    // BASE_NOTE_NUMBER=60 / NOTE_STEP=2 是"每键差 2 个半音"的等间距映射，只适用
    // 于按键编号连续的场合，因此这里显式覆盖为 69 / 3。
    logic                               ev_valid;
    logic                               ev_ready;
    logic [31:0]                        ev_overflow_count;
    audio_defs_pkg::performance_event_t ev_data;

    // This is the button adapter's local drop count. T025 will aggregate
    // local input drops separately from the shared queue watermarks.
    button_event_converter #(
        .BUTTON_COUNT    (2),
        .BASE_NOTE_NUMBER(69),
        .NOTE_STEP       (3),
        .SOURCE_ID       (4'd1)
    ) u_button_event_converter (
        .clk                  (core_clk),
        .rst_n                (rst_sync_n),
        .button_press_pulse   (key_press_pulse),
        .button_release_pulse (key_release_pulse),
        .event_ready          (ev_ready),
        .event_valid          (ev_valid),
        .event_data           (ev_data),
        .overflow_count       (ev_overflow_count)
    );

    // T025 common event FIFO: both input adapters keep their local buffers.
    // MIDI and key events share the 50 MHz clock and common queue.
    logic                               shared_event_valid;
    logic                               shared_event_ready;
    audio_defs_pkg::performance_event_t shared_event_data;
    logic [15:0]                        event_fifo_level;
    logic [15:0]                        event_fifo_high_watermark;
    logic midi_event_valid, midi_event_ready;
    audio_defs_pkg::performance_event_t midi_event_data;
    logic [31:0] midi_event_overflow;
    midi_input #(.CLK_HZ(CLK_HZ), .SOURCE_ID(4'd0)) u_midi_input (
        .clk(core_clk), .rst_n(rst_sync_n), .midi_rx_async(midi_rx),
        .event_ready(midi_event_ready), .event_valid(midi_event_valid),
        .event_data(midi_event_data),
        .event_fifo_level(), .event_fifo_high_watermark(),
        .uart_frame_error_count(), .parser_error_count(),
        .event_fifo_overflow_count(midi_event_overflow), .midi_rx_busy()
    );
    performance_event_fifo #(.DEPTH(EVENT_FIFO_DEPTH)) u_performance_event_fifo (
        .clk(core_clk), .rst_n(rst_sync_n),
        .button_valid(ev_valid), .button_ready(ev_ready),
        .button_data(ev_data),
        .midi_valid(midi_event_valid), .midi_ready(midi_event_ready),
        .midi_data(midi_event_data),
        .event_valid(shared_event_valid),
        .event_ready(shared_event_ready),
        .event_data(shared_event_data),
        .event_fifo_level(event_fifo_level),
        .event_fifo_high_watermark(event_fifo_high_watermark)
    );

    // T024 normal mode: four actual DDS/ADSR voices and approved Q15 gain.
    wire [31:0] status_active_voice_count, status_clip_count;
    wire [31:0] core_max_processing_cycles;
    wire [31:0] legacy_max_processing_cycles;
    logic voice_active;
    logic [6:0] voice_note;
    generate
      if (SOURCE_MODE == 1) begin:g_fixed_tone
        // Fixed-tone diagnostic keeps legacy timing; not a STAT acceptance build.
        wire signed [23:0] voice_pcm_left,voice_pcm_right;
        wire fixed_event_ready;
        logic signed [23:0] pcm_left,pcm_right;
        assign shared_event_ready=fixed_event_ready;
    simple_voice #(
        .ACC_BITS   (TICK_ACC_BITS),
        .SINE_DEPTH (SINE_DEPTH),
        .PCM_WIDTH  (PCM_WIDTH),
        .AMPLITUDE  (TEST_AMPLITUDE)
    ) u_simple_voice (
        .clk          (core_clk),
        .rst_n        (rst_sync_n),
        .sample_tick  (sample_tick),
        .event_valid  (shared_event_valid),
        .event_ready  (fixed_event_ready),
        .event_data   (shared_event_data),
        .pcm_left     (voice_pcm_left),
        .pcm_right    (voice_pcm_right),
        .voice_active (voice_active),
        .current_note (voice_note)
    );

            logic [TICK_ACC_BITS-1:0] tone_phase;
            logic [TICK_ACC_BITS:0]   tone_sum;
            logic [SINE_IDX_BITS-1:0] sine_index;
            logic signed [15:0]       tone_sample;

            assign tone_sum    = {1'b0, tone_phase} + {1'b0, TONE_STEP};
            assign sine_index  = tone_phase[TICK_ACC_BITS-1 -: SINE_IDX_BITS];
            assign tone_sample = sine_sample(sine_index);

            always_ff @(posedge core_clk or negedge rst_sync_n) begin
                if (!rst_sync_n)     tone_phase <= '0;
                else if (sample_tick) tone_phase <= tone_sum[TICK_ACC_BITS-1:0];
            end

            assign pcm_left  = $signed({tone_sample, 8'b0});
            assign pcm_right = $signed({tone_sample, 8'b0});

    always_ff @(posedge core_clk or negedge rst_sync_n) begin
        if (!rst_sync_n) begin
            produced_left <= '0;
            produced_right <= '0;
            produced_req_id <= '0;
            pcm_valid_q <= 1'b0;
        end else if (sample_tick) begin
            produced_left <= pcm_left;
            produced_right <= pcm_right;
            produced_req_id <= sample_req_id;
            pcm_valid_q <= 1'b1;
        end else if (i2s_frame_tick || (pcm_valid_q && pcm_ready)) begin
            // Cancel an expired result at the full-frame boundary.
            pcm_valid_q <= 1'b0;
        end
    end

    pcm_frame_buffer #(.PCM_WIDTH(PCM_WIDTH)) u_pcm_frame_buffer (
        .clk(core_clk), .rst_n(rst_sync_n),
        .frame_tick(i2s_frame_tick),
        .calc_ready(!pcm_valid_q || i2s_frame_tick),
        .sample_req(frame_sample_req), .sample_req_id(sample_req_id),
        .pcm_valid(pcm_valid_q), .pcm_ready(pcm_ready),
        .pcm_req_id(produced_req_id),
        .pcm_left(produced_left), .pcm_right(produced_right),
        .play_left(buffered_left), .play_right(buffered_right),
        .pending_valid(pending_valid),
        .audio_frame_count(audio_frame_count),
        .pcm_request_count(pcm_request_count),
        .pcm_commit_count(pcm_commit_count),
        .audio_underrun(audio_underrun)
    );

        assign status_active_voice_count={31'd0,voice_active};
        assign status_clip_count=0;
        assign core_max_processing_cycles=0;
      end else begin:g_polyphonic
        logic m1_config_pending;
        wire m1_config_ready, m1_request_accept, m1_commit;
        wire [31:0] m1_request_id;
        always_ff @(posedge core_clk or negedge rst_sync_n) begin
          if (!rst_sync_n) m1_config_pending <= 1'b1;
          else if (m1_config_pending && m1_config_ready) m1_config_pending <= 1'b0;
        end
        m2_fourvoice_timbre_delay_frame_core u_audio_core (
          .clk(core_clk), .rst_n(rst_sync_n), .event_valid(shared_event_valid),
          .event_ready(shared_event_ready), .event_data(shared_event_data),
          .frame_tick(i2s_frame_tick), .config_valid(m1_config_pending),
          .config_ready(m1_config_ready), .config_enable(1'b1),
          .config_delay_samples(16'd1), .config_dry_gain(15'd32767),
          .config_wet_gain(15'd16384), .config_feedback(15'd0),
          .play_left(buffered_left), .play_right(buffered_right),
          .pending_valid(pending_valid), .commit_pulse(m1_commit),
          .active_voice_count(status_active_voice_count),
          .clip_count(status_clip_count), .audio_underrun(audio_underrun),
          .audio_frame_count(audio_frame_count),
          .pcm_request_count(pcm_request_count),
          .pcm_commit_count(pcm_commit_count),
          .max_processing_cycles(core_max_processing_cycles),
          .request_accept(m1_request_accept), .request_id(m1_request_id),
          .committed_id(produced_req_id), .committed_left(produced_left),
          .committed_right(produced_right), .committed_clip()
        );
        assign voice_active = |status_active_voice_count;
        // Legacy debug alias is not consumed outside the fixed-tone branch.
        assign voice_note = 7'd0;
        assign frame_sample_req = m1_request_accept;
        assign sample_req_id = m1_request_id;
        assign pcm_valid_q = m1_commit;
        assign pcm_ready = 1'b1;
      end
    endgenerate
    // Public FIFO overflow remains a saturating sum of actual input drops.
    system_status_counters u_system_status_counters (
        .clk(core_clk),.rst_n(rst_sync_n),.pcm_request(frame_sample_req),
        .pcm_commit(pcm_valid_q && pcm_ready),.button_overflow(ev_overflow_count),
        .midi_overflow(midi_event_overflow),.event_fifo_overflow(status_event_overflow),
        .max_processing_cycles(legacy_max_processing_cycles)
    );
    assign status_max_processing_cycles= SOURCE_MODE==1 ? legacy_max_processing_cycles : core_max_processing_cycles;

    i2s_tx #(
        .ACC_BITS         (TICK_ACC_BITS),
        .BCLK_PHASE_STEP  (CORE_BCLK_PHASE_STEP),
        .PCM_WIDTH        (PCM_WIDTH),
        .DAC_WIDTH        (16)
    ) u_i2s_tx (
        .clk       (core_clk),
        .rst_n     (rst_sync_n),
        .valid     (1'b1),
        .pcm_left  (buffered_left),
        .pcm_right (buffered_right),
        .bclk      (i2s_bclk),
        .lrck      (i2s_lrck),
        .din       (i2s_din),
        .ready     (i2s_ready),
        .frame_tick(i2s_frame_tick)
    );

    // -------------------------------------------------------------------------
    // 7. T025 normal seven-field STAT on U15; fixed tone is DIAG.
    // Normal mode reports real seven-field STAT; fixed-tone remains DIAG.
    // -------------------------------------------------------------------------
    logic status_report_busy;
    uart_status_reporter #(.CLK_HZ(CLK_HZ), .CLIP_COUNT_VALID(SOURCE_MODE != 1))
    u_uart_status_reporter (
        .clk(core_clk), .rst_n(rst_sync_n),
        .active_voice_count(status_active_voice_count),
        .clip_count(status_clip_count),
        .event_fifo_level({16'd0, event_fifo_level}),
        .event_fifo_high_watermark({16'd0, event_fifo_high_watermark}),
        .event_fifo_overflow(status_event_overflow),
        .audio_underrun(audio_underrun),
        .max_processing_cycles(status_max_processing_cycles),
        .tx(uart_tx), .report_busy(status_report_busy)
    );

    // -------------------------------------------------------------------------
    // 未使用的信号，显式标注避免 lint 警告
    // -------------------------------------------------------------------------
    logic unused_ok;
    assign unused_ok = i2s_ready;


    // Display-only copy of events already accepted by the current audio core.
    // Same accepted-event CDC contract, but its source domain is now40MHz.
    audio_visual_display_probe #(.SYS_CLK_HZ(CLK_HZ)) u_visual (
        .sys_clk(core_clk),.sys_rst_n(sys_rst_n),.ref_clk(sys_clk),.core_clk(core_clk),
        .accepted_valid(shared_event_valid && shared_event_ready),
        .accepted_data(shared_event_data),
        .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
        .tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n),
        .visual_pll_locked(visual_pll_locked)
    );

endmodule

`endif  // M2_FOURVOICE_TIMBRE_DELAY_TOP_SV
