// Isolated four-voice M1 timbre/delay to the existing 138K frame contract.
// Async active-low reset assertion; release is synchronized by the board top.
// This is not the production top or a physical-timing admission.
module m2_fourvoice_timbre_delay_frame_core (
    input logic clk, rst_n, frame_tick,
    input logic event_valid,
    output wire event_ready,
    input logic [63:0] event_data,
    input logic config_valid,
    output wire config_ready,
    input logic config_enable,
    input logic [15:0] config_delay_samples,
    input logic [14:0] config_dry_gain, config_wet_gain, config_feedback,
    output wire signed [23:0] play_left, play_right,
    output wire pending_valid, commit_pulse,
    output wire [31:0] active_voice_count, clip_count, audio_underrun,
    output wire [31:0] audio_frame_count, pcm_request_count, pcm_commit_count,
    output wire [31:0] max_processing_cycles,
    output wire request_accept,
    output wire [31:0] request_id, committed_id,
    output wire signed [23:0] committed_left, committed_right,
    output wire committed_clip
);
    wire candidate_cancel, request_valid, request_ready;
    wire result_valid, result_ready, chain_calc_ready;
    wire [31:0] result_id;
    wire signed [23:0] result_left, result_right;
    wire clip_left, clip_right;
    wire dispatched_this_frame;
    assign request_ready = chain_calc_ready && !config_valid;
    assign request_accept = request_valid && request_ready;

    m1td_timbre_delay_chain u_chain (
        .clk(clk), .rst_n(rst_n), .event_valid(event_valid),
        .event_ready(event_ready), .event_data(event_data),
        .frame_tick(frame_tick), .sample_req(request_accept),
        .sample_req_id(request_id), .calc_ready(chain_calc_ready),
        .config_valid(config_valid), .config_ready(config_ready),
        .config_enable(config_enable), .config_delay_samples(config_delay_samples),
        .config_dry_gain(config_dry_gain), .config_wet_gain(config_wet_gain),
        .config_feedback(config_feedback),
        .result_valid(result_valid), .result_ready(result_ready),
        .result_id(result_id), .result_left(result_left),
        .result_right(result_right), .clipped_left(clip_left),
        .clipped_right(clip_right), .upstream_clipped_left(),
        .upstream_clipped_right(), .effect_clipped_left(),
        .effect_clipped_right(), .feedback_clipped_left(),
        .feedback_clipped_right(), .active_voice_count(active_voice_count)
    );

    premixed_frame_adapter u_frame_adapter (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick),
        .candidate_cancel(candidate_cancel),
        .candidate_sample_valid(request_valid),
        .candidate_sample_ready(request_ready),
        .candidate_sample_id(request_id),
        .candidate_result_valid(result_valid),
        .candidate_result_ready(result_ready),
        .candidate_result_id(result_id),
        .candidate_left(result_left), .candidate_right(result_right),
        .candidate_clipped(clip_left | clip_right),
        .play_left(play_left), .play_right(play_right),
        .pending_valid(pending_valid), .commit_pulse(commit_pulse),
        .frame_count(audio_frame_count),
        .frame_request_count(pcm_request_count),
        .commit_count(pcm_commit_count),
        .underrun_count(audio_underrun), .clip_count(clip_count),
        .current_id(), .committed_id(committed_id),
        .committed_left(committed_left),
        .committed_right(committed_right),
        .committed_clip(committed_clip),
        .dispatched_this_frame(dispatched_this_frame)
    );

    // One real request acceptance to one successful PCM commit; no DUT internals.
    wire [31:0] unused_overflow;
    system_status_counters u_latency (
        .clk(clk), .rst_n(rst_n), .pcm_request(request_accept),
        .pcm_commit(commit_pulse), .button_overflow(32'd0),
        .midi_overflow(32'd0), .event_fifo_overflow(unused_overflow),
        .max_processing_cycles(max_processing_cycles)
    );
endmodule