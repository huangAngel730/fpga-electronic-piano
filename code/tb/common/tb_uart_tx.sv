// -----------------------------------------------------------------------------
// tb_uart_tx.sv
// uart_tx 自检 testbench（code/tb/common）。
//
// 覆盖：复位、正常帧的位序与帧长、数据边界值、背靠背连发、
//       以及两个异常场景（帧中改数据、帧中拉握手）。
// 自动判定 PASS/FAIL。
//
// 运行（工作目录为仓库根）：
//   .\code\scripts\run_uart_rx_probe_sim.ps1
//
// 参数取 CLK_HZ=1 MHz、BAUD=100 kbps，即 DIV=10，位周期 10 个 clk。
// 用小于实际的 DIV 是为了让波形逐位可核对；位周期是纯计数逻辑，
// 结论与 50 MHz/115200（DIV=434）一致。
//
// 【两个容易写错的点，本 TB 特意按正确方式处理】
//   1. 数帧不能用 tx 的下降沿。0xA5 这样的数据位本身就带着若干下降沿，
//      会把一帧数成四帧。tx_ready 每拉低一次才对应受理一个字节。
//   2. 不能在帧还没结束时发起下一次握手。起始位中点采样只走到 9.5 个位
//      周期，此时 tx_ready 还是 0，握手会被丢掉，然后 TB 会一直等一个
//      永远不来的下降沿。所以每次发字节前都先 wait_idle。
//
//   另外：背靠背两帧之间固定有 1 个 clk 的间隔，不是 0。原因是 tx_ready 是
//   寄存器输出，只在停止位最后一拍拉高一个周期，下一帧要到再下一拍才受理。
//   这是"ready 脉冲式握手"的必然代价，对 UART 无影响（115200 下 1 个 clk
//   只占一个位周期的 1/434）。本 TB 按真实值断言，不做美化。
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_uart_tx;

    localparam real CLK_PERIOD = 1000.0;               // 1 MHz，仿真时间单位 1 ns
    localparam int  CLK_NS     = 1000;
    localparam int  DIV        = 10;                   // 1e6 / 100e3
    localparam int  BIT_NS     = CLK_NS * DIV;         // 一个位周期 10000 ns

    logic clk;
    logic rst_n;
    logic [7:0] tx_data;
    logic       tx_valid;
    logic       tx_ready;
    logic       tx;

    int error_count = 0;
    int check_count = 0;

    initial clk = 1'b0;
    always #(CLK_PERIOD/2) clk = ~clk;

    uart_tx #(
        .CLK_HZ    (1_000_000),
        .BAUD      (100_000),
        .DATA_BITS (8),
        .STOP_BITS (1)
    ) dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .tx_data  (tx_data),
        .tx_valid (tx_valid),
        .tx_ready (tx_ready),
        .tx       (tx)
    );

    // -------------------------------------------------------------------------
    // 帧计数与帧间隔：以 tx_ready 的下降沿为准
    // -------------------------------------------------------------------------
    int  frame_cnt    = 0;
    time t_ready_prev = 0;
    time t_gap        = 0;      // 相邻两次受理之间的时间
    bit  first_frame  = 1'b1;

    always @(negedge tx_ready) begin
        frame_cnt = frame_cnt + 1;
        if (first_frame) begin
            first_frame = 1'b0;
        end else begin
            t_gap = $time - t_ready_prev;
        end
        t_ready_prev = $time;
    end

    // -------------------------------------------------------------------------
    // 检查辅助
    // -------------------------------------------------------------------------
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

    // 等到发送器空闲：tx_ready 回到 1
    task automatic wait_idle;
        begin
            @(negedge clk);
            while (tx_ready !== 1'b1) @(negedge clk);
        end
    endtask

    // 采一帧：等起始位下降沿，然后在每个位的正中间采样。
    // frame = {停止位, b7..b0, 起始位}，即 frame[1+i] 是数据位 i。
    // 调用前必须保证 tx 处于空闲（高），否则会锁到帧内数据位的下降沿上。
    task automatic recv_frame(output logic [9:0] frame);
        int i;
        begin
            @(negedge tx);
            #(BIT_NS/2);
            frame[0] = tx;                    // 起始位中点
            for (i = 1; i <= 8; i = i + 1) begin
                #(BIT_NS);
                frame[i] = tx;                // 数据位 b(i-1)
            end
            #(BIT_NS);
            frame[9] = tx;                    // 停止位
        end
    endtask

    // 发起一次握手。tx_valid 保持一拍。
    task automatic send(input logic [7:0] d);
        begin
            @(negedge clk);
            tx_data  = d;
            tx_valid = 1'b1;
            @(negedge clk);
            tx_valid = 1'b0;
        end
    endtask

    // 期望的帧值：起始位 0 + 数据 LSB 先 + 停止位 1
    function automatic logic [9:0] exp_frame(input logic [7:0] d);
        logic [9:0] f;
        begin
            f[0]      = 1'b0;
            f[8:1]    = d;
            f[9]      = 1'b1;
            exp_frame = f;
        end
    endfunction

    logic [9:0] f1, f2, f3, f4, f5, f6, f7;

    // -------------------------------------------------------------------------
    // 主流程
    // -------------------------------------------------------------------------
    initial begin
        rst_n    = 1'b0;
        tx_data  = 8'h00;
        tx_valid = 1'b0;

        // ---- [1] 复位 ------------------------------------------------------
        $display("\n[1] 复位状态");
        repeat (5) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        repeat (3) @(negedge clk);
        check("复位后 tx 空闲为高",       tx === 1'b1);
        check("复位后 tx_ready 为 1",     tx_ready === 1'b1);
        check("复位期间没有受理任何字节", frame_cnt == 0);

        // ---- [2] 正常帧位序 ------------------------------------------------
        $display("\n[2] 发送 0xA5，逐位核对");
        fork
            recv_frame(f1);
            send(8'hA5);
        join
        check("0xA5 整帧位序正确",        f1 === exp_frame(8'hA5));
        check("0xA5 起始位为低",          f1[0] === 1'b0);
        check("0xA5 停止位为高",          f1[9] === 1'b1);
        check("只受理了一个字节",         frame_cnt == 1);
        wait_idle();
        check("帧结束后 tx_ready 恢复为 1", tx_ready === 1'b1);
        check("帧结束后 tx 回到高",       tx === 1'b1);

        // ---- [3] 数据边界 --------------------------------------------------
        $display("\n[3] 边界值 0x00 / 0xFF");
        fork
            recv_frame(f2);
            send(8'h00);
        join
        check("0x00 整帧位序正确",        f2 === exp_frame(8'h00));
        wait_idle();
        fork
            recv_frame(f3);
            send(8'hFF);
        join
        check("0xFF 整帧位序正确",        f3 === exp_frame(8'hFF));
        wait_idle();

        // ---- [4] 背靠背 ----------------------------------------------------
        //   tx_valid 全程保持高：第一帧结束后 tx_ready 拉高的那一拍
        //   立即受理第二个字节。两帧之间只有 1 个 clk 的空隙。
        $display("\n[4] 背靠背连发两个字");
        @(negedge clk);
        tx_data  = 8'h3C;
        tx_valid = 1'b1;
        fork
            begin
                recv_frame(f4);           // 9.5 个位周期后返回
                recv_frame(f5);           // 立刻接着等第二帧的起始位
            end
            begin
                @(negedge tx);
                #(5 * BIT_NS);            // 帧中途改数据，为第二帧做准备
                tx_data = 8'h5A;
            end
            begin
                @(negedge tx);
                #(11 * BIT_NS);           // 第二帧已在 10.1 个位周期被受理
                tx_valid = 1'b0;          // 撤掉握手，避免再受理第三帧
            end
        join
        check("背靠背第一帧为 0x3C",      f4 === exp_frame(8'h3C));
        check("背靠背第二帧为 0x5A",      f5 === exp_frame(8'h5A));
        check("背靠背共受理两帧",         frame_cnt == 5);
        check("两帧间隔 = 10 个位周期 + 1 拍",
              t_gap == (BIT_NS * 10 + CLK_NS));
        wait_idle();

        // ---- [5] 异常：帧中改数据 ------------------------------------------
        //   数据在握手那一拍就被锁存，帧中改 tx_data 不得影响在飞的帧。
        //   三个分支都必须并发：recv_frame 要在帧起跳之前就开始等下降沿，
        //   否则会锁到帧内数据位的边沿上。
        $display("\n[5] 异常场景：帧中途改 tx_data");
        fork
            recv_frame(f6);
            begin
                @(negedge clk);
                tx_data  = 8'h69;
                tx_valid = 1'b1;
                @(negedge clk);
                tx_valid = 1'b0;
            end
            begin
                @(negedge tx);
                #(3 * BIT_NS);            // 帧刚开始就改数据
                tx_data = 8'h96;
            end
        join
        check("帧中改数据不影响在飞的帧", f6 === exp_frame(8'h69));
        wait_idle();

        // ---- [6] 异常：帧中拉握手 ------------------------------------------
        //   帧进行中 tx_ready=0，此时拉高 tx_valid 不得被受理，
        //   也不得在帧结束后补发。
        $display("\n[6] 异常场景：帧中途拉 tx_valid");
        fork
            recv_frame(f7);
            send(8'h0F);
            begin
                @(negedge tx);
                #(3 * BIT_NS);            // 已经进入数据位
                tx_data  = 8'h77;
                tx_valid = 1'b1;
                @(negedge clk);
                tx_valid = 1'b0;
            end
        join
        check("帧中拉 tx_valid 未破坏当前帧", f7 === exp_frame(8'h0F));
        // 等这一帧彻底结束，确认没有补发
        repeat (12 * DIV + 20) @(negedge clk);
        check("帧中拉 tx_valid 未产生额外帧", frame_cnt == 7);
        check("结束时 tx 回到空闲高",        tx === 1'b1);

        // ---- 汇总 ----------------------------------------------------------
        $display("\n共 %0d 项检查，%0d 项失败，实际受理 %0d 字节",
                 check_count, error_count, frame_cnt);
        if (error_count == 0) $display("PASS");
        else                  $display("FAIL: %0d errors", error_count);
        $finish;
    end

    // -------------------------------------------------------------------------
    // 看门狗
    // -------------------------------------------------------------------------
    initial begin
        #(CLK_PERIOD * 20000);
        $display("FAIL: 仿真超时");
        $finish;
    end

endmodule
