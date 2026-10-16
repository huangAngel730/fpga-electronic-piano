// T027 private lane adapter: Program 0 keeps the approved Piano V1 sound;
// Program 1 uses M1's triangle ROM/oscillator. Both DDS phases advance once
// per sample_tick. An extra three registers align Piano V1 with T027 E+3.
// No external clock or reset: rst_n is active low, released upstream.
`timescale 1ns/1ps
module m1td_piano_triangle_voice #(
    parameter PIANO_ROM_FILE = "rom/piano_band_4x256_8191.mem",
    parameter SINE_ROM_FILE = "rom/sine_wavetable.hex",
    parameter TRIANGLE_ROM_FILE = "rom/triangle_wavetable.hex"
) (
    input logic clk, rst_n, sample_tick, note_on, note_off, timbre_triangle,
    input logic [9:0] velocity,
    input logic [31:0] fcw,
    output logic signed [15:0] wt_sample
);
    wire signed [15:0] piano_wave, triangle_wave;
    wire triangle_valid;
    logic signed [15:0] triangle_hold;
    logic signed [15:0] piano_delay [0:2];
    m1td_piano_dds_oscillator #(.ROM_FILE(PIANO_ROM_FILE)) u_piano (
        .sys_clk(clk), .sys_rst_n(rst_n), .sample_tick(sample_tick),
        .note_on(note_on), .velocity(velocity), .fcw(fcw), .wt_sample(piano_wave)
    );
    // M1's oscillator owns the triangle ROM and phase policy. Its sine ROM
    // is unused here and is removed by synthesis when timbre_select=1.
    m1td_timbre_oscillator #(.SINE_ROM_FILE(SINE_ROM_FILE),
        .TRIANGLE_ROM_FILE(TRIANGLE_ROM_FILE)) u_triangle (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick), .fcw(fcw),
        .timbre_select(1'b1), .note_on(note_on), .note_off(note_off),
        .sample_out(triangle_wave), .sample_valid(triangle_valid)
    );
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            triangle_hold <= '0;
            piano_delay[0] <= '0;
            piano_delay[1] <= '0;
            piano_delay[2] <= '0;
        end else begin
            if (triangle_valid) triangle_hold <= triangle_wave;
            piano_delay[0] <= piano_wave;
            piano_delay[1] <= piano_delay[0];
            piano_delay[2] <= piano_delay[1];
        end
    end
    always_comb wt_sample = timbre_triangle ? triangle_hold : piano_delay[2];
endmodule
