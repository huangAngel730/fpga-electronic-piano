// Source-logic snapshot read from commit 54774f1; comments are shortened.
// T004 DDS single-voice oscillator: 32-bit phase + 1024-point sine ROM.
`timescale 1ns/1ps

module dds_oscillator #(
    parameter ROM_FILE = "model/generated/wavetables/sine_1024_32767.mem"
) (
    input  logic        sys_clk,
    input  logic        sys_rst_n,
    input  logic        sample_tick,
    input  logic [31:0] fcw,
    output logic signed [15:0] wt_sample
);
    logic [31:0] phase_acc;
    logic [9:0] wt_addr;
    assign wt_addr = phase_acc[31:22];

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n)
            phase_acc <= 32'h0;
        else if (sample_tick)
            phase_acc <= phase_acc + fcw;
    end

    sine_wavetable_1024 #(.ROM_FILE(ROM_FILE)) u_sine_table (
        .clk(sys_clk), .addr(wt_addr), .dout(wt_sample)
    );
endmodule

module sine_wavetable_1024 #(
    parameter ROM_FILE = "model/generated/wavetables/sine_1024_32767.mem"
) (
    input  logic        clk,
    input  logic [9:0]  addr,
    output logic signed [15:0] dout
);
    logic signed [15:0] rom_data [0:1023];
    // synthesis translate_off
    string wavetable_path;
    integer rom_index;
    // synthesis translate_on

    initial begin
        // synthesis translate_off
        if ($value$plusargs("WAVETABLE_PATH=%s", wavetable_path)) begin
            $readmemh(wavetable_path, rom_data);
        end else begin
            wavetable_path = ROM_FILE;
        // synthesis translate_on
            $readmemh(ROM_FILE, rom_data);
        // synthesis translate_off
        end
        for (rom_index = 0; rom_index < 1024; rom_index = rom_index + 1)
            if (^rom_data[rom_index] === 1'bx)
                $fatal(1, "Uninitialized wavetable word %0d in %s",
                       rom_index, wavetable_path);
        $display("INFO: Loaded 1024 wavetable words from %s", wavetable_path);
        // synthesis translate_on
    end

    always_ff @(posedge clk)
        dout <= rom_data[addr];
endmodule

