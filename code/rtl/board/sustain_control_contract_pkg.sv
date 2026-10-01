// M2/M3 standalone sustain contract. NOT enabled in formal MIDI parser yet.
// CTRL_SUSTAIN=6 is proposed from currently reserved public control IDs.
// Formal audio_defs_pkg/spec publication requires the specific group notice.
package sustain_control_contract_pkg;
    localparam logic [7:0] SUSTAIN_CTRL_ID_PROPOSED = 8'd6;
    localparam logic [11:0] SUSTAIN_DOWN_THRESHOLD = 12'd2048;
    localparam logic [2:0] SUSTAIN_CMD_NOTE_ON = 3'd0;
    localparam logic [2:0] SUSTAIN_CMD_NOTE_OFF = 3'd1;
    localparam logic [2:0] SUSTAIN_CMD_PEDAL = 3'd2;
    localparam logic [2:0] SUSTAIN_CMD_RETIRE = 3'd3;
    localparam logic [2:0] SUSTAIN_CMD_PANIC = 3'd4;
    function automatic logic [11:0] sustain_value_from_midi(input logic [6:0] value);
        return {value,value[6:2]};
    endfunction
endpackage
