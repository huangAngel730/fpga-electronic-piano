// -----------------------------------------------------------------------------
// tb_uart_rx.sv
// uart_rx 自检 testbench（code/tb/common）。
//
// 覆盖：复位、正常接收、数据边界值、背靠背连收，
//       以及三个异常场景（停止位为低、起始位毛刺、线路持续拉低）。
// 自动判定 PASS/FAIL。
//
// 运行（工作目录为仓库根）：
//   .\code\scripts\run_uart_rx_probe_sim.ps1
//
// 参数取 CLK_HZ=1 MHz、BAUD=50 kbps，即 DIV=20，位周期 20 个 clk。
// 取 20 而不是 10，是为了让"起始位毛刺"这一项有足够余量：
// 毛刺长度取 4 个 clk，远小于半个位周期（10 个 clk），必须被丢弃。
//
// 【本 TB 验证的核心语义，也是诊断工程依赖的语义】
//   rx_valid=1 表示"一帧结束"，它可能是好帧也可能是坏帧；
//   frame_err=1 表示该帧的停止位不是高。
//   线路持续拉低时接收器会不断产出 frame_err 帧而 good 帧为 0，
//   所以"收到数据"必须按 rx_valid && !frame_err 判定。
//   第 [7] 项就是钉这条语义的。
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_uart_rx;

    localparam real CLK_PERIOD = 1000.0;               // 1 MHz，仿真时间单位 1 ns
    localparam int  CLK_NS     = 1000;
    localparam int  DIV        = 20;                   // 1e6 / 50e3
    localparam int  BIT_NS     = CLK_NS * DIV;         // 一个位周期 20000 ns

    logic clk;
    logic rst_n;
    logic rx_line;
    logic [7:0] rx_data;
    logic       rx_valid;
    logic       frame_err;
    logic       rx_busy;

    int error_count = 0;
    int check_count = 0;

    initial clk = 1'b0;
    always #(CLK_PERIOD/2) clk = ~clk;

    uart_rx #(
        .CLK_HZ    (1_000_000),
        .BAUD      (50_000),
        .DATA_BITS (8)
    ) dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .rx        (rx_line),
        .rx_data   (rx_data),
        .rx_valid  (rx_valid),
        .frame_err (frame_err),
        .rx_busy   (rx_busy)
    );

    // -------------------------------------------------------------------------
    // 接收结果统计
    //   n_valid_cycles 统计 rx_valid 为高的拍数，用来确认它是"一拍脉冲"，
    //   而不是持续电平。它必须恰好等于 n_good + n_err。
    // -------------------------------------------------------------------------
    int n_valid_cycles = 0;
    int n_good         = 0;
    int n_err          = 0;
    logic [7:0] good_bytes [0:15];

    always @(posedge clk) begin
        if (rx_valid) begin
            n_valid_cycles = n_valid_cycles + 1;
            if (frame_err) begin
                n_err = n_err + 1;
            end else begin
                if (n_good < 16) good_bytes[n_good] = rx_data;
                n_good = n_good + 1;
            end
        end
    end

    // -------------------------------------------------------------------------
    // 行为级 UART 发送：按位周期把字节推到 rx_line 上
    //   stop_level  停止位电平。正常为 1；制造帧错误时给 0。
    //   stop_ns     停止位电平保持多久。正常给 BIT_NS（整个位周期）。
    //               制造"孤立帧错误"时给 0.6 * BIT_NS：接收器在停止位中点
    //               采样会读到低、判出帧错误，但线路在它回到空闲态重新找
    //               起始位之前就已经抬高，于是那次误检的起始位会被当成毛刺
    //               丢掉，不会级联出额外帧。若把低电平按满一个位周期，
    //               接收器会在同一帧结束后立刻误检到新的起始位，
    //               这是"线路被按住"的 break 场景，不是帧错误场景。
    //   gap_bits    一帧之后再保持几个位周期的空闲（高）
    // -------------------------------------------------------------------------
    task automatic drive_byte(input logic [7:0] d, input logic stop_level,
                              input int stop_ns, input int gap_bits);
        int i;
        begin
            rx_line = 1'b0;                       // 起始位
            #(BIT_NS);
            for (i = 0; i < 8; i = i + 1) begin
                rx_line = d[i];                   // LSB 先发
                #(BIT_NS);
            end
            rx_line = stop_level;                 // 停止位
            #(stop_ns);
            rx_line = 1'b1;                       // 回到空闲高
            if (gap_bits > 0) #(BIT_NS * gap_bits);
        end
    endtask

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

    int frames_before;

    // -------------------------------------------------------------------------
    // 主流程
    // -------------------------------------------------------------------------
    initial begin
        rst_n   = 1'b0;
        rx_line = 1'b1;      // 空闲为高

        // ---- [1] 复位 ------------------------------------------------------
        $display("\n[1] 复位状态");
        repeat (5) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        repeat (3) @(negedge clk);
        check("复位后 rx_busy 为 0",   rx_busy === 1'b0);
        check("复位后 rx_valid 为 0",  rx_valid === 1'b0);
        check("复位后没有收到任何帧",  (n_good + n_err) == 0);

        // ---- [2] 正常接收 --------------------------------------------------
        $display("\n[2] 接收 0xA5");
        drive_byte(8'hA5, 1'b1, BIT_NS, 2);
        check("0xA5 收到且无帧错误",   n_good == 1 && n_err == 0);
        check("0xA5 数值正确",         good_bytes[0] === 8'hA5);

        // ---- [3] 数据边界 --------------------------------------------------
        $display("\n[3] 边界值 0x00 / 0xFF");
        drive_byte(8'h00, 1'b1, BIT_NS, 2);
        check("0x00 数值正确",         n_good == 2 && good_bytes[1] === 8'h00);
        drive_byte(8'hFF, 1'b1, BIT_NS, 2);
        check("0xFF 数值正确",         n_good == 3 && good_bytes[2] === 8'hFF);

        // ---- [4] 背靠背 ----------------------------------------------------
        //   两帧之间不留空闲，第二帧的起始位紧跟第一帧的停止位。
        //   drive_byte 是阻塞任务，两个字节发完后才能检查，
        //   所以三项断言都放在两次发送之后。
        $display("\n[4] 背靠背连收两个字");
        drive_byte(8'h12, 1'b1, BIT_NS, 0);
        drive_byte(8'h34, 1'b1, BIT_NS, 2);
        check("背靠背第一字节 0x12",   good_bytes[3] === 8'h12);
        check("背靠背第二字节 0x34",   good_bytes[4] === 8'h34);
        check("背靠背未产生帧错误",    n_err == 0 && n_good == 5);

        // ---- [5] 异常：停止位为低 ------------------------------------------
        $display("\n[5] 异常场景：停止位为低");
        frames_before = n_good + n_err;
        drive_byte(8'h5A, 1'b0, (BIT_NS * 6) / 10, 2);
        repeat (2) @(negedge clk);
        check("坏停止位产生一帧 frame_err", n_err == 1);
        check("坏停止位不计入正确数据",     n_good == 5);
        check("坏帧仍然输出了一拍 rx_valid",
              (n_good + n_err) == frames_before + 1);

        // ---- [6] 异常：起始位毛刺 ------------------------------------------
        //   毛刺 4 个 clk，远小于半个位周期（10 个 clk），必须被丢弃。
        $display("\n[6] 异常场景：起始位毛刺");
        frames_before = n_good + n_err;
        @(negedge clk);
        rx_line = 1'b0;
        #(CLK_NS * 4);
        rx_line = 1'b1;
        repeat (30 * DIV) @(negedge clk);
        check("毛刺未产生任何帧",      (n_good + n_err) == frames_before);
        check("毛刺后回到空闲",        rx_busy === 1'b0);

        // ---- [7] 异常：线路持续拉低 ----------------------------------------
        //   这一项钉的是"收到数据"的判定语义：
        //   线路被拉低时接收器会不断产出 frame_err 帧，正确帧必须保持为 0。
        $display("\n[7] 异常场景：线路持续拉低");
        frames_before = n_good + n_err;
        @(negedge clk);
        rx_line = 1'b0;
        repeat (3000) @(negedge clk);
        check("持续拉低时正确帧仍为 0",  n_good == 5);
        check("持续拉低时产生多帧 frame_err", n_err >= 5);
        check("持续拉低时不会卡死",
              (n_good + n_err) > frames_before);
        rx_line = 1'b1;
        repeat (30 * DIV) @(negedge clk);
        check("恢复空闲后能重新同步",    rx_busy === 1'b0);

        // ---- 汇总 ----------------------------------------------------------
        $display("\n共 %0d 项检查，%0d 项失败；正确帧 %0d，帧错误 %0d，rx_valid 高电平 %0d 拍",
                 check_count, error_count, n_good, n_err, n_valid_cycles);
        check("rx_valid 是每帧一拍的脉冲",
              n_valid_cycles == (n_good + n_err));
        if (error_count == 0) $display("PASS");
        else                  $display("FAIL: %0d errors", error_count);
        $finish;
    end

    // -------------------------------------------------------------------------
    // 看门狗
    // -------------------------------------------------------------------------
    initial begin
        #(CLK_PERIOD * 30000);
        $display("FAIL: 仿真超时");
        $finish;
    end

endmodule
