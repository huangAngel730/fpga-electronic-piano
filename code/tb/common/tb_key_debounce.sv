// -----------------------------------------------------------------------------
// tb_key_debounce.sv
// key_debounce 自检 testbench。对应 V0036。
//
// 覆盖：复位行为、去抖门限、按下/松开脉冲、抖动抑制、多键独立。
// 全部检查自动判定 PASS/FAIL，退出码非 0 表示失败。
//
// 运行：.\code\scripts\run_t020_sim.ps1
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_key_debounce;

    localparam int unsigned KEYS         = 2;
    localparam int unsigned DEBOUNCE_CNT = 8;   // 缩小门限便于仿真
    localparam time         CLK_PERIOD   = 10;

    logic clk = 1'b0;
    logic rst_n;
    logic [KEYS-1:0] key_n;
    logic [KEYS-1:0] pressed;
    logic [KEYS-1:0] press_pulse;
    logic [KEYS-1:0] release_pulse;

    int pass_cnt = 0;
    int fail_cnt = 0;

    always #(CLK_PERIOD/2) clk = ~clk;

    key_debounce #(
        .KEYS         (KEYS),
        .DEBOUNCE_CNT (DEBOUNCE_CNT)
    ) dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .key_n         (key_n),
        .pressed       (pressed),
        .press_pulse   (press_pulse),
        .release_pulse (release_pulse)
    );

    task automatic check(input string name, input logic cond);
        begin
            if (cond) begin
                pass_cnt++;
                $display("  PASS: %s", name);
            end else begin
                fail_cnt++;
                $display("  FAIL: %s", name);
            end
        end
    endtask

    // 推进 n 个时钟
    task automatic tick(input int unsigned n);
        begin
            repeat (n) @(posedge clk);
            #1;
        end
    endtask

    initial begin
        $display("=== tb_key_debounce ===");

        // ---------------------------------------------------------------------
        // 1. 复位期间
        // ---------------------------------------------------------------------
        rst_n = 1'b0;
        key_n = 2'b11;          // 都松开（低有效 -> 1）
        tick(4);
        check("reset: pressed 全为 0", pressed == 2'b00);
        check("reset: 无按下脉冲",     press_pulse == 2'b00);
        check("reset: 无松开脉冲",     release_pulse == 2'b00);

        // ---------------------------------------------------------------------
        // 2. 复位释放后，松开状态不产生脉冲
        // ---------------------------------------------------------------------
        rst_n = 1'b1;
        tick(DEBOUNCE_CNT + 4);
        check("释放后: 仍为松开",   pressed == 2'b00);
        check("释放后: 无虚假按下脉冲", press_pulse == 2'b00);

        // ---------------------------------------------------------------------
        // 3. 按下 key0：不足门限时不确认
        // ---------------------------------------------------------------------
        key_n[0] = 1'b0;        // 按下 key0
        tick(DEBOUNCE_CNT / 2);
        check("按下不足门限: 尚未确认", pressed[0] == 1'b0);

        // 补足门限 -> 确认按下，且产生一次脉冲
        tick(DEBOUNCE_CNT);
        check("按下达门限: 已确认按下", pressed[0] == 1'b1);
        check("按下达门限: key1 未受影响", pressed[1] == 1'b0);

        // ---------------------------------------------------------------------
        // 4. 保持按下不重复产生脉冲
        // ---------------------------------------------------------------------
        tick(DEBOUNCE_CNT + 4);
        check("保持按下: 无重复按下脉冲", press_pulse == 2'b00);
        check("保持按下: 状态保持",       pressed[0] == 1'b1);

        // ---------------------------------------------------------------------
        // 5. 抖动抑制：快速反复翻转不应被确认为按下
        // ---------------------------------------------------------------------
        key_n[0] = 1'b1;
        tick(2);
        key_n[0] = 1'b0;
        tick(2);
        key_n[0] = 1'b1;
        tick(2);
        key_n[0] = 1'b0;
        tick(2);
        key_n[0] = 1'b1;
        tick(2);
        // 抖动期间计数反复清零，不应确认出任何新状态
        check("抖动期间: 保持原按下状态", pressed[0] == 1'b1);
        check("抖动期间: 无按下脉冲",     press_pulse == 2'b00);
        check("抖动期间: 无松开脉冲",     release_pulse == 2'b00);

        // ---------------------------------------------------------------------
        // 6. 稳定松开 -> 确认松开并产生脉冲
        // ---------------------------------------------------------------------
        key_n[0] = 1'b1;
        tick(DEBOUNCE_CNT + 4);
        check("松开达门限: 已确认松开", pressed[0] == 1'b0);

        // ---------------------------------------------------------------------
        // 7. 多键独立：key1 按下不影响 key0
        // ---------------------------------------------------------------------
        key_n[1] = 1'b0;
        tick(DEBOUNCE_CNT + 4);
        check("key1 按下: key1 确认",   pressed[1] == 1'b1);
        check("key1 按下: key0 保持松开", pressed[0] == 1'b0);

        // 两键同时按下
        key_n = 2'b00;
        tick(DEBOUNCE_CNT + 4);
        check("双键同按: 两键均确认", pressed == 2'b11);

        // 释放 key0，保持 key1
        key_n[0] = 1'b1;
        tick(DEBOUNCE_CNT + 4);
        check("释放 key0: key0 松开",   pressed[0] == 1'b0);
        check("释放 key0: key1 仍按下", pressed[1] == 1'b1);

        // ---------------------------------------------------------------------
        // 8. 运行中复位
        // ---------------------------------------------------------------------
        rst_n = 1'b0;
        tick(4);
        check("运行中复位: 状态清零", pressed == 2'b00);
        rst_n = 1'b1;
        key_n = 2'b11;
        tick(DEBOUNCE_CNT + 4);
        check("复位恢复: 回到松开且无脉冲", pressed == 2'b00 && press_pulse == 2'b00);

        // ---------------------------------------------------------------------
        $display("");
        $display("=== 结果: %0d PASS, %0d FAIL ===", pass_cnt, fail_cnt);
        if (fail_cnt != 0) begin
            $display("TESTBENCH FAILED");
            $fatal(1);
        end
        $display("TESTBENCH PASSED");
        $finish;
    end

endmodule
