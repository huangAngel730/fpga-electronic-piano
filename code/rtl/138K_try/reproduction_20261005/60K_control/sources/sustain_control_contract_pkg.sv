// M2/M3 standalone sustain contract. NOT enabled in formal MIDI parser yet.
// CC64 ID/value helpers now use the released v1.6 public package.
// PROPOSED symbol name is retained solely for existing M3 contract callers.
package sustain_control_contract_pkg;
    localparam logic [7:0] SUSTAIN_CTRL_ID_PROPOSED = audio_defs_pkg::CTRL_SUSTAIN;
    localparam logic [11:0] SUSTAIN_DOWN_THRESHOLD = 12'd2048;
    localparam logic [2:0] SUSTAIN_CMD_NOTE_ON = 3'd0;
    localparam logic [2:0] SUSTAIN_CMD_NOTE_OFF = 3'd1;
    localparam logic [2:0] SUSTAIN_CMD_PEDAL = 3'd2;
    localparam logic [2:0] SUSTAIN_CMD_RETIRE = 3'd3;
    localparam logic [2:0] SUSTAIN_CMD_PANIC = 3'd4;
    function automatic logic [11:0] sustain_value_from_midi(input logic [6:0] value);
        return audio_defs_pkg::midi_cc_to_12bit(value);
    endfunction
endpackage
