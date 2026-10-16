// -----------------------------------------------------------------------------
// button_debouncer.sv
// 两级同步器与按键去抖器。对应任务 T021（M3，rtl/input/）。
//
// 作者：M3（YunZhongDuShu），提交 e54e1fc "button_debouncer"。
// 本文件由 M2 在目录重命名（代码/ -> code/）时迁入新结构，并完成与集成骨架的
// 接线替换。**实现体未做任何改动**，仅补充本说明头与迁移记录。
//
// -----------------------------------------------------------------------------
// 迁移记录（M2，方案 A）
// -----------------------------------------------------------------------------
//   原路径：代码/rtl/input/button_debouncer.sv
//   新路径：code/rtl/input/button_debouncer/button_debouncer.sv
//
//   （原为 code/rtl/input/button_debouncer.sv。2026-09-15 M2 采纳 M3 建议的
//     "rtl/input/ 每模块一子目录"布局，本文件与其 README 一并下移到同名
//     子目录内，源码内容仍逐字保留。）
//
//   本模块替换了 M2 在 T020 集成骨架中写的占位实现
//   code/rtl/common/key_debounce.sv。替换理由：M3 的实现在工程规范上更完备——
//     1. 去抖时间按毫秒参数化（CLK_FREQ_HZ + DEBOUNCE_TIME_MS），
//        比直接给周期数可读，换时钟频率时不必手算；
//     2. 两级同步器显式标注 (* ASYNC_REG = "TRUE" *)，亚稳态处理对工具可见；
//     3. 门限计算先除后乘，避免 32 位 integer 中间结果溢出。
//
//   两者功能语义一致，均为"低有效输入 -> 高有效按下 + 单周期跳变脉冲"。
//   接口名不同（本模块统一带 button_ 前缀），顶层已按本模块接口接线。
//
// -----------------------------------------------------------------------------
// 电平时序
// -----------------------------------------------------------------------------
//   物理按键**低有效**：按下接地 = 0，松开上拉 = 1。
//   输出统一转换为**高有效**：button_down = 1 表示按下。
//   CST 中必须配置 PULL_MODE=UP，否则悬空会乱跳。
//
// -----------------------------------------------------------------------------
// 复位
// -----------------------------------------------------------------------------
//   同步复位、低有效。顶层传入的是 reset_sync 产生的 rst_sync_n，
//   它已完成异步复位、同步释放，因此此处用同步复位正确且时序更友好。
//   复位后 button_down = 0（未按下），且不产生任何跳变脉冲。
// -----------------------------------------------------------------------------

`ifndef BUTTON_DEBOUNCER_SV
`define BUTTON_DEBOUNCER_SV

`timescale 1ns / 1ps

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

`endif // BUTTON_DEBOUNCER_SV
