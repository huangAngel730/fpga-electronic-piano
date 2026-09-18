// -----------------------------------------------------------------------------
// tb_uart_echo_probe.sv
// uart_echo_probe 顶层自检 testbench（code/tb/board）。
//
// 被测对象：code/rtl/board/uart_echo_probe.sv
// 运行：.\code\scripts\run_uart_echo_probe_sim.ps1
//
// -----------------------------------------------------------------------------
// 这份 TB 要证明什么（每一项都对应上板时的判读方法）
// -----------------------------------------------------------------------------
//   [1] 复位与静音：pa_en 恒为 1（功放关闭），i2s 三脚恒为 0。
//   [2] 报告帧头：报告第一行必须是 "ECHO-PROBE RX=R17 ECHO115200=R18
//       ECHO31250=T18"，第二行是 "PBIT=0009 DB=0020"。
//       —— 上板时脚名指错人，是"接线对了但读数对不上"的最常见原因，
//          所以脚名写进报告、并由 TB 对着 CST 逐字校验。
//   [3] 未接线时的静态读数：复位后到第一次刺激之前，两路必须是
//       lv=1 / ed=0000 / by=0000。ed=0 说明这根脚没有被别的东西扰动
//       （上板时若这里就不是 0，见 .cst 第三节第 5 条的 SDRAM 共球位提示）。
//   [4] A 路回传（115200）：连发 3 个 0x55，回传引脚上必须收到同样的
//       3 个字节（逐字节比较，不是"看起来像"）；报告 A 行出现
//       by=0003 fe=0000 dr=0000，且那个时刻的 ed=0030、mn=0009。
//       ed=0030 的来历：每帧 0x55 是 0 1 0 1 0 1 0 1 0 1 十个位，
//       含 9 次跳变，加上帧间一次，3 帧共 1+9+1+9+1+9 = 30。
//       mn=0009 = 位周期 9 拍，正是 1 MHz / 115200 的解码位周期。
//   [5] 帧错误：停止位持续为低（线路被一直压住）必须让 A 行 fe 涨、
//       by 不涨、且不产生回传。—— 上板时"有跳变但收不到数据"就长这样，
//       这条分得清"电平/接线问题"和"波特率问题"。
//       不用"停止位只压低 3/4 位"这种部分违规：本 TB 的 DIV=9 下停止位
//       采样点紧贴停止位起点，剩下的 1/4 位低电平释放后会被重新分帧成一个
//       好帧，判定随相位变化（详见正文 [5] 的注释）。
//   [6] B 路回传（31250，MIDI）：先发真实 MIDI Note On 序列
//       90 3C 64 80 3C 00 F8，再连发 24 字节，两段都必须逐字节回传一致，
//       B 行 by 累加、dr 恒为 0000。
//   [7] 对端偏快：对端位周期比本地短约 1.9%（UART 允许的偏差范围内），
//       连发 32 字节。这是回传缓冲真正要挡住的工况：接收持续快于发送时
//       相位差会逐字节累积，缓冲把它吸收掉，dr 仍为 0000。
//
//   本 TB 不检查的项（必须在板上做，见 uart_echo_probe.sv 文件头）：
//   * CH340 的实际电平与共地（仿真里没有电气模型）；
//   * 50 MHz 下 115200 / 31250 的真实位周期（本 TB 用 1 MHz，
//     按比例 DIV=9 / DIV=32 等比例缩放，无法覆盖真实计数器的位宽与余量）；
//   * 报告在 COM13 上的可读性。
//
// -----------------------------------------------------------------------------
// 仿真速率选择
// -----------------------------------------------------------------------------
//   CLK = 1 MHz，DIV_A = 9，DIV_B = 32：与 50 MHz 下 DIV=434 / 1600 同比例，
//   但把一条报告（约 175 字节）的仿真时间从 15 ms 压到同一量级而不需要
//   跑几百万个时钟周期。
//   BIT_A_NS=9000 与 DIV_A=9 精确对应（1 MHz / 9 拍 = 111111 bps，
//   TB 送出的位周期也取 9000 ns），因此收发位周期完全一致 ——
//   这点很重要：若 TB 的位周期与 DUT 的 DIV 不等，[4] 的 ed=30 /
//   mn=9 这类精确值会随相位漂移而变，断言就成了碰运气。
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_uart_echo_probe;

    localparam real CLK_PERIOD  = 1000.0;   // 1 MHz
    localparam int  BIT_A_NS    = 9000;     // 1e6 / 115200 -> DIV=9
    localparam int  BIT_B_NS    = 32000;    // 1e6 / 31250  -> DIV=32（精确）
    localparam int  BIT_FAST_NS = 31400;    // 对端比本地 B 路快约 1.9%

    localparam int  MAXLINES = 128;
    localparam int  MAXLEN   = 200;

    // ---- DUT 端口 -----------------------------------------------------------
    logic sys_clk;
    logic sys_rst_n;
    logic probe_rx;
    logic echo_tx_a;
    logic echo_tx_b;
    logic pa_en;
    logic i2s_bclk;
    logic i2s_lrck;
    logic i2s_din;
    logic uart_tx;

    int error_count = 0;
    int check_count = 0;

    initial sys_clk = 1'b0;
    always #(CLK_PERIOD / 2.0) sys_clk = ~sys_clk;

    uart_echo_probe #(
        .CLK_HZ    (1_000_000),
        .BAUD_A    (115_200),
        .BAUD_B    (31_250),
        .REPORT_MS (1)
    ) dut (
        .sys_clk    (sys_clk),
        .sys_rst_n  (sys_rst_n),
        .probe_rx   (probe_rx),
        .echo_tx_a  (echo_tx_a),
        .echo_tx_b  (echo_tx_b),
        .pa_en      (pa_en),
        .i2s_bclk   (i2s_bclk),
        .i2s_lrck   (i2s_lrck),
        .i2s_din    (i2s_din),
        .uart_tx    (uart_tx)
    );

    task automatic check(input string name, input bit cond);
        begin
            check_count = check_count + 1;
            if (cond) begin
                $display("  [OK]   %s", name);
            end else begin
                $display("  [FAIL] %s", name);
                error_count = error_count + 1;
            end
        end
    endtask

    // =========================================================================
    // 报告接收：只在 uart_tx 上收，按 LF 切行，行内容存成左对齐定宽向量
    // =========================================================================
    //   行内容不用 string 类型（iverilog 对 string 的运算支持有限），
    //   存成 [8*MAXLEN-1:0]：第 i 个字符在 bit 8*(MAXLEN-1-i)，
    //   与 SystemVerilog 给字符串字面量赋值时的左对齐约定一致，
    //   因此可以直接与期望字符串常量整段比较。
    // =========================================================================
    logic [8*MAXLEN-1:0] lines [0:MAXLINES-1];
    int                  line_len [0:MAXLINES-1];
    int                  line_count = 0;

    logic [8*MAXLEN-1:0] cur_line;
    int                  cur_len = 0;

    integer ri;
    logic [7:0] rb;

    // 收一个字节（在 uart_tx 的下降沿被调用，此时正处于起始位）
    task automatic rx_report_byte(output logic [7:0] d);
        integer b;
        begin
            #(BIT_A_NS + BIT_A_NS / 2);      // 起始位中点之后 = 数据位 0 中心
            for (b = 0; b < 8; b = b + 1) begin
                d[b] = uart_tx;
                #(BIT_A_NS);
            end
        end
    endtask

    initial begin : g_report_rx
        cur_line = '0;
        cur_len  = 0;
        forever begin
            @(negedge uart_tx);
            rx_report_byte(rb);
            if (rb == 8'h0A) begin
                if (line_count < MAXLINES) begin
                    // 【左对齐】逐字节追加时新字节进低位、旧内容上移，
                    // 因此整行内容落在**低位**端（第 i 个字符在 bit
                    // 8*(cur_len-1-i)）。而字符串字面量赋给定宽向量时是
                    // 第 0 个字符占**最高字节**。两边约定不同，直接整段
                    // 比较必然失败（长度却仍然对得上，很容易误判成"内容
                    // 错了"）。这里在收满一行时整体左移一次，把第 0 个
                    // 字符顶到 bit 8*(MAXLEN-1)，之后就可以和期望字符串
                    // 常量逐位比较，ch() 也能按从高位往低位取字符。
                    lines[line_count]    = cur_line << (8 * (MAXLEN - cur_len));
                    line_len[line_count] = cur_len;
                end
                line_count = line_count + 1;
                cur_line   = '0;
                cur_len    = 0;
            end
            else if (rb != 8'h0D) begin
                if (cur_len < MAXLEN) begin
                    cur_line = {cur_line[8*(MAXLEN-1)-1:0], rb};
                    cur_len  = cur_len + 1;
                end
            end
        end
    end

    // =========================================================================
    // 回传接收：A / B 两路各一个行为级接收器
    // =========================================================================
    logic [7:0] ea_buf [0:127];
    logic [7:0] eb_buf [0:127];
    int         ea_n = 0;
    int         eb_n = 0;

    task automatic rx_echo_byte(input int bit_ns, output logic [7:0] d);
        integer b;
        begin
            #(bit_ns + bit_ns / 2);
            for (b = 0; b < 8; b = b + 1) begin
                d[b] = (bit_ns == BIT_A_NS) ? echo_tx_a : echo_tx_b;
                #(bit_ns);
            end
        end
    endtask

    logic [7:0] ea_tmp, eb_tmp;

    initial begin : g_echo_rx_a
        forever begin
            @(negedge echo_tx_a);
            rx_echo_byte(BIT_A_NS, ea_tmp);
            if (ea_n < 128) ea_buf[ea_n] = ea_tmp;
            ea_n = ea_n + 1;
        end
    end

    initial begin : g_echo_rx_b
        forever begin
            @(negedge echo_tx_b);
            rx_echo_byte(BIT_B_NS, eb_tmp);
            if (eb_n < 128) eb_buf[eb_n] = eb_tmp;
            eb_n = eb_n + 1;
        end
    end

    // =========================================================================
    // 激励：驱动 probe_rx
    // =========================================================================
    //   stop_ns 一般等于 bit_ns（标准一位停止位）；[5] 用 3/4 位制造帧错误。
    //   gap_ns = 0 表示背靠背：一个字节的停止位结束后立刻开始下一字节的
    //   起始位，这正是"接收持续快于发送"的最坏工况。
    // =========================================================================
    task automatic drive_byte(
        input logic [7:0] d,
        input int         bit_ns,
        input logic       stop_level,
        input int         stop_ns,
        input int         gap_ns
    );
        integer b;
        begin
            probe_rx = 1'b0;                 // 起始位
            #(bit_ns);
            for (b = 0; b < 8; b = b + 1) begin
                probe_rx = d[b];             // LSB 先出
                #(bit_ns);
            end
            probe_rx = stop_level;           // 停止位
            #(stop_ns);
            probe_rx = 1'b1;                 // 回到空闲（下一字节若 gap_ns=0
                                             // 会立刻再拉低，形成背靠背）
            if (gap_ns > 0) #(gap_ns);
        end
    endtask

    task automatic send_btb(input logic [7:0] d, input int bit_ns);
        begin
            drive_byte(d, bit_ns, 1'b1, bit_ns, 0);
        end
    endtask

    // =========================================================================
    // 报告解析
    // =========================================================================
    //   一行的固定布局（字符下标）：
    //     0        'A' / 'B'
    //     1..4     " lv="   5       lv 值（1 位十六进制）
    //     6..9     " ed="   10..13  ed 值
    //     14..17   " by="   18..21  by 值
    //     22..25   " la="   26..27  la 值（"--" 表示未收到过）
    //     28..31   " fe="   32..35  fe 值
    //     36..39   " mn="   40..43  mn 值（"----" 表示样本不足）
    //     44..47   " dr="   48..51  dr 值
    //   共 52 字符。布局由 uart_echo_probe.sv 的 fld_byte/fld_last 决定，
    //   改字段顺序必须同步改这里。
    // =========================================================================
    function automatic logic [7:0] ch(input int li, input int idx);
        ch = lines[li][8*(MAXLEN-1-idx) +: 8];
    endfunction

    function automatic logic [3:0] nib(input logic [7:0] c);
        if ((c >= "0") && (c <= "9"))      nib = c - "0";
        else if ((c >= "A") && (c <= "F")) nib = c - "A" + 4'd10;
        else                               nib = 4'h0;
    endfunction

    function automatic logic [15:0] hex4(input int li, input int off);
        hex4 = {nib(ch(li, off)), nib(ch(li, off+1)),
                nib(ch(li, off+2)), nib(ch(li, off+3))};
    endfunction

    function automatic bit is_dash(input int li, input int off);
        is_dash = (ch(li, off) == "-");
    endfunction

    // 是不是一行合法的通道行：长度 52 且标签逐字匹配
    function automatic bit is_lane_line(input int li, input logic [7:0] tag);
        is_lane_line = (line_len[li] == 52) &&
                       (ch(li, 0) == tag) &&
                       (ch(li, 1) == " ") && (ch(li, 2) == "l") &&
                       (ch(li, 3) == "v") && (ch(li, 4) == "=") &&
                       (ch(li, 6) == " ") && (ch(li, 7) == "e") &&
                       (ch(li, 8) == "d") && (ch(li, 9) == "=");
    endfunction

    // ---- 期望文本（与 uart_echo_probe.sv 的 S_H1/S_H2/S_H3、S_PBIT 一致）----
    localparam logic [8*46-1:0] EXP_HDR =
        "ECHO-PROBE RX=R17 ECHO115200=R18 ECHO31250=T18";
    localparam logic [8*17-1:0] EXP_PBIT = "PBIT=0009 DB=0020";

    bit hdr_seen = 1'b0;
    bit pbit_seen = 1'b0;

    // 第一行 A 行（未受任何刺激时的那一条）
    bit          a_first_seen = 1'b0;
    logic        a_first_lv;
    logic [15:0] a_first_ed, a_first_by, a_first_fe, a_first_dr;
    bit          a_first_mn_ok;
    logic [15:0] a_first_mn;

    // 第一行 by=3 且 fe=0 的 A 行（A 路回传的干净读数）
    bit          a_good_seen = 1'b0;
    logic        a_good_lv;
    logic [15:0] a_good_ed, a_good_by, a_good_fe, a_good_dr, a_good_mn;
    logic [7:0]  a_good_la;
    bit          a_good_la_ok, a_good_mn_ok;

    // 第一行 by=3 且 fe>=1 的 A 行（帧错误）
    bit          a_bad_seen = 1'b0;
    logic [15:0] a_bad_by, a_bad_fe;

    // 最后一行 B 行（在 [7] 之前的快照）
    bit          b_seen = 1'b0;
    logic        b_lv;
    logic [15:0] b_ed, b_by, b_fe, b_dr, b_mn;
    logic [7:0]  b_la;
    bit          b_la_ok, b_mn_ok;

    // [7] 之后的最终读数
    bit          b_fin_seen = 1'b0;
    logic [15:0] b_fin_by, b_fin_dr;
    logic [7:0]  b_fin_la;
    bit          b_fin_la_ok;

    // 阶段 0：帧头 + 通路快照（在 [7] 之前调用）
    task automatic scan_phase0;
        int li;
        begin
            for (li = 0; li < line_count && li < MAXLINES; li = li + 1) begin
                // 帧头行
                if ((line_len[li] == 46) &&
                    (lines[li][8*MAXLEN-1 -: 8*46] == EXP_HDR)) begin
                    hdr_seen = 1'b1;
                end
                if ((line_len[li] == 17) &&
                    (lines[li][8*MAXLEN-1 -: 8*17] == EXP_PBIT)) begin
                    pbit_seen = 1'b1;
                end

                // A 行
                if (is_lane_line(li, "A")) begin
                    if (!a_first_seen) begin
                        a_first_seen  = 1'b1;
                        a_first_lv    = ch(li, 5) == "1";
                        a_first_ed    = hex4(li, 10);
                        a_first_by    = hex4(li, 18);
                        a_first_fe    = hex4(li, 32);
                        a_first_dr    = hex4(li, 48);
                        a_first_mn_ok = !is_dash(li, 40);
                        a_first_mn    = hex4(li, 40);
                    end
                    if (!a_good_seen && (hex4(li, 18) == 16'd3) &&
                        (hex4(li, 32) == 16'd0)) begin
                        a_good_seen   = 1'b1;
                        a_good_lv     = ch(li, 5) == "1";
                        a_good_ed     = hex4(li, 10);
                        a_good_by     = hex4(li, 18);
                        a_good_fe     = hex4(li, 32);
                        a_good_dr     = hex4(li, 48);
                        a_good_mn     = hex4(li, 40);
                        a_good_mn_ok  = !is_dash(li, 40);
                        a_good_la_ok  = !is_dash(li, 26);
                        a_good_la     = {nib(ch(li, 26)), nib(ch(li, 27))};
                    end
                    if (!a_bad_seen && (hex4(li, 18) == 16'd3) &&
                        (hex4(li, 32) >= 16'd1)) begin
                        a_bad_seen = 1'b1;
                        a_bad_by   = hex4(li, 18);
                        a_bad_fe   = hex4(li, 32);
                    end
                end

                // B 行：记录最后一条
                if (is_lane_line(li, "B")) begin
                    b_seen      = 1'b1;
                    b_lv        = ch(li, 5) == "1";
                    b_ed        = hex4(li, 10);
                    b_by        = hex4(li, 18);
                    b_fe        = hex4(li, 32);
                    b_dr        = hex4(li, 48);
                    b_mn        = hex4(li, 40);
                    b_mn_ok     = !is_dash(li, 40);
                    b_la_ok     = !is_dash(li, 26);
                    b_la        = {nib(ch(li, 26)), nib(ch(li, 27))};
                end
            end
        end
    endtask

    // 阶段 1：[7] 之后的 B 行（只看 by / la / dr）
    task automatic scan_phase1;
        int li;
        begin
            for (li = 0; li < line_count && li < MAXLINES; li = li + 1) begin
                if (is_lane_line(li, "B")) begin
                    b_fin_seen = 1'b1;
                    b_fin_by   = hex4(li, 18);
                    b_fin_dr   = hex4(li, 48);
                    b_fin_la_ok = !is_dash(li, 26);
                    b_fin_la   = {nib(ch(li, 26)), nib(ch(li, 27))};
                end
            end
        end
    endtask

    // =========================================================================
    // 主流程
    // =========================================================================
    int i;
    int ea_base, eb_base;
    logic [7:0] exp_midi [0:6];
    logic [7:0] exp_burst[0:23];
    logic [7:0] exp_fast [0:31];

    initial begin
        sys_rst_n = 1'b0;
        probe_rx  = 1'b1;

        exp_midi[0] = 8'h90; exp_midi[1] = 8'h3C; exp_midi[2] = 8'h64;
        exp_midi[3] = 8'h80; exp_midi[4] = 8'h3C; exp_midi[5] = 8'h00;
        exp_midi[6] = 8'hF8;
        for (i = 0; i < 24; i = i + 1) exp_burst[i] = 8'h40 + i[7:0];
        for (i = 0; i < 32; i = i + 1) exp_fast[i]  = 8'h80 + i[7:0];

        // ---- [1] 复位与静音 ------------------------------------------------
        $display("\n[1] 复位与静音");
        repeat (20) @(negedge sys_clk);
        sys_rst_n = 1'b1;
        repeat (20) @(negedge sys_clk);
        check("复位后 pa_en=1（功放关闭）", pa_en === 1'b1);
        check("复位后 i2s_bclk=0",         i2s_bclk === 1'b0);
        check("复位后 i2s_lrck=0",         i2s_lrck === 1'b0);
        check("复位后 i2s_din=0",          i2s_din === 1'b0);
        check("复位后 echo_tx_a 空闲为高", echo_tx_a === 1'b1);
        check("复位后 echo_tx_b 空闲为高", echo_tx_b === 1'b1);
        check("复位后 uart_tx 空闲为高",   uart_tx === 1'b1);

        // ---- [2][3] 等第一条报告，检查静态读数 -----------------------------
        //   一条报告约 175 字节，1 MHz/115200 下约 15.8 ms；这里等 20 ms。
        $display("\n[2][3] 等待第一条完整报告（约 20 ms 仿真时间）");
        #(20 * 1000 * 1000);
        scan_phase0;

        check("报告出现帧头行且与 CST 脚名一致", hdr_seen);
        check("报告出现 PBIT=0009 DB=0020",      pbit_seen);
        check("出现通道 A 行",                   a_first_seen);
        check("出现通道 B 行",                   b_seen);
        check("未加刺激时 A 行 lv=1",            a_first_lv === 1'b1);
        check("未加刺激时 A 行 ed=0000（引脚无扰动）", a_first_ed === 16'd0);
        check("未加刺激时 A 行 by=0000",         a_first_by === 16'd0);
        check("未加刺激时 B 行 ed=0000",         b_ed === 16'd0);
        check("未加刺激时 B 行 by=0000",         b_by === 16'd0);

        // ---- [4] A 路回传：3 个 0x55 背靠背 -------------------------------
        $display("\n[4] A 路 115200 回传：连发 3 个 0x55");
        ea_base = ea_n;
        send_btb(8'h55, BIT_A_NS);
        send_btb(8'h55, BIT_A_NS);
        send_btb(8'h55, BIT_A_NS);
        #(35 * 1000 * 1000);            // 等至少一轮完整报告刷新计数器

        check("A 路收到 3 个字节", ea_n == ea_base + 3);
        if (ea_n >= ea_base + 3) begin
            for (i = 0; i < 3; i = i + 1) begin
                if (ea_buf[ea_base + i] !== 8'h55) begin
                    $display("  [FAIL] A 回声第 %0d 个应为 55，实际 %02X",
                             i, ea_buf[ea_base + i]);
                    error_count = error_count + 1;
                end
                check_count = check_count + 1;
            end
            $display("  [OK]   A 回声逐字节等于 55 55 55");
        end

        scan_phase0;
        check("A 行出现 by=0003 且 fe=0000",     a_good_seen);
        check("该行 lv=1",                       a_good_lv === 1'b1);
        check("该行 ed=0030",                    a_good_ed === 16'd30);
        check("该行 mn=0009（位周期 9 拍）",     a_good_mn_ok && (a_good_mn === 16'd9));
        check("该行 la=55",                      a_good_la_ok && (a_good_la === 8'h55));
        check("该行 dr=0000（无丢弃）",          a_good_dr === 16'd0);

        // ---- [5] A 路帧错误：停止位持续为低 -------------------------------
        //   【为什么不用"停止位只压 3/4 位"】uart_rx 在本 TB 的 DIV=9
        //   （等价于 50 MHz 下 DIV=434 的等比缩小）时 HALF_LAST 被夹到 0，
        //   停止位采样点紧贴停止位起点。这种帧在停止位末尾还留 1/4 位低
        //   电平，接收器随即把这段低电平当成新的起始位、再配上后面拉高
        //   的空闲电平，解出一个**好帧**（实测 0xFF）。结果是"坏帧本身没
        //   回传"成立，却多出一个由释放边沿造成的伪帧，判定随相位变化，
        //   是碰运气而不是验证。改成把停止位一直压住：线路持续为低时每帧
        //   的数据位和停止位都采到 0，帧错误恒定成立，也不会解出任何好帧
        //   （与 tb_uart_rx 第 [7] 段同源）。低电平期间判定完再释放。
        $display("\n[5] A 路帧错误：停止位持续为低");
        probe_rx = 1'b0;
        #(20 * 1000 * 1000);
        scan_phase0;
        check("A 行出现 by=0003 且 fe>=1",       a_bad_seen);
        check("帧错误时 by 不增加（仍为 3）",    a_bad_by === 16'd3);
        check("帧错误计数 fe>=1",                a_bad_fe >= 16'd1);
        //   坏帧不应产生回传：只有无帧错误的帧才进缓冲
        check("坏帧不产生回传",                  ea_n == ea_base + 3);
        //   释放回空闲。释放边沿本身可能被重新分帧成一个伪字节，这是
        //   "线路被外部持续拉低后突然放开"的物理现象，不是设计缺陷，
        //   所以放在判定之后，并等报告刷新后再进入下一段。
        probe_rx = 1'b1;
        #(20 * 1000 * 1000);

        // ---- [6] B 路回传：真实 MIDI 序列 + 24 字节连发 --------------------
        $display("\n[6] B 路 31250 回传：MIDI 序列 + 24 字节连发");
        eb_base = eb_n;
        for (i = 0; i < 7; i = i + 1) send_btb(exp_midi[i], BIT_B_NS);
        //   先单独扫一次：此时 la 必然等于最后一个 MIDI 字节 F8。
        //   这样"la 字段跟着 MIDI 流走"和"31 字节连发不丢"是两条独立
        //   证据；混在一次扫描里，后者会把前者覆盖掉。
        #(20 * 1000 * 1000);
        scan_phase0;
        check("B 行 by>=0007（MIDI 前 7 字节）", b_by >= 16'd7);
        check("B 行 la=F8（最后一个是 MIDI 时钟）",
              b_la_ok && (b_la === 8'hF8));

        for (i = 0; i < 24; i = i + 1) send_btb(exp_burst[i], BIT_B_NS);
        #(35 * 1000 * 1000);

        check("B 路共收到 31 个字节", eb_n == eb_base + 31);
        if (eb_n >= eb_base + 31) begin
            for (i = 0; i < 7; i = i + 1) begin
                if (eb_buf[eb_base + i] !== exp_midi[i]) begin
                    $display("  [FAIL] B 回声 MIDI 第 %0d 个应为 %02X，实际 %02X",
                             i, exp_midi[i], eb_buf[eb_base + i]);
                    error_count = error_count + 1;
                end
                check_count = check_count + 1;
            end
            for (i = 0; i < 24; i = i + 1) begin
                if (eb_buf[eb_base + 7 + i] !== exp_burst[i]) begin
                    $display("  [FAIL] B 回声连发第 %0d 个应为 %02X，实际 %02X",
                             i, exp_burst[i], eb_buf[eb_base + 7 + i]);
                    error_count = error_count + 1;
                end
                check_count = check_count + 1;
            end
            $display("  [OK]   B 回声 31 字节逐字节一致（含 MIDI 90 3C 64 80 3C 00 F8）");
        end

        scan_phase0;
        check("B 行 by>=0031（两段都算上）",     b_by >= 16'd31);
        check("B 行 dr=0000（连续 31 字节不丢）", b_dr === 16'd0);
        check("B 行 lv=1",                       b_lv === 1'b1);
        //   连发之后 la 应等于连发末字节 0x40+23=0x57（F8 的检查已在前一次
        //   扫描完成，这里再要求 F8 就与激励自相矛盾）。
        check("B 行 la=57（连发末字节）",
              b_la_ok && (b_la === 8'h57));

        // ---- [7] 对端偏快 1.9%，连发 32 字节 -------------------------------
        //   本地 B 路位周期 32000 ns，对端 31400 ns -> 接收快于发送，
        //   相位差逐字节累积。回传缓冲必须把这 32 个字节全部送出去。
        $display("\n[7] B 路对端偏快 1.9%%：连发 32 字节");
        eb_base = eb_n;
        for (i = 0; i < 32; i = i + 1) send_btb(exp_fast[i], BIT_FAST_NS);
        #(50 * 1000 * 1000);

        check("B 路偏快工况共收到 32 个字节", eb_n == eb_base + 32);
        if (eb_n >= eb_base + 32) begin
            for (i = 0; i < 32; i = i + 1) begin
                if (eb_buf[eb_base + i] !== exp_fast[i]) begin
                    $display("  [FAIL] 偏快回声第 %0d 个应为 %02X，实际 %02X",
                             i, exp_fast[i], eb_buf[eb_base + i]);
                    error_count = error_count + 1;
                end
                check_count = check_count + 1;
            end
            $display("  [OK]   偏快工况 32 字节回声逐字节一致");
        end
        scan_phase1;
        check("偏快工况 B 行 dr=0000",           b_fin_dr === 16'd0);
        check("偏快工况 B 行 by>=0063",
              b_fin_by >= 16'd63);
        check("偏快工况 B 行 la=9F",
              b_fin_la_ok && (b_fin_la === 8'h9F));

        // ---- 汇总 ----------------------------------------------------------
        $display("\n共 %0d 项检查，%0d 项失败", check_count, error_count);
        if (error_count == 0) $display("PASS");
        else                  $display("FAIL: %0d errors", error_count);
        $finish;
    end

    // 看门狗：全部流程约 210 ms 仿真时间，600 ms 足够
    initial begin
        #(CLK_PERIOD * 600000);
        $display("FAIL: 仿真超时");
        $finish;
    end

endmodule
