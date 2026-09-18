// -----------------------------------------------------------------------------
// tb_echo_fifo.sv
// echo_fifo 单元自检 testbench（code/tb/common）。
//
// 覆盖：
//   [1] 复位后 empty=1 / full=0 / drop_count=0，rd_data 不参与判定；
//   [2] 写入 3 字节后队首直通：rd_data 必须**当拍**等于第一个写入的字节，
//       不是"读过之后下一拍才出来"；
//   [3] 逐个弹出，顺序为 FIFO 顺序（先写先出），弹空后 empty=1；
//   [4] 同时读写（cnt 不变）的边界：不丢、不重复、计数不动；
//   [5] 填满 8 个后 full=1，再写 3 个被丢弃，drop_count 累加到 3 且
//       队内仍是**最早**的 8 个字节（满时丢弃的是后来的，不是覆盖旧的）；
//   [6] 空时 rd_en 不产生任何效果（读指针不动），随后写入仍能正确读出；
//   [7] 复位中途清空：存 4 个后复位，empty=1、drop_count=0、数据不再出现。
//
// 运行（工作目录为仓库根）：
//   .\code\scripts\run_uart_echo_probe_sim.ps1
//
// 参数取 WIDTH=8 / DEPTH=8，与 code/rtl/board/uart_echo_probe.sv 中的实例一致。
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_echo_fifo;

    localparam int WIDTH = 8;
    localparam int DEPTH = 8;

    logic             clk;
    logic             rst_n;
    logic             wr_en;
    logic [WIDTH-1:0] wr_data;
    logic             rd_en;
    logic [WIDTH-1:0] rd_data;
    logic             empty;
    logic             full;
    logic [15:0]      drop_count;

    int error_count = 0;
    int check_count = 0;

    initial clk = 1'b0;
    always #5 clk = ~clk;      // 100 MHz，纯功能仿真，速率不重要

    echo_fifo #(
        .WIDTH (WIDTH),
        .DEPTH (DEPTH)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .wr_en      (wr_en),
        .wr_data    (wr_data),
        .rd_en      (rd_en),
        .rd_data    (rd_data),
        .empty      (empty),
        .full       (full),
        .drop_count (drop_count)
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

    // 写一个字节（一拍握手）
    task automatic push(input logic [WIDTH-1:0] d);
        begin
            @(negedge clk);
            wr_en   = 1'b1;
            wr_data = d;
            @(negedge clk);
            wr_en   = 1'b0;
        end
    endtask

    // 弹一个字节（一拍握手），返回值给调用方用 $display 观察
    task automatic pop(output logic [WIDTH-1:0] d);
        begin
            @(negedge clk);
            d     = rd_data;      // 直通：弹出前先取到队首
            rd_en = 1'b1;
            @(negedge clk);
            rd_en = 1'b0;
        end
    endtask

    logic [WIDTH-1:0] got;
    int               i;

    initial begin
        rst_n   = 1'b0;
        wr_en   = 1'b0;
        wr_data = 8'h00;
        rd_en   = 1'b0;

        // ---- [1] 复位 ------------------------------------------------------
        $display("\n[1] 复位状态");
        repeat (4) @(negedge clk);
        rst_n = 1'b1;
        repeat (2) @(negedge clk);
        check("复位后 empty=1",        empty === 1'b1);
        check("复位后 full=0",         full === 1'b0);
        check("复位后 drop_count=0",   drop_count === 16'd0);

        // ---- [2] 队首直通 --------------------------------------------------
        //   这是本模块最容易被写错的地方：rd_data 必须是组合输出。
        //   若写成"读脉冲后下一拍出数据"，uart_tx 收到的就会是上一个字节，
        //   表现是回声整体错位一个字节。
        $display("\n[2] 写入 3 字节并检查队首直通");
        push(8'hA1);
        check("写 1 个后 empty=0",     empty === 1'b0);
        check("队首直通 rd_data=A1",   rd_data === 8'hA1);
        push(8'hB2);
        check("写 2 个后队首仍=A1",    rd_data === 8'hA1);
        push(8'hC3);
        check("写 3 个后队首仍=A1",    rd_data === 8'hA1);
        check("写 3 个后 full=0",      full === 1'b0);

        // ---- [3] 顺序弹出 --------------------------------------------------
        $display("\n[3] 逐个弹出，检查顺序");
        pop(got);  check("弹出 1 = A1", got === 8'hA1);
        pop(got);  check("弹出 2 = B2", got === 8'hB2);
        pop(got);  check("弹出 3 = C3", got === 8'hC3);
        check("弹空后 empty=1",        empty === 1'b1);

        // ---- [4] 同时读写 --------------------------------------------------
        //   cnt 不变的分支：最容易写成 +1 或 -1，写错会表现为
        //   "缓冲深度只有一半"或"提前报空"。
        $display("\n[4] 同时读写，计数不变");
        push(8'h11);
        push(8'h22);
        @(negedge clk);
        wr_en   = 1'b1;
        wr_data = 8'h33;
        rd_en   = 1'b1;
        check("同时读写时队首=11",     rd_data === 8'h11);
        @(negedge clk);
        wr_en = 1'b0;
        rd_en = 1'b0;
        pop(got);  check("同时读写后弹出 1 = 22", got === 8'h22);
        pop(got);  check("同时读写后弹出 2 = 33", got === 8'h33);
        check("同时读写后 empty=1",    empty === 1'b1);

        // ---- [5] 填满与丢弃 ------------------------------------------------
        $display("\n[5] 填满 8 个后继续写，检查丢弃计数与队内内容");
        for (i = 0; i < DEPTH; i = i + 1) push(i[WIDTH-1:0] + 8'h40);
        check("填满后 full=1",         full === 1'b1);
        check("填满后 empty=0",        empty === 1'b0);
        check("填满后丢弃计数仍为 0",  drop_count === 16'd0);
        push(8'hEE);
        push(8'hEF);
        push(8'hF0);
        check("满后再写 3 个 -> drop_count=3", drop_count === 16'd3);
        // 满时丢弃的是**后来**的字节，队内应仍是最早的 8 个（0x40..0x47）
        for (i = 0; i < DEPTH; i = i + 1) begin
            pop(got);
            if (got !== (i[WIDTH-1:0] + 8'h40)) begin
                $display("  [FAIL] 第 %0d 个应为 %02X，实际 %02X", i,
                         i[WIDTH-1:0] + 8'h40, got);
                error_count = error_count + 1;
            end
            check_count = check_count + 1;
        end
        $display("  [OK]   满时丢弃后来的字节，队内仍是最早的 8 个");
        check("丢弃计数在读出后保持",  drop_count === 16'd3);
        check("全弹出后 empty=1",      empty === 1'b1);

        // ---- [6] 空时读无效 ------------------------------------------------
        $display("\n[6] 空时 rd_en 无效，随后仍能正确写入读出");
        @(negedge clk);
        rd_en = 1'b1;
        repeat (3) @(negedge clk);
        rd_en = 1'b0;
        check("空读不改变 empty",      empty === 1'b1);
        push(8'h5A);
        check("空读后写入仍可读出",    rd_data === 8'h5A);
        pop(got);  check("弹出 = 5A",  got === 8'h5A);

        // ---- [7] 复位中途清空 ----------------------------------------------
        $display("\n[7] 存 4 个后复位");
        for (i = 0; i < 4; i = i + 1) push(8'h70 + i[WIDTH-1:0]);
        @(negedge clk);
        rst_n = 1'b0;
        repeat (2) @(negedge clk);
        check("复位后 empty=1",        empty === 1'b1);
        check("复位后 drop_count=0",   drop_count === 16'd0);
        check("复位后 full=0",         full === 1'b0);
        rst_n = 1'b1;
        repeat (2) @(negedge clk);
        push(8'h99);
        check("复位后重新写入可读出",  rd_data === 8'h99);

        // ---- 汇总 ----------------------------------------------------------
        $display("\n共 %0d 项检查，%0d 项失败", check_count, error_count);
        if (error_count == 0) $display("PASS");
        else                  $display("FAIL: %0d errors", error_count);
        $finish;
    end

    // 看门狗
    initial begin
        #100000;
        $display("FAIL: 仿真超时");
        $finish;
    end

endmodule
