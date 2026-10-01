// M2 independent control storage/binding candidate. NOT in formal GPRJ.
// Single clk; rst_n async assert, sync release supplied by caller.
// accepted_valid must equal an upstream event_valid && event_ready pulse.
// No MIDI decode, FCW math, LFO, PCM output, CDC or voice allocation here.
`timescale 1ns/1ps
module performance_control_state (
    input logic clk, rst_n,
    input logic accepted_valid,
    input logic [63:0] accepted_data,
    input logic [3:0] slot_occupied,
    input logic [15:0] slot_source_ids, slot_channels,
    input logic [127:0] slot_generations,
    input logic sample_capture,
    input logic [31:0] sample_id,
    output logic [47:0] slot_pitch_bend, slot_modulation,
    output logic [19:0] slot_pitch_range,
    output logic snapshot_valid,
    output logic [31:0] snapshot_id,
    output logic [3:0] snapshot_occupied,
    output logic [15:0] snapshot_sources, snapshot_channels,
    output logic [127:0] snapshot_generations,
    output logic [47:0] snapshot_pitch_bend, snapshot_modulation,
    output logic [19:0] snapshot_pitch_range,
    output logic control_applied, invalid_range
);
    import audio_defs_pkg::*;
    wire performance_event_t event_in = accepted_data;
    logic [11:0] pitch_mem [0:255]; // signed12 bit pattern; center exactly0
    logic [11:0] modulation_mem [0:255];
    logic [4:0] range_mem [0:255]; // semitones 0..24
    wire [7:0] write_identity={event_in.source_id,event_in.channel};
    wire apply_pitch=rst_n && accepted_valid &&
        event_in.event_type==EVENT_PITCH_BEND && event_in.control_id==CTRL_PITCH_BEND;
    wire apply_mod=rst_n && accepted_valid &&
        event_in.event_type==EVENT_CONTROL_CHANGE && event_in.control_id==CTRL_MODULATION;
    wire range_event=rst_n && accepted_valid &&
        event_in.event_type==EVENT_CONTROL_CHANGE && event_in.control_id==CTRL_PITCH_RANGE;
    wire apply_range=range_event && event_in.control_value<=12'd24;
    wire reject_range=range_event && event_in.control_value>12'd24;
    // Live query is the pre-edge state. A sample edge incorporates an accepted
    // same-edge control update into the whole four-lane snapshot (write-through).
    always_comb begin
        slot_pitch_bend=0;slot_modulation=0;
        slot_pitch_range={4{5'd2}};
        for(integer lane=0;lane<4;lane++)begin
            if(rst_n && slot_occupied[lane])begin
                slot_pitch_bend[12*lane+:12]=pitch_mem[{slot_source_ids[4*lane+:4],slot_channels[4*lane+:4]}];
                slot_modulation[12*lane+:12]=modulation_mem[{slot_source_ids[4*lane+:4],slot_channels[4*lane+:4]}];
                slot_pitch_range[5*lane+:5]=range_mem[{slot_source_ids[4*lane+:4],slot_channels[4*lane+:4]}];
            end
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            for(integer identity=0;identity<256;identity++)begin
                pitch_mem[identity]<=0;modulation_mem[identity]<=0;range_mem[identity]<=2;
            end
            snapshot_valid<=0;snapshot_id<=0;snapshot_occupied<=0;
            snapshot_sources<=0;snapshot_channels<=0;snapshot_generations<=0;
            snapshot_pitch_bend<=0;snapshot_modulation<=0;snapshot_pitch_range<={4{5'd2}};
            control_applied<=0;invalid_range<=0;
        end else begin
            control_applied<=apply_pitch || apply_mod || apply_range;
            invalid_range<=reject_range;
            if(apply_pitch)pitch_mem[write_identity]<=event_in.control_value;
            if(apply_mod)modulation_mem[write_identity]<=event_in.control_value;
            if(apply_range)range_mem[write_identity]<=event_in.control_value[4:0];
            // NoteOn/Off/CC64 and global all-notes-off do not reposition wheels.
            // Assignment/retrigger/release/steal is supplied by router identities.
            if(sample_capture)begin
                snapshot_valid<=1;snapshot_id<=sample_id;
                snapshot_occupied<=slot_occupied;
                snapshot_sources<=slot_source_ids;snapshot_channels<=slot_channels;
                snapshot_generations<=slot_generations;
                for(integer lane=0;lane<4;lane++)begin
                    snapshot_pitch_bend[12*lane+:12]<=slot_pitch_bend[12*lane+:12];
                    snapshot_modulation[12*lane+:12]<=slot_modulation[12*lane+:12];
                    snapshot_pitch_range[5*lane+:5]<=slot_pitch_range[5*lane+:5];
                    if(slot_occupied[lane] &&
                       {slot_source_ids[4*lane+:4],slot_channels[4*lane+:4]}==write_identity)begin
                        if(apply_pitch)snapshot_pitch_bend[12*lane+:12]<=event_in.control_value;
                        if(apply_mod)snapshot_modulation[12*lane+:12]<=event_in.control_value;
                        if(apply_range)snapshot_pitch_range[5*lane+:5]<=event_in.control_value[4:0];
                    end
                end
            end
        end
    end
endmodule
