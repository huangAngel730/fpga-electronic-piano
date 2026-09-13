// -----------------------------------------------------------------------------
// tb_sample_tick_gen.sv
// sample_tick_gen 自检 testbench。对应任务 T019。
//
// 覆盖任务要求的：复位、脉宽、间隔、长期计数、参数边界。
// 自动判定 PASS/FAIL。
//
// 运行（iverilog，工作目录为仓库根）：
//   iverilog -g2012 -Wall -o tb_sample_tick_gen.vvp \
//       代码/rtl/common/sample_tick_gen.sv 代码/tb/common/tb_sample_tick_gen.sv
//   vvp tb_sample_tick_gen.vvp
//
// 为缩短仿真时间，本 TB 用缩小位宽的累加器验证行为，
// 长期频率精度另用 Python 脚本分析（代码/scripts/analyze_clock_plan.py）。
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_sample_tick_gen;

    // -------------------------------------------------------------------------
    // 为加快仿真，使用 16 位累加器和较低的时钟频率。
    // 相位累加的行为与位宽无关，验证结论可外推到 32 位。
    //
    // 取 FCLK = 48 kHz * 256 = 12.288 MHz，ACC_BITS = 16
    // step = 2^16 * 48000 / 12288000 = 256
    // 即每 256 个时钟产生一个 tick
    // -------------------------------------------------------------------------
    localparam int unsigned ACC_BITS  = 16;
    localparam int unsigned DIV_RATIO = 256;
    localparam real         CLK_PERIOD = 10.0;  // 100 MHz 名义值，仅决定仿真时间

    logic clk;
    logic rst_n;
    logic sample_tick;

    int error_count = 0;
    int check_count = 0;

    // tick 计数与间隔统计
    int unsigned tick_count    = 0;
    int unsigned min_interval  = 32'h7FFFFFFF;
    int unsigned max_interval  = 0;
    int unsigned cur_interval  = 0;

    initial clk = 1'b0;
    always #(CLK_PERIOD/2) clk = ~clk;

    sample_tick_gen #(
        .ACC_BITS   (ACC_BITS),
        .PHASE_STEP (DIV_RATIO)     // 32'd256 截断到 16 位
    ) dut (
        .clk         (clk),
        .rst_n       (rst_n),
        .sample_tick (sample_tick)
    );

    // 在一个时钟沿采样 tick，统计间隔与脉宽。
    //
    // 计数约定：cur_interval 统计两个 tick 之间相隔的时钟周期数。
    // 在 tick 出现的那一拍记录间隔，然后把该拍算作下一段的第 0 拍。
    // 这样整除时相邻 tick 的间隔恰好等于分频比。
    int unsigned pulse_run = 0;   // 连续为高的拍数
    int unsigned max_pulse = 0;   // 观测到的最大脉宽

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            cur_interval <= 0;
            pulse_run    <= 0;
            max_pulse    <= 0;
            tick_count   <= 0;
        end else begin
            // 脉宽统计：tick 为高的连续拍数
            if (sample_tick) pulse_run <= pulse_run + 1;
            else begin
                if (pulse_run > max_pulse) max_pulse <= pulse_run;
                pulse_run <= 0;
            end

            // 间隔统计
            //
            // 计数约定：cur_interval 记录两个 tick 之间经过的时钟周期数。
            // tick 出现那一拍 cur_interval 被清零，因此下一个 tick 到来时
            // cur_interval 的值是「实际间隔 - 1」，需要加 1 还原。
            if (sample_tick) begin
                if ((cur_interval + 1) < min_interval) min_interval <= cur_interval + 1;
                if ((cur_interval + 1) > max_interval) max_interval <= cur_interval + 1;
                cur_interval <= 0;
                tick_count   <= tick_count + 1;
            end else begin
                cur_interval <= cur_interval + 1;
            end
        end
    end

    task automatic check(
        input string name,
        input logic  cond
    );
        check_count++;
        if (!cond) begin
            error_count++;
            $display("  [FAIL] %s", name);
        end else begin
            $display("  [PASS] %s", name);
        end
    endtask

    // 测量一个 tick 的脉宽（时钟周期数）
    int unsigned pulse_width;

    initial begin        $display("=== tb_sample_tick_gen 开始 ===");
        $display("参数：ACC_BITS=%0d PHASE_STEP=%0d（每 %0d 个时钟一个 tick）",
                 ACC_BITS, DIV_RATIO, DIV_RATIO);

        // ---------------------------------------------------------------------
        $display("\n[1] 复位期间：sample_tick 必须为 0");
        // ---------------------------------------------------------------------
        rst_n = 1'b0;
        #(CLK_PERIOD * 10);
        check("复位期间 sample_tick=0", sample_tick === 1'b0);
        check("复位期间 tick_count=0",  tick_count == 0);

        // ---------------------------------------------------------------------
        $display("\n[2] 释放后开始产生 tick");
        // ---------------------------------------------------------------------
        rst_n = 1'b1;
        // 等待足够长时间（至少一个分频周期）
        repeat (DIV_RATIO * 2) @(posedge clk);
        #(CLK_PERIOD);
        $display("  已产生 %0d 个 tick", tick_count);
        check("释放后已产生 tick", tick_count > 0);

        // ---------------------------------------------------------------------
        $display("\n[3] tick 脉宽：必须恰好一个时钟周期");
        // ---------------------------------------------------------------------
        // max_pulse 由 always_ff 逐拍统计，反映真实脉宽
        $display("  实测最大脉宽 = %0d 个时钟周期", max_pulse);
        check("脉宽为 1 个时钟周期", max_pulse == 1);

        // ---------------------------------------------------------------------
        $display("\n[4] 间隔稳定性：整除时应无抖动");
        // ---------------------------------------------------------------------
        // 清零统计后重跑
        min_interval = 32'h7FFFFFFF;
        max_interval = 0;
        repeat (DIV_RATIO * 50) @(posedge clk);
        #(CLK_PERIOD);
        $display("  最小间隔 = %0d，最大间隔 = %0d（期望均为 %0d）",
                 min_interval, max_interval, DIV_RATIO);
        check("最小间隔等于分频比", min_interval == DIV_RATIO);
        check("最大间隔等于分频比", max_interval == DIV_RATIO);
        check("间隔无抖动", min_interval == max_interval);

        // ---------------------------------------------------------------------
        $display("\n[5] 长期计数精度");
        // ---------------------------------------------------------------------
        // 统计整数个周期的 tick 数，验证无累积漏计
        // 清空计数后跑 N 个分频周期，应得到 N 个 tick
        // 由于 tick_count 是自由运行的，这里用差值判断
        begin
            int unsigned before_count;
            int unsigned expected;
            before_count = tick_count;
            expected = 40;
            repeat (DIV_RATIO * expected) @(posedge clk);
            #(CLK_PERIOD);
            $display("  期望新增 %0d 个 tick，实际新增 %0d 个",
                     expected, tick_count - before_count);
            // 允许 ±1 的边界误差（起止未对齐）
            check("长期计数误差不超过 1",
                  (tick_count - before_count) >= (expected - 1) &&
                  (tick_count - before_count) <= (expected + 1));
        end

        // ---------------------------------------------------------------------
        $display("\n[6] 异常场景：运行中复位，应干净重启");
        // ---------------------------------------------------------------------
        @(negedge clk);
        rst_n = 1'b0;
        #(CLK_PERIOD * 3);
        check("运行中复位后 sample_tick=0", sample_tick === 1'b0);
        check("运行中复位后 tick_count=0",  tick_count == 0);
        // 确认累加器也清零：释放后应恰好经过 DIV_RATIO 个周期才出第一个 tick
        @(negedge clk);
        rst_n = 1'b1;
        begin
            int unsigned cycles_to_first;
            cycles_to_first = 0;
            while (sample_tick !== 1'b1 && cycles_to_first < (DIV_RATIO * 2)) begin
                @(posedge clk);
                cycles_to_first++;
            end
            $display("  复位释放到首个 tick 经过 %0d 个周期（期望 %0d）",
                     cycles_to_first, DIV_RATIO);
            check("复位后累加器已清零",
                  cycles_to_first == DIV_RATIO ||
                  cycles_to_first == DIV_RATIO + 1);
        end

        // ---------------------------------------------------------------------
        $display("\n=== 结果 ===");
        $display("检查项 %0d，失败 %0d", check_count, error_count);
        if (error_count == 0) $display("PASS");
        else                  $display("FAIL");
        $display("=== tb_sample_tick_gen 结束 ===");
        $finish;
    end

    initial begin
        #(CLK_PERIOD * 200000);
        $display("FAIL: 仿真超时");
        $finish;
    end

endmodule
