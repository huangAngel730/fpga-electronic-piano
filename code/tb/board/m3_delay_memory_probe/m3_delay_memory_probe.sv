// I isolated synthesis-only probe. All data/parameters/output stay live.
// No extra clock/register/reset/RAM changes. DEPTH replaced only in scratch.
module m3_delay_memory_probe #(
    parameter integer DEPTH = 1024
) (
    input wire sys_clk, sys_rst_n, sample_enable,
    input wire signed [23:0] pcm_in,
    input wire [15:0] delay_samples,
    input wire [14:0] dry_gain, wet_gain, feedback,
    output wire signed [23:0] pcm_out,
    output wire pcm_valid
);
    delay_effect #(.DEPTH(DEPTH)) effect (
        .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.sample_enable(sample_enable),
        .pcm_in(pcm_in),.delay_samples(delay_samples),.dry_gain(dry_gain),
        .wet_gain(wet_gain),.feedback(feedback),.pcm_out(pcm_out),.pcm_valid(pcm_valid)
    );
endmodule
