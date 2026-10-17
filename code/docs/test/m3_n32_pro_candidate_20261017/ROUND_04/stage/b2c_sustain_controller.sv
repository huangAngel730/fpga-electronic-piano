// Four-slot CC64 lifecycle controller, M2 contract 2026-10-01 / v1.6.
// Single clk domain. rst_n asserts asynchronously; upstream synchronizes release.
// This module delays Release requests, never freezes or computes an ADSR curve.
`timescale 1ns / 1ps


module b2c_sustain_controller #(parameter integer N=8, SW=$clog2(N)) (
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
    wire [7:0] pedal_index = {cmd_source_id, cmd_channel};
    wire identity_matches = occupied[cmd_slot] &&
        source_mem[cmd_slot] == cmd_source_id &&
        channel_mem[cmd_slot] == cmd_channel &&
        note_mem[cmd_slot] == cmd_note_number &&
        generation_mem[cmd_slot] == cmd_generation;
    integer slot_index;

    assign release_valid = |pending_mask;
    assign release_mask = pending_mask;
    assign release_generations = pending_generations;
    assign cmd_ready = rst_n && !release_valid;
    assign occupied_mask = occupied;
    assign key_down_mask = key_down;
    assign deferred_mask = deferred;
    assign releasing_mask = releasing;

    // Pending payload is immutable until acknowledged. Even an ACK edge cannot
    // accept a command: ready depends on the pre-edge pending state.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pedal_down <= '0;
            occupied <= '0;
            key_down <= '0;
            deferred <= '0;
            releasing <= '0;
            pending_mask <= '0;
            pending_generations <= '0;
            for (slot_index = 0; slot_index < N; slot_index = slot_index + 1) begin
                source_mem[slot_index] <= '0;
                channel_mem[slot_index] <= '0;
                note_mem[slot_index] <= '0;
                generation_mem[slot_index] <= '0;
            end
        end else if (release_valid) begin
            if (release_ready) begin
                pending_mask <= '0;
                pending_generations <= '0;
            end
        end else if (cmd_valid && cmd_ready) begin
            case (cmd_type)
                SUSTAIN_CMD_NOTE_ON: begin
                    occupied[cmd_slot] <= 1'b1;
                    key_down[cmd_slot] <= 1'b1;
                    deferred[cmd_slot] <= 1'b0;
                    releasing[cmd_slot] <= 1'b0;
                    source_mem[cmd_slot] <= cmd_source_id;
                    channel_mem[cmd_slot] <= cmd_channel;
                    note_mem[cmd_slot] <= cmd_note_number;
                    generation_mem[cmd_slot] <= cmd_generation;
                end
                SUSTAIN_CMD_NOTE_OFF: begin
                    if (identity_matches && key_down[cmd_slot] &&
                        !releasing[cmd_slot]) begin
                        key_down[cmd_slot] <= 1'b0;
                        if (pedal_down[pedal_index]) begin
                            deferred[cmd_slot] <= 1'b1;
                        end else begin
                            deferred[cmd_slot] <= 1'b0;
                            releasing[cmd_slot] <= 1'b1;
                            pending_mask[cmd_slot] <= 1'b1;
                            pending_generations[32*cmd_slot +: 32] <=
                                generation_mem[cmd_slot];
                        end
                    end
                end
                SUSTAIN_CMD_PEDAL: begin
                    pedal_down[pedal_index] <=
                        cmd_control_value >= SUSTAIN_DOWN_THRESHOLD;
                    if (cmd_control_value < SUSTAIN_DOWN_THRESHOLD) begin
                        for (slot_index = 0; slot_index < N;
                             slot_index = slot_index + 1) begin
                            if (occupied[slot_index] && !key_down[slot_index] &&
                                deferred[slot_index] && !releasing[slot_index] &&
                                source_mem[slot_index] == cmd_source_id &&
                                channel_mem[slot_index] == cmd_channel) begin
                                deferred[slot_index] <= 1'b0;
                                releasing[slot_index] <= 1'b1;
                                pending_mask[slot_index] <= 1'b1;
                                pending_generations[32*slot_index +: 32] <=
                                    generation_mem[slot_index];
                            end
                        end
                    end
                end
                SUSTAIN_CMD_RETIRE: begin
                    if (identity_matches && releasing[cmd_slot]) begin
                        occupied[cmd_slot] <= 1'b0;
                        key_down[cmd_slot] <= 1'b0;
                        deferred[cmd_slot] <= 1'b0;
                        releasing[cmd_slot] <= 1'b0;
                        source_mem[cmd_slot] <= '0;
                        channel_mem[cmd_slot] <= '0;
                        note_mem[cmd_slot] <= '0;
                        generation_mem[cmd_slot] <= '0;
                    end
                end
                SUSTAIN_CMD_PANIC: begin
                    pedal_down <= '0;
                    key_down <= '0;
                    deferred <= '0;
                    for (slot_index = 0; slot_index < N;
                         slot_index = slot_index + 1) begin
                        if (occupied[slot_index] && !releasing[slot_index]) begin
                            releasing[slot_index] <= 1'b1;
                            pending_mask[slot_index] <= 1'b1;
                            pending_generations[32*slot_index +: 32] <=
                                generation_mem[slot_index];
                        end
                    end
                end
                default: begin
                    // Reserved command encodings 5..7 have no effect.
                end
            endcase
        end
    end
endmodule
