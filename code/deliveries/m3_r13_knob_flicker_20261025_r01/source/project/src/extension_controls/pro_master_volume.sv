`timescale 1ns/1ps
// R08: global gain, no ready output and no feedback into the audio producer.
// clk/rst_n are the audio domain, asynchronous active-low reset.
// The existing i2s_tx captures both outputs together at its full-frame tick.
// There is no PCM register here: even a result committed on the last legal
// cycle before that tick retains the original R07 frame/metadata association.
// Gain changes on that same edge take effect at the NEXT frame capture.
module pro_master_volume (
    input wire clk,
    input wire rst_n,
    input wire event_valid,
    input wire event_ready,
    input wire audio_defs_pkg::performance_event_t event_data,
    input wire signed [23:0] pcm_in_left,
    input wire signed [23:0] pcm_in_right,
    output wire signed [23:0] pcm_out_left,
    output wire signed [23:0] pcm_out_right,
    output logic [11:0] volume_value
);
    import audio_defs_pkg::*;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) volume_value <= 12'hfff;
        else if (event_valid && event_ready &&
                 event_data.event_type == EVENT_CONTROL_CHANGE &&
                 event_data.control_id == CTRL_VOLUME)
            volume_value <= event_data.control_value;
    end

    // Unsigned Q0.12 gain: 0 is mute; 4095 is promoted to 4096 for exact
    // unity. Other values retain the shared midi_cc_to_12bit mapping / 4096.
    wire signed [13:0] gain = volume_value == 12'hfff ?
        14'sd4096 : $signed({2'b00, volume_value});
    // Keep multiplication separate from rounding. The former expression
    // sign-extended P + (sign ? 2047 : 2048) encouraged a DSP post-adder /
    // CSHIFT packing path that failed in Gowin V1.9.12.04 (SP00019).
    wire signed [37:0] product_left = pcm_in_left * gain;
    wire signed [37:0] product_right = pcm_in_right * gain;
    function automatic logic signed [23:0] round_product(
        input logic signed [37:0] product
    );
        logic increment;
        logic signed [23:0] quotient;
        begin
            // P = 4096*floor(P/4096) + remainder, remainder=unsigned P[11:0].
            // Positive: increment iff remainder>=2048; negative: iff >2048.
            // A negative exact half therefore keeps floor (away from zero).
            increment = product[11] && (!product[37] || (|product[10:0]));
            quotient = $signed(product[35:12]);
            // gain <= 1 ensures the rounded result fits signed 24 bits,
            // including -8388608 at unity. P[37:36] are sign extension.
            round_product = quotient + $signed({23'd0, increment});
        end
    endfunction
    assign pcm_out_left = round_product(product_left);
    assign pcm_out_right = round_product(product_right);
endmodule
