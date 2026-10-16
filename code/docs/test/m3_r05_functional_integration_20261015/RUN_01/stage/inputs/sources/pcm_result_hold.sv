// T025/T055: register one result generation, stereo PCM and clip flag.
// sys_clk domain; rst_n async assertion, synchronous release by caller.
// Producer holds valid/data until ready; expires old result on next frame.
`timescale 1ns/1ps
module pcm_result_hold #(
    parameter integer PCM_WIDTH = 24,
    parameter integer ID_WIDTH = 32
) (
    input  logic                        clk,
    input  logic                        rst_n,
    input  logic                        frame_tick,
    input  logic                        calc_ready,
    input  logic [ID_WIDTH-1:0]         current_req_id,
    input  logic                        result_valid,
    output logic                        result_ready,
    input  logic [ID_WIDTH-1:0]         result_req_id,
    input  logic signed [PCM_WIDTH-1:0] result_left,
    input  logic signed [PCM_WIDTH-1:0] result_right,
    input  logic                        result_clip_any,
    output logic                        pcm_valid,
    input  logic                        pcm_ready,
    output logic [ID_WIDTH-1:0]         pcm_req_id,
    output logic signed [PCM_WIDTH-1:0] pcm_left,
    output logic signed [PCM_WIDTH-1:0] pcm_right,
    output logic                        pcm_clip_any
);
    logic request_window;
    // On a frame edge, frame_buffer uses calc_ready to accept a new request;
    // capture at most one result for that generation. A stale or duplicate
    // result has ready=0 and the producer must cancel it at its frame edge.
    assign result_ready = rst_n && request_window && !frame_tick &&
                          !pcm_valid && result_req_id == current_req_id;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            request_window <= 1'b0;
            pcm_valid <= 1'b0;
            pcm_req_id <= '0;
            pcm_left <= '0;
            pcm_right <= '0;
            pcm_clip_any <= 1'b0;
        end else if (frame_tick) begin
            // Same-edge arrival cannot rescue an expired result.
            request_window <= calc_ready;
            pcm_valid <= 1'b0;
            pcm_clip_any <= 1'b0;
        end else if (pcm_valid && pcm_ready) begin
            pcm_valid <= 1'b0;
            pcm_clip_any <= 1'b0;
        end else if (result_valid && result_ready) begin
            request_window <= 1'b0;
            pcm_valid <= 1'b1;
            pcm_req_id <= result_req_id;
            pcm_left <= result_left;
            pcm_right <= result_right;
            pcm_clip_any <= result_clip_any;
        end
    end
`ifndef SYNTHESIS
    initial if (PCM_WIDTH < 2 || ID_WIDTH < 1)
        $fatal(1, "Invalid PCM/ID width");
`endif
endmodule
