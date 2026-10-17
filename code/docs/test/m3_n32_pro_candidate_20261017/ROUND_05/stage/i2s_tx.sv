// -----------------------------------------------------------------------------
// i2s_tx.sv
// LSBJ 音频串行发送器。对应任务 T005，接口规范 v1.1 第五节与 D017。
//
// 目标器件：板载 PT8211（16 位双通道 DAC，LSBJ / 日本格式）
//   - 不是标准 I2S（Philips 格式）。两者在 64 BCLK/帧下相差 15 个 BCLK。
//   - BCK = 位时钟，WS = 字选择（低=右声道），DIN = 数据。
//   - 数据右对齐：每声道 16 位有效数据，LSB 紧贴 WS 跳变沿。
//
// 作用：
//   1. 用相位累加器产生 3.072 MHz 的 BCLK 和 48 kHz 的 LRCK，两者严格 64:1。
//   2. 把 24 位有符号 PCM 做舍入与饱和，转成 16 位。
//   3. 按 LSBJ 相位串行移出 DIN。
//
// 为什么 BCLK 用相位累加而不是整数分频：
//   50e6 / 3.072e6 = 16.276042，非整数。除以 16 得 3.125 MHz，
//   误差 +17253 ppm，音高偏高约 0.29 半音，人耳可直接察觉。
//   相位累加给出 +0.0013 ppm，详见 code/scripts/analyze_clock_50m.py。
//
// 采样率由 BCLK/LRCK 的比值保证，与 sample_tick 的抖动无关。
//
// -----------------------------------------------------------------------------
// 帧结构（64 BCLK = 1 帧 = 32 槽位 x 2 声道）
// -----------------------------------------------------------------------------
//   slot 0..31  : 右声道，LRCK = 0
//   slot 32..63 : 左声道，LRCK = 1
//
//   每声道槽位 32 位，其中低 16 位为有效 PCM，高 16 位为填充：
//
//     slot 内序号   31 ... 16 | 15 14 ... 1  0
//     含义          填充(忽略) | MSB ........ LSB
//
//   DUT 内部计数在 BCK 下降沿推进；PT8211 在 BCK 上升沿采样。
//   因此内部槽号 16 装载后，DAC 实际看到的是本 WS 半帧的最后
//   16 次上升沿依次送出 MSB..LSB（V0113 定向反例）。
//   前 16 次上升沿为填充位；物理解码以实际 WS 翻转为边界，
//   不能以复位时 BCK 的第 32 次上升沿替代这个边界。
//
// -----------------------------------------------------------------------------
// 定点约定（位宽、舍入与饱和）
// -----------------------------------------------------------------------------
//   输入：24 位有符号二进制补码，满量程 [-2^23, 2^23-1]
//   输出：16 位有符号二进制补码，满量程 [-2^15, 2^15-1]
//
//   直接取高 16 位（>>8）会引入两个问题：
//     1. 截断产生负向直流偏置，且量化噪声比舍入差约 6 dB；
//     2. src[23] 与 src[22] 不同时，>>8 的结果正好是 -32768，
//        这是 16 位范围的端点，必须单独判断。
//
//   采用「加半个 LSB 后算术右移」：
//     ROUND_BIAS = 1 << (SHIFT-1) = 8'h80，等价于 +0.5 LSB
//     biased  = src + 8'h80      （25 位有符号，保留进位）
//     shifted = biased >>> 8     （算术右移，保留全部高位）
//     out     = shifted[15:0]    （在范围内时取低 16 位）
//
//   加偏置可能使结果进位到 +32768，超出 16 位有符号范围。
//   判断必须用**移位后**的 25 位值 shifted 与 ±32767 / -32768 比较，
//   不能先截位再判溢出位：那样会把「进位到第 15 位」误当成符号扩展，
//   使 0x7FFF80 这类正常输入被错判并截成 0x8000。
//
//   另一个必须注意的陷阱：SystemVerilog 中「有符号 24 位 + 无符号常量」
//   会按**无符号**运算。若不先把 src 显式符号扩展到 25 位，负满量程
//   0x800000 会被当成大正数，从而饱和到 +32767 而不是 -32768。
//   因此实现中先做 src_ext / bias_ext 的显式扩展再相加。
//
//   负方向不会因加正偏置而越过 -32768，但保留该分支以保证任何输入
//   都有确定输出，不依赖调用者的取值范围假设。
//
//   验证：tb/audio_out/tb_i2s_tx.sv 用独立 LSBJ 解码器逐样本比对，
//   覆盖正负满量程、半 LSB 进位边界与 200 组随机样点；
//   另用临时脚本对 8 个边界值逐点核对过舍入表。见 验证记录.md V0020。
// -----------------------------------------------------------------------------

`ifndef I2S_TX_SV
`define I2S_TX_SV

`timescale 1ns / 1ps

module i2s_tx #(
    // 相位累加器位宽，与 audio_defs_pkg 的 TICK_ACC_BITS 保持一致
    parameter int unsigned ACC_BITS = 32,
    // BCLK 相位步进（翻转率），由顶层用 audio_defs_pkg::I2S_BCLK_PHASE_STEP 传入。
    // 默认值 527765581 对应翻转率 6.144 MHz，即 BCLK = 3.072 MHz。
    parameter logic [ACC_BITS-1:0] BCLK_PHASE_STEP = 32'd527_765_581,
    // 输入 PCM 位宽
    parameter int unsigned PCM_WIDTH = 24,
    // PT8211 有效位宽
    parameter int unsigned DAC_WIDTH = 16
) (
    input  logic                        clk,        // sys_clk
    input  logic                        rst_n,      // 本域同步后的复位，低有效
    input  logic                        valid,      // 请求发送一组新样点
    input  logic signed [PCM_WIDTH-1:0] pcm_left,   // 24 位有符号
    input  logic signed [PCM_WIDTH-1:0] pcm_right,
    output logic                        bclk,       // PT8211 pin 1 (BCK)
    output logic                        lrck,       // PT8211 pin 2 (WS)，低=右
    output logic                        din,        // PT8211 pin 3 (DIN)
    output logic                        ready,      // legacy direct-input indicator
    output logic                        frame_tick  // one pulse per full stereo frame
);

    // PT8211 有效位宽与 24 位输入的位移量。
    // PCM_WIDTH=24、DAC_WIDTH=16 时为 8。
    localparam int unsigned SHIFT = PCM_WIDTH - DAC_WIDTH;

    // 帧结构：64 BCLK 每帧，每声道 32 个槽位，有效数据占低 16 位。
    localparam int unsigned BCLK_PER_FRAME = 64;
    localparam int unsigned SLOT_BITS      = BCLK_PER_FRAME / 2;   // 32
    localparam int unsigned SLOT_CNT_BITS  = 5;                    // 0..31
    localparam int unsigned FRAME_CNT_BITS = 6;                    // 0..63

    // 装载声道数据的槽位。装载后该声道还要输出 16 位有效数据，
    // 按 PT8211 的 BCK 上升沿观测：槽内序号16装载，后续16个上升沿
    // 恰好采到16位有效数据，LSB落在该WS半帧的最后一次上升沿。
    //
    // 为什么不是内部槽号 15：
    // 旧代码以下降沿内部槽号推断上升沿采样边界，装载15使DAC实采值
    // 整体左移1位（V0113）。装载16已由独立的BCK上升沿/WS物理解码验证。
    localparam logic [SLOT_CNT_BITS-1:0] LOAD_SLOT =
        SLOT_CNT_BITS'(DAC_WIDTH);

    // =========================================================================
    // 1. BCLK 相位累加器
    //
    // 累加器进位即为一个 BCLK **半周期**结束。bclk_ce 是内部时钟使能，
    // 不是时钟，符合「不使用逻辑门控时钟」的约束。
    //
    // 【关键：BCLK_PHASE_STEP 的语义是「翻转率」＝ 2 x BCLK 频率】
    //   bclk 在每个 bclk_ce 翻转一次，而一个完整 BCLK 周期包含两次翻转
    //   （一高、一低），因此
    //     BCLK 频率 = BCLK_PHASE_STEP x FCLK / 2^ACC_BITS / 2
    //   要得到 BCLK = 3.072 MHz，PHASE_STEP 必须按 6.144 MHz 计算：
    //     step = round(2^32 x 6.144e6 / 50e6) = 527765581
    //   实际翻转率 6.143999996 MHz，折合 BCLK = 3.071999998 MHz，
    //   误差 -0.0006 ppm。
    //
    // 【曾经的事故，记录以免重犯】
    //   audio_defs_pkg 最初把 I2S_BCLK_PHASE_STEP 按 3.072 MHz 算成
    //   263882791，注释还写着「实际 BCLK = 3.072000004 MHz」。
    //   语义搞错了一半：该值实际给出 BCLK = 1.536 MHz，LRCLK 掉到 12 kHz，
    //   帧长翻倍到 128 个 BCLK。
    //   这个缺陷在 T005 的模块级 testbench 中【不可能】被发现，因为那里
    //   用的是 BCLK_PHASE_STEP=1 / ACC_BITS=8 的合成参数，只验证了
    //   「翻转次数与帧长的比例」，从未验证 BCLK 的绝对频率。
    //   直到 T007 顶层用真实参数例化并测量引脚周期才暴露。见 V0029。
    //   教训：分频器的「率」必须写清是周期率还是翻转率，并且模块级仿真
    //   必须至少有一组用真实参数跑绝对频率的用例。
    // =========================================================================
    logic [ACC_BITS-1:0] bclk_acc;
    logic [ACC_BITS:0]   bclk_sum;

    assign bclk_sum = {1'b0, bclk_acc} + {1'b0, BCLK_PHASE_STEP};

    logic bclk_ce;
    assign bclk_ce = bclk_sum[ACC_BITS];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) bclk_acc <= '0;
        else        bclk_acc <= bclk_sum[ACC_BITS-1:0];
    end

    // =========================================================================
    // 2. 帧与槽位计数
    //
    // 重要：一个「槽位」= 一个完整的 BCLK 周期 = 两个 bclk_ce 脉冲。
    // bclk 每个 bclk_ce 翻转一次，因此若让 slot_cnt 也每个 bclk_ce 递增，
    // 就会变成半个 BCLK 一个槽位，帧长会缩水一半。
    //
    // 这里用 bclk 的**下降沿**作为槽位边界：bclk 每个 bclk_ce 翻转一次，
    // 而一个完整 BCLK 周期恰好包含一个下降沿。
    //
    // 为什么不用上升沿（!bclk && bclk_ce）：那样写会让 slot_tick 去门控
    // bclk 自身的翻转，而 bclk 翻到 1 之后 !bclk 恒为 0，slot_tick 再不复
    // 出现，bclk 永久卡死在高电平。用下降沿（bclk 当前为 1）则与 bclk 的
    // 翻转逻辑互不依赖，不会自锁。
    // =========================================================================
    logic [FRAME_CNT_BITS-1:0] slot_cnt;

    wire slot_tick = bclk_ce && bclk;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)            slot_cnt <= '0;
        else if (slot_tick) begin
            if (slot_cnt == BCLK_PER_FRAME-1) slot_cnt <= '0;
            else                              slot_cnt <= slot_cnt + 1'b1;
        end
    end

    // 当前槽位在声道内的序号，0..31
    wire [SLOT_CNT_BITS-1:0] slot_in_ch = slot_cnt[SLOT_CNT_BITS-1:0];
    wire                     right_ch   = slot_cnt[FRAME_CNT_BITS-1];

    // 帧起始：本拍是帧内最后一个槽位
    wire frame_start = slot_tick && (slot_cnt == BCLK_PER_FRAME-1);
    assign frame_tick = frame_start;

    // =========================================================================
    // 3. 24 -> 16 位舍入与饱和
    //
    // 组合逻辑给出 next 值，在帧边界寄存后于本声道的槽号16装载，
    // 使通路不在移位链上。
    // =========================================================================
    logic signed [DAC_WIDTH-1:0] sample_left;
    logic signed [DAC_WIDTH-1:0] sample_right;

    function automatic logic signed [DAC_WIDTH-1:0] round_saturate(
        input logic signed [PCM_WIDTH-1:0] src
    );
        logic signed [PCM_WIDTH:0] biased;   // 25 位，容纳进位
        logic signed [PCM_WIDTH:0] shifted;  // 舍入后的完整值，仍为 25 位
        logic signed [PCM_WIDTH:0] src_ext;  // src 的符号扩展副本
        logic signed [PCM_WIDTH:0] bias_ext; // 偏置的符号扩展副本
        begin
            // 关键：必须先把两个操作数都符号扩展到目标位宽再相加。
            // SystemVerilog 中「有符号 24 位 + 无符号常量」会按无符号运算，
            // 负输入会被当成大正数，导致 -8388608 饱和到 +32767 而不是
            // -32768。这里显式扩展，强制走有符号算术。
            // 24 位 -> 25 位只需补 1 位符号位。
            src_ext  = {src[PCM_WIDTH-1], src};
            bias_ext = {{(PCM_WIDTH-SHIFT+1){1'b0}}, 1'b1,
                        {(SHIFT-1){1'b0}}};

            // 加半个 LSB。SHIFT 位宽下偏置为 1 << (SHIFT-1)。
            biased = src_ext + bias_ext;
            // 算术右移 SHIFT 位得到舍入后的值，保留全部高位以便判断范围。
            // 不能改写位宽后再判断：那样会把「进位到第 15 位」误当成
            // 符号扩展，正的 0x7FFF80 会被错判并在下面被截成 0x8000。
            shifted = biased >>> SHIFT;

            if (shifted > 25'sd32767) begin
                // 上溢：饱和到最大正值。典型来源是 0x7FFFFF + 半 LSB。
                round_saturate = 16'sh7FFF;
            end else if (shifted < -25'sd32768) begin
                // 下溢：饱和到最小负值。加正偏置不会产生这种情况，
                // 保留分支以保证任何输入都有确定输出。
                round_saturate = 16'sh8000;
            end else begin
                // 在范围内：取低 16 位
                round_saturate = shifted[DAC_WIDTH-1:0];
            end
        end
    endfunction

    logic signed [DAC_WIDTH-1:0] next_left;
    logic signed [DAC_WIDTH-1:0] next_right;

    always_comb begin
        next_left  = round_saturate(pcm_left);
        next_right = round_saturate(pcm_right);
    end

    // =========================================================================
    // 4. 数据移位寄存器与 BCLK/LRCK/DIN 输出
    //
    // BCLK、LRCK、DIN 都在 clk 上升沿更新，因此三者之间只有寄存器延迟，
    // 不引入额外的组合路径。
    //
    // 移位方向：数据装在移位寄存器的【高】16 位，每次左移一位，
    // din 取最高位 shift_reg[SLOT_BITS-1]。这样装载后第一个 BCLK 移出
    // 的就是 MSB，最后一个移出的是 LSB，符合手册的 MSB first。
    //
    // 在内部槽号16装载，PT8211 在后续BCK上升沿采到16位有效数据。
    // LSB是该WS半帧最后一个上升沿采样的位（V0113定向反例）。
    // =========================================================================
    logic [SLOT_BITS-1:0] shift_reg;
    logic [SLOT_BITS-1:0] shift_next;

    // 下一拍的移位寄存器内容
    always_comb begin
        if (slot_in_ch == LOAD_SLOT) begin
            // 装载：数据放高位，低位补 0
            if (right_ch) shift_next = {sample_left,
                                        {(SLOT_BITS-DAC_WIDTH){1'b0}}};
            else          shift_next = {sample_right,
                                        {(SLOT_BITS-DAC_WIDTH){1'b0}}};
        end else begin
            // 左移一位，低位补 0
            shift_next = {shift_reg[SLOT_BITS-2:0], 1'b0};
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bclk      <= 1'b0;
            lrck      <= 1'b0;
            din       <= 1'b0;
            shift_reg <= '0;
        end else begin
            // BCLK 每个 bclk_ce 翻转一次，构成一个半周期。
            // 这一条必须独立于 slot_tick，否则 bclk 会被自己的电平锁死。
            if (bclk_ce) bclk <= ~bclk;

            if (slot_tick) begin
                // LRCK 跟随槽位划分：PT8211 的 WS=0 为右声道，
                // WS=1 为左声道；每个区间保留32个BCK周期。
                //
                // 【曾经的事故】原实现写 `if (frame_start) lrck <= ~lrck;`，
                // 即每帧翻转一次。但一帧本身就是「左 32 + 右 32」的完整
                // LRCK 周期，翻转一次相当于把 LRCK 周期拉长到两帧，
                // 实测 LRCK = 24 kHz 而非 48 kHz，采样率整整低一倍。
                // 该写法与同一模块内 right_ch = slot_cnt[5] 的半帧划分
                // 自相矛盾：数据按一帧内左右划分，时钟却按跨帧划分。
                // 现改为直接跟随 right_ch，两者由同一来源保证一致。
                // 见 验证记录.md V0029。
                lrck <= right_ch;

                shift_reg <= shift_next;

                // DIN 输出最高位，PT8211于BCK上升沿采样；
                // 最后16个采样沿按MSB→LSB读取。
                din <= shift_next[SLOT_BITS-1];
            end
        end
    end

    // =========================================================================
    // 5. 帧起始采样与 ready
    //
    // 在帧末尾（slot 63）采样 valid，使同一组样点在整帧内保持稳定。
    // T055 uses the frame buffer for real backpressure; this legacy ready
    // port is not PCM ready. frame_tick marks a complete 64-BCLK frame.
    // =========================================================================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_left  <= '0;
            sample_right <= '0;
        end else if (frame_start && valid) begin
            sample_left  <= next_left;
            sample_right <= next_right;
        end
    end

    assign ready = 1'b1;

endmodule

`endif  // I2S_TX_SV
