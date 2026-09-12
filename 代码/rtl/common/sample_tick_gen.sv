// -----------------------------------------------------------------------------
// sample_tick_gen.sv
// 48 kHz 采样节拍发生器。对应任务 T019，接口规范 v1.0 第 2.3 节。
//
// 原理（相位累加）：
//   每个 sys_clk 周期累加 PHASE_STEP，累加器溢出时产生一个 sample_tick。
//   长期平均频率 = PHASE_STEP * FCLK / 2^ACC_BITS
//
// 为什么用相位累加而不是计数器分频：
//   当 FCLK 可被 48 kHz 整除时（例如 98.304 MHz），
//   PHASE_STEP 恰好是 2 的整数次幂，累加器退化为整数分频器，
//   无量化误差、无间隔抖动。
//   当 FCLK 不能整除时（例如 50 MHz），仍能得到最接近的长期平均频率，
//   无需为换频率改写 RTL。
//   分析见 代码/scripts/analyze_clock_plan.py。
//
// 重要：sample_tick 是时钟使能，不是时钟。禁止用它驱动 always_ff 的时钟沿
//       （接口规范 2.1 节）。
// -----------------------------------------------------------------------------

`ifndef SAMPLE_TICK_GEN_SV
`define SAMPLE_TICK_GEN_SV

`timescale 1ns / 1ps

module sample_tick_gen #(
    // 相位累加器位宽
    parameter int unsigned ACC_BITS = 32,
    // 每个 sys_clk 周期的相位步进，由顶层按实际频率计算后传入。
    // 默认值对应本板 50 MHz 晶振、48 kHz 采样率：
    //   round(2^32 * 48000 / 50000000) = 4123169 = 0x003EEA21
    //   实际平均采样率 48000.004608 Hz，误差 +0.0960 ppm
    // 该值必须与 audio_defs_pkg::BOARD_TICK_PHASE_STEP 一致，
    // 顶层例化时应显式传入，不要依赖默认值。
    parameter logic [ACC_BITS-1:0] PHASE_STEP = 32'd4_123_169
) (
    input  logic                    clk,        // sys_clk
    input  logic                    rst_n,      // 本域同步后的复位，低有效
    output logic                    sample_tick // 单周期脉冲
);

    // 相位累加器。位宽大于 32 时保持可扩展。
    logic [ACC_BITS-1:0] phase_acc;

    // 累加器溢出条件：当前值加步进后产生进位。
    // 用扩展位判断进位，避免依赖截断行为。
    logic [ACC_BITS:0] phase_sum;
    assign phase_sum = {1'b0, phase_acc} + {1'b0, PHASE_STEP};

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase_acc   <= '0;
            sample_tick <= 1'b0;
        end else begin
            phase_acc   <= phase_sum[ACC_BITS-1:0];
            sample_tick <= phase_sum[ACC_BITS];  // 进位即为 tick
        end
    end

endmodule

`endif  // SAMPLE_TICK_GEN_SV
