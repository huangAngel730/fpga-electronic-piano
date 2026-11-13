// N-slot structural successor, current M1 Program0/1 and NoteOn latch semantics.
// rst_n asserts asynchronously and is synchronously released by caller.
// One accepted event is held until the registered allocator result is applied.
// event_ready applies backpressure while dispatching; sample_owner_ready lets
// the PCM scheduler defer events during an in-flight sample generation.
`timescale 1ns/1ps
module m2_polyphony_event_router #(parameter integer N=8, SW=$clog2(N)) (
    input logic clk, rst_n, sample_owner_ready,
    input logic event_valid,
    output wire event_ready, dispatch_busy,
    output logic note_pulse_valid,
    input logic [63:0] event_data,
    input logic [N-1:0] release_done,
    output logic [N-1:0] slot_note_on, slot_note_off, slot_occupied, slot_releasing,
    output logic [N*10-1:0] slot_velocity,
    output logic [N*32-1:0] slot_fcw,
    output logic [N*8-1:0] slot_notes,
    output logic [N-1:0] slot_timbre,
    output wire [31:0] active_voice_count,
    output wire [N*4-1:0] slot_source_ids, slot_channel_ids,
    output wire [N*32-1:0] slot_generations,
    output logic [31:0] identity_epoch
);
    import audio_defs_pkg::*;
    import sustain_control_contract_pkg::*;
    localparam logic [4:0] IDLE=0, ALLOC_SEND=1, ALLOC_APPLY=2,
        CTRL_ON=3, CTRL_OFF=4, CTRL_PEDAL=5, CTRL_PANIC=6,
        RELEASE_SCAN=7, RELEASE_SEND=8, RELEASE_APPLY=9,
        RELEASE_ACK=10, RETIRE=11, IGNORE_EVENT=12, CTRL_TIMBRE=13,
        ALLOC_GENERATION=14, ALLOC_COMMIT=15, EVENT_DECODE=16,
        MATCH_SCAN=17, ALLOC_INCREMENT=18;
    logic [4:0] state;
    performance_event_t held_event;
    wire performance_event_t incoming=event_data;
    logic [N*4-1:0] slot_sources,slot_channels;
    logic program_timbre [0:255];
    logic [31:0] slot_generation [0:N-1];
    logic [31:0] alloc_generation_q;
    // M2 candidate: exported registered identity, no functional routing change.
    assign slot_source_ids=slot_sources;
    assign slot_channel_ids=slot_channels;
    for(genvar identity_lane=0;identity_lane<N;identity_lane++) begin:g_identity
        assign slot_generations[32*identity_lane+:32]=slot_generation[identity_lane];
    end
    logic [N-1:0] retire_pending;
    logic [31:0] retire_generation [0:N-1];
    logic [SW-1:0] target_slot;
    logic [SW:0] release_index;
    logic [SW-1:0] release_lane_q;
    logic [SW-1:0] retire_scan_index;
    logic [SW-1:0] match_scan_index;
    logic [N-1:0] match_scan_onehot;
    logic match_lane_now;
    logic [SW-1:0] match_lane_value;
    logic retire_valid;
    logic [SW-1:0] retire_slot;
    logic cmd_valid,cmd_ready,release_valid,release_ready;
    logic [2:0] cmd_type;
    wire [N-1:0] release_mask;
    wire [N*32-1:0] release_generations;
    wire [N-1:0] controller_occupied,controller_keys,controller_deferred,controller_releasing;
    wire is_release_slot=release_index<N;
    wire [SW-1:0] release_lane=release_index[SW-1:0];
    wire release_matches=is_release_slot && release_mask[release_lane] &&
        slot_occupied[release_lane] &&
        slot_generation[release_lane]==release_generations[32*release_lane+:32];
    wire [SW-1:0] allocated_slot,release_slot;
    wire slot_valid,release_target_valid;
    wire [31:0] held_fcw;
    wire [N-1:0] alloc_retire=(state==RETIRE && cmd_ready) ? ( {{(N-1){1'b0}},1'b1} << target_slot) : {N{1'b0}};
    wire [3:0] alloc_source=state==RELEASE_SEND ? slot_sources[4*release_lane_q+:4] : held_event.source_id;
    wire [3:0] alloc_channel=state==RELEASE_SEND ? slot_channels[4*release_lane_q+:4] : held_event.channel;
    wire [7:0] alloc_note=state==RELEASE_SEND ? slot_notes[8*release_lane_q+:8] : {1'b0,held_event.note_number};
    // Do not dispatch a new event until pending release/retirement is committed.
    assign dispatch_busy=state!=IDLE || release_valid || retire_valid;
    assign event_ready=state==IDLE && sample_owner_ready && !release_valid && !retire_valid;
    // Allocation and retirement are serialized by this state machine, so a
    // small registered population count is exact.  This replaces the former
    // 32-input, 32-bit combinational adder chain on the status path.
    logic [SW:0] active_count;
    assign active_voice_count=32'(active_count);
    always_comb begin
        match_lane_now=1'b0;match_lane_value='0;
        for(integer i=0;i<N;i++)begin
            if(match_scan_onehot[i] && slot_occupied[i] &&
               slot_sources[4*i+:4]==held_event.source_id &&
               slot_channels[4*i+:4]==held_event.channel &&
               slot_notes[8*i+:8]=={1'b0,held_event.note_number})begin
                match_lane_now=1'b1;match_lane_value=i[SW-1:0];
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
    assign release_ready=state==RELEASE_ACK;
    m2_polyphony_sustain_controller #(.N(N)) u_sustain(
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
    m2_polyphony_voice_allocator #(.N(N)) u_allocator(
        .sys_clk(clk),.sys_rst_n(rst_n),.note_on(state==ALLOC_SEND),
        .note_off(state==RELEASE_SEND),
        .source_id(alloc_source),.channel_id(alloc_channel),.midi_note(alloc_note),
        .release_done(alloc_retire),.allocated_slot(allocated_slot),.slot_valid(slot_valid),
        .release_slot(release_slot),.release_target_valid(release_target_valid));
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;held_event<='0;target_slot<=0;release_index<=0;release_lane_q<=0;
            match_scan_index<=0;match_scan_onehot<={{(N-1){1'b0}},1'b1};
            retire_scan_index<=0;retire_valid<=0;retire_slot<=0;
            note_pulse_valid<=0;
            slot_note_on<=0;slot_note_off<=0;slot_occupied<=0;slot_releasing<=0;
            slot_velocity<=0;slot_fcw<=0;slot_notes<=0;slot_sources<=0;slot_channels<=0;
            retire_pending<=0;slot_timbre<=0;identity_epoch<=0;active_count<=0;
            alloc_generation_q<=0;
            for(integer p=0;p<256;p++) program_timbre[p]<=0;
            for(integer i=0;i<N;i++)begin slot_generation[i]<=0;retire_generation[i]<=0;end
        end else begin
            note_pulse_valid<=0;
            slot_note_on<=0;slot_note_off<=0;
            // Bound retirement detection to one registered 32-bit identity
            // comparison per clock.  This removes the N-lane generation cone
            // from event_ready and the upstream FIFO enables while preserving
            // the existing retirement priority at IDLE.
            if(!retire_valid)begin
                if(retire_pending[retire_scan_index] &&
                   retire_generation[retire_scan_index]==slot_generation[retire_scan_index] &&
                   slot_occupied[retire_scan_index] && slot_releasing[retire_scan_index])begin
                    retire_valid<=1'b1;
                    retire_slot<=retire_scan_index;
                end
                if(retire_scan_index==N-1)retire_scan_index<=0;
                else retire_scan_index<=retire_scan_index+1'b1;
            end
            for(integer i=0;i<N;i++)begin
                if(release_done[i] && slot_occupied[i] && slot_releasing[i])begin
                    retire_pending[i]<=1;retire_generation[i]<=slot_generation[i];
                end
            end
            case(state)
                IDLE:begin
                    if(release_valid)begin release_index<=0;state<=RELEASE_SCAN;end
                    else if(retire_valid)begin
                        target_slot<=retire_slot;retire_valid<=1'b0;state<=RETIRE;
                    end
                    else if(event_valid && event_ready)begin
                        held_event<=incoming;
                        // Decode only the registered payload on the following
                        // cycle.  The upstream FIFO count/data no longer drive
                        // the router state D cone through the full decoder.
                        state<=EVENT_DECODE;
                    end
                end
                EVENT_DECODE:begin
                        if(held_event.event_type==EVENT_NOTE_ON && held_event.velocity!=0)state<=ALLOC_SEND;
                        else if(held_event.event_type==EVENT_NOTE_OFF ||
                                (held_event.event_type==EVENT_NOTE_ON && held_event.velocity==0))begin
                            match_scan_index<=0;
                            match_scan_onehot<={{(N-1){1'b0}},1'b1};
                            state<=MATCH_SCAN;
                        end else if(held_event.event_type==EVENT_CONTROL_CHANGE && held_event.control_id==CTRL_SUSTAIN)state<=CTRL_PEDAL;
                        else if(held_event.event_type==EVENT_ALL_NOTES_OFF)state<=CTRL_PANIC;
                        else if(held_event.event_type==EVENT_CONTROL_CHANGE &&
                                held_event.control_id==CTRL_VOICE_SELECT && held_event.control_value<=1)
                            state<=CTRL_TIMBRE;
                        else state<=IGNORE_EVENT;
                end
                ALLOC_SEND:state<=ALLOC_APPLY;
                MATCH_SCAN:begin
                    if(match_lane_now)begin
                        target_slot<=match_lane_value;
                        state<=CTRL_OFF;
                    end else if(match_scan_index==N-1)begin
                        state<=IGNORE_EVENT;
                    end else begin
                        match_scan_index<=match_scan_index+1'b1;
                        match_scan_onehot<=match_scan_onehot<<1;
                    end
                end
                ALLOC_APPLY:if(slot_valid)begin
                    target_slot<=allocated_slot;
                    state<=ALLOC_GENERATION;
                end
                // First register the selected lane, then read its generation
                // into a scalar.  Increment that scalar on the following
                // cycle so the 32-lane read mux and the 32-bit carry chain are
                // never on the same timing path.
                ALLOC_GENERATION:begin
                    alloc_generation_q<=slot_generation[target_slot];
                    state<=ALLOC_INCREMENT;
                end
                ALLOC_INCREMENT:begin
                    alloc_generation_q<=alloc_generation_q+1'b1;
                    state<=ALLOC_COMMIT;
                end
                ALLOC_COMMIT:begin
                    retire_pending[target_slot]<=0;
                    slot_occupied[target_slot]<=1;slot_releasing[target_slot]<=0;
                    slot_velocity[10*target_slot+:10]<=held_event.velocity;
                    slot_fcw[32*target_slot+:32]<=held_fcw;
                    slot_notes[8*target_slot+:8]<={1'b0,held_event.note_number};
                    slot_timbre[target_slot]<=program_timbre[{held_event.source_id,held_event.channel}];
                    slot_sources[4*target_slot+:4]<=held_event.source_id;
                    slot_channels[4*target_slot+:4]<=held_event.channel;
                    slot_generation[target_slot]<=alloc_generation_q;
                    identity_epoch<=identity_epoch+1'b1;
                    active_count<=active_count+1'b1;
                    state<=CTRL_ON;
                end
                CTRL_TIMBRE:begin
                    program_timbre[{held_event.source_id,held_event.channel}]<=held_event.control_value[0];
                    state<=IDLE;
                end
                CTRL_ON:if(cmd_ready)begin
                    note_pulse_valid<=1;slot_note_on[target_slot]<=1;state<=IDLE;
                end
                CTRL_OFF,CTRL_PEDAL,CTRL_PANIC:if(cmd_ready)state<=IDLE;
                RELEASE_SCAN:begin
                    if(release_index==N)state<=RELEASE_ACK;
                    else if(release_matches && !slot_releasing[release_lane])begin
                        release_lane_q<=release_lane;
                        state<=RELEASE_SEND;
                    end
                    else release_index<=release_index+1'b1;
                end
                RELEASE_SEND:state<=RELEASE_APPLY;
                // The N32 allocator now performs one identity comparison per
                // cycle.  Hold the release lane stable until its registered
                // result arrives instead of rebuilding a 32-lane compare cone.
                RELEASE_APPLY:if(release_target_valid)begin
                    if(release_slot==release_lane_q)begin
                        note_pulse_valid<=1;slot_note_off[release_slot]<=1;slot_releasing[release_slot]<=1;
                    end
                    release_index<=release_index+1'b1;state<=RELEASE_SCAN;
                end
                RELEASE_ACK,IGNORE_EVENT:state<=IDLE;
                RETIRE:if(cmd_ready)begin
                    slot_occupied[target_slot]<=0;slot_releasing[target_slot]<=0;
                    retire_pending[target_slot]<=0;identity_epoch<=identity_epoch+1'b1;
                    active_count<=active_count-1'b1;
                    state<=IDLE;
                end
                default:state<=IDLE;
            endcase
        end
    end
endmodule
