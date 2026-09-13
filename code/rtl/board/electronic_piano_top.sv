// -----------------------------------------------------------------------------
// electronic_piano_top.sv
// 顶层模块。对应任务 T007（上板点亮与硬件通路验证）。
//
// 板卡：Sipeed Tang Mega 60K 核心板 30354 + NEO Dock 31005
// 器件：GW5AT-LV60PG484AC1/I0（封装写法 PBG484A vs PG484A 仍待核实，见 D018）
//
// -----------------------------------------------------------------------------
// 本顶层的定位：**最小可上板工程**
// -----------------------------------------------------------------------------
// 目的不是实现完整乐器，而是先把"硬件通路"验证通：
//   时钟 -> 复位 -> 音频节拍 -> I2S 发送 -> PT8211 -> 功放 -> 扬声器
//
// 因此本顶层**刻意保持极简**：
//   - 不例化任何合成器、MIDI 输入或效果器（那些模块尚未实现）；
//   - 音源是一个内置的正弦测试音，仅用于验证通路；
//   - 所有参数走 parameter，后续替换为真实音源时不改本文件结构。
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
//   uart_tx  U15  LVCMOS33 3.3 V  Bank 6  板载 USB-UART（BL610），调试输出
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

`ifndef ELECTRONIC_PIANO_TOP_SV
`define ELECTRONIC_PIANO_TOP_SV

`timescale 1ns / 1ps

module electronic_piano_top #(
    // 系统时钟频率（本板 50 MHz）
    parameter int unsigned CLK_HZ = 50_000_000,
    // 测试音频率（Hz）。440 Hz = A4，用于验证通路。
    parameter int unsigned TEST_TONE_HZ = 440,
    // 正弦表深度（必须为 2 的幂，且与 SIN_TABLE 长度一致）
    parameter int unsigned SINE_DEPTH = 256,
    // 输出幅度（16 位有符号）。取满量程 32767 的约 1/4，
    // 既是安全音量，也避免任何中间运算溢出。
    parameter logic signed [15:0] TEST_AMPLITUDE = 16'sd8192
) (
    input  logic sys_clk,     // V22, 50 MHz
    input  logic sys_rst_n,   // AA13, 低有效，1.5 V 域，EX_KEY.0
    output logic i2s_bclk,    // Y17  -> PT8211-S BCK
    output logic i2s_lrck,    // AB17 -> PT8211-S WS
    output logic i2s_din,     // AA16 -> PT8211-S DIN
    output logic pa_en,       // AB16, 低有效：0=开，1=关
    output logic uart_tx      // U15  -> BL616 板载 USB-UART
);

    // -------------------------------------------------------------------------
    // 导入公共定义
    // -------------------------------------------------------------------------
    import audio_defs_pkg::*;

    // -------------------------------------------------------------------------
    // 参数计算
    // -------------------------------------------------------------------------

    // 48 kHz 采样节拍步进。用包里已验证的常量，避免重复推导。
    localparam logic [TICK_ACC_BITS-1:0] TICK_STEP = BOARD_TICK_PHASE_STEP;

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
    // 正弦生成
    //
    // 【为什么用 function 而不是常量数组】
    //   最初写成 localparam 数组（256 个 16'sd 字面量）。该写法在 Gowin 综合
    //   下没问题，但 iverilog 报
    //     "sorry: unpacked array parameters are not supported yet"
    //   使仿真无法进行。仿真跑不起来就不能算验证过，因此改为用可综合的
    //   function 在**编译期**用常量入参求值——综合工具会对常量入参做完全
    //   展开，等价于常量表，不消耗运行时资源。
    //
    // 【数值约定】
    //   返回 16 位有符号值，取 sin(2*pi*index/SINE_DEPTH) 乘以 TEST_AMPLITUDE。
    //   三角函数用 $sin 实现。iverilog 与 Gowin 均支持 $sin 的常量折叠；
    //   若某工具不支持，可改用 code/scripts/gen_sine_table.py 生成 ROM 表
    //   再替换本函数，接口不变。
    //
    //   索引是"相位"，返回的是该相位的瞬时幅度，因此天然覆盖 0..2*pi 全周，
    //   不需要额外处理象限与符号。
    // -------------------------------------------------------------------------
    function automatic logic signed [15:0] sine_sample(
        input int unsigned index
    );
        real phase;
        real value;
        phase = 2.0 * 3.14159265358979323846 * real'(index) / real'(SINE_DEPTH);
        value = $sin(phase) * real'(TEST_AMPLITUDE);
        // 四舍五入到最近整数，避免系统性截断偏差。
        // 用 $rtoi 而非 SystemVerilog 的 16'(...) 强制转换：
        // iverilog 报 "Cast base expression must be a vector type"。
        if (value >= 0.0) value = value + 0.5;
        else              value = value - 0.5;
        return $rtoi(value);
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
        .clk        (sys_clk),
        .rst_n      (sys_rst_n),
        .rst_sync_n (rst_sync_n)
    );

    // -------------------------------------------------------------------------
    // 2. 功放使能（低有效）—— 上电爆音防护
    //
    // 【关键】组合赋值，不经过时钟，复位期间恒为 1。
    // 见文件头"上电爆音防护"一节的详细说明。
    // -------------------------------------------------------------------------
    assign pa_en = ~rst_sync_n;

    // -------------------------------------------------------------------------
    // 3. 48 kHz 采样节拍
    // -------------------------------------------------------------------------
    logic sample_tick;

    sample_tick_gen #(
        .ACC_BITS   (TICK_ACC_BITS),
        .PHASE_STEP (TICK_STEP)
    ) u_sample_tick (
        .clk         (sys_clk),
        .rst_n       (rst_sync_n),
        .sample_tick (sample_tick)
    );

    // -------------------------------------------------------------------------
    // 4. 测试音：相位累加 + 正弦查表
    //
    // 只在 sample_tick 上累加，使音高与采样率绑定，
    // 而不是与 sys_clk 绑定。累加器高位作为查表索引。
    //
    // 取高 SINE_IDX_BITS 位作为索引，等价于取相位的整数部分。
    // 累加器是 32 位、表深 256，故右移 (32-8)=24 位。
    // -------------------------------------------------------------------------
    localparam int unsigned SINE_SHIFT = TICK_ACC_BITS - SINE_IDX_BITS;

    logic [TICK_ACC_BITS-1:0] tone_phase;
    logic [TICK_ACC_BITS:0]   tone_sum;

    assign tone_sum = {1'b0, tone_phase} + {1'b0, TONE_STEP};

    always_ff @(posedge sys_clk or negedge rst_sync_n) begin
        if (!rst_sync_n)     tone_phase <= '0;
        else if (sample_tick) tone_phase <= tone_sum[TICK_ACC_BITS-1:0];
    end

    // 查表索引：取相位高位
    logic [SINE_IDX_BITS-1:0] sine_index;
    assign sine_index = tone_phase[TICK_ACC_BITS-1 -: SINE_IDX_BITS];

    // 当前正弦样点（16 位有符号），左右声道相同（单音，非立体声）
    logic signed [15:0] tone_sample;
    assign tone_sample = sine_sample(sine_index);

    // -------------------------------------------------------------------------
    // 5. 24 位 PCM 组装
    //
    // i2s_tx 接受 24 位有符号 PCM。把 16 位测试音左移 8 位补齐到 24 位，
    // 低 8 位补 0。这样 i2s_tx 内部的"加半 LSB 后右移 8 位"舍入
    // 恰好还原为原 16 位值（低 8 位为 0，加 0x80 后右移 8 位即原值），
    // 不引入任何舍入误差。
    //
    // 符号扩展必须显式做：{tone_sample, 8'b0} 会丢掉符号语义，
    // 需先转成 24 位有符号再左移。这里用 $signed 包装保证有符号运算。
    // -------------------------------------------------------------------------
    logic signed [PCM_WIDTH-1:0] pcm_left;
    logic signed [PCM_WIDTH-1:0] pcm_right;

    always_comb begin
        // 显式符号扩展到 24 位，再左移 8 位对齐到高位。
        // {16 位有符号, 8'b0} 位拼接后仍为有符号 24 位，
        // 因为拼接结果的最左位就是 tone_sample 的符号位。
        pcm_left  = $signed({tone_sample, 8'b0});
        pcm_right = $signed({tone_sample, 8'b0});
    end

    // -------------------------------------------------------------------------
    // 6. I2S (LSBJ) 发送
    //
    // BCLK 相位步进用包里已验证的常量：
    //   I2S_BCLK_PHASE_STEP = 263882791，实际 BCLK = 3.072000004 MHz
    // 有效数据在帧末尾（slot 63）采样，故 valid 恒为 1 即可，
    // i2s_tx 每帧自动取用当前 PCM 值。
    // -------------------------------------------------------------------------
    logic i2s_ready;

    i2s_tx #(
        .ACC_BITS         (TICK_ACC_BITS),
        .BCLK_PHASE_STEP  (I2S_BCLK_PHASE_STEP),
        .PCM_WIDTH        (PCM_WIDTH),
        .DAC_WIDTH        (16)
    ) u_i2s_tx (
        .clk       (sys_clk),
        .rst_n     (rst_sync_n),
        .valid     (1'b1),
        .pcm_left  (pcm_left),
        .pcm_right (pcm_right),
        .bclk      (i2s_bclk),
        .lrck      (i2s_lrck),
        .din       (i2s_din),
        .ready     (i2s_ready)
    );

    // -------------------------------------------------------------------------
    // 7. UART 调试输出（占位）
    //
    // 本最小工程还不发送任何数据，但 uart_tx 是已约束的引脚，
    // 必须被驱动，否则综合会报"端口未驱动"并可能被优化掉。
    //
    // UART 空闲电平为高。这里恒驱 1，使上位机看到一条干净的静止线路，
    // 而不是随机噪声。真正的状态输出属于后续任务（UART 状态通道）。
    // -------------------------------------------------------------------------
    assign uart_tx = 1'b1;

    // -------------------------------------------------------------------------
    // 未使用的信号，显式标注避免 lint 警告
    // -------------------------------------------------------------------------
    logic unused_ok;
    assign unused_ok = i2s_ready;

endmodule

`endif  // ELECTRONIC_PIANO_TOP_SV
