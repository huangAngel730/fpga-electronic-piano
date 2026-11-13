// Private wave adapter: Program0 preserves external Piano V1, Program1 Organ.
// Both DDS paths advance on every sample_tick. Envelopes belong to the bank.
// rst_n is asynchronous active-low; release is synchronized upstream.
// Organ request E -> DDS E+3 -> hold E+4 -> bank samples pre-NBA E+5.
// Lane requests are separated by >=7 clocks; timbre ownership must be stable
// through the bank snapshot. The adapter makes no arbitrary-rate mux promise.
`timescale 1ns/1ps

module piano_organ_voice #(
    parameter PIANO_ROM_FILE = "model/generated/wavetables/piano_band_4x256_8191.mem",
    parameter ORGAN_ROM_FILE = "organ_band_4x256_8191.mem",
    parameter bit PRIVATE_M1TD_PIANO = 1'b0
) (
    input  logic               clk,
    input  logic               rst_n,
    input  logic               sample_tick,
    input  logic               note_on,
    input  logic               note_off,
    input  logic               timbre_organ,
    input  logic [9:0]         velocity,
    input  logic [31:0]        fcw,
    output logic signed [15:0] wt_sample
);
    wire signed [15:0] piano_wave;
    wire signed [15:0] organ_wave;
    wire organ_valid;
    logic signed [15:0] organ_hold;
    logic signed [15:0] piano_delay [0:2];

    // These are external, original dependencies. This delivery copies neither
    // module and does not alter the selected Piano oscillator's input wiring.
    generate
        if (PRIVATE_M1TD_PIANO) begin : g_m1td_piano
            m1td_piano_dds_oscillator #(.ROM_FILE(PIANO_ROM_FILE)) u_piano (
                .sys_clk(clk), .sys_rst_n(rst_n), .sample_tick(sample_tick),
                .note_on(note_on), .velocity(velocity), .fcw(fcw), .wt_sample(piano_wave)
            );
        end else begin : g_original_piano
            piano_dds_oscillator #(.ROM_FILE(PIANO_ROM_FILE)) u_piano (
                .sys_clk(clk), .sys_rst_n(rst_n), .sample_tick(sample_tick),
                .note_on(note_on), .velocity(velocity), .fcw(fcw), .wt_sample(piano_wave)
            );
        end
    endgenerate

    organ_dds_oscillator #(.ROM_FILE(ORGAN_ROM_FILE)) u_organ (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick), .fcw(fcw),
        .note_on(note_on), .note_off(note_off),
        .sample_out(organ_wave), .sample_valid(organ_valid)
    );

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            organ_hold <= '0;
            piano_delay[0] <= '0;
            piano_delay[1] <= '0;
            piano_delay[2] <= '0;
        end else begin
            if (organ_valid) organ_hold <= organ_wave;
            piano_delay[0] <= piano_wave;
            piano_delay[1] <= piano_delay[0];
            piano_delay[2] <= piano_delay[1];
        end
    end
    always_comb wt_sample = timbre_organ ? organ_hold : piano_delay[2];
endmodule
