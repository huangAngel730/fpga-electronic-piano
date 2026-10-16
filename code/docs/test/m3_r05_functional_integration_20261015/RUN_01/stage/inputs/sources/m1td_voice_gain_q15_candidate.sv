// M2 isolated implementation of M1's proposed DDS*ADSR floor-Q15 rule.
// This does not amend D028 or scale the 32767 DDS ROM to an 8192 waveform.
// Caller supplies a signed waveform already scaled to its approved amplitude.
// product is signed 33-bit: signed16 sample times unsigned16 envelope,
// zero-extended to signed17. Arithmetic shift is floor toward -infinity.
module m1td_voice_gain_q15_candidate (
    input wire signed [15:0] wave_sample,
    input wire [15:0] envelope,
    output wire signed [15:0] sample_out,
    output wire signed [23:0] pcm_out
);
    wire signed [16:0] positive_gain = $signed({1'b0,envelope});
    wire signed [32:0] product = wave_sample * positive_gain;
    wire signed [32:0] scaled = product >>> 15;
    assign sample_out = scaled[15:0];
    assign pcm_out = {sample_out,8'b0};
    // Contract envelope <= 32767 guarantees sample_out fits signed16.
endmodule