// M2 independent serialized control-read candidate, NOT in formal GPRJ.
// One50MHz clk, async reset assert/synchronous deassert supplied upstream.
// Event and request streams have independent valid/ready handshakes.
// Four reads are atomic: no event update accepted from E+1 through E+4.
// Accepted request at E -> all-four output valid at E+4; held until ready.
module m1td_performance_control_snapshot (
    input logic clk,rst_n,
    input logic event_valid,
    output wire event_ready,
    input logic [63:0] event_data,
    input logic request_valid,
    output wire request_ready,
    input logic [31:0] request_id,
    input logic [3:0] slot_occupied,
    input logic [15:0] slot_source_ids,slot_channels,
    input logic [127:0] slot_generations,
    output logic snapshot_valid,
    input logic snapshot_ready,
    output logic [31:0] snapshot_id,
    output logic [3:0] snapshot_occupied,
    output logic [15:0] snapshot_sources,snapshot_channels,
    output logic [127:0] snapshot_generations,
    output logic [47:0] snapshot_pitch_bend,snapshot_modulation,
    output logic [19:0] snapshot_pitch_range,
    output logic control_applied,invalid_range
);
    import audio_defs_pkg::*;
    localparam logic [28:0] DEFAULT_WORD={5'd2,12'd0,12'd0};
    wire performance_event_t incoming=event_data;
    logic [28:0] control_mem [0:255]; // packed range/mod/Pitch, ONE shared read
    logic [255:0] initialized;
    logic busy;
    logic [1:0] read_slot;
    wire [7:0] event_identity={incoming.source_id,incoming.channel};
    wire [7:0] read_identity=busy ?
        {snapshot_sources[4*read_slot+:4],snapshot_channels[4*read_slot+:4]} : event_identity;
    wire [28:0] raw_word=control_mem[read_identity];
    wire [28:0] stored_word=initialized[read_identity] ? raw_word : DEFAULT_WORD;
    wire accepted_event=event_valid && event_ready;
    wire accepted_request=request_valid && request_ready;
    wire apply_pitch=accepted_event && incoming.event_type==EVENT_PITCH_BEND && incoming.control_id==CTRL_PITCH_BEND;
    wire apply_mod=accepted_event && incoming.event_type==EVENT_CONTROL_CHANGE && incoming.control_id==CTRL_MODULATION;
    wire range_event=accepted_event && incoming.event_type==EVENT_CONTROL_CHANGE && incoming.control_id==CTRL_PITCH_RANGE;
    wire apply_range=range_event && incoming.control_value<=24;
    wire reject_range=range_event && incoming.control_value>24;
    // R05: preserve the request-ID capture edge; only this consumer branch
    // receives two shallow identity cells per bit. No clock or FF is added.
    (* syn_keep = 1, syn_dont_touch = 1 *) wire [31:0] request_id_hold1;
    (* syn_keep = 1, syn_dont_touch = 1 *) wire [31:0] request_id_capture;
    genvar id_bit;
    generate for (id_bit = 0; id_bit < 32; id_bit = id_bit + 1) begin : g_request_id_hold
        (* syn_keep = 1, syn_dont_touch = 1 *)
        LUT1 #(.INIT(2'b10)) u_hold1 (.I0(request_id[id_bit]), .F(request_id_hold1[id_bit]));
        (* syn_keep = 1, syn_dont_touch = 1 *)
        LUT1 #(.INIT(2'b10)) u_hold2 (.I0(request_id_hold1[id_bit]), .F(request_id_capture[id_bit]));
    end endgenerate
    logic [28:0] write_word;
    // A request may replace an output only when that output handshakes.
    assign event_ready=rst_n && !busy;
    assign request_ready=rst_n && !busy && (!snapshot_valid || snapshot_ready);
    always_comb begin
        write_word=stored_word;
        if(apply_pitch)write_word[11:0]=incoming.control_value;
        if(apply_mod)write_word[23:12]=incoming.control_value;
        if(apply_range)write_word[28:24]=incoming.control_value[4:0];
    end
    // RAM is never cleared/reset. initialized provides the logical reset defaults
    // and guards every read, including the first partial-field update after reset.
    // This separates reset semantics from data-storage inference, allowing one
    // async read port and one synchronous write, never four replicated read ports.
    always_ff @(posedge clk)begin
        if(rst_n && (apply_pitch || apply_mod || apply_range))
            control_mem[event_identity]<=write_word;
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            initialized<=0;busy<=0;read_slot<=0;
            control_applied<=0;invalid_range<=0;
            snapshot_valid<=0;snapshot_id<=0;snapshot_occupied<=0;
            snapshot_sources<=0;snapshot_channels<=0;snapshot_generations<=0;
            snapshot_pitch_bend<=0;snapshot_modulation<=0;snapshot_pitch_range<={4{5'd2}};
        end else begin
            control_applied<=apply_pitch || apply_mod || apply_range;
            invalid_range<=reject_range;
            if(apply_pitch || apply_mod || apply_range)initialized[event_identity]<=1;
            if(snapshot_valid && snapshot_ready)snapshot_valid<=0;
            if(accepted_request)begin
                // Simultaneous control update at E writes the RAM before reads,
                // so every matching slot observes the newly accepted value.
                snapshot_valid<=0;snapshot_id<=request_id_capture;snapshot_occupied<=slot_occupied;
                snapshot_sources<=slot_source_ids;snapshot_channels<=slot_channels;
                snapshot_generations<=slot_generations;read_slot<=0;busy<=1;
            end else if(busy)begin
                snapshot_pitch_bend[12*read_slot+:12]<=snapshot_occupied[read_slot] ? stored_word[11:0] : 12'd0;
                snapshot_modulation[12*read_slot+:12]<=snapshot_occupied[read_slot] ? stored_word[23:12] : 12'd0;
                snapshot_pitch_range[5*read_slot+:5]<=snapshot_occupied[read_slot] ? stored_word[28:24] : 5'd2;
                if(read_slot==3)begin busy<=0;snapshot_valid<=1;end
                else read_slot<=read_slot+1'b1;
            end
        end
    end
endmodule
