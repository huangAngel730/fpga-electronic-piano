// R06 isolated observation successor. M1 chain and PCM math remain frozen.
// Isolated four-voice M1 timbre/delay to the existing 138K frame contract.
// Async active-low reset assertion; release is synchronized by the board top.
// This is not the production top or a physical-timing admission.
module m2_fourvoice_timbre_delay_frame_core_r06c9 (
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
    output wire committed_clip,
    output wire obs_req_valid,
    output wire obs_req_ready,
    output wire obs_result_valid,
    output wire obs_result_ready,
    output wire [31:0] obs_result_id,
    output wire signed [23:0] obs_result_left,
    output wire signed [23:0] obs_result_right,
    output wire [1:0] obs_result_clip_mask,
    output wire obs_cancel,
    output wire [1:0] obs_raw_cancel_reason,
    output wire obs_tx_sample_valid,
    output wire obs_tx_metadata_valid,
    output wire obs_tx_req_id_valid,
    output wire [31:0] obs_tx_frame_id,
    output wire [31:0] obs_tx_req_id,
    output wire [1:0] obs_tx_clip_mask,
    output wire obs_tx_clip_any,
    output wire obs_tx_hold,
    output wire obs_tx_startup_zero,
    output wire obs_metadata_error,
    output wire obs_frame_id_overflow
    // BEGIN M2_C9_PORTS
    ,output wire obs_apply_valid,
    output wire [63:0] obs_apply_data,
    output wire [3:0] obs_occupied_mask,
    output wire [3:0] obs_releasing_mask,
    output wire [3:0] obs_note_on_mask,
    output wire [3:0] obs_note_off_mask,
    output wire [3:0] obs_retire_mask,
    output wire [15:0] obs_slot_sources,
    output wire [15:0] obs_slot_channels,
    output wire [31:0] obs_slot_notes,
    output wire [127:0] obs_slot_generations,
    output wire [3:0] obs_advance_mask,
    output wire [31:0] obs_advance_frame_req_id,
    output wire obs_effect_input_valid,
    output wire obs_effect_input_ready,
    output wire [31:0] obs_effect_input_id,
    output wire signed [23:0] obs_effect_input_left,
    output wire signed [23:0] obs_effect_input_right,
    output wire [1:0] obs_effect_input_clip_mask,
    output wire [3:0] obs_apply_kind,
    output wire [3:0] obs_apply_mask,
    output wire [31:0] obs_router_apply_seq,
    output wire obs_router_apply_seq_valid,
    output wire obs_config_take,
    output wire [61:0] obs_config_payload,
    output wire [1:0] obs_upstream_clip_mask,
    output wire [1:0] obs_effect_clip_mask,
    output wire [1:0] obs_feedback_clip_mask
    // END M2_C9_PORTS
    // BEGIN R10_LIFECYCLE_DIAG_PORTS
    ,output wire [3:0] diag_key_down, diag_deferred, diag_sustain_releasing, diag_bank_phase
    ,output wire [11:0] diag_adsr_states
    // END R10_LIFECYCLE_DIAG_PORTS
);
    wire candidate_cancel, request_valid, request_ready;
    wire result_valid, result_ready, chain_calc_ready;
    wire [31:0] result_id;
    wire signed [23:0] result_left, result_right;
    wire clip_left, clip_right;
    wire dispatched_this_frame;
    assign request_ready = chain_calc_ready && !config_valid;
    assign request_accept = request_valid && request_ready;

    // Explicit diagnostics. Capture on clk posedge PRE_NBA; never infer A from FRAME F.
    assign obs_req_valid = request_valid;
    assign obs_req_ready = request_ready;
    assign obs_result_valid = result_valid;
    assign obs_result_ready = result_ready;
    assign obs_result_id = result_id;
    assign obs_result_left = result_left;
    assign obs_result_right = result_right;
    assign obs_result_clip_mask = {clip_right, clip_left};
    // Raw frame-window cancel; an observer must not invent a transaction CANCEL.
    assign obs_cancel = candidate_cancel;

    // Raw control cause only: 00=NONE, 01=FRAME_BOUNDARY, 10/11 reserved.
    // Qualification by public rst_n/epoch belongs to the capture contract.
    // This does not declare an outstanding transaction legally cancelled.
    m2_r06_raw_cancel_reason u_raw_cancel_reason (
        .raw_cancel(candidate_cancel), .raw_reason(obs_raw_cancel_reason)
    );

    m1td_timbre_delay_chain u_chain (
        // BEGIN R10_LIFECYCLE_DIAG_CONNECTIONS
        .diag_key_down(diag_key_down),
        .diag_deferred(diag_deferred),
        .diag_sustain_releasing(diag_sustain_releasing),
        .diag_bank_phase(diag_bank_phase),
        .diag_adsr_states(diag_adsr_states),
        // END R10_LIFECYCLE_DIAG_CONNECTIONS

    // BEGIN M2_C9_CHAIN
    .obs_apply_valid(obs_apply_valid),
    .obs_apply_data(obs_apply_data),
    .obs_slot_occupied(obs_occupied_mask),
    .obs_slot_releasing(obs_releasing_mask),
    .obs_slot_note_on(obs_note_on_mask),
    .obs_slot_note_off(obs_note_off_mask),
    .obs_retire_mask(obs_retire_mask),
    .obs_slot_sources(obs_slot_sources),
    .obs_slot_channels(obs_slot_channels),
    .obs_slot_notes(obs_slot_notes),
    .obs_slot_generations(obs_slot_generations),
    .obs_advance_mask(obs_advance_mask),
    .obs_advance_frame_id(obs_advance_frame_req_id),
    .obs_effect_input_valid(obs_effect_input_valid),
    .obs_effect_input_ready(obs_effect_input_ready),
    .obs_effect_input_id(obs_effect_input_id),
    .obs_effect_input_left(obs_effect_input_left),
    .obs_effect_input_right(obs_effect_input_right),
    .obs_effect_input_clip(obs_effect_input_clip_mask),
    .obs_apply_kind(obs_apply_kind),
    .obs_apply_mask(obs_apply_mask),
    .obs_apply_seq(obs_router_apply_seq),
    .obs_apply_seq_valid(obs_router_apply_seq_valid),
    .obs_config_take(obs_config_take),
    .obs_config_payload(obs_config_payload),
    // END M2_C9_CHAIN
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
        .clipped_right(clip_right), .upstream_clipped_left(obs_upstream_clip_mask[0]),
        .upstream_clipped_right(obs_upstream_clip_mask[1]), .effect_clipped_left(obs_effect_clip_mask[0]),
        .effect_clipped_right(obs_effect_clip_mask[1]), .feedback_clipped_left(obs_feedback_clip_mask[0]),
        .feedback_clipped_right(obs_feedback_clip_mask[1]), .active_voice_count(active_voice_count)
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

    // The sidecar mirrors result-hold, pending and held identity only. It does
    // not drive PCM, reset, ready, valid, or any mathematical datapath control.
    // The board connects TX valid to 1 and its frame_tick to this same FRAME.
    // Reset invalidates identities; capture assigns epoch from independent reset edges.
    m2_r06_tx_identity_sidecar u_tx_identity_sidecar (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick), .tx_valid(1'b1),
        .result_valid(result_valid), .result_ready(result_ready),
        .result_id(result_id), .result_clip_mask({clip_right, clip_left}),
        .commit_pulse(commit_pulse), .commit_id(committed_id),
        .commit_left(committed_left), .commit_right(committed_right),
        .buffer_pending_valid(pending_valid),
        .play_left(play_left), .play_right(play_right),
        .tx_sample_valid(obs_tx_sample_valid),
        .tx_metadata_valid(obs_tx_metadata_valid),
        .tx_req_id_valid(obs_tx_req_id_valid),
        .tx_frame_id(obs_tx_frame_id), .tx_req_id(obs_tx_req_id),
        .tx_clip_mask(obs_tx_clip_mask), .tx_clip_any(obs_tx_clip_any),
        .tx_hold(obs_tx_hold), .tx_startup_zero(obs_tx_startup_zero),
        .tx_left(), .tx_right(),
        .metadata_error(obs_metadata_error),
        .frame_id_overflow(obs_frame_id_overflow)
    );
endmodule