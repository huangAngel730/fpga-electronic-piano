// -----------------------------------------------------------------------------
// uart_rx_probe.sv
// UART RX 可用性诊断顶层。**独立诊断工程**，不并进 electronic_piano_top。
//
// -----------------------------------------------------------------------------
// 它要回答的问题
// -----------------------------------------------------------------------------
// 板载 USB-UART 的接收脚在官方参考约束里是"冲突/禁止采用"状态：
//
//   //IO_LOC  "rxp"  Y14;   // 31002 版本
//   //IO_PORT "rxp"  IO_TYPE=LVCMOS15 PULL_MODE=NONE DRIVE=OFF BANK_VCCIO=1.5;
//   //IO_LOC  "rxp"  V14;   // 31004 及以后
//   //IO_PORT "rxp"  IO_TYPE=LVCMOS15 PULL_MODE=NONE DRIVE=OFF BANK_VCCIO=3.3;
//
// 两个问题一直没有实测答案：
//   Q1 本板（30354）的 UART RX 到底是 V14 还是 Y14？
//   Q2 它的真实电平标准是 1.5 V 域还是 3.3 V 域？
//
// 本工程把 V14 与 Y14 **同时**接进来当输入，两路并行解码，用一份串口报告
// 同时回答这两个问题：哪个脚能解出正确的字节，哪个脚就是本板的真 RX。
//
// 【为什么两路都只作输入是安全的】
//   FPGA 侧两个脚都配置为输入（不驱动），因此无论这两个球位在板上还连着
//   什么别的器件（例如 BL616 的 TX），本工程都不会与它抢驱动，
//   不存在电气争用。这也是本诊断能安全上板的前提。
//   风险只在于"配错电平标准导致读不到"，那恰好就是 Q2 要测的东西。
//
// -----------------------------------------------------------------------------
// 结果怎么读（串口，默认 115200 8N1）
// -----------------------------------------------------------------------------
// 上电后先打一行固定的版本与引脚对照，然后每 REPORT_MS 毫秒重复一次报告：
//
//   UART-RX-PROBE A=V14 B=Y14\r\n     <- 仅复位后打一次
//   PBIT=01B2\r\n                     <- 本工程自己的位周期（clk 数，十六进制）
//   A lv=1 ed=0000 by=0000 la=-- fe=0000 mn=----\r\n
//   B lv=1 ed=0000 by=0000 la=-- fe=0000 mn=----\r\n
//
// 字段含义：
//   lv  当前同步后的引脚电平。1 = 空闲高（正常），0 = 被拉低。
//   ed  引脚跳变次数（十六进制，饱和）。>0 说明这个脚电气上是活的。
//   by  正确接收到的字节数（不帧错误的帧才计数）。
//   la  最后一个正确收到的字节；还没收到过就是 "--"。
//   fe  帧错误帧数（停止位不是高）。只有跳变没有正确字节时，这个数会涨。
//   mn  实测到的最小跳变间隔（clk 数，十六进制）也就是对端的位周期。
//       对端波特率 = CLK_HZ / mn。mn=01B2 即 434 拍 = 115200 bps。
//       发 0x55（字符 'U'）最容易量准：它每一位都翻转一次。
//       少于两次跳变时显示 "----"。
//
// 判定表：
//   by 在涨、la 随发送内容变      -> 该脚能收，且电平标准配对了。它就是真 RX。
//   ed 在涨、fe 在涨、by 不动     -> 脚是活的但解不出帧：多半是波特率不匹配，
//                                     用 mn 反算对端波特率后改 BAUD 重烧；
//                                     若 mn 也显示 "----" 则信号太窄或电平读错。
//   ed=0000、lv=1                 -> 这个脚上没有任何信号（接错脚 / 没接线）。
//   ed=0000、lv=0                 -> 被持续拉低（接错 / 短路 / 对端一直占线）。
//   A 与 B 表现完全一样           -> 两脚可能被短接，或 CH340 同时接到了两个脚。
//
// 【关于电平标准：两路为什么配得不一样】
//   probe_a = V14 属 Bank 8，配 LVCMOS33 / 3.3 V；
//   probe_b = Y14 属 Bank 9，配 LVCMOS15 / 1.5 V。
//   依据"一个 Bank 只有一个 VCCIO"：官方参考 .cst 里 Bank 8 的其它脚
//   （cmos_*、PHY_CLK=V19 等）全部写 LVCMOS33，Bank 9 的其它脚
//   （AA13、Y13/Y12）全部写 LVCMOS15。那条矛盾的 rxp 行里
//   BANK_VCCIO=3.3 是对的，IO_TYPE=LVCMOS15 是从上一行复制漏改。
//   完整推导见 constraints/uart_rx_probe.cst 文件头第二节。
//
//   若 A 路读不到、且怀疑 3.3 V 判断有误，把 uart_rx_probe.cst 里
//   probe_a 换成该文件末尾附的 LVCMOS15 / 1.5 V 备选写法重烧一次再对比。
//   输入脚配错电平只会读错，不会损坏器件。
//
//   静态推导的预期：本板核心板 30354 + NEO 底板 31005（>= 31004），
//   官方注释给出的 RX 就是 V14。因此**A 路应当收到正确字节，B 路应当
//   完全没有跳变**。若实测与此相反，说明板的版本对应关系与推导不同，
//   以实测为准。
//
// -----------------------------------------------------------------------------
// 用法（接线）
// -----------------------------------------------------------------------------
//   1. 先只连电源线开机，确认开机后再插调试线（板级事实表的开机顺序）。
//   2. 串口接收软件（CH340）的 RX 接 FPGA 的 uart_tx（U15）。
//      注意 U15 在核心板上还连着板载 BL616 的 RX，两个都是输入，并联安全。
//   3. CH340 的 TX 接候选脚：先接 V14，测完再改接 Y14；
//      **不要同时接两个候选脚**，否则两路报告会一模一样，区分不出结论。
//   4. 串口软件设 115200 8N1，发送 'U'（0x55）或任意字符串。
//   5. 看报告：哪个通道的 by 在涨，哪个就是真 RX。
//
//   【不要在 BL616 的 USB 口也在工作时把 CH340 的 TX 并到 V14 上】
//   V14 在核心板上连着 BL616 的 TX。若 BL616 也在驱动该网络，
//   再并一个 CH340 的推挽输出就会出现两个驱动源争用。
//   只插 CH340、不插核心板 USB 口时不存在这个问题。
//
// -----------------------------------------------------------------------------
// 资源与时序
// -----------------------------------------------------------------------------
//   单时钟域 sys_clk，所有使能都是时钟使能，不产生新时钟，无 CDC。
//   报告发射器的分频、状态机、以及两路监视器都在 sys_clk 下。
//   引脚约束见 code/constraints/uart_rx_probe.cst。
//
// 自检 testbench：code/tb/board/tb_uart_rx_probe.sv
// -----------------------------------------------------------------------------
`ifndef UART_RX_PROBE_SV
`define UART_RX_PROBE_SV

`timescale 1ns / 1ps

module uart_rx_probe #(
    parameter int unsigned CLK_HZ    = 50_000_000,
    parameter int unsigned BAUD      = 115_200,
    parameter int unsigned REPORT_MS = 250
) (
    input  logic sys_clk,     // V22  50 MHz
    input  logic sys_rst_n,   // AA13 EX_KEY.0，低有效，内部上拉
    input  logic probe_a,     // V14  候选 RX 甲（只作输入）
    input  logic probe_b,     // Y14  候选 RX 乙（只作输入）
    output logic pa_en,       // AB16 功放使能，低有效
    output logic i2s_bclk,    // Y17  以下三脚本工程不用，只为不让它们悬空
    output logic i2s_lrck,    // AB17
    output logic i2s_din,     // AA16
    output logic uart_tx      // U15  板载 USB-UART，报告输出
);

    // -------------------------------------------------------------------------
    // 位周期与报告周期
    // -------------------------------------------------------------------------
    localparam int unsigned DIV = (CLK_HZ + (BAUD / 2)) / BAUD;

    localparam logic [15:0] DIV16 = DIV;

    // 跳变间隔落在 [DIV/4, 4*DIV] 才当作"位周期候选"。
    // 下限滤掉毛刺，上限滤掉帧间空闲（空闲间隔远大于 4 个位周期）。
    // MAX_T 是 16 位，要求 DIV <= 16383，即 50 MHz 下 BAUD >= 3052。
    localparam logic [15:0] MIN_T = DIV16 >> 2;
    localparam logic [15:0] MAX_T = DIV16 << 2;

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
    // 两路 UART 接收（被测对象）
    // -------------------------------------------------------------------------
    logic [15:0] rx_data_v;   // [7:0] = A 路，[15:8] = B 路
    logic [1:0] rx_valid_v;
    logic [1:0] rx_fe_v;

    uart_rx #(
        .CLK_HZ    (CLK_HZ),
        .BAUD      (BAUD),
        .DATA_BITS (8)
    ) u_rx_a (
        .clk       (sys_clk),
        .rst_n     (rst_n),
        .rx        (probe_a),
        .rx_data   (rx_data_v[7:0]),
        .rx_valid  (rx_valid_v[0]),
        .frame_err (rx_fe_v[0]),
        .rx_busy   ()
    );

    uart_rx #(
        .CLK_HZ    (CLK_HZ),
        .BAUD      (BAUD),
        .DATA_BITS (8)
    ) u_rx_b (
        .clk       (sys_clk),
        .rst_n     (rst_n),
        .rx        (probe_b),
        .rx_data   (rx_data_v[15:8]),
        .rx_valid  (rx_valid_v[1]),
        .frame_err (rx_fe_v[1]),
        .rx_busy   ()
    );

    // -------------------------------------------------------------------------
    // 引脚监视：电平、跳变次数、最小跳变间隔、正确字节数、帧错误数
    // -------------------------------------------------------------------------
    logic [1:0] pin_in;
    assign pin_in = {probe_b, probe_a};

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

    // -------------------------------------------------------------------------
    // 报告文本
    // -------------------------------------------------------------------------
    //   静态文本直接以字符串常量存成定宽向量，省掉逐字符的 case。
    //
    //   【下标方向 —— 这里踩过一次坑，改文本前务必看这段】
    //   SystemVerilog 把字符串字面量赋给 [8*L-1:0] 的向量时是左对齐的：
    //   最左边的字符落在**最高字节**，即"UART..." 的 'U' 在 [8L-1 -: 8]。
    //   所以第 i 个字符（i=0 是最左字符）在 8*(L-1-i) 处，
    //   取字符要**反着数**，不能写 S[8*i +: 8]。
    //   写成 S[8*i +: 8] 不会报错，只会把整条报告按字符倒着发出去，
    //   表现是串口助手里出现 "EBORP-XR-TRAU" 这种倒序文本。
    //
    //   下面每个常量的注释里都写着"字符 0..L-1"，改文本时同时改长度常量。
    // -------------------------------------------------------------------------
    localparam logic [8*16-1:0] S_HDR1 = "UART-RX-PROBE A=";   // 16 字节
    localparam logic [8*3-1:0]  S_HDR2 = " B=";                // 3 字节
    localparam logic [8*4-1:0]  S_LV   = " lv=";               // 4 字节
    localparam logic [8*4-1:0]  S_ED   = " ed=";               // 4 字节
    localparam logic [8*4-1:0]  S_BY   = " by=";               // 4 字节
    localparam logic [8*4-1:0]  S_LA   = " la=";               // 4 字节
    localparam logic [8*4-1:0]  S_FE   = " fe=";               // 4 字节
    localparam logic [8*4-1:0]  S_MN   = " mn=";               // 4 字节
    localparam logic [8*5-1:0]  S_PBIT = "PBIT=";              // 5 字节

    // 取第 i 个字符（i=0 为最左字符）的下标：8*(L-1-i)。
    // 4 字节常量用 4'd3 - i，3 字节常量用 3'd2 - i，以此类推。

    // 【必须与 uart_rx_probe.cst 一致】改 CST 里的 probe_a / probe_b 落点时，
    // 同步改这两个常量，否则串口报告会把脚名指错。
    localparam logic [8*3-1:0]  NAME_A = "V14";
    localparam logic [8*3-1:0]  NAME_B = "Y14";

    // 报告步骤。A 段与 B 段的字段结构完全相同（14 个字段），
    // 只是 step 偏移不同，代价是每条通道 14 个 step。
    localparam logic [5:0] ST_IDLE   = 6'd0;
    localparam logic [5:0] ST_HDR    = 6'd1;    // 27 字节：版本 + 两个脚名
    localparam logic [5:0] ST_PBIT   = 6'd2;    // 11 字节：PBIT=xxxx\r\n
    localparam logic [5:0] ST_A_BASE = 6'd3;    // 3..16  通道 A 的 14 个字段
    localparam logic [5:0] ST_B_BASE = 6'd17;   // 17..30 通道 B 的 14 个字段
    localparam logic [5:0] ST_LAST   = 6'd30;

    // 半字节 -> ASCII 十六进制字符
    function automatic logic [7:0] hx(input logic [31:0] v, input logic [3:0] n);
        logic [3:0] d;
        d  = v[4*n +: 4];
        hx = (d < 4'd10) ? (8'h30 + {4'b0, d}) : (8'h37 + {4'b0, d});
    endfunction

    // 某个字段的第 sub 个字节。f=0..13，含义见 uart_rx_probe.cst 之外的
    // 文件头"结果怎么读"一节。
    function automatic logic [7:0] fld_byte(
        input logic [3:0]  f,
        input logic [2:0]  sub,
        input logic        sel_b,
        input logic        lv,
        input logic [15:0] ed,
        input logic [15:0] by,
        input logic [15:0] fe,
        input logic [15:0] mn,
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
            4'd13:   fld_byte = (sub == 3'd0) ? 8'h0D : 8'h0A;   // CR / LF
            default: fld_byte = 8'h3F;                            // '?'
        endcase
    endfunction

    // 字段是否已发完
    function automatic logic fld_last(input logic [3:0] f, input logic [2:0] sub);
        case (f)
            4'd0:    fld_last = (sub == 3'd0);
            4'd2:    fld_last = (sub == 3'd0);
            4'd8:    fld_last = (sub == 3'd1);
            4'd13:   fld_last = (sub == 3'd1);
            default: fld_last = (sub == 3'd3);
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
    logic        tx_ready;      // uart_tx 的就绪输出，报告发射器的唯一节拍

    logic [31:0] tick_cnt;
    logic        report_tick;

    logic        cur_ch;        // 0 = A 段，1 = B 段
    logic [15:0] sel_ed;
    logic [15:0] sel_by;
    logic [15:0] sel_fe;
    logic [15:0] sel_mn;
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
            // 下标 0..15  S_HDR1 "UART-RX-PROBE A="
            //      16..18 NAME_A
            //      19..21 S_HDR2 " B="
            //      22..24 NAME_B
            //      25     CR
            //      26     LF
            // 字符串常量的字节序见上面的下标方向说明：第 i 个字符在 L-1-i 处。
            if      (sub < 6'd16) cur_byte = S_HDR1[8*(6'd15 - sub) +: 8];
            else if (sub < 6'd19) cur_byte = NAME_A[8*(6'd2 - (sub - 6'd16)) +: 8];
            else if (sub < 6'd22) cur_byte = S_HDR2[8*(6'd2 - (sub - 6'd19)) +: 8];
            else if (sub < 6'd25) cur_byte = NAME_B[8*(6'd2 - (sub - 6'd22)) +: 8];
            else if (sub == 6'd25) cur_byte = 8'h0D;
            else                   cur_byte = 8'h0A;
            step_last = (sub == 6'd26);
        end
        else if (step == ST_PBIT) begin
            // 下标 0..4  "PBIT="
            //      5..8  本工程位周期的 4 个十六进制位（高位在前）
            //      9     CR
            //      10    LF
            if      (sub < 6'd5)  cur_byte = S_PBIT[8*(6'd4 - sub) +: 8];
            else if (sub < 6'd9)  cur_byte = hx({16'b0, DIV16}, 8 - sub);
            else if (sub == 6'd9) cur_byte = 8'h0D;
            else                  cur_byte = 8'h0A;
            step_last = (sub == 6'd10);
        end
        else if (step >= ST_A_BASE) begin
            // 通道 A 的字段号 = step - 3；通道 B 的字段号 = step - 17。
            cur_byte  = fld_byte(step - ST_A_BASE - (cur_ch ? 6'd14 : 6'd0),
                                 sub[2:0], cur_ch, sel_lv, sel_ed, sel_by, sel_fe,
                                 sel_mn, sel_la_ok, sel_mn_ok, sel_la);
            step_last = fld_last(step - ST_A_BASE - (cur_ch ? 6'd14 : 6'd0),
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
        .BAUD      (BAUD),
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

`endif  // UART_RX_PROBE_SV
