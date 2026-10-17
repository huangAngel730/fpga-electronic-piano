// Isolated M2 downstream transport; no sound math or production connection.
// Audio40MHz/pixel25MHz. Async reset assertion, release policy supplied upstream.
module m2_n32_output_transport #(
    parameter [31:0] BCLK_STEP=32'd659706977,
    parameter integer OBS_DEPTH=32
) (
    input wire clk,pixel_clk,rst_n,display_rst_n,
    output wire candidate_cancel,candidate_sample_valid,
    input wire candidate_sample_ready,
    output wire [31:0] candidate_sample_id,
    input wire candidate_result_valid,
    output wire candidate_result_ready,
    input wire [31:0] candidate_result_id,
    input wire signed [23:0] candidate_left,candidate_right,
    input wire candidate_clipped,
    output wire signed [23:0] play_left,play_right,
    output wire bclk,lrck,din,frame_tick,commit_pulse,
    output wire [31:0] frame_count,frame_request_count,commit_count,underrun_count,clip_count,
    output wire [31:0] committed_id,
    output wire signed [23:0] committed_left,committed_right,
    output wire committed_clip,observed_valid,
    output wire [31:0] observed_seq,
    output wire signed [23:0] observed_left,observed_right,
    output wire waveform_rst_n,stream_restart,sample_valid,
    output wire [31:0] sample_seq,
    output wire signed [23:0] sample_left,sample_right,
    output wire [31:0] observation_drop_count
);
    wire signed [23:0] left_transport;
`ifdef M2_OUTPUT_BAD_LEFT
    assign left_transport=24'sd0;
`else
    assign left_transport=candidate_left;
`endif
    wire clip_transport;
`ifdef M2_OUTPUT_BAD_CLIP
    assign clip_transport=1'b0;
`else
    assign clip_transport=candidate_clipped;
`endif
    premixed_frame_adapter adapter (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),
        .candidate_cancel(candidate_cancel),.candidate_sample_valid(candidate_sample_valid),
        .candidate_sample_ready(candidate_sample_ready),.candidate_sample_id(candidate_sample_id),
        .candidate_result_valid(candidate_result_valid),.candidate_result_ready(candidate_result_ready),
        .candidate_result_id(candidate_result_id),.candidate_left(left_transport),
        .candidate_right(candidate_right),.candidate_clipped(clip_transport),
        .play_left(play_left),.play_right(play_right),.commit_pulse(commit_pulse),
        .frame_count(frame_count),.frame_request_count(frame_request_count),
        .commit_count(commit_count),.underrun_count(underrun_count),.clip_count(clip_count),
        .committed_id(committed_id),.committed_left(committed_left),
        .committed_right(committed_right),.committed_clip(committed_clip)
    );
    i2s_tx #(.ACC_BITS(32),.BCLK_PHASE_STEP(BCLK_STEP),.PCM_WIDTH(24),.DAC_WIDTH(16)) sender (
        .clk(clk),.rst_n(rst_n),.valid(1'b1),.pcm_left(play_left),.pcm_right(play_right),
        .bclk(bclk),.lrck(lrck),.din(din),.frame_tick(frame_tick)
    );
    pcm_waveform_observer_bridge #(.DEPTH(OBS_DEPTH)) observer (
        .audio_clk(clk),.pixel_clk(pixel_clk),.audio_rst_n(rst_n),.display_rst_n(display_rst_n),
        .audio_frame_load(frame_tick),.audio_play_left(play_left),.audio_play_right(play_right),
        .waveform_rst_n(waveform_rst_n),.stream_restart(stream_restart),
        .sample_valid(sample_valid),.sample_seq(sample_seq),.sample_left(sample_left),.sample_right(sample_right),
        .observed_valid(observed_valid),.observed_seq(observed_seq),
        .observed_left(observed_left),.observed_right(observed_right),.observation_drop_count(observation_drop_count)
    );
endmodule
