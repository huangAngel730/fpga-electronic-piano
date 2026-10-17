// M2 candidate only. Sample exactly the sender's pre-NBA frame-load inputs.
// No ready, enable, or display control can feed back into the audio source.
`timescale 1ns/1ps
module pcm_frame_observer #(
    parameter [31:0] FIRST_SEQ = 32'd0
) (
    input wire audio_clk, audio_rst_n,
    input wire frame_load,
    input wire signed [23:0] play_left, play_right,
    output reg observed_valid,
    output reg [31:0] observed_seq,
    output reg signed [23:0] observed_left, observed_right
);
    reg [31:0] next_seq;
    always @(posedge audio_clk or negedge audio_rst_n) begin
        if (!audio_rst_n) begin
            observed_valid <= 1'b0;
            observed_seq <= FIRST_SEQ;
            observed_left <= 24'sd0;
            observed_right <= 24'sd0;
            next_seq <= FIRST_SEQ;
        end else begin
            observed_valid <= frame_load;
            if (frame_load) begin
                observed_seq <= next_seq;
                next_seq <= next_seq + 32'd1;
                observed_left <= play_left;
                observed_right <= play_right;
            end
        end
    end
endmodule
