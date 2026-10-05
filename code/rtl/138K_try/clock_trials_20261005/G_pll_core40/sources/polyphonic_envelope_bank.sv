// M2 isolation candidate: actual router + CC64 + four DDS/ADSR + Pitch/Mod FCW.
// No waveform scaling or PCM arithmetic; M1 ADSR and allocator are unchanged.
// All logic uses clk. rst_n: async assert, synchronously released upstream.
// frame_tick cancels an old generation. One accepted sample_req causes at most
// one lane_tick. Cancelling a computed result does not roll back DSP state.
module polyphonic_envelope_bank #(
    parameter integer PIANO_TIMBRE_ENABLE = 0,
    parameter OCT_FILE="E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005/G_pll_core40/rom/oct_ratio_q16.mem",
    parameter SUB_FILE="E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005/G_pll_core40/rom/sub_ratio_q16.mem",
    parameter LFO_FILE="E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005/G_pll_core40/rom/lfo_sine_q15.mem",
    parameter logic[31:0] LFO_INC=32'd447392,
    parameter WAVE_ROM_FILE = "E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005/G_pll_core40/rom/sine_1024_32767.mem"
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
);
    localparam logic [3:0] IDLE=0, WAIT_DISPATCH=1, SETTLE=2,
        CAPTURE=3, WAIT_CONTROL=4, ADVANCE=5, SNAPSHOT=6, HOLD=7, DRAIN=8;
    logic [3:0] phase;
    logic [2:0] delay_count;
    logic [31:0] pending_req_id;
    logic resume_requested;
    wire dispatch_busy,router_ready,control_event_ready;
    wire [3:0] slot_note_on,slot_note_off,slot_occupied,slot_releasing;
    wire [39:0] slot_velocity;
    wire [127:0] slot_fcw;
    wire [31:0] slot_notes;
    wire [15:0] slot_sources,slot_channels;
    wire [127:0] slot_generations;
    wire [63:0] envelopes,waves;
    wire [11:0] states;
    wire [3:0] release_done;
    wire owner_idle=phase==IDLE && !sample_req && !frame_tick && !result_valid;
    // Fork a SINGLE actual accepted event to router and control RAM.  Neither
    // side may accept alone.  All discrete semantics remain in the real router.
    assign event_ready=router_ready && control_event_ready;
    polyphonic_event_router u_events(
        .clk(clk),.rst_n(rst_n),.sample_owner_ready(owner_idle),
        .event_valid(event_valid && control_event_ready),.event_ready(router_ready),
        .event_data(event_data),.release_done(release_done),.dispatch_busy(dispatch_busy),
        .slot_note_on(slot_note_on),.slot_note_off(slot_note_off),
        .slot_occupied(slot_occupied),.slot_releasing(slot_releasing),
        .slot_velocity(slot_velocity),.slot_fcw(slot_fcw),.slot_notes(slot_notes),
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
    performance_control_snapshot u_controls(
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
    pitch_mod_snapshot_pipeline #(.OCT_FILE(OCT_FILE),.SUB_FILE(SUB_FILE),
        .LFO_FILE(LFO_FILE),.LFO_INC(LFO_INC))u_pitch_mod(
        .clk(clk),.rst_n(rst_n),.cancel(frame_tick),
        .request_valid(control_snapshot_valid && phase==WAIT_CONTROL && !frame_tick),
        .request_ready(fcw_request_ready),.request_id(control_id),
        .request_occupied(control_occupied),.note_on_mask(slot_note_on),
        .request_sources(control_sources),.request_channels(control_channels),
        .request_generations(control_generations),.request_base_fcw(frozen_base),
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
    wire lane_tick=rst_n && !frame_tick && phase==ADVANCE && live_identity_matches;
    // A retiring/replaced identity never receives another generation's FCW.
    assign calc_ready=rst_n && (phase==IDLE || frame_tick);
    wire [127:0] dds_fcw=phase==IDLE || phase==WAIT_DISPATCH || phase==SETTLE ||
        phase==CAPTURE ? slot_fcw : computed_fcw;
    for(genvar i=0;i<4;i++)begin:g_lane
        if(PIANO_TIMBRE_ENABLE)begin:g_piano
            piano_dds_oscillator #(.ROM_FILE(WAVE_ROM_FILE))u_dds(
                .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(lane_tick),
                .note_on(slot_note_on[i]),.velocity(slot_velocity[10*i+:10]),
                .fcw(dds_fcw[32*i+:32]),.wt_sample(waves[16*i+:16]));
        end else begin:g_sine
            dds_oscillator #(.ROM_FILE(WAVE_ROM_FILE))u_dds(
                .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(lane_tick),
                .fcw(dds_fcw[32*i+:32]),.wt_sample(waves[16*i+:16]));
        end
        adsr_piano_envelope u_envelope(
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(lane_tick),
            .note_on(slot_note_on[i]),.note_off(slot_note_off[i]),
            .velocity(slot_velocity[10*i+:10]),
            .envelope_level(envelopes[16*i+:16]),.state_out(states[3*i+:3]));
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
                    frozen_generations<=slot_generations;phase<=WAIT_CONTROL;
                end
                WAIT_CONTROL:if(fcw_result_valid && fcw_result_ready)begin
                    if(math_identity_matches && live_identity_matches)begin
                        for(integer k=0;k<4;k++)
                            computed_fcw[32*k+:32]<=frozen_occupied[k] ? fcw_values[32*k+:32] : frozen_base[32*k+:32];
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
