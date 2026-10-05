`timescale 1ns/1ps

module tb_button_debouncer;

    localparam integer BUTTON_COUNT       = 2;
    localparam integer CLK_FREQ_HZ        = 10_000;
    localparam integer DEBOUNCE_TIME_MS   = 1;
    localparam integer DEBOUNCE_CYCLES    = 10;
    localparam time    CLK_HALF_PERIOD_NS = 50_000;

    logic                    clk;
    logic                    rst_n;
    logic [BUTTON_COUNT-1:0] button_n_async;
    logic [BUTTON_COUNT-1:0] button_down;
    logic [BUTTON_COUNT-1:0] button_press_pulse;
    logic [BUTTON_COUNT-1:0] button_release_pulse;

    integer error_count;
    integer press_count_0;
    integer press_count_1;
    integer release_count_0;
    integer release_count_1;

    button_debouncer #(
        .BUTTON_COUNT     (BUTTON_COUNT),
        .CLK_FREQ_HZ      (CLK_FREQ_HZ),
        .DEBOUNCE_TIME_MS (DEBOUNCE_TIME_MS)
    ) dut (
        .button_n_async     (button_n_async),
        .clk                (clk),
        .rst_n              (rst_n),
        .button_down        (button_down),
        .button_press_pulse (button_press_pulse),
        .button_release_pulse(button_release_pulse)
    );

    initial begin
        clk = 1'b0;
        forever #CLK_HALF_PERIOD_NS clk = ~clk;
    end

    // 在下降沿统计脉冲，避开上升沿非阻塞赋值的更新时刻。
    always @(negedge clk) begin
        if (button_press_pulse[0]) begin
            press_count_0 = press_count_0 + 1;
        end
        if (button_press_pulse[1]) begin
            press_count_1 = press_count_1 + 1;
        end
        if (button_release_pulse[0]) begin
            release_count_0 = release_count_0 + 1;
        end
        if (button_release_pulse[1]) begin
            release_count_1 = release_count_1 + 1;
        end
    end

    task automatic wait_clock_cycles(input integer cycle_count);
        integer cycle_index;
        begin
            for (cycle_index = 0; cycle_index < cycle_count; cycle_index = cycle_index + 1) begin
                @(posedge clk);
                #1;
            end
        end
    endtask

    task automatic check_value(
        input logic condition,
        input string description
    );
        begin
            if (!condition) begin
                error_count = error_count + 1;
                $display("ERROR: %s, time=%0t", description, $time);
            end
        end
    endtask

    initial begin
        rst_n             = 1'b0;
        button_n_async    = {BUTTON_COUNT{1'b1}};
        error_count       = 0;
        press_count_0     = 0;
        press_count_1     = 0;
        release_count_0   = 0;
        release_count_1   = 0;

        // 用例 1：复位时所有按键和事件输出都必须清零。
        wait_clock_cycles(3);
        check_value(button_down == 2'b00, "reset must clear button_down");
        check_value(button_press_pulse == 2'b00, "reset must clear press pulses");
        check_value(button_release_pulse == 2'b00, "reset must clear release pulses");
        @(negedge clk);
        rst_n = 1'b1;

        // 用例 2：多次短抖动不应被识别为按下。
        button_n_async[0] = 1'b0;
        wait_clock_cycles(3);
        button_n_async[0] = 1'b1;
        wait_clock_cycles(3);
        button_n_async[0] = 1'b0;
        wait_clock_cycles(2);
        button_n_async[0] = 1'b1;
        wait_clock_cycles(DEBOUNCE_CYCLES + 2);
        check_value(button_down[0] == 1'b0, "bounce must not change stable state");
        check_value(press_count_0 == 0, "bounce must not create press event");

        // 用例 3：新状态少一个去抖周期时不更新，到达边界时恰好更新。
        @(negedge clk);
        button_n_async[0] = 1'b0;
        wait_clock_cycles(2 + DEBOUNCE_CYCLES - 1);
        check_value(button_down[0] == 1'b0, "state changed before debounce boundary");
        check_value(button_press_pulse[0] == 1'b0, "press pulse appeared too early");
        wait_clock_cycles(1);
        check_value(button_down[0] == 1'b1, "stable press was not accepted at boundary");
        check_value(button_press_pulse[0] == 1'b1, "press pulse missing at boundary");
        wait_clock_cycles(1);
        check_value(button_press_pulse[0] == 1'b0, "press pulse lasted more than one cycle");

        // 用例 4：长按期间不得重复生成按下事件。
        wait_clock_cycles(DEBOUNCE_CYCLES * 2);
        check_value(button_down[0] == 1'b1, "long press must keep stable state");
        check_value(press_count_0 == 1, "long press created repeated press events");

        // 用例 5：释放边界与按下边界一致，只生成一个释放脉冲。
        @(negedge clk);
        button_n_async[0] = 1'b1;
        wait_clock_cycles(2 + DEBOUNCE_CYCLES - 1);
        check_value(button_down[0] == 1'b1, "release changed before debounce boundary");
        wait_clock_cycles(1);
        check_value(button_down[0] == 1'b0, "stable release was not accepted at boundary");
        check_value(button_release_pulse[0] == 1'b1, "release pulse missing at boundary");
        wait_clock_cycles(1);
        check_value(button_release_pulse[0] == 1'b0, "release pulse lasted more than one cycle");
        check_value(release_count_0 == 1, "release event count is incorrect");

        // 用例 6：第二路少于阈值的低电平毛刺必须被忽略。
        @(negedge clk);
        button_n_async[1] = 1'b0;
        wait_clock_cycles(DEBOUNCE_CYCLES - 1);
        @(negedge clk);
        button_n_async[1] = 1'b1;
        wait_clock_cycles(DEBOUNCE_CYCLES + 3);
        check_value(button_down[1] == 1'b0, "short glitch changed channel 1 state");
        check_value(press_count_1 == 0, "short glitch created channel 1 event");

        // 用例 7：两路同时按下时应独立完成去抖。
        @(negedge clk);
        button_n_async = 2'b00;
        wait_clock_cycles(2 + DEBOUNCE_CYCLES);
        check_value(button_down == 2'b11, "simultaneous press did not update both channels");
        check_value(button_press_pulse == 2'b11, "simultaneous press pulses are incorrect");
        wait_clock_cycles(1);
        check_value(button_press_pulse == 2'b00, "simultaneous press pulses lasted more than one cycle");
        check_value(press_count_0 == 2, "channel 0 simultaneous press count is incorrect");
        check_value(press_count_1 == 1, "channel 1 simultaneous press count is incorrect");

        // 用例 8：按键正在按下时进入复位，所有状态必须在下一上升沿清除。
        @(negedge clk);
        rst_n = 1'b0;
        wait_clock_cycles(1);
        check_value(button_down == 2'b00, "reset during press did not clear stable state");
        check_value(button_press_pulse == 2'b00, "reset during press did not clear press pulses");
        check_value(button_release_pulse == 2'b00, "reset during press did not clear release pulses");

        if (error_count == 0) begin
            $display("PASS: tb_button_debouncer completed all checks");
        end else begin
            $display("FAIL: tb_button_debouncer found %0d error(s)", error_count);
            $fatal(1);
        end

        $finish;
    end

endmodule
