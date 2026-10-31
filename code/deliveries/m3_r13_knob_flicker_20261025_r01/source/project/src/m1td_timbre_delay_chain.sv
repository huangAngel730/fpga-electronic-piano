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
    // BEGIN R10_LIFECYCLE_DIAG_PORTS
    ,output wire [3:0] diag_key_down, diag_deferred, diag_sustain_releasing, diag_bank_phase
    ,output wire [11:0] diag_adsr_states
    // END R10_LIFECYCLE_DIAG_PORTS
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
    m1td_audio_candidate u_audio(
        // BEGIN R10_LIFECYCLE_DIAG_CONNECTIONS
        .diag_key_down(diag_key_down),
        .diag_deferred(diag_deferred),
        .diag_sustain_releasing(diag_sustain_releasing),
        .diag_bank_phase(diag_bank_phase),
        .diag_adsr_states(diag_adsr_states),
        // END R10_LIFECYCLE_DIAG_CONNECTIONS
.clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),
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
    // R06 narrow hold candidate from exact R05 native STA: retain id20/31,
    // add failing id28/24/12/18 and left10/20/11 at the u_post consumer only.
    // Two kept LUT1 identity stages add no clock, state or protocol latency.
    // Other consumers (including observers), valid/ready and right stay direct.
    wire [31:0] audio_id_to_post;
    for(genvar id_bit=0;id_bit<32;id_bit=id_bit+1)begin:g_post_id_hold
        if(id_bit==20 || id_bit==31 || id_bit==28 || id_bit==24 || id_bit==12 || id_bit==18)begin:g_delayed
            (* syn_keep=1, syn_dont_touch=1 *) wire [2:0] chain;
            assign chain[0]=audio_id[id_bit];
            for(genvar stage=0;stage<2;stage=stage+1)begin:g_stage
                (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                    .I0(chain[stage]),.F(chain[stage+1]));
            end
            assign audio_id_to_post[id_bit]=chain[2];
        end else begin:g_direct
            assign audio_id_to_post[id_bit]=audio_id[id_bit];
        end
    end
    wire signed [23:0] audio_left_to_post;
    for(genvar left_bit=0;left_bit<24;left_bit=left_bit+1)begin:g_post_left_hold
        if(left_bit==10 || left_bit==20 || left_bit==11)begin:g_delayed
            (* syn_keep=1, syn_dont_touch=1 *) wire [2:0] chain;
            assign chain[0]=audio_left[left_bit];
            for(genvar stage=0;stage<2;stage=stage+1)begin:g_stage
                (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                    .I0(chain[stage]),.F(chain[stage+1]));
            end
            assign audio_left_to_post[left_bit]=chain[2];
        end else begin:g_direct
            assign audio_left_to_post[left_bit]=audio_left[left_bit];
        end
    end
    m1td_stereo_delay u_post(.clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.current_req_id(sample_req_id),
        .input_valid(audio_valid),.input_ready(audio_ready),.input_id(audio_id_to_post),
        .input_left(audio_left_to_post),.input_right(audio_right),.input_clipped_left(audio_clip_left),.input_clipped_right(audio_clip_right),
        .config_valid(config_valid && config_idle),.config_ready(raw_config_ready),.config_enable(config_enable),
        .config_delay_samples(config_delay_samples),.config_dry_gain(config_dry_gain),.config_wet_gain(config_wet_gain),
        .config_feedback(config_feedback),.output_valid(result_valid),.output_ready(result_ready),.output_id(result_id),
        .output_left(result_left),.output_right(result_right),.clipped_left(clipped_left),.clipped_right(clipped_right),
        .upstream_clipped_left(upstream_clipped_left),.upstream_clipped_right(upstream_clipped_right),
        .effect_clipped_left(effect_clipped_left),.effect_clipped_right(effect_clipped_right),
        .feedback_clipped_left(feedback_clipped_left),.feedback_clipped_right(feedback_clipped_right),.busy());
endmodule
