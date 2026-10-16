// Include inside module sustain_controller (...); default four slots fixed.
// Implementation belongs to M3; this file is M2's agreed port declaration.
`ifndef SUSTAIN_CONTROLLER_PORTS_SVH
`define SUSTAIN_CONTROLLER_PORTS_SVH
`define SUSTAIN_CONTROLLER_PORTS \
    input wire clk, rst_n, \
    input wire cmd_valid, \
    output wire cmd_ready, \
    input wire [2:0] cmd_type, \
    input wire [1:0] cmd_slot, \
    input wire [3:0] cmd_source_id, cmd_channel, \
    input wire [6:0] cmd_note_number, \
    input wire [11:0] cmd_control_value, \
    input wire [31:0] cmd_generation, \
    output wire release_valid, \
    input wire release_ready, \
    output wire [3:0] release_mask, \
    output wire [127:0] release_generations, \
    output wire [3:0] occupied_mask, key_down_mask, deferred_mask, releasing_mask
`endif
