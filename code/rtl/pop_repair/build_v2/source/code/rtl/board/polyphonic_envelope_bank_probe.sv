// Independent internal STA harness. No physical pins are assigned; never program.
// Runtime view selects every bank result field so synthesis retains each lane.
module polyphonic_envelope_bank_probe (
    input logic clk,rst_n,event_valid,frame_tick,sample_req,result_ready,
    input logic [63:0] event_data,
    input logic [31:0] sample_req_id,
    input logic [3:0] view,
    output wire event_ready,calc_ready,result_valid,
    output logic [31:0] observed
);
    wire [31:0] result_req_id,active_voice_count;
    wire [63:0] result_envelopes,result_waves;
    wire [127:0] result_fcw;
    wire [3:0] result_occupied;
    wire [11:0] result_states;
    polyphonic_envelope_bank u_bank(.*);
    always_comb begin
        case(view)
          0:observed=result_req_id;
          1:observed=active_voice_count;
          2:observed=result_envelopes[31:0];
          3:observed=result_envelopes[63:32];
          4:observed=result_waves[31:0];
          5:observed=result_waves[63:32];
          6:observed=result_fcw[31:0];
          7:observed=result_fcw[63:32];
          8:observed=result_fcw[95:64];
          9:observed=result_fcw[127:96];
          10:observed={16'd0,result_states,result_occupied};
          default:observed=0;
        endcase
    end
endmodule