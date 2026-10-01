// -----------------------------------------------------------------------------
// uart_echo_probe.sv
// UART RX 外部驱动"回传（echo）"诊断顶层。**独立诊断工程**，不并进 electronic_piano_top。
//
// -----------------------------------------------------------------------------
// 它要回答的问题
// -----------------------------------------------------------------------------
//   前面用板载 USB-UART（BL616）自己发自己收，已经证明 uart_rx 解帧正确
//   （见 code/docs/验证记录.md V0058）。但那一路的结论有两处空白：
//
//     Q1 外部的一只 USB 转 TTL（CH340）能不能驱动 FPGA 的一根 3.3 V IO？
//        —— 板载那一路的驱动来自 BL616，电平特性、驱动能力、共地关系都不同。
//     Q2 31250 bps（MIDI 波特率）从来没实测过，一直标着"未验证"。
//
//   本工程把一根普通 3.3 V IO 接成 UART RX，**收到什么就原样回传什么**：
//   电脑在串口助手里打字，字打进去、同样的字弹回来，就是 Q1 的直接证据；
//   换一根回传线走 31250，就是 Q2 的直接证据。
//
//   【为什么不是"回传报告"而是"回传原字节"】
//   报告说的是"我认为我收到了什么"。回传是让电脑自己比对"我发的"和
//   "板子回来的"是否逐字节相同 —— 判定权在电脑侧，不依赖 FPAG 的自述。
//   报告仍然保留，用来解释失败情形（跳变数、帧错误、实测位周期）。
//
// -----------------------------------------------------------------------------
// 引脚（必须与 code/constraints/uart_echo_probe.cst 一致）
// -----------------------------------------------------------------------------
//   端口        球号   方向   用途
//   probe_rx    R17    输入   被侧 RX，PMOD0(J9) IO5。CH340 的 TX 接这里。
//   echo_tx_a   R18    输出   A 路回传（115200），PMOD0 IO6。CH340 的 RX 接这里。
//   echo_tx_b   T18    输出   B 路回传（31250，MIDI 波特率），PMOD0 IO7。
//   uart_tx     U15    输出   报告，走板载 USB-UART（BL616）-> 电脑 COM13。
//
//   【为什么不在 V14 上做这件事】
//   V14 是板载 USB-UART 的 RX，但它在核心板上经 0 欧电阻接 BL616 的 TX：
//   推挽输出、空闲为高。调试线插着时 CH340 的 TX 与它对着顶，谁能拉低
//   取决于驱动能力，读数不可信；拔掉调试线 COM13 就没了，报告无处可看。
//   而且 V14/Y14 只在核心板经 BTB 到底板，手边没有可插的排针点。
//   PMOD0 是标准 2x6 座，本来就是方案 B 的 MIDI 输入候选脚，
//   这次实测同时验证了那几只脚。
//
//   【为什么是 IO5/IO6/IO7 而不是 IO0/IO1/IO2】
//   官方参考 CST 里的 `LEDs[0..7]` 不是板上 LED，就是 PMOD0 八根线的别名。
//   最初的约束按 IO0 起顺排用了 P19/R19/T21，布局布线直接报硬错误：
//     ERROR (PR2028) : The constrained location is useless in current package
//     ERROR (PR2017) : 'probe_rx' cannot be placed according to constraint,
//                      for the location is a dedicated pin (CPU)
//   原因是 device.cfg 里 `set CPU regular_io = false`：本器件有硬核 CPU，
//   P19/R19/T21 这三颗球位归它，默认不能当普通 IO。T18/R18/R17 不在其中。
//   详见 code/constraints/uart_echo_probe.cst 第二节之二。
//
// -----------------------------------------------------------------------------
// 结果怎么读
// -----------------------------------------------------------------------------
//   两路回传线各自独立，互不干扰，也不会互相抢驱动：
//     echo_tx_a = 115200 解码器的回声
//     echo_tx_b = 31250 解码器的回声（MIDI）
//   用哪一路，就把 CH340 的 RX 接哪一路，串口助手设成对应波特率。
//   **不要只用一根线来回换波特率**：回声的波特率由引脚决定，不由软件决定，
//   端子设错波特率只会看到乱码，不代表板子坏。
//
//   报告（COM13，固定 115200 8N1）上电后先打一行版本与引脚对照，
//   然后每 REPORT_MS 毫秒重复一次：
//
//     ECHO-PROBE RX=R17 ECHO115200=R18 ECHO31250=T18\r\n   <- 仅复位后打一次
//     PBIT=01B2 DB=0640\r\n                    <- 本工程两个解码位周期（clk 数）
//     A lv=1 ed=0000 by=0000 la=-- fe=0000 mn=---- dr=0000\r\n
//     B lv=1 ed=0000 by=0000 la=-- fe=0000 mn=---- dr=0000\r\n
//
//   A 路 = 115200 解码器，B 路 = 31250 解码器。两路看的是**同一根引脚**，
//   所以两行的 lv / ed / mn 必然相同，差异只在 by / la / fe / dr。
//
//   字段含义：
//     lv  当前同步后的引脚电平。1 = 空闲高（正常），0 = 被拉低。
//     ed  引脚跳变次数（十六进制，饱和）。>0 说明这根脚电气上是活的。
//     by  正确接收到的字节数（只有不帧错误的帧才计数）。
//     la  最后一个正确收到的字节；还没收到过就是 "--"。
//     fe  帧错误帧数（停止位不是高）。只有跳变没有正确字节时，这个数会涨。
//     mn  实测到的最小跳变间隔（clk 数，十六进制）也就是对端的位周期。
//         对端波特率 = CLK_HZ / mn。mn=01B2 即 434 拍 = 115200 bps；
//         mn=0640 即 1600 拍 = 31250 bps。发 0x55（字符 'U'）最容易量准：
//         它每一位都翻转一次。少于两次跳变时显示 "----"。
//     dr  回传缓冲丢掉的字节数（饱和）。非 0 = 板子收到的字节比发出去的多，
//         回声内容不可信，此时应降低对端的连续发送速率。
//
//   判定表：
//   A/B 行的 by 在涨、la 随发送内容变，且电脑收到的回声与发出的逐字节相同
//        -> 这根脚能收，电平标准正确，该波特率可用。这就是本工程要的结论。
//   两行 by 都不涨、ed 在涨、fe 在涨
//        -> 脚是活的但解不出帧：看 mn 反算对端波特率。若 mn 落在
//           [DIV_A/4, DIV_A*4] 之外，说明信号太窄（波特率高于 460800）
//           或太宽（低于 28800），也可能电平读错。
//   ed=0000、lv=1
//        -> 这根脚上没有任何信号（没接线 / 接错针 / CH340 没发数据）。
//   ed=0000、lv=0
//        -> 被持续拉低（接错 / 短路 / 对端一直占线）。
//   ed 在涨但两路都不成帧、且没接线
//        -> 引脚被底板上共用 SDRAM1_D 的网络扰动，见 .cst 第三节第 5 条，
//           换 PMOD1 重做。
//
// -----------------------------------------------------------------------------
// 上板步骤（接线）
// -----------------------------------------------------------------------------
//   1. 先只连电源线开机（板级硬件事实.md 的开机顺序与电源键操作）。
//   2. 调试线（DEBUG-USB2）**保持插着**：报告走它，COM13，115200。
//      本工程不碰 V14/U15 之外的任何调试网络，只把报告发出去。
//   3. CH340（3.3 V 档！）三根线，都在 PMOD0（J9）这一只 2x6 座上：
//        TX  -> 第 8 针（R17，IO5）
//        RX  -> 第 9 针（R18，IO6）   ；测 31250 时改接第 10 针（T18，IO7）
//        GND -> 第 11 针（GND；第 5 针也是 GND）
//      5 V 档绝对不要用：5 V 直接进 FPGA 引脚是禁项。
//   4. 串口助手打开 CH340 的口，115200 8N1，随便打字。
//      打什么弹回什么 = PASS。同时看 COM13 的报告：A 行 by 在涨。
//   5. 测 MIDI 波特率：CH340 的 RX 挪到第 10 针（T18），串口助手改 31250 8N1，
//      发 90 3C 64（Note On ch1 C4 力度 100），应原样弹回；
//      COM13 上 B 行 by=0001 la=64 mn=0640。
//      （小写十六进制显示时 la 是最后收到的字节，所以发多个字节时看最后一个。）
//
//   【不要在调试线插着时把 CH340 的 TX 接到 V14】见上面"为什么不在 V14 上做"。
//
// -----------------------------------------------------------------------------
// 资源与时序
// -----------------------------------------------------------------------------
//   单时钟域 sys_clk，所有使能都是时钟使能，不产生新时钟，无 CDC。
//   两路接收器 + 两路回传发送器 + 两路监视器 + 一个报告发射器 + 报告发送器，
//   外加两个 8 深 8 位回传缓冲。资源占用见 code/docs/验证记录.md 对应行。
//   引脚约束见 code/constraints/uart_echo_probe.cst。
//
// 自检 testbench：code/tb/board/tb_uart_echo_probe.sv
// 回传缓冲单元自检：code/tb/common/tb_echo_fifo.sv
// -----------------------------------------------------------------------------
`ifndef UART_ECHO_PROBE_SV
`define UART_ECHO_PROBE_SV

`timescale 1ns / 1ps

module uart_echo_probe #(
    parameter int unsigned CLK_HZ    = 50_000_000,
    // A 路：报告通道波特率，也是 115200 解码器与 A 路回传的波特率。
    parameter int unsigned BAUD_A    = 115_200,
    // B 路：MIDI 波特率。31250 = 50 MHz / 1600，无舍入误差。
    parameter int unsigned BAUD_B    = 31_250,
    parameter int unsigned REPORT_MS = 250
) (
    input  logic sys_clk,     // V22  50 MHz
    input  logic sys_rst_n,   // AA13 EX_KEY.0，低有效，内部上拉
    input  logic probe_rx,    // R17  PMOD0 IO5，被侧 RX（只作输入）
    output logic echo_tx_a,   // R18  PMOD0 IO6，A 路回传（115200）
    output logic echo_tx_b,   // T18  PMOD0 IO7，B 路回传（31250）
    output logic pa_en,       // AB16 功放使能，低有效
    output logic i2s_bclk,    // Y17  以下三脚本工程不用，只为不让它们悬空
    output logic i2s_lrck,    // AB17
    output logic i2s_din,     // AA16
    output logic uart_tx      // U15  板载 USB-UART，报告输出
);

    // -------------------------------------------------------------------------
    // 位周期与报告周期
    // -------------------------------------------------------------------------
    localparam int unsigned DIV_A = (CLK_HZ + (BAUD_A / 2)) / BAUD_A;
    localparam int unsigned DIV_B = (CLK_HZ + (BAUD_B / 2)) / BAUD_B;

    localparam logic [15:0] DIV_A16 = DIV_A;
    localparam logic [15:0] DIV_B16 = DIV_B;

    // 跳变间隔落在 [DIV_A/4, 4*DIV_A] 才当作"位周期候选"。
    // 下限滤掉毛刺，上限滤掉帧间空闲（空闲间隔远大于 4 个位周期）。
    // 窗口按 A 路的位周期定：DIV_A=434 时窗口是 [108, 1736]，
    // 同时覆盖 115200 的 434 与 31250 的 1600，因此两路共用一套监视参数。
    // MAX_T 是 16 位，要求 DIV_A <= 16383，即 50 MHz 下 BAUD_A >= 3052。
    localparam logic [15:0] MIN_T = DIV_A16 >> 2;
    localparam logic [15:0] MAX_T = DIV_A16 << 2;

    localparam logic [31:0] TICK_CYCLES = (CLK_HZ / 1000) * REPORT_MS;

    // -------------------------------------------------------------------------
    // 复位同步
    // -------------------------------------------------------------------------
    logic rst_n;

    reset_sync #(.STAGES(2)) u_reset_sync (
        .clk        (sys_clk),
        .rst_n      (sys_rst_n),
        .rst_sync_n (rst_n)
    );

    // -------------------------------------------------------------------------
    // 音频通路保持安静
    // -------------------------------------------------------------------------
    //   本工程不产生音频。三项措施：
    //     1. pa_en 显式驱动为 1（关闭功放）——不驱动会让该脚悬空，
    //        功放可能在测试期间被误开启并发出噪声，也违背上电爆音防护要求；
    //     2. 三个 DAC 脚驱动为 0，不让它们悬空；
    //     3. 仍把它们写进 CST 且电平属性与 electronic_piano.cst 逐字一致。
    assign pa_en     = 1'b1;
    assign i2s_bclk  = 1'b0;
    assign i2s_lrck  = 1'b0;
    assign i2s_din   = 1'b0;

    // -------------------------------------------------------------------------
    // 两路 UART 接收：同一根脚，两个波特率
    // -------------------------------------------------------------------------
    //   这是本工程与 uart_rx_probe 的关键差别：那边两路看两只不同的脚，
    //   这边两路看**同一只脚**，用来同时回答"能不能收"和"是哪个波特率"。
    //   错误的是错的那一路会自己产生帧错误，报告里的 fe/by 会把它区分出来，
    //   不需要软件协商波特率。
    logic [15:0] rx_data_v;   // [7:0] = A 路（115200），[15:8] = B 路（31250）
    logic [1:0]  rx_valid_v;
    logic [1:0]  rx_fe_v;

    uart_rx #(
        .CLK_HZ    (CLK_HZ),
        .BAUD      (BAUD_A),
        .DATA_BITS (8)
    ) u_rx_a (
        .clk       (sys_clk),
        .rst_n     (rst_n),
        .rx        (probe_rx),
        .rx_data   (rx_data_v[7:0]),
        .rx_valid  (rx_valid_v[0]),
        .frame_err (rx_fe_v[0]),
        .rx_busy   ()
    );

    uart_rx #(
        .CLK_HZ    (CLK_HZ),
        .BAUD      (BAUD_B),
        .DATA_BITS (8)
    ) u_rx_b (
        .clk       (sys_clk),
        .rst_n     (rst_n),
        .rx        (probe_rx),
        .rx_data   (rx_data_v[15:8]),
        .rx_valid  (rx_valid_v[1]),
        .frame_err (rx_fe_v[1]),
        .rx_busy   ()
    );

    // -------------------------------------------------------------------------
    // 回传：接收 -> 缓冲 -> 同波特率重新发送
    // -------------------------------------------------------------------------
    //   缓冲为什么必须有、深度怎么定，见 code/rtl/common/echo_fifo.sv 文件头。
    //   一句话：发送比接收晚半个位周期开始，逐字节累积，不缓冲就会丢字节。
    logic        ec_we_a, ec_we_b;
    logic [7:0]  ec_dout_a, ec_dout_b;
    logic        ec_empty_a, ec_empty_b;
    logic        ec_full_a, ec_full_b;
    logic [15:0] ec_drop_a, ec_drop_b;
    logic        ec_rd_a, ec_rd_b;
    logic        tx_ready_ea, tx_ready_eb;

    // 只有"无帧错误"的帧才回传：引脚被拉低时接收器会不断产出 frame_err 帧，
    // 把它们回传出去只会让电脑收到一串 0x00，看不出是接线问题。
    assign ec_we_a = rx_valid_v[0] && !rx_fe_v[0];
    assign ec_we_b = rx_valid_v[1] && !rx_fe_v[1];

    // 发送器空闲且缓冲非空时弹出队首。tx_valid 用 !empty 直接给，
    // 因此"弹出"必须同时满足 tx_ready：这就是 uart_tx 的握手要求。
    assign ec_rd_a = !ec_empty_a && tx_ready_ea;
    assign ec_rd_b = !ec_empty_b && tx_ready_eb;

    echo_fifo #(
        .WIDTH (8),
        .DEPTH (8)
    ) u_ec_a (
        .clk        (sys_clk),
        .rst_n      (rst_n),
        .wr_en      (ec_we_a),
        .wr_data    (rx_data_v[7:0]),
        .rd_en      (ec_rd_a),
        .rd_data    (ec_dout_a),
        .empty      (ec_empty_a),
        .full       (ec_full_a),
        .drop_count (ec_drop_a)
    );

    echo_fifo #(
        .WIDTH (8),
        .DEPTH (8)
    ) u_ec_b (
        .clk        (sys_clk),
        .rst_n      (rst_n),
        .wr_en      (ec_we_b),
        .wr_data    (rx_data_v[15:8]),
        .rd_en      (ec_rd_b),
        .rd_data    (ec_dout_b),
        .empty      (ec_empty_b),
        .full       (ec_full_b),
        .drop_count (ec_drop_b)
    );

    uart_tx #(
        .CLK_HZ    (CLK_HZ),
        .BAUD      (BAUD_A),
        .DATA_BITS (8),
        .STOP_BITS (1)
    ) u_tx_echo_a (
        .clk      (sys_clk),
        .rst_n    (rst_n),
        .tx_data  (ec_dout_a),
        .tx_valid (!ec_empty_a),
        .tx_ready (tx_ready_ea),
        .tx       (echo_tx_a)
    );

    uart_tx #(
        .CLK_HZ    (CLK_HZ),
        .BAUD      (BAUD_B),
        .DATA_BITS (8),
        .STOP_BITS (1)
    ) u_tx_echo_b (
        .clk      (sys_clk),
        .rst_n    (rst_n),
        .tx_data  (ec_dout_b),
        .tx_valid (!ec_empty_b),
        .tx_ready (tx_ready_eb),
        .tx       (echo_tx_b)
    );

    // -------------------------------------------------------------------------
    // 引脚监视：电平、跳变次数、最小跳变间隔、正确字节数、帧错误数
    // -------------------------------------------------------------------------
    //   两路监视器都接同一根 probe_rx，因此两行的 lv/ed/mn 必然相同。
    //   这是刻意的：报告里每一行都是自解释的（哪一路的解码结论配哪一路的
    //   引脚证据），不需要读者去别处找另一路的电平。
    (* async_reg = "true" *) logic [1:0] mon_meta;
    (* async_reg = "true" *) logic [1:0] mon_sync;
    logic [1:0] mon_sync_d;

    // 上电后前几拍不计跳变：同步链的复位值与被测引脚的真实电平之间的
    // 第一次"变化"不是真边沿，若计入会让 ed 从 1 起跳，误导判断。
    logic [2:0] mon_arm_sr;
    logic       mon_arm;
    assign mon_arm = mon_arm_sr[2];

    logic [15:0] mon_ed    [0:1];
    logic [15:0] mon_by    [0:1];
    logic [15:0] mon_fe    [0:1];
    logic [15:0] mon_mn    [0:1];
    logic [15:0] mon_timer [0:1];
    logic [7:0]  mon_la    [0:1];
    logic        mon_la_ok [0:1];
    logic        mon_mn_ok [0:1];

    logic [1:0]  pin_in;
    assign pin_in = {probe_rx, probe_rx};

    always_ff @(posedge sys_clk) begin
        if (!rst_n) begin
            mon_meta   <= 2'b11;   // 引脚带内部上拉，空闲为高
            mon_sync   <= 2'b11;
            mon_sync_d <= 2'b11;
            mon_arm_sr <= 3'b000;
        end else begin
            mon_meta   <= pin_in;
            mon_sync   <= mon_meta;
            mon_sync_d <= mon_sync;
            mon_arm_sr <= {mon_arm_sr[1:0], 1'b1};
        end
    end

    genvar gi;
    generate
        for (gi = 0; gi < 2; gi++) begin : g_mon
            always_ff @(posedge sys_clk) begin
                if (!rst_n) begin
                    mon_ed[gi]    <= 16'd0;
                    mon_by[gi]    <= 16'd0;
                    mon_fe[gi]    <= 16'd0;
                    mon_mn[gi]    <= 16'hFFFF;
                    mon_timer[gi] <= 16'd0;
                    mon_la[gi]    <= 8'h00;
                    mon_la_ok[gi] <= 1'b0;
                    mon_mn_ok[gi] <= 1'b0;
                end else begin
                    // 距上一次跳变经过的 clk 数，饱和保持
                    if (mon_timer[gi] != 16'hFFFF) begin
                        mon_timer[gi] <= mon_timer[gi] + 16'd1;
                    end

                    // 跳变 -> 计数，并在合理窗口内更新最小间隔
                    if (mon_arm && (mon_sync[gi] != mon_sync_d[gi])) begin
                        if (mon_ed[gi] != 16'hFFFF) begin
                            mon_ed[gi] <= mon_ed[gi] + 16'd1;
                        end
                        // mon_timer 在跳变那一拍被清零、之后每拍 +1，
                        // 所以下一次跳变时读到的值比真实间隔少 1，必须补回来。
                        // 例：位周期 9 拍时读到 8，补 1 才是 9。
                        // 不补的话 mn 恒比真实位周期小 1 拍，
                        // 用 CLK_HZ/mn 反推对端波特率会偏大一点点。
                        if (((mon_timer[gi] + 16'd1) >= MIN_T) &&
                            ((mon_timer[gi] + 16'd1) <= MAX_T)) begin
                            if ((!mon_mn_ok[gi]) ||
                                ((mon_timer[gi] + 16'd1) < mon_mn[gi])) begin
                                mon_mn[gi]    <= mon_timer[gi] + 16'd1;
                                mon_mn_ok[gi] <= 1'b1;
                            end
                        end
                        mon_timer[gi] <= 16'd0;
                    end

                    // 接收结果：只有"无帧错误"的帧才算收到数据。
                    // 引脚被拉低时接收器会不断产出 frame_err 帧，
                    // 若把它们也算进 by，诊断结论会反过来。
                    if (rx_valid_v[gi]) begin
                        if (rx_fe_v[gi]) begin
                            if (mon_fe[gi] != 16'hFFFF) begin
                                mon_fe[gi] <= mon_fe[gi] + 16'd1;
                            end
                        end else begin
                            if (mon_by[gi] != 16'hFFFF) begin
                                mon_by[gi] <= mon_by[gi] + 16'd1;
                            end
                            mon_la[gi]    <= rx_data_v[8*gi +: 8];
                            mon_la_ok[gi] <= 1'b1;
                        end
                    end
                end
            end
        end
    endgenerate

    // 回传缓冲的丢弃计数，直接取自 FIFO（不另存一份，避免两处状态不一致）
    logic [15:0] drop_v [0:1];
    assign drop_v[0] = ec_drop_a;
    assign drop_v[1] = ec_drop_b;

    // -------------------------------------------------------------------------
    // 报告文本
    // -------------------------------------------------------------------------
    //   静态文本直接以字符串常量存成定宽向量，省掉逐字符的 case。
    //
    //   【下标方向 —— 这里踩过一次坑，改文本前务必看这段】
    //   SystemVerilog 把字符串字面量赋给 [8*L-1:0] 的向量时是左对齐的：
    //   最左边的字符落在**最高字节**，即 "ECHO..." 的 'E' 在 [8L-1 -: 8]。
    //   所以第 i 个字符（i=0 是最左字符）在 8*(L-1-i) 处，
    //   取字符要**反着数**，不能写 S[8*i +: 8]。
    //   写成 S[8*i +: 8] 不会报错，只会把整条报告按字符倒着发出去，
    //   表现是串口助手里出现 "BORP-OHCE" 这种倒序文本。
    //
    //   下面每个常量的注释里都写着字符数与"字符 0..L-1"，改文本时同时改长度常量。
    // -------------------------------------------------------------------------
    localparam logic [8*17-1:0] S_H1 = "ECHO-PROBE RX=R17";    // 17 字节
    localparam logic [8*15-1:0] S_H2 = " ECHO115200=R18";      // 15 字节
    localparam logic [8*14-1:0] S_H3 = " ECHO31250=T18";       // 14 字节
    localparam logic [8*5-1:0]  S_PBIT = "PBIT=";              // 5 字节
    localparam logic [8*4-1:0]  S_DB = " DB=";                 // 4 字节
    localparam logic [8*4-1:0]  S_LV = " lv=";                 // 4 字节
    localparam logic [8*4-1:0]  S_ED = " ed=";                 // 4 字节
    localparam logic [8*4-1:0]  S_BY = " by=";                 // 4 字节
    localparam logic [8*4-1:0]  S_LA = " la=";                 // 4 字节
    localparam logic [8*4-1:0]  S_FE = " fe=";                 // 4 字节
    localparam logic [8*4-1:0]  S_MN = " mn=";                 // 4 字节
    localparam logic [8*4-1:0]  S_DR = " dr=";                 // 4 字节

    // 【必须与 uart_echo_probe.cst 一致】本行的三个脚名是静态文本的一部分，
    // 改 CST 落点时同步改上面 S_H1 / S_H2 / S_H3，否则报告会把脚名指错。

    // 报告步骤。A 段与 B 段的字段结构完全相同（16 个字段），
    // 只是 step 偏移不同，代价是每条通道 16 个 step。
    // 一条通道 54 字节，整条报告 48 + 19 + 54 + 54 = 175 字节，
    // 115200 下约 15 ms 发完，远小于 250 ms 的报告周期。
    localparam logic [5:0] ST_IDLE   = 6'd0;
    localparam logic [5:0] ST_HDR    = 6'd1;    // 48 字节：版本 + 三个脚名
    localparam logic [5:0] ST_PBIT   = 6'd2;    // 19 字节：PBIT=xxxx DB=xxxx\r\n
    localparam logic [5:0] ST_A_BASE = 6'd3;    // 3..18  通道 A 的 16 个字段
    localparam logic [5:0] ST_B_BASE = 6'd19;   // 19..34 通道 B 的 16 个字段
    localparam logic [5:0] ST_LAST   = 6'd34;

    // 半字节 -> ASCII 十六进制字符
    function automatic logic [7:0] hx(input logic [31:0] v, input logic [3:0] n);
        logic [3:0] d;
        d  = v[4*n +: 4];
        hx = (d < 4'd10) ? (8'h30 + {4'b0, d}) : (8'h37 + {4'b0, d});
    endfunction

    // 某个字段的第 sub 个字节。f=0..8，含义见文件头"结果怎么读"一节。
    function automatic logic [7:0] fld_byte(
        input logic [3:0]  f,
        input logic [2:0]  sub,
        input logic        sel_b,
        input logic        lv,
        input logic [15:0] ed,
        input logic [15:0] by,
        input logic [15:0] fe,
        input logic [15:0] mn,
        input logic [15:0] dr,
        input logic        la_ok,
        input logic        mn_ok,
        input logic [7:0]  la
    );
        logic [7:0] tag;
        tag = sel_b ? 8'h42 : 8'h41;   // 'B' / 'A'
        case (f)
            4'd0:    fld_byte = tag;
            4'd1:    fld_byte = S_LV[8*(3'd3 - sub) +: 8];
            4'd2:    fld_byte = hx({31'b0, lv}, 4'd0);
            4'd3:    fld_byte = S_ED[8*(3'd3 - sub) +: 8];
            4'd4:    fld_byte = hx({16'b0, ed}, 3'd3 - sub);
            4'd5:    fld_byte = S_BY[8*(3'd3 - sub) +: 8];
            4'd6:    fld_byte = hx({16'b0, by}, 3'd3 - sub);
            4'd7:    fld_byte = S_LA[8*(3'd3 - sub) +: 8];
            4'd8:    fld_byte = la_ok ? hx({24'b0, la}, 3'd1 - sub) : 8'h2D;  // '-'
            4'd9:    fld_byte = S_FE[8*(3'd3 - sub) +: 8];
            4'd10:   fld_byte = hx({16'b0, fe}, 3'd3 - sub);
            4'd11:   fld_byte = S_MN[8*(3'd3 - sub) +: 8];
            4'd12:   fld_byte = mn_ok ? hx({16'b0, mn}, 3'd3 - sub) : 8'h2D;
            4'd13:   fld_byte = S_DR[8*(3'd3 - sub) +: 8];
            4'd14:   fld_byte = hx({16'b0, dr}, 3'd3 - sub);
            4'd15:   fld_byte = (sub == 3'd0) ? 8'h0D : 8'h0A;   // CR / LF
            default: fld_byte = 8'h3F;                            // '?'
        endcase
    endfunction

    // 字段是否已发完。字段长度必须与 fld_byte 的取值一一对应：
    //   f0 路标 1 字节 / f2 lv 值 1 字节 / f8 la 值 2 字节 / f15 CR LF 2 字节，
    //   其余都是"4 字节标签 + 4 字节值"里的标签段（4 字节）。
    // 少写一项不会报错，只会让短字段被当成 4 字节字段重复发 4 遍。
    function automatic logic fld_last(input logic [3:0] f, input logic [2:0] sub);
        case (f)
            4'd0, 4'd2:      fld_last = (sub == 3'd0);
            4'd8, 4'd15:     fld_last = (sub == 3'd1);
            default:         fld_last = (sub == 3'd3);
        endcase
    endfunction

    // -------------------------------------------------------------------------
    // 报告发射器
    // -------------------------------------------------------------------------
    logic [5:0]  step;
    logic [5:0]  sub;
    logic [7:0]  cur_byte;
    logic        step_last;
    logic [7:0]  send_byte;
    logic        send_pending;
    logic        tx_ready;      // 报告用 uart_tx 的就绪输出，发射器的唯一节拍

    logic [31:0] tick_cnt;
    logic        report_tick;

    logic        cur_ch;        // 0 = A 段，1 = B 段
    logic [15:0] sel_ed;
    logic [15:0] sel_by;
    logic [15:0] sel_fe;
    logic [15:0] sel_mn;
    logic [15:0] sel_dr;
    logic [7:0]  sel_la;
    logic        sel_la_ok;
    logic        sel_mn_ok;
    logic        sel_lv;

    assign cur_ch = (step >= ST_B_BASE);

    always_comb begin
        sel_ed    = mon_ed[cur_ch];
        sel_by    = mon_by[cur_ch];
        sel_fe    = mon_fe[cur_ch];
        sel_mn    = mon_mn[cur_ch];
        sel_dr    = drop_v[cur_ch];
        sel_la    = mon_la[cur_ch];
        sel_la_ok = mon_la_ok[cur_ch];
        sel_mn_ok = mon_mn_ok[cur_ch];
        sel_lv    = mon_sync[cur_ch];
    end

    // 当前 step/sub 下要发出的字节，以及该字段是否已到最后一个字节。
    always_comb begin
        cur_byte  = 8'h3F;
        step_last = 1'b0;

        if (step == ST_HDR) begin
            // 下标 0..16  S_H1 "ECHO-PROBE RX=R17"   (17 字节)
            //      17..31 S_H2 " ECHO115200=R18"     (15 字节)
            //      32..45 S_H3 " ECHO31250=T18"      (14 字节)
            //      46     CR
            //      47     LF
            // 字符串常量的字节序见上面的下标方向说明：第 i 个字符在 L-1-i 处。
            if      (sub < 6'd17) cur_byte = S_H1[8*(6'd16 - sub) +: 8];
            else if (sub < 6'd32) cur_byte = S_H2[8*(6'd14 - (sub - 6'd17)) +: 8];
            else if (sub < 6'd46) cur_byte = S_H3[8*(6'd13 - (sub - 6'd32)) +: 8];
            else if (sub == 6'd46) cur_byte = 8'h0D;
            else                   cur_byte = 8'h0A;
            step_last = (sub == 6'd47);
        end
        else if (step == ST_PBIT) begin
            // 下标 0..4   "PBIT="
            //      5..8   A 路位周期的 4 个十六进制位（高位在前）
            //      9..12  " DB="
            //      13..16 B 路位周期的 4 个十六进制位
            //      17     CR
            //      18     LF
            if      (sub < 6'd5)  cur_byte = S_PBIT[8*(6'd4 - sub) +: 8];
            else if (sub < 6'd9)  cur_byte = hx({16'b0, DIV_A16}, 8 - sub);
            else if (sub < 6'd13) cur_byte = S_DB[8*(6'd3 - (sub - 6'd9)) +: 8];
            else if (sub < 6'd17) cur_byte = hx({16'b0, DIV_B16}, 16 - sub);
            else if (sub == 6'd17) cur_byte = 8'h0D;
            else                   cur_byte = 8'h0A;
            step_last = (sub == 6'd18);
        end
        else if (step >= ST_A_BASE) begin
            // 通道 A 的字段号 = step - 3；通道 B 的字段号 = step - 19。
            cur_byte  = fld_byte(step - ST_A_BASE - (cur_ch ? 6'd16 : 6'd0),
                                 sub[2:0], cur_ch, sel_lv, sel_ed, sel_by, sel_fe,
                                 sel_mn, sel_dr, sel_la_ok, sel_mn_ok, sel_la);
            step_last = fld_last(step - ST_A_BASE - (cur_ch ? 6'd16 : 6'd0),
                                 sub[2:0]);
        end
    end

    // 一个字节一个字节地喂给 uart_tx。tx_ready 是唯一节拍来源，
    // 因此发射器天然被 UART 的帧时长限速，不需要额外的等待计数。
    always_ff @(posedge sys_clk) begin
        if (!rst_n) begin
            step         <= ST_HDR;   // 复位后先打一次版本行
            sub          <= 6'd0;
            send_byte    <= 8'h00;
            send_pending <= 1'b0;
        end else begin
            if (send_pending) begin
                if (tx_ready) begin
                    send_pending <= 1'b0;
                    if (step_last) begin
                        sub  <= 6'd0;
                        step <= (step == ST_LAST) ? ST_IDLE : (step + 6'd1);
                    end else begin
                        sub <= sub + 6'd1;
                    end
                end
            end
            else if (step == ST_IDLE) begin
                // 报告只在空闲时启动；报告进行中到来的 tick 直接丢弃。
                // 下一拍 step 已不是 ST_IDLE，于是自然开始锁存第一个字节。
                if (report_tick) begin
                    step <= ST_PBIT;
                    sub  <= 6'd0;
                end
            end
            else begin
                send_byte    <= cur_byte;
                send_pending <= 1'b1;
            end
        end
    end

    // 报告周期计时。tick 是一拍脉冲。
    always_ff @(posedge sys_clk) begin
        if (!rst_n) begin
            tick_cnt    <= 32'd0;
            report_tick <= 1'b0;
        end else begin
            if (tick_cnt == TICK_CYCLES - 32'd1) begin
                tick_cnt    <= 32'd0;
                report_tick <= 1'b1;
            end else begin
                tick_cnt    <= tick_cnt + 32'd1;
                report_tick <= 1'b0;
            end
        end
    end

    uart_tx #(
        .CLK_HZ    (CLK_HZ),
        .BAUD      (BAUD_A),
        .DATA_BITS (8),
        .STOP_BITS (1)
    ) u_tx (
        .clk      (sys_clk),
        .rst_n    (rst_n),
        .tx_data  (send_byte),
        .tx_valid (send_pending),
        .tx_ready (tx_ready),
        .tx       (uart_tx)
    );

endmodule

`endif  // UART_ECHO_PROBE_SV
