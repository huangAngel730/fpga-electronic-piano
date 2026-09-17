// -----------------------------------------------------------------------------
// tb_uart_rx_probe.sv
// uart_rx_probe 集成自检 testbench（code/tb/board）。
//
// 这是本诊断工程最要紧的一层验证：它不只看端口电平，而是把 DUT 从 uart_tx
// 发出来的**报告文本**用行为级接收器解回来，切行、按字段解析成数字，
// 再断言每一个诊断字段。换句话说，它验证的是"人拿串口软件能读到什么"。
//
// 覆盖：
//   A 路 = 正常的 0x55 串流（模拟 CH340 发 'U'），然后补一个坏停止位字节；
//   B 路 = 持续拉低（模拟接错脚或被占线）。
// 断言：
//   * 版本行里的两个脚名正确；
//   * PBIT 行等于本工程自己的位周期；
//   * A 路出现 by=0003 / la=55 / mn=0009 / ed=001E / lv=1 / fe=0 的行；
//   * 之后出现 by=0003 / fe>=1 的行（坏停止位被如实计入 frame_err）；
//   * B 路 lv=0 / ed=0000 / by=0000 / fe>0 / la=-- / mn=----；
//     其中 ed=0000 同时验证了"上电初值不算跳变"的 arming 逻辑；
//   * pa_en 恒为 1（功放关闭）。
//
// 运行（工作目录为仓库根）：
//   .\code\scripts\run_uart_rx_probe_sim.ps1
//
// 参数取 CLK_HZ=1 MHz、BAUD=115200、REPORT_MS=1，即 DIV=9、位周期 9000 ns、
// 报告周期 1000 个 clk。取小 DIV 是为了让仿真快；
// 报告格式与判定逻辑与 50 MHz/115200（DIV=434）完全一致。
// 因此 PBIT 行期望是 0009 而不是 01B2。
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_uart_rx_probe;

    localparam real CLK_PERIOD = 1000.0;               // 1 MHz，仿真时间单位 1 ns
    localparam int  CLK_NS     = 1000;
    localparam int  DIV        = 9;                    // 1e6 / 115200 四舍五入
    localparam int  BIT_NS     = CLK_NS * DIV;         // 一个位周期 9000 ns

    localparam int MAXLINE  = 64;
    localparam int MAXLINES = 64;

    logic clk;
    logic sys_rst_n;
    logic pin_a;
    logic pin_b;
    logic pa_en;
    logic i2s_bclk;
    logic i2s_lrck;
    logic i2s_din;
    logic uart_tx;

    int error_count = 0;
    int check_count = 0;

    initial clk = 1'b0;
    always #(CLK_PERIOD/2) clk = ~clk;

    uart_rx_probe #(
        .CLK_HZ    (1_000_000),
        .BAUD      (115_200),
        .REPORT_MS (1)
    ) dut (
        .sys_clk   (clk),
        .sys_rst_n (sys_rst_n),
        .probe_a   (pin_a),
        .probe_b   (pin_b),
        .pa_en     (pa_en),
        .i2s_bclk  (i2s_bclk),
        .i2s_lrck  (i2s_lrck),
        .i2s_din   (i2s_din),
        .uart_tx   (uart_tx)
    );

    // -------------------------------------------------------------------------
    // 报告文本接收与切行
    // -------------------------------------------------------------------------
    logic [7:0] lineb [0:MAXLINES-1][0:MAXLINE-1];
    int         linelen [0:MAXLINES-1];
    int         nlines     = 0;
    int         curbuf_len = 0;

    task automatic push_byte(input logic [7:0] c);
        begin
            if (c === 8'h0A) begin                       // LF：一行结束
                if (nlines < MAXLINES) begin
                    linelen[nlines] = curbuf_len;
                    nlines          = nlines + 1;
                end
                curbuf_len = 0;
            end else if (c !== 8'h0D) begin              // CR 丢弃
                if ((nlines < MAXLINES) && (curbuf_len < MAXLINE)) begin
                    lineb[nlines][curbuf_len] = c;
                    curbuf_len = curbuf_len + 1;
                end
            end
        end
    endtask

    int cap_i;
    logic [7:0] cap_ch;

    // 行为级 UART 接收：从 uart_tx 的每个起始位下降沿开始，
    // 在 8 个数据位的正中间采样。
    initial begin
        forever begin
            @(negedge uart_tx);
            #(BIT_NS + BIT_NS/2);                        // 到 b0 中点
            for (cap_i = 0; cap_i < 8; cap_i = cap_i + 1) begin
                cap_ch[cap_i] = uart_tx;
                #(BIT_NS);
            end
            push_byte(cap_ch);
        end
    end

    // -------------------------------------------------------------------------
    // 文本解析辅助
    // -------------------------------------------------------------------------
    function automatic int hexval(input logic [7:0] c);
        if (c >= 8'h30 && c <= 8'h39) begin
            hexval = c - 8'h30;
        end else if (c >= 8'h41 && c <= 8'h46) begin
            hexval = c - 8'h41 + 10;
        end else if (c >= 8'h61 && c <= 8'h66) begin
            hexval = c - 8'h61 + 10;
        end else begin
            hexval = -1;
        end
    endfunction

    // 在第 l 行找三字符键 (c0,c1,c2)（形如 "by="），
    // 把紧随其后的 ndig 个十六进制字符解析成整数。
    //   返回 -1 表示没找到这个字段；
    //   返回 -2 表示找到了但内容不是十六进制（即 "--"/"----" 占位）。
    function automatic int field_hex(input int l, input logic [7:0] c0,
                                     input logic [7:0] c1, input logic [7:0] c2,
                                     input int ndig);
        int i, j, v, d, res;
        bit found;
        res   = -1;
        found = 1'b0;
        for (i = 0; i + 3 + ndig <= linelen[l]; i = i + 1) begin
            if (!found && (lineb[l][i] === c0) && (lineb[l][i+1] === c1)
                       && (lineb[l][i+2] === c2)) begin
                found = 1'b1;
                v     = 0;
                for (j = 0; j < ndig; j = j + 1) begin
                    d = hexval(lineb[l][i + 3 + j]);
                    if (d < 0) begin
                        v = -2;
                        j = ndig;                        // 提前结束内层循环
                    end else begin
                        v = v * 16 + d;
                    end
                end
                res = v;
            end
        end
        field_hex = res;
    endfunction

    // 第 l 行是否恰好等于给定字符串（右对齐存在 s 的低 n 个字节里）
    function automatic bit cmp_str(input int l, input logic [8*32-1:0] s, input int n);
        int i;
        bit ok;
        ok = (linelen[l] == n);
        for (i = 0; i < n; i = i + 1) begin
            if (lineb[l][i] !== s[8*(n-1-i) +: 8]) ok = 1'b0;
        end
        cmp_str = ok;
    endfunction

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

    // -------------------------------------------------------------------------
    // 行为级 UART 发送：模拟电脑经 CH340 往候选脚发字节
    //   stop_level / stop_ns 的含义见 tb_uart_rx.sv 的同名参数：
    //   制造孤立帧错误时把停止位拉低约 0.6 个位周期，既能被中点采样读到低，
    //   又能在接收器重新找起始位之前抬高，不会级联出额外帧。
    // -------------------------------------------------------------------------
    task automatic drive_byte_a(input logic [7:0] d, input logic stop_level,
                                input int stop_ns, input int gap_bits);
        int i;
        begin
            pin_a = 1'b0;
            #(BIT_NS);
            for (i = 0; i < 8; i = i + 1) begin
                pin_a = d[i];
                #(BIT_NS);
            end
            pin_a = stop_level;
            #(stop_ns);
            pin_a = 1'b1;
            if (gap_bits > 0) #(BIT_NS * gap_bits);
        end
    endtask

    // -------------------------------------------------------------------------
    // 结果汇总
    // -------------------------------------------------------------------------
    localparam logic [8*32-1:0] P_HDR  = "UART-RX-PROBE A=V14 B=Y14";   // 25 字符
    localparam logic [8*32-1:0] P_PBIT = "PBIT=0009";                   // 9 字符

    bit  hdr_ok      = 1'b0;
    bit  pbit_ok     = 1'b0;
    bit  a_good_seen = 1'b0;      // A 路 by=3 且 fe=0 的行
    bit  a_bad_seen  = 1'b0;      // A 路 by=3 且 fe>=1 的行
    int  a_ed_g = -1, a_la_g = -1, a_mn_g = -1, a_lv_g = -1;
    int  a_by_bad = -1, a_fe_bad = -1;
    int  b_lv = -1, b_ed = -1, b_by = -1, b_fe = -1, b_la = 0, b_mn = 0;
    int  b_line_seen = 0;

    int l, v;

    task automatic scan_lines;
        begin
            hdr_ok      = 1'b0;
            pbit_ok     = 1'b0;
            a_good_seen = 1'b0;
            a_bad_seen  = 1'b0;
            b_line_seen = 0;

            for (l = 0; l < nlines; l = l + 1) begin
                if (cmp_str(l, P_HDR, 25))  hdr_ok  = 1'b1;
                if (cmp_str(l, P_PBIT, 9))  pbit_ok = 1'b1;

                // ---- 通道 A ----
                if (lineb[l][0] === 8'h41) begin
                    v = field_hex(l, "b", "y", "=", 4);
                    if (v == 3) begin
                        if (field_hex(l, "f", "e", "=", 4) == 0) begin
                            a_good_seen = 1'b1;
                            a_ed_g = field_hex(l, "e", "d", "=", 4);
                            a_la_g = field_hex(l, "l", "a", "=", 2);
                            a_mn_g = field_hex(l, "m", "n", "=", 4);
                            a_lv_g = field_hex(l, "l", "v", "=", 1);
                        end else begin
                            a_bad_seen = 1'b1;
                            a_by_bad   = v;
                            a_fe_bad   = field_hex(l, "f", "e", "=", 4);
                        end
                    end
                end

                // ---- 通道 B ----
                if (lineb[l][0] === 8'h42) begin
                    b_line_seen = b_line_seen + 1;
                    b_lv = field_hex(l, "l", "v", "=", 1);
                    b_ed = field_hex(l, "e", "d", "=", 4);
                    b_by = field_hex(l, "b", "y", "=", 4);
                    b_fe = field_hex(l, "f", "e", "=", 4);
                    b_la = field_hex(l, "l", "a", "=", 2);
                    b_mn = field_hex(l, "m", "n", "=", 4);
                end
            end
        end
    endtask

    // -------------------------------------------------------------------------
    // 主流程
    // -------------------------------------------------------------------------
    initial begin
        sys_rst_n = 1'b0;
        pin_a     = 1'b1;      // 候选脚空闲为高
        pin_b     = 1'b0;      // 候选脚乙：持续拉低

        // ---- [1] 复位 ------------------------------------------------------
        $display("\n[1] 复位与静音状态");
        repeat (5) @(posedge clk);
        @(negedge clk);
        sys_rst_n = 1'b1;
        repeat (20) @(negedge clk);
        check("pa_en 恒为 1（功放关闭）", pa_en === 1'b1);
        check("i2s 三脚被驱动为低",       i2s_bclk === 1'b0 && i2s_lrck === 1'b0 && i2s_din === 1'b0);

        // ---- [2] A 路正常串流 ----------------------------------------------
        //   0x55 = 'U'，每一位都翻转，跳变间隔等于一个位周期，
        //   既容易量位周期，也是最常用的"连通性测试字节"。
        $display("\n[2] A 路发送 3 个 0x55");
        drive_byte_a(8'h55, 1'b1, BIT_NS, 2);
        drive_byte_a(8'h55, 1'b1, BIT_NS, 2);
        drive_byte_a(8'h55, 1'b1, BIT_NS, 2);
        repeat (25000) @(negedge clk);

        // ---- [3] A 路补一个坏停止位字节 ------------------------------------
        $display("\n[3] A 路发送一个坏停止位字节");
        drive_byte_a(8'h0F, 1'b0, (BIT_NS * 6) / 10, 2);
        repeat (25000) @(negedge clk);

        // ---- [4] 解析报告 --------------------------------------------------
        $display("\n[4] 解析串口报告（共收到 %0d 行）", nlines);
        // 先原样打印收到的文本，断言失败时可以直接看出是格式问题
        // 还是接收端采样问题。
        for (l = 0; l < nlines; l = l + 1) begin
            $write("  [line %0d] \"", l);
            for (v = 0; v < linelen[l]; v = v + 1) $write("%c", lineb[l][v]);
            $write("\"\n");
        end
        scan_lines;

        check("收到版本行且脚名正确",     hdr_ok);
        check("收到 PBIT 行且等于本工程位周期", pbit_ok);

        check("A 路出现 by=0003 且 fe=0 的行", a_good_seen);
        check("A 路 by=0003 行 la=55",   a_la_g == 8'h55);
        check("A 路 by=0003 行 mn=0009（位周期）", a_mn_g == DIV);
        check("A 路 by=0003 行 ed=001E（30 次跳变）", a_ed_g == 30);
        check("A 路 by=0003 行 lv=1（空闲高）", a_lv_g == 1);

        check("A 路出现 by=0003 且 fe>=1 的行", a_bad_seen);
        check("A 路坏停止位后 by 仍为 3",  a_by_bad == 3);
        check("A 路坏停止位计入 fe",       a_fe_bad >= 1);

        check("B 路收到报告行",           b_line_seen > 0);
        check("B 路 lv=0（持续拉低）",     b_lv == 0);
        check("B 路 ed=0000（上电初值不计跳变）", b_ed == 0);
        check("B 路 by=0000（没有正确帧）", b_by == 0);
        check("B 路 fe>0（持续帧错误）",   b_fe > 0);
        check("B 路 la 显示占位符 --",     b_la == -2);
        check("B 路 mn 显示占位符 ----",   b_mn == -2);

        // ---- 汇总 ----------------------------------------------------------
        $display("\n共 %0d 项检查，%0d 项失败", check_count, error_count);
        if (error_count == 0) $display("PASS");
        else                  $display("FAIL: %0d errors", error_count);
        $finish;
    end

    // -------------------------------------------------------------------------
    // 看门狗
    // -------------------------------------------------------------------------
    initial begin
        #(CLK_PERIOD * 300000);
        $display("FAIL: 仿真超时");
        $finish;
    end

endmodule
