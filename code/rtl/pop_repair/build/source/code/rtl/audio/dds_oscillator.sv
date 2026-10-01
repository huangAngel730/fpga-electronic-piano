// T004 DDS单声部振荡器
// 基于M1 Python模型: code/model/dds_model.py
// 32位相位累加 + 1024点波表查表
`timescale 1ns/1ps

module dds_oscillator #(
    parameter ROM_FILE = "model/generated/wavetables/sine_1024_32767.mem"
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


// 1024点正弦波表ROM
// 数据来源: code/model/generated/wavetables/sine_1024_32767.mem
module sine_wavetable_1024 #(
    parameter ROM_FILE = "model/generated/wavetables/sine_1024_32767.mem"
) (
    input  logic        clk,
    input  logic [9:0]  addr,
    output logic signed [15:0] dout
);

    // 1024点正弦波表ROM（同步读取）
    logic signed [15:0] rom_data [0:1023];
    // synthesis translate_off
    string wavetable_path;
    integer rom_index;
    // synthesis translate_on

    initial begin
        // Simulation can override the ROM path; synthesis sees a constant file.
        // synthesis translate_off
        if ($value$plusargs("WAVETABLE_PATH=%s", wavetable_path)) begin
            $readmemh(wavetable_path, rom_data);
        end else begin
            wavetable_path = ROM_FILE;
        // synthesis translate_on
            $readmemh(ROM_FILE, rom_data);
        // synthesis translate_off
        end
        for (rom_index = 0; rom_index < 1024; rom_index = rom_index + 1) begin
            if (^rom_data[rom_index] === 1'bx)
                $fatal(1, "Uninitialized wavetable word %0d in %s", rom_index, wavetable_path);
        end
        $display("INFO: Loaded 1024 wavetable words from %s", wavetable_path);
        // synthesis translate_on
    end

    // 同步读取（BSRAM特性）
    always_ff @(posedge clk) begin
        dout <= rom_data[addr];
    end

endmodule
