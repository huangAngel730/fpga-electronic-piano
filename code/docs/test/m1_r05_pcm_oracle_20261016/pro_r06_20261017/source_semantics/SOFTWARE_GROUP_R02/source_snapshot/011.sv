// Single isolated event-to-stereo-result entry point, default bit-exact bypass.
// M2 connects its frame request/commit buffer and I2S; no new production controls.
// BEGIN M1_OBSERVER_R06
// M1 R06 observation candidate: all added aliases are pre-NBA observations.
// obs_config_payload is a proposed diagnostic packing, not a new control input.
// END M1_OBSERVER_R06
module m1td_timbre_delay_chain (
    input logic clk,rst_n,event_valid,frame_tick,sample_req,
    input logic [63:0] event_data,
    input logic [31:0] sample_req_id,
    output wire event_ready,calc_ready,
    input logic config_valid,
    output wire config_ready,
    input logic config_enable,
    input logic [15:0] config_delay_samples,
    input logic [14:0] config_dry_gain,config_wet_gain,config_feedback,
    output wire result_valid,
    input logic result_ready,
    output wire [31:0] result_id,
    output wire signed [23:0] result_left,result_right,
    output wire clipped_left,clipped_right,
    output wire upstream_clipped_left,upstream_clipped_right,
    output wire effect_clipped_left,effect_clipped_right,
    output wire feedback_clipped_left,feedback_clipped_right,
    output wire [31:0] active_voice_count
    // BEGIN M1_OBSERVER_R06
    ,output wire [3:0] obs_slot_occupied, obs_slot_releasing,
    output wire [3:0] obs_slot_note_on, obs_slot_note_off,
    output wire [15:0] obs_slot_sources, obs_slot_channels,
    output wire [31:0] obs_slot_notes,
    output wire [127:0] obs_slot_generations,
    output wire [3:0] obs_advance_mask,
    output wire [31:0] obs_advance_frame_id,
    output wire obs_apply_valid,
    output wire [63:0] obs_apply_data,
    output wire [3:0] obs_apply_kind, obs_apply_mask,
    output wire [31:0] obs_apply_seq,
    output wire obs_apply_seq_valid,
    output wire [3:0] obs_retire_mask,
    output wire obs_effect_input_valid, obs_effect_input_ready,
    output wire [31:0] obs_effect_input_id,
    output wire signed [23:0] obs_effect_input_left, obs_effect_input_right,
    output wire [1:0] obs_effect_input_clip,
    output wire obs_config_take,
    output wire [61:0] obs_config_payload
    // END M1_OBSERVER_R06
);
    wire audio_valid,audio_ready,raw_config_ready,audio_calc_ready;
    wire [31:0] audio_id;
    wire signed [23:0] audio_left,audio_right;
    wire audio_clip_left,audio_clip_right;
    wire config_idle=audio_calc_ready && !audio_valid && !sample_req && !frame_tick;
    assign config_ready=raw_config_ready && config_idle;
    assign calc_ready=audio_calc_ready;
    // BEGIN M1_OBSERVER_R06
    assign obs_effect_input_valid=audio_valid;
    assign obs_effect_input_ready=audio_ready;
    assign obs_effect_input_id=audio_id;
    assign obs_effect_input_left=audio_left;
    assign obs_effect_input_right=audio_right;
    assign obs_effect_input_clip={audio_clip_right,audio_clip_left};
    assign obs_config_take=config_valid && config_ready;
    assign obs_config_payload={config_enable,config_delay_samples,
        config_dry_gain,config_wet_gain,config_feedback};
    // END M1_OBSERVER_R06
    m1td_audio_candidate u_audio(.clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),
        // BEGIN M1_OBSERVER_R06
        .obs_slot_occupied(obs_slot_occupied),.obs_slot_releasing(obs_slot_releasing),
        .obs_slot_note_on(obs_slot_note_on),.obs_slot_note_off(obs_slot_note_off),
        .obs_slot_sources(obs_slot_sources),.obs_slot_channels(obs_slot_channels),
        .obs_slot_notes(obs_slot_notes),.obs_slot_generations(obs_slot_generations),
        .obs_advance_mask(obs_advance_mask),.obs_advance_frame_id(obs_advance_frame_id),
        .obs_apply_valid(obs_apply_valid),.obs_apply_data(obs_apply_data),
        .obs_apply_kind(obs_apply_kind),.obs_apply_mask(obs_apply_mask),
        .obs_apply_seq(obs_apply_seq),.obs_apply_seq_valid(obs_apply_seq_valid),
        .obs_retire_mask(obs_retire_mask),
        // END M1_OBSERVER_R06
        .event_data(event_data),.frame_tick(frame_tick),.sample_req(sample_req),.sample_req_id(sample_req_id),
        .calc_ready(audio_calc_ready),.result_valid(audio_valid),.result_ready(audio_ready),.result_id(audio_id),
        .result_left(audio_left),.result_right(audio_right),.clipped_left(audio_clip_left),
        .clipped_right(audio_clip_right),.active_voice_count(active_voice_count));
    m1td_stereo_delay u_post(.clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.current_req_id(sample_req_id),
        .input_valid(audio_valid),.input_ready(audio_ready),.input_id(audio_id),
        .input_left(audio_left),.input_right(audio_right),.input_clipped_left(audio_clip_left),.input_clipped_right(audio_clip_right),
        .config_valid(config_valid && config_idle),.config_ready(raw_config_ready),.config_enable(config_enable),
        .config_delay_samples(config_delay_samples),.config_dry_gain(config_dry_gain),.config_wet_gain(config_wet_gain),
        .config_feedback(config_feedback),.output_valid(result_valid),.output_ready(result_ready),.output_id(result_id),
        .output_left(result_left),.output_right(result_right),.clipped_left(clipped_left),.clipped_right(clipped_right),
        .upstream_clipped_left(upstream_clipped_left),.upstream_clipped_right(upstream_clipped_right),
        .effect_clipped_left(effect_clipped_left),.effect_clipped_right(effect_clipped_right),
        .feedback_clipped_left(feedback_clipped_left),.feedback_clipped_right(feedback_clipped_right),.busy());
endmodule
