// -----------------------------------------------------------------------------
// tb_reset_sync.sv
// reset_sync 自检 testbench。对应任务 T019。
//
// 覆盖：正常流程、边界条件、复位过程、异常场景。
// 自动判定 PASS/FAIL，不依赖人工看波形。
//
// 运行（iverilog，工作目录为仓库根）：
//   iverilog -g2012 -Wall -o tb_reset_sync.vvp \
//       code/rtl/common/reset_sync.sv code/tb/common/tb_reset_sync.sv
//   vvp tb_reset_sync.vvp
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_reset_sync;

    localparam int unsigned STAGES = 2;
    localparam real         CLK_PERIOD = 10.0;  // 100 MHz

    logic clk;
    logic rst_n;
    logic rst_sync_n;

    int error_count = 0;
    int check_count = 0;

    // 时钟
    initial clk = 1'b0;
    always #(CLK_PERIOD/2) clk = ~clk;

    // 被测模块
    reset_sync #(
        .STAGES (STAGES)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .rst_sync_n (rst_sync_n)
    );

    // 检查任务
    task automatic check(
        input string   name,
        input logic    actual,
        input logic    expected
    );
        check_count++;
        if (actual !== expected) begin
            error_count++;
            $display("  [FAIL] %-40s actual=%b expected=%b", name, actual, expected);
        end else begin
            $display("  [PASS] %-40s = %b", name, actual);
        end
    endtask

    // 精确验证：从确定的参考沿开始计到输出变高
    int unsigned precise_cycles;

    initial begin
        $display("=== tb_reset_sync 开始 ===");

        // ---------------------------------------------------------------------
        $display("\n[1] 上电即复位：rst_n=0 时输出必须为 0");
        // ---------------------------------------------------------------------
        rst_n = 1'b0;
        #(CLK_PERIOD * 5);
        check("复位期间 rst_sync_n=0", rst_sync_n, 1'b0);

        // ---------------------------------------------------------------------
        $display("\n[2] 正常释放：rst_n 拉高后经 STAGES 个时钟释放");
        // ---------------------------------------------------------------------
        // 在 negedge 释放 rst_n，使释放点远离上升沿，起点明确
        @(negedge clk);
        rst_n = 1'b1;

        // 从释放后的第一个上升沿开始，逐周期检查移位链各级
        precise_cycles = 0;
        @(posedge clk);  // 第 1 个沿：sync_chain[0] 应变 1，输出仍 0
        precise_cycles = 1;
        if (rst_sync_n !== 1'b0) begin
            $display("  [FAIL] 释放后第 1 个沿输出不应为高");
            error_count++;
        end

        @(posedge clk);  // 第 2 个沿：sync_chain[1] 应变 1，输出变高
        precise_cycles = 2;
        #(CLK_PERIOD/10);  // 略过沿附近的建立时间
        check("释放延迟等于 STAGES", rst_sync_n, 1'b1);
        $display("  释放经过 %0d 个时钟周期（期望 %0d）", precise_cycles, STAGES);

        // ---------------------------------------------------------------------
        $display("\n[3] 稳定后保持高电平");
        // ---------------------------------------------------------------------
        #(CLK_PERIOD * 10);
        check("稳定后 rst_sync_n=1", rst_sync_n, 1'b1);

        // ---------------------------------------------------------------------
        $display("\n[4] 异常场景：运行中异步拉低，必须立即生效");
        // ---------------------------------------------------------------------
        // 在时钟沿之间拉低，检验异步特性
        #(CLK_PERIOD/4);
        rst_n = 1'b0;
        #(CLK_PERIOD/8);  // 远小于一个时钟周期
        check("异步拉低立即生效", rst_sync_n, 1'b0);

        // ---------------------------------------------------------------------
        $display("\n[5] 二次释放：复位可重复");
        // ---------------------------------------------------------------------
        @(negedge clk);
        rst_n = 1'b1;
        @(posedge clk);  // 第 1 个沿，输出仍应为 0
        check("二次释放第 1 个沿仍为 0", rst_sync_n, 1'b0);
        @(posedge clk);  // 第 2 个沿，输出变高
        #(CLK_PERIOD/10);
        check("二次释放延迟等于 STAGES", rst_sync_n, 1'b1);

        // ---------------------------------------------------------------------
        $display("\n[6] 边界：极短复位脉冲（小于一个时钟周期）");
        // ---------------------------------------------------------------------
        // 异步复位应能捕获这种窄脉冲
        @(negedge clk);
        rst_n = 1'b0;
        #(CLK_PERIOD/8);
        rst_n = 1'b1;
        #(CLK_PERIOD/8);
        // 由于异步拉低立即生效，且持续到时钟沿之前，移位寄存器应已清零
        // 此处只验证不出现亚稳态或挂死，最终仍能正常释放
        @(posedge clk);
        @(posedge clk);
        #(CLK_PERIOD/10);
        check("窄脉冲后仍能正常释放", rst_sync_n, 1'b1);

        // ---------------------------------------------------------------------
        $display("\n=== 结果 ===");
        $display("检查项 %0d，失败 %0d", check_count, error_count);
        if (error_count == 0) begin
            $display("PASS");
        end else begin
            $display("FAIL");
        end
        $display("=== tb_reset_sync 结束 ===");
        $finish;
    end

    // 超时保护
    initial begin
        #(CLK_PERIOD * 2000);
        $display("FAIL: 仿真超时");
        $finish;
    end

endmodule
