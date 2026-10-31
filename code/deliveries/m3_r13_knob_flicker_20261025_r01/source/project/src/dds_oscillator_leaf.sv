// T004 DDS单声部振荡器
// 基于M1 Python模型: code/model/dds_model.py
// 32位相位累加 + 1024点波表查表
`timescale 1ns/1ps

module dds_oscillator #(
    parameter ROM_FILE = "rom/sine_1024_32767.mem"
) (
    input  logic        sys_clk,        // 系统时钟 (50 MHz)
    input  logic        sys_rst_n,      // 系统复位，低有效
    input  logic        sample_tick,    // 采样时钟使能 (48 kHz)
    input  logic [31:0] fcw,            // 频率控制字 (Frequency Control Word)
    output logic signed [15:0] wt_sample  // 波表输出 (16位有符号)
);

    // 32位相位累加器
    logic [31:0] phase_acc;

    // 波表地址：取相位高10位
    logic [9:0] wt_addr;
    assign wt_addr = phase_acc[31:22];

    // 相位累加逻辑
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            phase_acc <= 32'h0;
        end else if (sample_tick) begin
            // 32位加法自然回绕，无需显式取模
            phase_acc <= phase_acc + fcw;
        end
    end

    // 波表ROM实例化
    sine_wavetable_1024 #(.ROM_FILE(ROM_FILE)) u_sine_table (
        .clk(sys_clk),
        .addr(wt_addr),
        .dout(wt_sample)
    );

endmodule
