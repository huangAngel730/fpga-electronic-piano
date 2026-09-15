// 两级同步器与按键去抖器。
// 物理按键低电平表示按下，输出统一转换为高电平表示按下。
module button_debouncer #(
    parameter integer BUTTON_COUNT      = 2,
    parameter integer CLK_FREQ_HZ       = 50_000_000,
    parameter integer DEBOUNCE_TIME_MS  = 20
) (
    input  logic [BUTTON_COUNT-1:0] button_n_async,
    input  logic                    clk,
    input  logic                    rst_n,
    output logic [BUTTON_COUNT-1:0] button_down,
    output logic [BUTTON_COUNT-1:0] button_press_pulse,
    output logic [BUTTON_COUNT-1:0] button_release_pulse
);

    // 采用向上取整，保证实际去抖时间不短于设定值。
    // 先做除法再相乘，降低 32 位 integer 中间结果溢出的风险。
    localparam integer DEBOUNCE_CYCLES_CALC =
        ((CLK_FREQ_HZ / 1000) * DEBOUNCE_TIME_MS) +
        ((((CLK_FREQ_HZ % 1000) * DEBOUNCE_TIME_MS) + 999) / 1000);
    localparam integer DEBOUNCE_CYCLES =
        (DEBOUNCE_CYCLES_CALC < 1) ? 1 : DEBOUNCE_CYCLES_CALC;
    localparam integer COUNTER_WIDTH =
        (DEBOUNCE_CYCLES <= 1) ? 1 : $clog2(DEBOUNCE_CYCLES);
    localparam logic [COUNTER_WIDTH-1:0] DEBOUNCE_LIMIT =
        DEBOUNCE_CYCLES - 1;

    // 异步机械按键先经两级触发器，减少亚稳态传入后续逻辑的风险。
    (* ASYNC_REG = "TRUE" *) logic [BUTTON_COUNT-1:0] button_sync_ff1;
    (* ASYNC_REG = "TRUE" *) logic [BUTTON_COUNT-1:0] button_sync_ff2;

    logic [COUNTER_WIDTH-1:0] debounce_counter [0:BUTTON_COUNT-1];
    integer                   button_index;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            // 复位后按键默认为未按下，不产生伪事件。
            button_sync_ff1    <= {BUTTON_COUNT{1'b1}};
            button_sync_ff2    <= {BUTTON_COUNT{1'b1}};
            button_down        <= {BUTTON_COUNT{1'b0}};
            button_press_pulse <= {BUTTON_COUNT{1'b0}};
            button_release_pulse <= {BUTTON_COUNT{1'b0}};

            for (button_index = 0; button_index < BUTTON_COUNT; button_index = button_index + 1) begin
                debounce_counter[button_index] <= {COUNTER_WIDTH{1'b0}};
            end
        end else begin
            button_sync_ff1 <= button_n_async;
            button_sync_ff2 <= button_sync_ff1;

            for (button_index = 0; button_index < BUTTON_COUNT; button_index = button_index + 1) begin
                // 事件默认只保持一个时钟周期。
                button_press_pulse[button_index]   <= 1'b0;
                button_release_pulse[button_index] <= 1'b0;

                if ((~button_sync_ff2[button_index]) == button_down[button_index]) begin
                    // 采样值回到已确认状态，说明还在抖动，重新计时。
                    debounce_counter[button_index] <= {COUNTER_WIDTH{1'b0}};
                end else if (debounce_counter[button_index] == DEBOUNCE_LIMIT) begin
                    // 新状态持续足够久，才真正更新输出。
                    debounce_counter[button_index] <= {COUNTER_WIDTH{1'b0}};
                    button_down[button_index]      <= ~button_sync_ff2[button_index];

                    if (!button_sync_ff2[button_index]) begin
                        button_press_pulse[button_index] <= 1'b1;
                    end else begin
                        button_release_pulse[button_index] <= 1'b1;
                    end
                end else begin
                    debounce_counter[button_index] <= debounce_counter[button_index] + 1'b1;
                end
            end
        end
    end

endmodule
