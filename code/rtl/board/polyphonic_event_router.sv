// T024 M2 event/allocator integration only: no sample arithmetic or new clocks.
// rst_n asserts asynchronously and is synchronously released by caller.
// One accepted event is held until the registered allocator result is applied.
// event_ready applies backpressure while dispatching; sample_owner_ready lets
// the PCM scheduler defer events during an in-flight sample generation.
`timescale 1ns/1ps
module polyphonic_event_router (
    input logic clk, rst_n, sample_owner_ready,
    input logic event_valid,
    output wire event_ready, dispatch_busy,
    input logic [63:0] event_data,
    input logic [3:0] release_done,
    output logic [3:0] slot_note_on, slot_note_off, slot_occupied, slot_releasing,
    output logic [39:0] slot_velocity,
    output logic [127:0] slot_fcw,
    output logic [31:0] slot_notes,
    output wire [31:0] active_voice_count
);
    import audio_defs_pkg::*;
    localparam logic [2:0] IDLE=0, SEND=1, APPLY=2, ALL_SEND=3;
    logic [2:0] state;
    performance_event_t held_event;
    wire performance_event_t incoming = event_data;
    logic [15:0] slot_sources, slot_channels;
    logic [1:0] all_index;
    wire is_on = held_event.event_type == EVENT_NOTE_ON && held_event.velocity != 0;
    wire is_off = held_event.event_type == EVENT_NOTE_OFF ||
                 (held_event.event_type == EVENT_NOTE_ON && held_event.velocity == 0);
    // Frozen ALL_NOTES_OFF is a global panic, not a channel-scoped command.
    wire all_match = slot_occupied[all_index] && !slot_releasing[all_index];
    wire [3:0] alloc_source = state == ALL_SEND ? slot_sources[4*all_index+:4] : held_event.source_id;
    wire [3:0] alloc_channel = state == ALL_SEND ? slot_channels[4*all_index+:4] : held_event.channel;
    wire alloc_on = state == SEND && is_on;
    wire alloc_off = (state == SEND && is_off) || (state == ALL_SEND && all_match);
    wire [7:0] alloc_note = state == ALL_SEND ? slot_notes[8*all_index+:8] : {1'b0,held_event.note_number};
    wire [1:0] allocated_slot, release_slot;
    wire slot_valid, release_target_valid;
    wire [31:0] held_fcw;
    assign dispatch_busy = rst_n && state != IDLE;
    assign event_ready = rst_n && state == IDLE && sample_owner_ready;
    assign active_voice_count = {31'd0,slot_occupied[0]} + {31'd0,slot_occupied[1]} +
                               {31'd0,slot_occupied[2]} + {31'd0,slot_occupied[3]};
    note_pitch u_pitch(.note_number(held_event.note_number),.phase_step(held_fcw));
    voice_allocator_4 u_allocator (
        .sys_clk(clk),.sys_rst_n(rst_n),.note_on(alloc_on),.note_off(alloc_off),
        .source_id(alloc_source),.channel_id(alloc_channel),.midi_note(alloc_note),
        .release_done(release_done),.allocated_slot(allocated_slot),.slot_valid(slot_valid),
        .release_slot(release_slot),.release_target_valid(release_target_valid)
    );
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; held_event<='0; all_index<=0;
            slot_note_on<=0;slot_note_off<=0;slot_occupied<=0;slot_releasing<=0;
            slot_velocity<=0;slot_fcw<=0;slot_notes<=0;slot_sources<=0;slot_channels<=0;
        end else begin
            slot_note_on<=0;slot_note_off<=0;
            for(integer i=0;i<4;i=i+1) begin
                if(release_done[i] && slot_releasing[i]) begin
                    slot_occupied[i]<=0;slot_releasing[i]<=0;
                end
            end
            case(state)
              IDLE: if(event_valid && event_ready) begin
                  held_event<=incoming;
                  if(incoming.event_type==EVENT_ALL_NOTES_OFF) begin all_index<=0;state<=ALL_SEND;end
                  else state<=SEND;
              end
              SEND: state<=APPLY;
              ALL_SEND: state<=APPLY;
              APPLY: begin
                  if(slot_valid) begin
                      slot_note_on[allocated_slot]<=1;
                      slot_occupied[allocated_slot]<=1;slot_releasing[allocated_slot]<=0;
                      slot_velocity[10*allocated_slot+:10]<=held_event.velocity;
                      slot_fcw[32*allocated_slot+:32]<=held_fcw;
                      slot_notes[8*allocated_slot+:8]<={1'b0,held_event.note_number};
                      slot_sources[4*allocated_slot+:4]<=held_event.source_id;
                      slot_channels[4*allocated_slot+:4]<=held_event.channel;
                  end
                  if(release_target_valid) begin
                      slot_note_off[release_slot]<=1;slot_releasing[release_slot]<=1;
                  end
                  if(held_event.event_type==EVENT_ALL_NOTES_OFF && all_index!=3) begin
                      all_index<=all_index+1'b1;state<=ALL_SEND;
                  end else state<=IDLE;
              end
              default: state<=IDLE;
            endcase
        end
    end
endmodule