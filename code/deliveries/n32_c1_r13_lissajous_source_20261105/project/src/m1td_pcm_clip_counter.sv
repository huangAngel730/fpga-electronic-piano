// T025: count only stereo samples actually committed into the PCM frame buffer.
// Same sys_clk domain as PCM valid/ready; rst_n asserts low asynchronously and
// must be released synchronously upstream. clip_any belongs to the SAME
// request generation and held sample as pcm_valid; a late/discarded result
// never handshakes. One accepted stereo sample contributes at most one clip.
`timescale 1ns/1ps
module m1td_pcm_clip_counter #(
    parameter integer COUNTER_WIDTH = 32
) (
    input  logic clk,
    input  logic rst_n,
    input  logic pcm_valid,
    input  logic pcm_ready,
    input  logic clip_any,
    output logic [COUNTER_WIDTH-1:0] clip_count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) clip_count <= '0;
        else if (pcm_valid && pcm_ready && clip_any && !(&clip_count))
            clip_count <= clip_count + 1'b1;
    end
`ifndef SYNTHESIS
    initial if (COUNTER_WIDTH < 1 || COUNTER_WIDTH > 32)
        $fatal(1, "COUNTER_WIDTH must be 1..32");
`endif
endmodule
