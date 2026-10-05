// T024 M2 event/allocator integration only: no sample arithmetic or new clocks.
// rst_n asserts asynchronously and is synchronously released by caller.
// One accepted event is held until the registered allocator result is applied.
// event_ready applies backpressure while dispatching; sample_owner_ready lets
// the PCM scheduler defer events during an in-flight sample generation.
`timescale 1ns/1ps
module polyphonic_event_router (
    input logic clk, rst_n, sample_owner_ready,
    input logic identity_hold, // private sample lease; queues retirement, does not discard it
    input logic event_valid,
    output wire event_ready, dispatch_busy,
    input logic [63:0] event_data,
    input logic [3:0] release_done,
    output logic [3:0] slot_note_on, slot_note_off, slot_occupied, slot_releasing,
    output logic [39:0] slot_velocity,
    output logic [127:0] slot_fcw,
    output logic [31:0] slot_notes,
    output wire [31:0] active_voice_count,
    output wire [15:0] slot_source_ids, slot_channel_ids,
    output wire [127:0] slot_generations
);
    import audio_defs_pkg::*;
    import sustain_control_contract_pkg::*;
    localparam logic [3:0] IDLE=0, ALLOC_SEND=1, ALLOC_APPLY=2,
        CTRL_ON=3, CTRL_OFF=4, CTRL_PEDAL=5, CTRL_PANIC=6,
        RELEASE_SCAN=7, RELEASE_SEND=8, RELEASE_APPLY=9,
        RELEASE_ACK=10, RETIRE=11, IGNORE_EVENT=12;
    logic [3:0] state;
    performance_event_t held_event;
    wire performance_event_t incoming=event_data;
    logic [15:0] slot_sources,slot_channels;
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
    assign dispatch_busy=rst_n && (state!=IDLE || (!identity_hold && (release_valid || retire_valid)));
    assign event_ready=rst_n && state==IDLE && sample_owner_ready && !identity_hold && !release_valid && !retire_valid;
    assign active_voice_count={31'd0,slot_occupied[0]}+{31'd0,slot_occupied[1]}+
                              {31'd0,slot_occupied[2]}+{31'd0,slot_occupied[3]};
    always_comb begin
        match_valid=0;match_slot=0;retire_valid=0;retire_slot=0;
        for(integer i=0;i<4;i++)begin
            if(!match_valid && slot_occupied[i] &&
               slot_sources[4*i+:4]==incoming.source_id &&
               slot_channels[4*i+:4]==incoming.channel &&
               slot_notes[8*i+:8]=={1'b0,incoming.note_number})begin
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
    sustain_controller u_sustain(
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
    note_pitch u_pitch(.note_number(held_event.note_number),.phase_step(held_fcw));
    voice_allocator_4 u_allocator(
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
            retire_pending<=0;
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
                    if(!identity_hold && release_valid)begin release_index<=0;state<=RELEASE_SCAN;end
                    else if(!identity_hold && retire_valid)begin target_slot<=retire_slot;state<=RETIRE;end
                    else if(event_valid && event_ready)begin
                        held_event<=incoming;
                        if(incoming.event_type==EVENT_NOTE_ON && incoming.velocity!=0)state<=ALLOC_SEND;
                        else if(incoming.event_type==EVENT_NOTE_OFF ||
                                (incoming.event_type==EVENT_NOTE_ON && incoming.velocity==0))begin
                            if(match_valid)begin target_slot<=match_slot;state<=CTRL_OFF;end
                            else state<=IGNORE_EVENT;
                        end else if(incoming.event_type==EVENT_CONTROL_CHANGE && incoming.control_id==CTRL_SUSTAIN)state<=CTRL_PEDAL;
                        else if(incoming.event_type==EVENT_ALL_NOTES_OFF)state<=CTRL_PANIC;
                        else state<=IGNORE_EVENT;
                    end
                end
                ALLOC_SEND:state<=ALLOC_APPLY;
                ALLOC_APPLY:if(slot_valid)begin
                    target_slot<=allocated_slot;retire_pending[allocated_slot]<=0;
                    slot_occupied[allocated_slot]<=1;slot_releasing[allocated_slot]<=0;
                    slot_velocity[10*allocated_slot+:10]<=held_event.velocity;
                    slot_fcw[32*allocated_slot+:32]<=held_fcw;
                    slot_notes[8*allocated_slot+:8]<={1'b0,held_event.note_number};
                    slot_sources[4*allocated_slot+:4]<=held_event.source_id;
                    slot_channels[4*allocated_slot+:4]<=held_event.channel;
                    slot_generation[allocated_slot]<=slot_generation[allocated_slot]+1'b1;
                    state<=CTRL_ON;
                end
                CTRL_ON:if(cmd_ready)begin slot_note_on[target_slot]<=1;state<=IDLE;end
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
endmodule
