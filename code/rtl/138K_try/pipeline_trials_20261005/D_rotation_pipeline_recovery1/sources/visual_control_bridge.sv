// M2 candidate ingress for the existing M3 video-domain control ports.
// This independent adapter does not freeze or modify the common event package.
// Both clocks share a reset assertion source including the video PLL lock.
// Source score/mode commands use valid/ready; a raw button pulse must first be
// retained by the producer until ready. Not connected to audio backpressure.
`timescale 1ns/1ps
module visual_control_bridge #(
    parameter integer FRAME_WIDTH = 32
) (
    input logic sys_clk, pixel_clk, rst_n,
    input logic src_mode_valid,
    output wire src_mode_ready,
    output wire video_mode_toggle_pulse,
    input logic src_score_valid,
    output wire src_score_ready,
    input logic [15:0] src_score_note_id,
    input logic [6:0] src_score_note_number,
    input logic [FRAME_WIDTH-1:0] src_score_hit_frame,
    input logic src_score_duration_valid,
    input logic [FRAME_WIDTH-1:0] src_score_duration_frames,
    input logic [9:0] src_score_velocity,
    output wire video_score_valid,
    input logic video_score_ready,
    output wire [15:0] video_score_note_id,
    output wire [6:0] video_score_note_number,
    output wire [FRAME_WIDTH-1:0] video_score_hit_frame,
    output wire video_score_duration_valid,
    output wire [FRAME_WIDTH-1:0] video_score_duration_frames,
    output wire [9:0] video_score_velocity,
    output wire sys_reset_done, video_reset_done
);
    localparam integer SCORE_WIDTH = 34 + 2*FRAME_WIDTH;
    wire [SCORE_WIDTH-1:0] src_payload, video_payload;
    wire mode_valid, mode_data;
    wire score_src_done, score_dst_done, mode_src_done, mode_dst_done;
    assign src_payload = {src_score_note_id, src_score_note_number,
        src_score_hit_frame, src_score_duration_valid,
        src_score_duration_frames, src_score_velocity};
    assign {video_score_note_id, video_score_note_number,
        video_score_hit_frame, video_score_duration_valid,
        video_score_duration_frames, video_score_velocity} = video_payload;
    visual_mailbox_cdc #(.WIDTH(SCORE_WIDTH)) u_score_mailbox (
        .src_clk(sys_clk), .dst_clk(pixel_clk), .rst_n(rst_n),
        .src_valid(src_score_valid), .src_ready(src_score_ready),
        .src_data(src_payload), .dst_valid(video_score_valid),
        .dst_ready(video_score_ready), .dst_data(video_payload),
        .src_reset_done(score_src_done), .dst_reset_done(score_dst_done)
    );
    visual_mailbox_cdc #(.WIDTH(1)) u_mode_mailbox (
        .src_clk(sys_clk), .dst_clk(pixel_clk), .rst_n(rst_n),
        .src_valid(src_mode_valid), .src_ready(src_mode_ready),
        .src_data(1'b1), .dst_valid(mode_valid),
        .dst_ready(1'b1), .dst_data(mode_data),
        .src_reset_done(mode_src_done), .dst_reset_done(mode_dst_done)
    );
    // Valid is a single destination cycle, since the consumer is always ready.
    assign video_mode_toggle_pulse = mode_valid && mode_dst_done;
    assign sys_reset_done = score_src_done && mode_src_done;
    assign video_reset_done = score_dst_done && mode_dst_done;
`ifndef SYNTHESIS
    initial if (FRAME_WIDTH < 1 || FRAME_WIDTH > 32)
        $fatal(1,"visual_control_bridge FRAME_WIDTH must be 1..32");
`endif
endmodule
