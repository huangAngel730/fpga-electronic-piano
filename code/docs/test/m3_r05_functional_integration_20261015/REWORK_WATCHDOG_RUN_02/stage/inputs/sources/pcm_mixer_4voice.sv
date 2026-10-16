// T023 four-voice, two-channel PCM mixer core (M2 implementing M1 model).
// The input slice [24*i +: 24] is voice i, i=0..3, signed PCM24.
// Combinational/stateless: no clock, no reset, no sample-time advancement.
// clip_any is a *per-result* flag. Count it ONLY on a successful PCM commit.
// Mathematical authority: code/model/mixer.py; frozen width: >=32-bit sum.
`timescale 1ns/1ps
module pcm_mixer_4voice (
    input  logic [95:0] voices_left,
    input  logic [95:0] voices_right,
    output logic signed [23:0] mixed_left,
    output logic signed [23:0] mixed_right,
    output logic clip_left,
    output logic clip_right,
    output logic clip_any
);
    localparam logic signed [31:0] PCM_MAX_32 = 32'sd8388607;
    localparam logic signed [31:0] PCM_MIN_32 = -32'sd8388608;
    logic signed [31:0] sum_left, sum_right;
    logic signed [23:0] left_word, right_word;
    integer i;

    always @* begin
        sum_left = 32'sd0;
        sum_right = 32'sd0;
        left_word = 24'sd0;
        right_word = 24'sd0;
        for (i = 0; i < 4; i = i + 1) begin
            left_word = $signed(voices_left[24*i +: 24]);
            right_word = $signed(voices_right[24*i +: 24]);
            sum_left = sum_left + {{8{left_word[23]}}, left_word};
            sum_right = sum_right + {{8{right_word[23]}}, right_word};
        end
        clip_left = 1'b0;
        clip_right = 1'b0;
        mixed_left = 24'sd0;
        mixed_right = 24'sd0;
        if (sum_left > PCM_MAX_32) begin
            mixed_left = 24'sh7fffff;
            clip_left = 1'b1;
        end else if (sum_left < PCM_MIN_32) begin
            mixed_left = 24'sh800000;
            clip_left = 1'b1;
        end else mixed_left = sum_left[23:0];
        if (sum_right > PCM_MAX_32) begin
            mixed_right = 24'sh7fffff;
            clip_right = 1'b1;
        end else if (sum_right < PCM_MIN_32) begin
            mixed_right = 24'sh800000;
            clip_right = 1'b1;
        end else mixed_right = sum_right[23:0];
        clip_any = clip_left | clip_right;
    end
endmodule
