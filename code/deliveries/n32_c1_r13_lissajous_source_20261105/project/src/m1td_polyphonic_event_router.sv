// T024 M2 event/allocator integration only: no sample arithmetic or new clocks.
// rst_n asserts asynchronously and is synchronously released by caller.
// One accepted event is held until the registered allocator result is applied.
// event_ready applies backpressure while dispatching; sample_owner_ready lets
// the PCM scheduler defer events during an in-flight sample generation.
`timescale 1ns/1ps
module m1td_polyphonic_event_router (
    input logic clk, rst_n, sample_owner_ready,
    input logic event_valid,
    output wire event_ready, dispatch_busy,
    input logic [63:0] event_data,
    input logic [3:0] release_done,
    output logic [3:0] slot_note_on, slot_note_off, slot_occupied, slot_releasing,
    output logic [39:0] slot_velocity,
    output logic [127:0] slot_fcw,
    output logic [31:0] slot_notes,
    output logic [3:0] slot_timbre,
    output wire [31:0] active_voice_count,
    output wire [15:0] slot_source_ids, slot_channel_ids,
    output wire [127:0] slot_generations
    // BEGIN M1_OBSERVER_R06_PORTS
    // Diagnostic-only outputs; sampled at posedge before NBA updates.
    , output wire obs_apply_valid
    , output wire [63:0] obs_apply_data
    , output wire [3:0] obs_apply_kind
    , output wire [3:0] obs_apply_mask
    , output wire [31:0] obs_apply_seq
    , output wire obs_apply_seq_valid
    , output wire [3:0] obs_retire_mask
    // END M1_OBSERVER_R06_PORTS
    // BEGIN R10_LIFECYCLE_DIAG_PORTS
    ,output wire [3:0] diag_key_down, diag_deferred, diag_sustain_releasing
    // END R10_LIFECYCLE_DIAG_PORTS
);
    import audio_defs_pkg::*;
    import sustain_control_contract_pkg::*;
    localparam logic [3:0] IDLE=0, ALLOC_SEND=1, ALLOC_APPLY=2,
        CTRL_ON=3, CTRL_OFF=4, CTRL_PEDAL=5, CTRL_PANIC=6,
        RELEASE_SCAN=7, RELEASE_SEND=8, RELEASE_APPLY=9,
        RELEASE_ACK=10, RETIRE=11, IGNORE_EVENT=12, CTRL_TIMBRE=13, DECODE_EVENT=14;
    logic [3:0] state;
    performance_event_t held_event;
    wire performance_event_t incoming=event_data;
    logic [15:0] slot_sources,slot_channels;
    logic program_timbre [0:255];
    // Static per-destination write enables retain the original asynchronous
    // reset and program write edge. Only the six selected D consumers get
    // independent two-LUT identities; controller command data stays direct.
    for(genvar p=0;p<256;p=p+1) begin:g_program_write
        wire program_write_data;
        if(p==2 || p==6 || p==12 || p==177 || p==238 || p==243) begin:g_hold
            (* syn_keep=1, syn_dont_touch=1 *) wire l0,l1;
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_hold0(.I0(held_event.control_value[0]),.F(l0));
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_hold1(.I0(l0),.F(l1));
            assign program_write_data=l1;
        end else begin:g_direct
            assign program_write_data=held_event.control_value[0];
        end
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) program_timbre[p]<=1'b0;
            else if(state==CTRL_TIMBRE && {held_event.source_id,held_event.channel}==8'(p))
                program_timbre[p]<=program_write_data;
        end
    end
    logic [31:0] slot_generation [0:3];
    // M2 candidate: exported registered identity, no functional routing change.
    assign slot_source_ids=slot_sources;
    assign slot_channel_ids=slot_channels;
    for(genvar identity_lane=0;identity_lane<4;identity_lane++) begin:g_identity
        assign slot_generations[32*identity_lane+:32]=slot_generation[identity_lane];
    end
    logic [3:0] retire_pending;
    logic [31:0] retire_generation [0:3];
    logic [1:0] target_slot;
    logic [2:0] release_index;
    logic match_valid,retire_valid;
    logic [1:0] match_slot,retire_slot;
    logic cmd_valid,cmd_ready,release_valid,release_ready;
    logic [2:0] cmd_type;
    wire [3:0] release_mask;
    wire [127:0] release_generations;
    wire [3:0] controller_occupied,controller_keys,controller_deferred,controller_releasing;
    // BEGIN R10_LIFECYCLE_DIAG_ALIASES
    assign diag_key_down = controller_keys;
    assign diag_deferred = controller_deferred;
    assign diag_sustain_releasing = controller_releasing;
    // END R10_LIFECYCLE_DIAG_ALIASES
    wire is_release_slot=release_index<4;
    wire [1:0] release_lane=release_index[1:0];
    wire release_matches=is_release_slot && release_mask[release_lane] &&
        slot_occupied[release_lane] &&
        slot_generation[release_lane]==release_generations[32*release_lane+:32];
    wire [1:0] allocated_slot,release_slot;
    wire slot_valid,release_target_valid;
    wire [31:0] held_fcw;
    wire [3:0] alloc_retire=(state==RETIRE && cmd_ready) ? (4'b0001<<target_slot) : 4'd0;
    wire [3:0] alloc_source=state==RELEASE_SEND ? slot_sources[4*release_lane+:4] : held_event.source_id;
    wire [3:0] alloc_channel=state==RELEASE_SEND ? slot_channels[4*release_lane+:4] : held_event.channel;
    wire [7:0] alloc_note=state==RELEASE_SEND ? slot_notes[8*release_lane+:8] : {1'b0,held_event.note_number};
    // Do not dispatch a new event until pending release/retirement is committed.
    assign dispatch_busy=rst_n && (state!=IDLE || release_valid || retire_valid);
    assign event_ready=rst_n && state==IDLE && sample_owner_ready && !release_valid && !retire_valid;
    assign active_voice_count={31'd0,slot_occupied[0]}+{31'd0,slot_occupied[1]}+
                              {31'd0,slot_occupied[2]}+{31'd0,slot_occupied[3]};
    always_comb begin
        match_valid=0;match_slot=0;retire_valid=0;retire_slot=0;
        for(integer i=0;i<4;i++)begin
            if(!match_valid && slot_occupied[i] &&
               slot_sources[4*i+:4]==held_event.source_id &&
               slot_channels[4*i+:4]==held_event.channel &&
               slot_notes[8*i+:8]=={1'b0,held_event.note_number})begin
                match_valid=1;match_slot=i[1:0];
            end
            if(!retire_valid && retire_pending[i] && retire_generation[i]==slot_generation[i] && slot_occupied[i] && slot_releasing[i])begin
                retire_valid=1;retire_slot=i[1:0];
            end
        end
        cmd_valid=0;cmd_type=SUSTAIN_CMD_NOTE_ON;
        case(state)
            CTRL_ON:begin cmd_valid=1;cmd_type=SUSTAIN_CMD_NOTE_ON;end
            CTRL_OFF:begin cmd_valid=1;cmd_type=SUSTAIN_CMD_NOTE_OFF;end
            CTRL_PEDAL:begin cmd_valid=1;cmd_type=SUSTAIN_CMD_PEDAL;end
            CTRL_PANIC:begin cmd_valid=1;cmd_type=SUSTAIN_CMD_PANIC;end
            RETIRE:begin cmd_valid=1;cmd_type=SUSTAIN_CMD_RETIRE;end
            default:begin end
        endcase
    end
    assign release_ready=rst_n && state==RELEASE_ACK;
    m1td_sustain_controller u_sustain(
        .clk(clk),.rst_n(rst_n),.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),
        .cmd_type(cmd_type),.cmd_slot(target_slot),
        .cmd_source_id((state==CTRL_ON || state==CTRL_OFF || state==RETIRE) ? slot_sources[4*target_slot+:4] : held_event.source_id),
        .cmd_channel((state==CTRL_ON || state==CTRL_OFF || state==RETIRE) ? slot_channels[4*target_slot+:4] : held_event.channel),
        .cmd_note_number(slot_notes[8*target_slot+:7]),
        .cmd_control_value(held_event.control_value),.cmd_generation(slot_generation[target_slot]),
        .release_valid(release_valid),.release_ready(release_ready),
        .release_mask(release_mask),.release_generations(release_generations),
        .occupied_mask(controller_occupied),.key_down_mask(controller_keys),
        .deferred_mask(controller_deferred),.releasing_mask(controller_releasing));
    m1td_note_pitch u_pitch(.note_number(held_event.note_number),.phase_step(held_fcw));
    m1td_voice_allocator_4 u_allocator(
        .sys_clk(clk),.sys_rst_n(rst_n),.note_on(state==ALLOC_SEND),
        .note_off(state==RELEASE_SEND && release_matches),
        .source_id(alloc_source),.channel_id(alloc_channel),.midi_note(alloc_note),
        .release_done(alloc_retire),.allocated_slot(allocated_slot),.slot_valid(slot_valid),
        .release_slot(release_slot),.release_target_valid(release_target_valid));
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;held_event<='0;target_slot<=0;release_index<=0;
            slot_note_on<=0;slot_note_off<=0;slot_occupied<=0;slot_releasing<=0;
            slot_velocity<=0;slot_fcw<=0;slot_notes<=0;slot_sources<=0;slot_channels<=0;
            retire_pending<=0;slot_timbre<=0;
            for(integer i=0;i<4;i++)begin slot_generation[i]<=0;retire_generation[i]<=0;end
        end else begin
            slot_note_on<=0;slot_note_off<=0;
            for(integer i=0;i<4;i++)begin
                if(release_done[i] && slot_occupied[i] && slot_releasing[i])begin
                    retire_pending[i]<=1;retire_generation[i]<=slot_generation[i];
                end
            end
            case(state)
                IDLE:begin
                    if(release_valid)begin release_index<=0;state<=RELEASE_SCAN;end
                    else if(retire_valid)begin target_slot<=retire_slot;state<=RETIRE;end
                    else if(event_valid && event_ready)begin
                        held_event<=incoming;
                        state<=DECODE_EVENT;
                    end
                end
                // Ingress edge captures only held_event. Decode/matching starts
                // from that register on the next edge, cutting the external
                // accepted_event_data/reset/arbiter cone before target_slot CE.
                DECODE_EVENT:begin
                        if(held_event.event_type==EVENT_NOTE_ON && held_event.velocity!=0)state<=ALLOC_SEND;
                        else if(held_event.event_type==EVENT_NOTE_OFF ||
                                (held_event.event_type==EVENT_NOTE_ON && held_event.velocity==0))begin
                            if(match_valid)begin target_slot<=match_slot;state<=CTRL_OFF;end
                            else state<=IGNORE_EVENT;
                        end else if(held_event.event_type==EVENT_CONTROL_CHANGE && held_event.control_id==CTRL_VOICE_SELECT && held_event.control_value<=1)state<=CTRL_TIMBRE;
                        else if(held_event.event_type==EVENT_CONTROL_CHANGE && held_event.control_id==CTRL_SUSTAIN)state<=CTRL_PEDAL;
                        else if(held_event.event_type==EVENT_ALL_NOTES_OFF)state<=CTRL_PANIC;
                        else state<=IGNORE_EVENT;
                end
                ALLOC_SEND:state<=ALLOC_APPLY;
                ALLOC_APPLY:if(slot_valid)begin
                    target_slot<=allocated_slot;retire_pending[allocated_slot]<=0;
                    slot_occupied[allocated_slot]<=1;slot_releasing[allocated_slot]<=0;
                    slot_velocity[10*allocated_slot+:10]<=held_event.velocity;
                    slot_fcw[32*allocated_slot+:32]<=held_fcw;
                    slot_timbre[allocated_slot]<=program_timbre[{held_event.source_id,held_event.channel}];
                    slot_notes[8*allocated_slot+:8]<={1'b0,held_event.note_number};
                    slot_sources[4*allocated_slot+:4]<=held_event.source_id;
                    slot_channels[4*allocated_slot+:4]<=held_event.channel;
                    slot_generation[allocated_slot]<=slot_generation[allocated_slot]+1'b1;
                    state<=CTRL_ON;
                end
                CTRL_ON:if(cmd_ready)begin slot_note_on[target_slot]<=1;state<=IDLE;end
                CTRL_TIMBRE:state<=IDLE;
                CTRL_OFF,CTRL_PEDAL,CTRL_PANIC:if(cmd_ready)state<=IDLE;
                RELEASE_SCAN:begin
                    if(release_index==4)state<=RELEASE_ACK;
                    else if(release_matches && !slot_releasing[release_lane])state<=RELEASE_SEND;
                    else release_index<=release_index+1'b1;
                end
                RELEASE_SEND:state<=RELEASE_APPLY;
                RELEASE_APPLY:begin
                    if(release_target_valid && release_slot==release_lane && release_matches)begin
                        slot_note_off[release_slot]<=1;slot_releasing[release_slot]<=1;
                    end
                    release_index<=release_index+1'b1;state<=RELEASE_SCAN;
                end
                RELEASE_ACK,IGNORE_EVENT:state<=IDLE;
                RETIRE:if(cmd_ready)begin
                    slot_occupied[target_slot]<=0;slot_releasing[target_slot]<=0;
                    retire_pending[target_slot]<=0;state<=IDLE;
                end
                default:state<=IDLE;
            endcase
        end
    end
    // BEGIN M1_OBSERVER_R06_LOGIC
    // Only these diagnostic registers are new. Nothing below feeds the router,
    // allocator, sustain controller, voice, or sample-owner functional logic.
    // An ingress tag identifies accepted event order, not apply count. Multiple
    // operations may carry one tag. Its unsigned 32-bit counter wraps modulo
    // 2**32; consumers must not claim unique correlation over a wrap in one epoch.
    logic [31:0] obs_next_event_seq_r;
    logic [31:0] obs_held_event_seq_r;
    logic obs_held_event_seq_valid_r;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            obs_next_event_seq_r <= 32'd0;
            obs_held_event_seq_r <= 32'd0;
            obs_held_event_seq_valid_r <= 1'b0;
        end else if (event_valid && event_ready) begin
            obs_held_event_seq_r <= obs_next_event_seq_r;
            obs_next_event_seq_r <= obs_next_event_seq_r + 32'd1;
            obs_held_event_seq_valid_r <= 1'b1;
        end
    end

    // Kind values are a versioned diagnostic contract, not performance events.
    // 0 NONE, 1 ALLOC_COMMIT, 2 NOTE_ON_CONSUME, 3 RELEASE_COMMIT,
    // 4 NOTE_OFF_CONSUME, 5 PROGRAM_COMMIT, 6 CONTROL_ACCEPT,
    // 7 IGNORE, 8 RETIRE. All predicates describe this pre-NBA edge.
    wire obs_alloc_commit_w = rst_n && state == ALLOC_APPLY && slot_valid;
    wire obs_note_on_consume_w = rst_n && (|slot_note_on);
    wire obs_release_commit_w = rst_n && state == RELEASE_APPLY &&
        release_target_valid && release_slot == release_lane && release_matches;
    wire obs_note_off_consume_w = rst_n && (|slot_note_off);
    wire obs_program_commit_w = rst_n && state == CTRL_TIMBRE;
    wire obs_control_accept_w = rst_n && cmd_ready &&
        (state == CTRL_OFF || state == CTRL_PEDAL || state == CTRL_PANIC);
    wire obs_ignore_w = rst_n && state == IGNORE_EVENT;
    wire obs_retire_w = rst_n && state == RETIRE && cmd_ready;

    assign obs_apply_kind = obs_alloc_commit_w ? 4'd1 :
        obs_note_on_consume_w ? 4'd2 : obs_release_commit_w ? 4'd3 :
        obs_note_off_consume_w ? 4'd4 : obs_program_commit_w ? 4'd5 :
        obs_control_accept_w ? 4'd6 : obs_ignore_w ? 4'd7 :
        obs_retire_w ? 4'd8 : 4'd0;
    assign obs_apply_valid = |obs_apply_kind;
    assign obs_apply_mask = obs_alloc_commit_w ? (4'b0001 << allocated_slot) :
        obs_note_on_consume_w ? slot_note_on :
        obs_release_commit_w ? (4'b0001 << release_slot) :
        obs_note_off_consume_w ? slot_note_off :
        (obs_control_accept_w && state == CTRL_OFF) ? (4'b0001 << target_slot) :
        obs_retire_w ? (4'b0001 << target_slot) : 4'd0;
    assign obs_retire_mask = obs_retire_w ? (4'b0001 << target_slot) : 4'd0;

    // Delayed sustain releases have no immutable original-event cause tag in
    // the frozen source. Do not borrow the current held_event for them. Their
    // mask/identity are real, but data/seq are invalid (zero sentinel only).
    // Autonomous retirement likewise has no original performance-event token.
    wire obs_original_event_w = obs_alloc_commit_w || obs_note_on_consume_w ||
        obs_program_commit_w || obs_control_accept_w || obs_ignore_w;
    assign obs_apply_data = obs_original_event_w ? held_event : 64'd0;
    assign obs_apply_seq_valid = obs_original_event_w && obs_held_event_seq_valid_r;
    assign obs_apply_seq = obs_apply_seq_valid ? obs_held_event_seq_r : 32'd0;
    // END M1_OBSERVER_R06_LOGIC
endmodule
