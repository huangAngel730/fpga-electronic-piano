// N-slot successor of the frozen M1 CC64 lifecycle contract. Not an R10 repair.
// Single clk domain. rst_n asserts asynchronously; upstream synchronizes release.
// This module delays Release requests, never freezes or computes an ADSR curve.
`timescale 1ns / 1ps


module m2_polyphony_sustain_controller #(parameter integer N=8, SW=$clog2(N)) (
    input wire clk, rst_n,
    input wire cmd_valid,
    output wire cmd_ready,
    input wire [2:0] cmd_type,
    input wire [SW-1:0] cmd_slot,
    input wire [3:0] cmd_source_id, cmd_channel,
    input wire [6:0] cmd_note_number,
    input wire [11:0] cmd_control_value,
    input wire [31:0] cmd_generation,
    output wire release_valid,
    input wire release_ready,
    output wire [N-1:0] release_mask,
    output wire [N*32-1:0] release_generations,
    output wire [N-1:0] occupied_mask, key_down_mask, deferred_mask, releasing_mask
);
    import sustain_control_contract_pkg::*;

    logic [255:0] pedal_down;
    logic [N-1:0] occupied, key_down, deferred, releasing;
    logic [N-1:0] pending_mask;
    logic [N*32-1:0] pending_generations;
    logic [3:0] source_mem [0:N-1];
    logic [3:0] channel_mem [0:N-1];
    logic [6:0] note_mem [0:N-1];
    logic [31:0] generation_mem [0:N-1];
    logic command_busy, release_pending_valid, scan_found_release;
    logic [2:0] pending_type;
    logic [SW-1:0] scan_index;
    logic [N-1:0] scan_onehot;
    logic [3:0] pending_source, pending_channel;
    logic [6:0] pending_note;
    logic [11:0] pending_control;
    logic [31:0] pending_generation;
    logic pending_pedal_down;
    logic pending_identity_match;
    logic [N-1:0] pending_source_channel_match;
    wire [7:0] pending_pedal_index={pending_source,pending_channel};
    wire single_lane_command=pending_type==SUSTAIN_CMD_NOTE_ON ||
        pending_type==SUSTAIN_CMD_NOTE_OFF || pending_type==SUSTAIN_CMD_RETIRE;
    logic release_lane_now;
    integer slot_index;

    // Commands are first captured into a narrow register set.  A one-hot scan
    // then touches one constant lane per cycle, avoiding the cmd_slot dynamic
    // decode and the former N-lane pedal/panic write cone.
    assign release_valid = release_pending_valid;
    assign release_mask = pending_mask;
    assign release_generations = pending_generations;
    assign cmd_ready = !release_pending_valid && !command_busy;
    assign occupied_mask = occupied;
    assign key_down_mask = key_down;
    assign deferred_mask = deferred;
    assign releasing_mask = releasing;

    always_comb begin
        release_lane_now=1'b0;
        for(integer lane=0;lane<N;lane=lane+1) begin
            if(scan_onehot[lane]) begin
                case(pending_type)
                    SUSTAIN_CMD_NOTE_OFF:
                        release_lane_now=pending_identity_match &&
                            key_down[lane] && !releasing[lane] &&
                            !pending_pedal_down;
                    SUSTAIN_CMD_PEDAL:
                        release_lane_now=pending_control<SUSTAIN_DOWN_THRESHOLD &&
                            occupied[lane] && !key_down[lane] &&
                            deferred[lane] && !releasing[lane] &&
                            pending_source_channel_match[lane];
                    SUSTAIN_CMD_PANIC:
                        release_lane_now=occupied[lane] && !releasing[lane];
                    default: release_lane_now=1'b0;
                endcase
            end
        end
    end

    // Pending release payload remains immutable until acknowledged.  Commands
    // that can touch all lanes are serialized; note commands use a captured
    // one-hot lane and therefore complete in one processing cycle.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pedal_down <= '0;
            occupied <= '0;
            key_down <= '0;
            deferred <= '0;
            releasing <= '0;
            pending_mask <= '0;
            pending_generations <= '0;
            command_busy<=1'b0;release_pending_valid<=1'b0;
            scan_found_release<=1'b0;pending_type<='0;scan_index<='0;
            scan_onehot<='0;pending_source<='0;pending_channel<='0;
            pending_note<='0;pending_control<='0;pending_generation<='0;
            pending_pedal_down<=1'b0;
            pending_identity_match<=1'b0;
            pending_source_channel_match<='0;
            for (slot_index = 0; slot_index < N; slot_index = slot_index + 1) begin
                source_mem[slot_index] <= '0;
                channel_mem[slot_index] <= '0;
                note_mem[slot_index] <= '0;
                generation_mem[slot_index] <= '0;
            end
        end else if (release_pending_valid) begin
            if (release_ready) begin
                pending_mask <= '0;
                pending_generations <= '0;
                release_pending_valid<=1'b0;
            end
        end else if (!command_busy) begin
            if(cmd_valid && cmd_ready) begin
                pending_type<=cmd_type;pending_source<=cmd_source_id;
                pending_channel<=cmd_channel;pending_note<=cmd_note_number;
                pending_control<=cmd_control_value;pending_generation<=cmd_generation;
                // Freeze the addressed pedal bit with the command.  This
                // avoids a 256-to-1 dynamic select feeding every slot update
                // while preserving the value observed on command acceptance.
                pending_pedal_down<=pedal_down[{cmd_source_id,cmd_channel}];
                // Identity is stable while command_busy is set.  Register the
                // full comparison at acceptance so the following state update
                // is driven by one bit, not by a 47-bit compare cone.
                pending_identity_match<=occupied[cmd_slot] &&
                    source_mem[cmd_slot]==cmd_source_id &&
                    channel_mem[cmd_slot]==cmd_channel &&
                    note_mem[cmd_slot]==cmd_note_number &&
                    generation_mem[cmd_slot]==cmd_generation;
                for(slot_index=0;slot_index<N;slot_index=slot_index+1)
                    pending_source_channel_match[slot_index]<=
                        source_mem[slot_index]==cmd_source_id &&
                        channel_mem[slot_index]==cmd_channel;
                scan_index<=(cmd_type==SUSTAIN_CMD_NOTE_ON ||
                    cmd_type==SUSTAIN_CMD_NOTE_OFF || cmd_type==SUSTAIN_CMD_RETIRE) ? cmd_slot : '0;
                scan_onehot<=(cmd_type==SUSTAIN_CMD_NOTE_ON ||
                    cmd_type==SUSTAIN_CMD_NOTE_OFF || cmd_type==SUSTAIN_CMD_RETIRE) ?
                    ({{(N-1){1'b0}},1'b1}<<cmd_slot) : {{(N-1){1'b0}},1'b1};
                scan_found_release<=1'b0;pending_mask<='0;pending_generations<='0;
                command_busy<=1'b1;
            end
        end else begin
            if(pending_type==SUSTAIN_CMD_PEDAL && scan_index=='0)
                pedal_down[pending_pedal_index]<=pending_control>=SUSTAIN_DOWN_THRESHOLD;
            if(pending_type==SUSTAIN_CMD_PANIC && scan_index=='0)
                pedal_down<='0;

            for(slot_index=0;slot_index<N;slot_index=slot_index+1) begin
                if(scan_onehot[slot_index]) begin
                    case(pending_type)
                        SUSTAIN_CMD_NOTE_ON: begin
                            occupied[slot_index]<=1'b1;key_down[slot_index]<=1'b1;
                            deferred[slot_index]<=1'b0;releasing[slot_index]<=1'b0;
                            source_mem[slot_index]<=pending_source;
                            channel_mem[slot_index]<=pending_channel;
                            note_mem[slot_index]<=pending_note;
                            generation_mem[slot_index]<=pending_generation;
                        end
                        SUSTAIN_CMD_NOTE_OFF: begin
                            if(pending_identity_match && key_down[slot_index] &&
                               !releasing[slot_index]) begin
                                key_down[slot_index]<=1'b0;
                                if(pending_pedal_down)
                                    deferred[slot_index]<=1'b1;
                                else begin
                                    deferred[slot_index]<=1'b0;releasing[slot_index]<=1'b1;
                                    pending_mask[slot_index]<=1'b1;
                                    pending_generations[32*slot_index+:32]<=generation_mem[slot_index];
                                end
                            end
                        end
                        SUSTAIN_CMD_PEDAL: if(release_lane_now) begin
                            deferred[slot_index]<=1'b0;releasing[slot_index]<=1'b1;
                            pending_mask[slot_index]<=1'b1;
                            pending_generations[32*slot_index+:32]<=generation_mem[slot_index];
                        end
                        SUSTAIN_CMD_RETIRE: begin
                            if(pending_identity_match && releasing[slot_index]) begin
                                occupied[slot_index]<=1'b0;key_down[slot_index]<=1'b0;
                                deferred[slot_index]<=1'b0;releasing[slot_index]<=1'b0;
                                source_mem[slot_index]<='0;channel_mem[slot_index]<='0;
                                note_mem[slot_index]<='0;generation_mem[slot_index]<='0;
                            end
                        end
                        SUSTAIN_CMD_PANIC: if(release_lane_now) begin
                            key_down[slot_index]<=1'b0;deferred[slot_index]<=1'b0;
                            releasing[slot_index]<=1'b1;pending_mask[slot_index]<=1'b1;
                            pending_generations[32*slot_index+:32]<=generation_mem[slot_index];
                        end
                        default: begin end
                    endcase
                end
            end

            if(release_lane_now)scan_found_release<=1'b1;
            if(single_lane_command || scan_index==N-1) begin
                command_busy<=1'b0;scan_onehot<='0;
                if(scan_found_release || release_lane_now)release_pending_valid<=1'b1;
            end else begin
                scan_index<=scan_index+1'b1;
                scan_onehot<=scan_onehot<<1;
            end
        end
    end
endmodule
