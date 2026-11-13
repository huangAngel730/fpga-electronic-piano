// R18 production adapter for the delivered N-slot core.
// Keeps the accepted frame/I2S contract and Bright Octave second timbre while
// parameterizing the voice/lifecycle state for 16/32 slots. The public legacy C9
// observation port remains four slots; full lifecycle buses are private to the
// production top so source-scoped score cleanup can scan all eight voices.
module m2_eightvoice_bright_frame_core #(
    parameter integer N=32, SW=$clog2(N), TW=72+SW,
    parameter integer FRAME_LIMIT=833, DRAIN_LIMIT=N*5+64, ENABLE_C1_FX=0
) (
    input  logic clk, rst_n, frame_tick,
    input wire [2:0] fx_mode,
    input wire [2:0] fx_timbre,
    input wire extra_pcm_ready,
    input wire signed [23:0] snare_pcm,sax_pcm,guitar_pcm,
    input  logic event_valid,
    output wire event_ready,
    input  logic [63:0] event_data,
    input  logic config_valid,
    output wire config_ready,
    input  logic config_enable,
    input  logic [15:0] config_delay_samples,
    input  logic [14:0] config_dry_gain, config_wet_gain, config_feedback,
    output wire signed [23:0] play_left, play_right,
    output wire pending_valid, commit_pulse,
    output wire [31:0] active_voice_count, clip_count, audio_underrun,
    output wire [31:0] audio_frame_count, pcm_request_count, pcm_commit_count,
    output wire [31:0] max_processing_cycles,
    output wire request_accept,
    output wire [31:0] request_id, committed_id,
    output wire signed [23:0] committed_left, committed_right,
    output wire committed_clip,
    output wire obs_req_valid, obs_req_ready,
    output wire obs_result_valid, obs_result_ready,
    output wire [31:0] obs_result_id,
    output wire signed [23:0] obs_result_left, obs_result_right,
    output wire [1:0] obs_result_clip_mask,
    output wire obs_cancel,
    output wire [1:0] obs_raw_cancel_reason,
    output wire obs_tx_sample_valid, obs_tx_metadata_valid, obs_tx_req_id_valid,
    output wire [31:0] obs_tx_frame_id, obs_tx_req_id,
    output wire [1:0] obs_tx_clip_mask,
    output wire obs_tx_clip_any, obs_tx_hold, obs_tx_startup_zero,
    output wire obs_metadata_error, obs_frame_id_overflow,
    output wire obs_apply_valid,
    output wire [63:0] obs_apply_data,
    output wire [3:0] obs_occupied_mask, obs_releasing_mask,
    output wire [3:0] obs_note_on_mask, obs_note_off_mask, obs_retire_mask,
    output wire [15:0] obs_slot_sources, obs_slot_channels,
    output wire [31:0] obs_slot_notes,
    output wire [127:0] obs_slot_generations,
    output wire [3:0] obs_advance_mask,
    output wire [31:0] obs_advance_frame_req_id,
    output wire obs_effect_input_valid, obs_effect_input_ready,
    output wire [31:0] obs_effect_input_id,
    output wire signed [23:0] obs_effect_input_left, obs_effect_input_right,
    output wire [1:0] obs_effect_input_clip_mask,
    output wire [3:0] obs_apply_kind, obs_apply_mask,
    output wire [31:0] obs_router_apply_seq,
    output wire obs_router_apply_seq_valid,
    output wire obs_config_take,
    output wire [61:0] obs_config_payload,
    output wire [1:0] obs_upstream_clip_mask,
    output wire [1:0] obs_effect_clip_mask,
    output wire [1:0] obs_feedback_clip_mask,
    output wire [3:0] diag_key_down, diag_deferred,
    output wire [3:0] diag_sustain_releasing, diag_bank_phase,
    output wire [11:0] diag_adsr_states,
    output wire [N-1:0] full_occupied, full_releasing,
    output wire [N*4-1:0] full_sources, full_channels,
    output wire [N*8-1:0] full_notes
);

    wire candidate_cancel, sample_valid, sample_ready;
    wire result_valid, result_ready;
    wire [31:0] result_id, completion_cycles;
    wire [31:0] frame_current_id;
    wire signed [23:0] result_left, result_right;
    wire [7:0] result_clip_bits;
    wire [N-1:0] note_on_mask, note_off_mask, timbre_mask;
    wire [N-1:0] retire_mask;
    wire [N*32-1:0] full_generations;
    wire [N*32-1:0] piano_phases, secondary_phases;
    wire [N*16-1:0] live_envelopes;
    wire [N*3-1:0] live_states;
    wire lane_valid;
    wire [SW-1:0] lane_slot;
    wire dispatched_this_frame;
    wire core_config_ready;
    wire core_idle;

    assign config_ready=core_config_ready;
    assign request_accept=sample_valid && sample_ready;
    assign max_processing_cycles=completion_cycles;
    assign obs_req_valid=sample_valid;
    assign obs_req_ready=sample_ready;
    assign obs_result_valid=result_valid;
    assign obs_result_ready=result_ready;
    assign obs_result_id=result_id;
    assign obs_result_left=result_left;
    assign obs_result_right=result_right;
    assign obs_result_clip_mask=result_clip_bits[1:0];
    assign obs_cancel=candidate_cancel;
    assign obs_raw_cancel_reason=candidate_cancel ? 2'b01 : 2'b00;

    assign obs_apply_valid=event_valid && event_ready;
    assign obs_apply_data=event_data;
    assign obs_occupied_mask=full_occupied[3:0];
    assign obs_releasing_mask=full_releasing[3:0];
    assign obs_note_on_mask=note_on_mask[3:0];
    assign obs_note_off_mask=note_off_mask[3:0];
    assign obs_retire_mask=retire_mask[3:0];
    assign obs_slot_sources=full_sources[15:0];
    assign obs_slot_channels=full_channels[15:0];
    assign obs_slot_notes=full_notes[31:0];
    assign obs_slot_generations=full_generations[127:0];
    assign obs_advance_mask=(lane_valid && lane_slot<4) ?
        (4'b0001 << lane_slot[1:0]) : 4'b0000;
    assign obs_advance_frame_req_id=request_id;
    assign obs_effect_input_valid=result_valid;
    assign obs_effect_input_ready=result_ready;
    assign obs_effect_input_id=result_id;
    assign obs_effect_input_left=result_left;
    assign obs_effect_input_right=result_right;
    assign obs_effect_input_clip_mask=result_clip_bits[5:4];
    assign obs_apply_kind=4'b0000;
    assign obs_apply_mask=note_on_mask[3:0] | note_off_mask[3:0];
    assign obs_router_apply_seq_valid=obs_apply_valid;
    assign obs_config_take=config_valid && core_config_ready;
    assign obs_config_payload={config_enable,config_delay_samples,
        config_dry_gain,config_wet_gain,config_feedback};
    assign obs_upstream_clip_mask=result_clip_bits[3:2];
    assign obs_effect_clip_mask=result_clip_bits[5:4];
    assign obs_feedback_clip_mask=result_clip_bits[7:6];
    assign diag_key_down=full_occupied[3:0] & ~full_releasing[3:0];
    assign diag_deferred=4'b0000;
    assign diag_sustain_releasing=full_releasing[3:0];
    assign diag_bank_phase=timbre_mask[3:0];
    assign diag_adsr_states=live_states[11:0];

    logic [31:0] apply_sequence;
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) apply_sequence<=32'd0;
        else if(obs_apply_valid) apply_sequence<=apply_sequence+1'b1;
    end
    assign obs_router_apply_seq=apply_sequence;

    for(genvar i=0;i<N;i=i+1) begin:g_retire_observe
        assign retire_mask[i]=full_occupied[i] && full_releasing[i] &&
            live_states[3*i+:3]==3'd0 && !note_on_mask[i];
    end

    m2_polyphony_timbre_core #(
        .N(N),.SW(SW),.TW(TW),.RESPONSE(1),.FRAME_LIMIT(FRAME_LIMIT),.DRAIN_LIMIT(DRAIN_LIMIT),
        .ENABLE_C1_FX(ENABLE_C1_FX),
        .WAVE_FILE("rom/piano_band_4x256_8191.mem"),
        .TRIANGLE_FILE("rom/bright_octave_4x256_8191.mem"),
        .OCT_FILE("rom/oct_ratio_q16.mem"),
        .SUB_FILE("rom/sub_ratio_q16.mem"),
        .LFO_FILE("rom/lfo_sine_q15.mem")
    ) u_n8_core (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.cancel_in(1'b0),
        .fx_mode(fx_mode),.fx_timbre(fx_timbre),.extra_pcm_ready(extra_pcm_ready),.snare_pcm(snare_pcm),.sax_pcm(sax_pcm),.guitar_pcm(guitar_pcm),
        .event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .sample_valid(sample_valid && !config_valid),.sample_ready(sample_ready),.sample_id(request_id),
        .result_valid(result_valid),.result_ready(result_ready),.result_id(result_id),
        .left(result_left),.right(result_right),.clip_bits(result_clip_bits),
        .late(),.completion_cycles(completion_cycles),.aborted(),.abort_reason(),
        .config_valid(config_valid),.config_ready(core_config_ready),
        .config_enable(config_enable),.config_delay_samples(config_delay_samples),
        .config_dry_gain(config_dry_gain),.config_wet_gain(config_wet_gain),
        .config_feedback(config_feedback),.idle(core_idle),.fault(),
        .inject_valid(1'b0),.inject_tag({TW{1'b0}}),.inject_context(75'd0),
        .inject_ready(),.read_valid(1'b0),.read_slot({SW{1'b0}}),
        .read_ready(),.read_out_valid(),.read_context(),
        .ons(note_on_mask),.offs(note_off_mask),.occupied(full_occupied),
        .releasing(full_releasing),.timbres(timbre_mask),
        .active_voice_count(active_voice_count),.velocities(),.bases(),
        .generations(full_generations),.notes(full_notes),.sources(full_sources),
        .channels(full_channels),.issue_valid(),.issue_tag(),.issue_context(),
        .issue_flags(),.issue_control(),.issue_pedal(),.write_valid(),
        .write_accepted(),.write_injected(),.write_tag(),.write_context(),
        .publish(),.be_launch(),.advance(),.lane_valid(lane_valid),
        .lane_slot(lane_slot),.lane_table(),.lane_timbre(),.lane_phase(),
        .lane_triangle_phase(),.lane_fcw(),.piano_phases(piano_phases),
        .triangle_phases(secondary_phases),.lane_wave(),.lane_env(),.lane_pcm(),
        .live_env(live_envelopes),.live_state(live_states)
    );

    premixed_frame_adapter u_frame_adapter (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),
        .candidate_cancel(candidate_cancel),.candidate_sample_valid(sample_valid),
        .candidate_sample_ready(sample_ready),.candidate_sample_id(request_id),
        .candidate_result_valid(result_valid),.candidate_result_ready(result_ready),
        .candidate_result_id(result_id),.candidate_left(result_left),
        .candidate_right(result_right),.candidate_clipped(|result_clip_bits),
        .play_left(play_left),.play_right(play_right),.pending_valid(pending_valid),
        .commit_pulse(commit_pulse),.frame_count(audio_frame_count),
        .frame_request_count(pcm_request_count),.commit_count(pcm_commit_count),
        .underrun_count(audio_underrun),.clip_count(clip_count),
        .current_id(frame_current_id),.committed_id(committed_id),
        .committed_left(committed_left),.committed_right(committed_right),
        .committed_clip(committed_clip),.dispatched_this_frame(dispatched_this_frame)
    );

    m2_r06_tx_identity_sidecar u_tx_identity_sidecar (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.tx_valid(1'b1),
        .result_valid(result_valid),.result_ready(result_ready),
        .result_id(result_id),.result_clip_mask(result_clip_bits[1:0]),
        .commit_pulse(commit_pulse),.commit_id(committed_id),
        .commit_left(committed_left),.commit_right(committed_right),
        .buffer_pending_valid(pending_valid),.play_left(play_left),.play_right(play_right),
        .tx_sample_valid(obs_tx_sample_valid),.tx_metadata_valid(obs_tx_metadata_valid),
        .tx_req_id_valid(obs_tx_req_id_valid),.tx_frame_id(obs_tx_frame_id),
        .tx_req_id(obs_tx_req_id),.tx_clip_mask(obs_tx_clip_mask),
        .tx_clip_any(obs_tx_clip_any),.tx_hold(obs_tx_hold),
        .tx_startup_zero(obs_tx_startup_zero),.tx_left(),.tx_right(),
        .metadata_error(obs_metadata_error),.frame_id_overflow(obs_frame_id_overflow)
    );
endmodule
