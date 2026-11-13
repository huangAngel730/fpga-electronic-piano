// M2 isolation candidate: actual router + CC64 + four DDS/ADSR + Pitch/Mod FCW.
// No waveform scaling or PCM arithmetic; M1 ADSR and allocator are unchanged.
// All logic uses clk. rst_n: async assert, synchronously released upstream.
// frame_tick cancels an old generation. One accepted sample_req causes at most
// one lane_tick. Cancelling a computed result does not roll back DSP state.
// BEGIN M1_OBSERVER_R06
// M1 R06 observation candidate: added outputs are combinational aliases only.
// Sample these outputs on clk posedge pre-NBA; no observation register is added.
// END M1_OBSERVER_R06
module m1td_polyphonic_envelope_bank #(
    parameter integer PIANO_TIMBRE_ENABLE = 1,
    parameter SINE_ROM_FILE="rom/sine_wavetable.hex",
    parameter TRIANGLE_ROM_FILE="rom/triangle_wavetable.hex",
    parameter ORGAN_ROM_FILE="rom/bright_octave_4x256_8191.mem",
    parameter ORGAN_GAIN_ROM_FILE="rom/organ_velocity_gain_1024.mem",
    parameter OCT_FILE="rom/oct_ratio_q16.mem",
    parameter SUB_FILE="rom/sub_ratio_q16.mem",
    parameter LFO_FILE="rom/lfo_sine_q15.mem",
    parameter logic[31:0] LFO_INC=32'd447392,
    parameter WAVE_ROM_FILE = "rom/sine_1024_32767.mem"
) (
    input logic clk, rst_n,
    input logic event_valid,
    output wire event_ready,
    input logic [63:0] event_data,
    input logic frame_tick, sample_req,
    input logic [31:0] sample_req_id,
    output wire calc_ready,
    output logic result_valid,
    input logic result_ready,
    output logic [31:0] result_req_id,
    output logic [63:0] result_envelopes,
    output logic [63:0] result_waves,
    output logic [127:0] result_fcw,
    output logic [3:0] result_occupied,
    output logic [11:0] result_states,
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
    output wire [3:0] obs_retire_mask
    // END M1_OBSERVER_R06
    // BEGIN R10_LIFECYCLE_DIAG_PORTS
    ,output wire [3:0] diag_key_down, diag_deferred, diag_sustain_releasing, diag_bank_phase
    ,output wire [11:0] diag_adsr_states
    // END R10_LIFECYCLE_DIAG_PORTS
);
    localparam logic [3:0] IDLE=0, WAIT_DISPATCH=1, SETTLE=2,
        CAPTURE=3, WAIT_CONTROL=4, ADVANCE=5, SNAPSHOT=6, HOLD=7, DRAIN=8;
    logic [3:0] phase;
    // BEGIN R10_LIFECYCLE_DIAG_ALIASES
    assign diag_bank_phase = phase;
    // END R10_LIFECYCLE_DIAG_ALIASES
    logic [2:0] delay_count;
    logic [31:0] pending_req_id;
    logic resume_requested;
    wire dispatch_busy,router_ready,control_event_ready;
    wire [3:0] slot_note_on,slot_note_off,slot_occupied,slot_releasing;
    wire [3:0] slot_timbre;
    wire [39:0] slot_velocity;
    wire [127:0] slot_fcw;
    wire [31:0] slot_notes;
    wire [15:0] slot_sources,slot_channels;
    wire [127:0] slot_generations;
    // BEGIN M1_OBSERVER_R06
    assign obs_slot_occupied=slot_occupied;
    assign obs_slot_releasing=slot_releasing;
    assign obs_slot_note_on=slot_note_on;
    assign obs_slot_note_off=slot_note_off;
    assign obs_slot_sources=slot_sources;
    assign obs_slot_channels=slot_channels;
    assign obs_slot_notes=slot_notes;
    assign obs_slot_generations=slot_generations;
    // END M1_OBSERVER_R06
    wire [63:0] envelopes,waves;
    wire [11:0] states;
    // Pure observer: lane n ADSR state is diag_adsr_states[3*n+:3].
    assign diag_adsr_states = states;
    wire [3:0] release_done;
    wire owner_idle=phase==IDLE && !sample_req && !frame_tick && !result_valid;
    // Fork a SINGLE actual accepted event to router and control RAM.  Neither
    // side may accept alone.  All discrete semantics remain in the real router.
    assign event_ready=router_ready && control_event_ready;
    m1td_polyphonic_event_router u_events(
        // BEGIN R10_LIFECYCLE_DIAG_CONNECTIONS
        .diag_key_down(diag_key_down),
        .diag_deferred(diag_deferred),
        .diag_sustain_releasing(diag_sustain_releasing),
        // END R10_LIFECYCLE_DIAG_CONNECTIONS

        // BEGIN M1_OBSERVER_R06
        .obs_apply_valid(obs_apply_valid),.obs_apply_data(obs_apply_data),
        .obs_apply_kind(obs_apply_kind),.obs_apply_mask(obs_apply_mask),
        .obs_apply_seq(obs_apply_seq),.obs_apply_seq_valid(obs_apply_seq_valid),
        .obs_retire_mask(obs_retire_mask),
        // END M1_OBSERVER_R06
        .clk(clk),.rst_n(rst_n),.sample_owner_ready(owner_idle),
        .event_valid(event_valid && control_event_ready),.event_ready(router_ready),
        .event_data(event_data),.release_done(release_done),.dispatch_busy(dispatch_busy),
        .slot_note_on(slot_note_on),.slot_note_off(slot_note_off),
        .slot_occupied(slot_occupied),.slot_releasing(slot_releasing),
        .slot_velocity(slot_velocity),.slot_fcw(slot_fcw),.slot_notes(slot_notes),.slot_timbre(slot_timbre),
        .active_voice_count(active_voice_count),.slot_source_ids(slot_sources),
        .slot_channel_ids(slot_channels),.slot_generations(slot_generations));

    wire control_request_ready,control_snapshot_valid,control_snapshot_ready;
    wire [31:0] control_id;
    wire [3:0] control_occupied;
    wire [15:0] control_sources,control_channels;
    wire [127:0] control_generations;
    wire [47:0] control_bend,control_mod;
    wire [19:0] control_range;
    wire fcw_request_ready,fcw_result_valid,fcw_result_ready;
    wire control_request_valid=rst_n && !frame_tick && phase==CAPTURE && fcw_request_ready;
    logic [127:0] frozen_base;
    logic [127:0] computed_fcw;
    logic [3:0] frozen_occupied;
    logic [15:0] frozen_sources,frozen_channels;
    logic [127:0] frozen_generations;
    // Native08 generation14/18 -> frozen_generations Hold failures. Pad only
    // this complete128bit snapshot consumer; original FF/edge/identity stay.
    wire[127:0]generation_for_frozen_snapshot;
    for(genvar gen_bit=0;gen_bit<128;gen_bit=gen_bit+1)begin:g_frozen_generation_hold
        (* syn_keep=1, syn_dont_touch=1 *) wire[2:0]chain;
        assign chain[0]=slot_generations[gen_bit];
        for(genvar gen_stage=0;gen_stage<2;gen_stage=gen_stage+1)begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2))u_identity(
                .I0(chain[gen_stage]),.F(chain[gen_stage+1]));
        end
        assign generation_for_frozen_snapshot[gen_bit]=chain[2];
    end
    m1td_performance_control_snapshot u_controls(
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid && router_ready),
        .event_ready(control_event_ready),.event_data(event_data),
        .request_valid(control_request_valid),.request_ready(control_request_ready),
        .request_id(pending_req_id),.slot_occupied(slot_occupied),
        .slot_source_ids(slot_sources),.slot_channels(slot_channels),
        .slot_generations(slot_generations),.snapshot_valid(control_snapshot_valid),
        .snapshot_ready(control_snapshot_ready),.snapshot_id(control_id),
        .snapshot_occupied(control_occupied),.snapshot_sources(control_sources),
        .snapshot_channels(control_channels),.snapshot_generations(control_generations),
        .snapshot_pitch_bend(control_bend),.snapshot_modulation(control_mod),
        .snapshot_pitch_range(control_range),.control_applied(),.invalid_range());
    wire [31:0] fcw_id;
    wire [3:0] fcw_occupied;
    wire [15:0] fcw_sources,fcw_channels;
    wire [127:0] fcw_generations,fcw_values;
    // Cancel only the math token, not the player's stored wheel parameters.
    // A discarded pre-DDS calculation may already advance its LFO once; it is
    // not rolled back, exactly as the previously verified consumer contract.
    assign control_snapshot_ready=rst_n && !frame_tick &&
        ((phase==WAIT_CONTROL && fcw_request_ready) || phase==DRAIN);
    assign fcw_result_ready=rst_n && !frame_tick &&
        (phase==WAIT_CONTROL || phase==DRAIN);
    // R05: actual R04 native hold paths are frozen-base data/bypass,
    // occupied bypass-select, and pitch snapshot identity D inputs.
    // Delay only these consumer branches; preserve identity guards/lane_tick,
    // diagnostics and all sequential behavior. Each of 296 bits uses two
    // retained INIT2 LUT1 cells, with no added clock cycle (592 LUT1 total).
    wire [127:0] base_to_pitch_and_bypass;
    wire [3:0] occupied_to_pitch, occupied_to_bypass;
    wire [15:0] sources_to_pitch, channels_to_pitch;
    wire [127:0] generations_to_pitch;
    wire [295:0] short_path_inputs = {frozen_base,control_occupied,
        control_sources,control_channels,control_generations,frozen_occupied};
    wire [295:0] short_path_outputs;
    for(genvar hold_bit=0;hold_bit<296;hold_bit=hold_bit+1)begin:g_snapshot_hold
        (* syn_keep=1, syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=short_path_inputs[hold_bit];
        for(genvar stage=0;stage<2;stage=stage+1)begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                .I0(chain[stage]),.F(chain[stage+1]));
        end
        assign short_path_outputs[hold_bit]=chain[2];
    end
    assign {base_to_pitch_and_bypass,occupied_to_pitch,sources_to_pitch,
        channels_to_pitch,generations_to_pitch,occupied_to_bypass}=short_path_outputs;
    m1td_pitch_mod_snapshot_pipeline #(.OCT_FILE(OCT_FILE),.SUB_FILE(SUB_FILE),
        .LFO_FILE(LFO_FILE),.LFO_INC(LFO_INC))u_pitch_mod(
        .clk(clk),.rst_n(rst_n),.cancel(frame_tick),
        .request_valid(control_snapshot_valid && phase==WAIT_CONTROL && !frame_tick),
        .request_ready(fcw_request_ready),.request_id(control_id),
        .request_occupied(occupied_to_pitch),.note_on_mask(slot_note_on),
        .request_sources(sources_to_pitch),.request_channels(channels_to_pitch),
        .request_generations(generations_to_pitch),.request_base_fcw(base_to_pitch_and_bypass),
        .request_pitch_bend(control_bend),.request_modulation(control_mod),
        .request_pitch_range(control_range),.result_valid(fcw_result_valid),
        .result_ready(fcw_result_ready),.result_id(fcw_id),
        .result_occupied(fcw_occupied),.result_sources(fcw_sources),
        .result_channels(fcw_channels),.result_generations(fcw_generations),
        .result_fcw(fcw_values));
    wire live_identity_matches=slot_occupied==frozen_occupied &&
        slot_sources==frozen_sources && slot_channels==frozen_channels &&
        slot_generations==frozen_generations;
    wire math_identity_matches=fcw_id==pending_req_id &&
        fcw_occupied==frozen_occupied && fcw_sources==frozen_sources &&
        fcw_channels==frozen_channels && fcw_generations==frozen_generations;
    // Split the wide identity comparison from the DDS/ADSR tick path.
    // Router accepts no new allocation while the sample owner is active;
    // WAIT_DISPATCH drains the previous allocation before CAPTURE. The sole
    // WAIT_CONTROL -> ADVANCE edge already checks the full current identity.
    // Retirement may clear occupied independently, so check occupied NOW.
    wire wide_identity_match_now=slot_sources==frozen_sources &&
        slot_channels==frozen_channels && slot_generations==frozen_generations;
    logic wide_identity_match_q;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)wide_identity_match_q<=1'b0;
        else wide_identity_match_q<=wide_identity_match_now;
    end
    wire lane_tick=rst_n && !frame_tick && phase==ADVANCE &&
        wide_identity_match_q && slot_occupied==frozen_occupied;
    // synthesis translate_off
    always @(posedge clk)if(rst_n)begin
        if(!frame_tick && phase==ADVANCE &&
            wide_identity_match_q !== wide_identity_match_now)
            $fatal(1,"registered identity is stale at ADVANCE");
        if(lane_tick !== (rst_n && !frame_tick && phase==ADVANCE && live_identity_matches))
            $fatal(1,"timing pipeline changed the original lane tick");
    end
    // synthesis translate_on
    // BEGIN M1_OBSERVER_R06
    assign obs_advance_mask={4{lane_tick}};
    assign obs_advance_frame_id=pending_req_id;
    // END M1_OBSERVER_R06
    // A retiring/replaced identity never receives another generation's FCW.
    assign calc_ready=rst_n && (phase==IDLE || frame_tick);
    wire [127:0] dds_fcw=phase==IDLE || phase==WAIT_DISPATCH || phase==SETTLE ||
        phase==CAPTURE ? slot_fcw : computed_fcw;
    for(genvar i=0;i<4;i++)begin:g_lane
        wire [15:0] piano_envelope,organ_envelope_level;
        wire [2:0] piano_state,organ_state;
        // Program 0 keeps the frozen R18 Piano path. Program 1 replaces only
        // the former triangle branch with the selected Bright Octave source.
        // The router already latches program ownership independently per slot.
        piano_organ_voice #(.PIANO_ROM_FILE(WAVE_ROM_FILE),
            .ORGAN_ROM_FILE(ORGAN_ROM_FILE),.PRIVATE_M1TD_PIANO(1'b1))u_voice(
            .clk(clk),.rst_n(rst_n),.sample_tick(lane_tick),
            .note_on(slot_note_on[i]),.note_off(slot_note_off[i]),
            .velocity(slot_velocity[10*i+:10]),.fcw(dds_fcw[32*i+:32]),
            .timbre_organ(slot_timbre[i]),.wt_sample(waves[16*i+:16]));
        m1td_adsr_piano_envelope u_piano_envelope(
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(lane_tick),
            .note_on(slot_note_on[i]),.note_off(slot_note_off[i]),
            .velocity(slot_velocity[10*i+:10]),
            .envelope_level(piano_envelope),.state_out(piano_state));
        organ_envelope #(.VELOCITY_ROM_FILE(ORGAN_GAIN_ROM_FILE))u_organ_envelope(
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(lane_tick),
            .note_on(slot_note_on[i]),.note_off(slot_note_off[i]),
            .velocity(slot_velocity[10*i+:10]),
            .envelope_level(organ_envelope_level),.state_out(organ_state));
        assign envelopes[16*i+:16]=slot_timbre[i] ? organ_envelope_level : piano_envelope;
        assign states[3*i+:3]=slot_timbre[i] ? organ_state : piano_state;
        assign release_done[i]=rst_n && slot_occupied[i] && slot_releasing[i] &&
            states[3*i+:3]==0 && !slot_note_on[i];
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            phase<=IDLE;delay_count<=0;pending_req_id<=0;resume_requested<=0;
            frozen_base<=0;computed_fcw<=0;frozen_occupied<=0;
            frozen_sources<=0;frozen_channels<=0;frozen_generations<=0;
            result_valid<=0;result_req_id<=0;result_envelopes<=0;result_waves<=0;
            result_fcw<=0;result_occupied<=0;result_states<=0;
        end else if(frame_tick)begin
            phase<=DRAIN;result_valid<=0;resume_requested<=0;
        end else begin
            case(phase)
                IDLE:if(sample_req)begin pending_req_id<=sample_req_id;phase<=WAIT_DISPATCH;end
                WAIT_DISPATCH:if(!dispatch_busy && !(|slot_note_on) && !(|slot_note_off))begin
                    delay_count<=6;phase<=SETTLE;
                end
                SETTLE:if(delay_count==0)phase<=CAPTURE;
                    else delay_count<=delay_count-1'b1;
                CAPTURE:if(control_request_valid && control_request_ready)begin
                    frozen_base<=slot_fcw;frozen_occupied<=slot_occupied;
                    frozen_sources<=slot_sources;frozen_channels<=slot_channels;
                    frozen_generations<=generation_for_frozen_snapshot;phase<=WAIT_CONTROL;
                end
                WAIT_CONTROL:if(fcw_result_valid && fcw_result_ready)begin
                    if(math_identity_matches && live_identity_matches)begin
                        for(integer k=0;k<4;k++)
                            computed_fcw[32*k+:32]<=occupied_to_bypass[k] ? fcw_values[32*k+:32] : base_to_pitch_and_bypass[32*k+:32];
                        phase<=ADVANCE;
                    end else phase<=DRAIN;
                end
                ADVANCE:if(live_identity_matches)begin delay_count<=4;phase<=SNAPSHOT;end
                    else phase<=DRAIN;
                SNAPSHOT:if(delay_count==0)begin
                    result_req_id<=pending_req_id;result_envelopes<=envelopes;
                    result_waves<=waves;result_fcw<=computed_fcw;
                    result_occupied<=frozen_occupied;result_states<=states;
                    result_valid<=1;phase<=HOLD;
                end else delay_count<=delay_count-1'b1;
                HOLD:if(result_valid && result_ready)begin result_valid<=0;phase<=IDLE;end
                DRAIN:begin
                    // Frame buffer emits the new request on the following
                    // edge. Keep its ID while the cancelled math drains.
                    if(sample_req)begin pending_req_id<=sample_req_id;resume_requested<=1;end
                    if(control_request_ready && !control_snapshot_valid && fcw_request_ready && !fcw_result_valid)begin
                        phase<=(resume_requested || sample_req) ? WAIT_DISPATCH : IDLE;
                        resume_requested<=0;
                    end
                end
                default:begin phase<=DRAIN;result_valid<=0;end
            endcase
        end
    end
endmodule
