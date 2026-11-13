// Coherent serialized control snapshot; no event writes during reads.
// Current M1 inactive-lane metadata defaults; live identity table itself persists.
// Single clk, asynchronous active-low reset; upstream synchronizes release.
module m2_polyphony_control_snapshot #(parameter integer N=8, SW=$clog2(N)) (
    input logic clk,rst_n,
    input logic event_valid,
    output wire event_ready,
    input logic [63:0] event_data,
    input logic request_valid,
    output wire request_ready,
    input logic [31:0] request_id,
    input logic [N-1:0] slot_occupied,
    input logic [N*4-1:0] slot_source_ids,slot_channels,
    input logic [N*32-1:0] slot_generations,
    output logic snapshot_valid,
    input logic snapshot_ready,
    output logic [31:0] snapshot_id,
    output logic [N-1:0] snapshot_occupied,
    output logic [N*4-1:0] snapshot_sources,snapshot_channels,
    output logic [N*32-1:0] snapshot_generations,
    output logic [N*12-1:0] snapshot_pitch_bend,snapshot_modulation,
    output logic [N*5-1:0] snapshot_pitch_range,
    output logic control_applied,invalid_range
);
    import audio_defs_pkg::*;
    localparam logic [28:0] DEFAULT_WORD={5'd2,12'd0,12'd0};
    wire performance_event_t incoming=event_data;
    logic [28:0] control_mem [0:255]; // packed range/mod/Pitch, ONE shared read
    logic [255:0] initialized;
    logic write_pending;
    logic [7:0] pending_identity;
    logic [28:0] pending_word;
    logic busy;
    logic [SW-1:0] read_slot;
    logic issuing, lookup_valid, write_valid;
    logic [7:0] lookup_identity;
    logic lookup_occupied;
    logic [N-1:0] issue_lane, lookup_lane, write_lane;
    logic [28:0] snapshot_word;
    wire [7:0] event_identity={incoming.source_id,incoming.channel};
    // The slot identity table is stable while the owner holds a snapshot
    // request.  Read one live lane per cycle; copying all N lanes at request
    // acceptance created a 1,312-bit clock-enable/data cone at N=32.
    wire [7:0] read_identity=busy ? lookup_identity : event_identity;
    wire [28:0] raw_word=control_mem[read_identity];
    // Forward the queued write to back-to-back updates and to the first
    // lane of a snapshot accepted on the same edge as a control event.
    wire [28:0] stored_word=write_pending && pending_identity==read_identity ? pending_word :
        initialized[read_identity] ? raw_word : DEFAULT_WORD;
    wire accepted_event=event_valid && event_ready;
    wire accepted_request=request_valid && request_ready;
    wire pitch_field=incoming.event_type==EVENT_PITCH_BEND && incoming.control_id==CTRL_PITCH_BEND;
    wire mod_field=incoming.event_type==EVENT_CONTROL_CHANGE && incoming.control_id==CTRL_MODULATION;
    wire range_field=incoming.event_type==EVENT_CONTROL_CHANGE && incoming.control_id==CTRL_PITCH_RANGE;
    wire apply_pitch=accepted_event && pitch_field;
    wire apply_mod=accepted_event && mod_field;
    wire range_event=accepted_event && range_field;
    wire apply_range=range_event && incoming.control_value<=24;
    wire reject_range=range_event && incoming.control_value>24;
    logic [28:0] write_word;
    // A request may replace an output only when that output handshakes.
    assign event_ready=!busy;
    assign request_ready=!busy && (!snapshot_valid || snapshot_ready);
    always_comb begin
        write_word=stored_word;
        if(pitch_field)write_word[11:0]=incoming.control_value;
        if(mod_field)write_word[23:12]=incoming.control_value;
        if(range_field)write_word[28:24]=incoming.control_value[4:0];
    end
    // RAM is never cleared/reset. initialized provides the logical reset defaults
    // and guards every read, including the first partial-field update after reset.
    // This separates reset semantics from data-storage inference, allowing one
    // async read port and one synchronous write, never four replicated read ports.
    always_ff @(posedge clk)begin
        if(write_pending)
            control_mem[pending_identity]<=pending_word;
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            initialized<=0;busy<=0;read_slot<=0;write_pending<=0;pending_identity<=0;pending_word<=0;
            control_applied<=0;invalid_range<=0;
            issuing<=0;lookup_valid<=0;write_valid<=0;
            issue_lane<=0;lookup_lane<=0;write_lane<=0;
            lookup_identity<=0;lookup_occupied<=0;snapshot_word<=DEFAULT_WORD;
            snapshot_valid<=0;snapshot_id<=0;snapshot_occupied<=0;
            snapshot_sources<=0;snapshot_channels<=0;snapshot_generations<=0;
            snapshot_pitch_bend<=0;snapshot_modulation<=0;snapshot_pitch_range<={N{5'd2}};
        end else begin
            control_applied<=apply_pitch || apply_mod || apply_range;
            invalid_range<=reject_range;
            write_pending<=apply_pitch || apply_mod || apply_range;
            if(!busy) begin pending_identity<=event_identity;pending_word<=write_word;end
            if(apply_pitch || apply_mod || apply_range)initialized[event_identity]<=1;
            if(snapshot_valid && snapshot_ready)snapshot_valid<=0;
            if(accepted_request)begin
                // Simultaneous control update at E writes the RAM before reads,
                // so every matching slot observes the newly accepted value.
                snapshot_valid<=0;snapshot_id<=request_id;read_slot<=0;busy<=1;
                issuing<=1;issue_lane<={{(N-1){1'b0}},1'b1};
            end
            // Separate lane identity selection, RAM access and lane write.
            // Each stage can accept one lane per cycle. The result remains
            // fenced until the final write, two cycles later than before.
            lookup_valid<=issuing;
            if(issuing)begin
                lookup_identity<={slot_source_ids[4*read_slot+:4],slot_channels[4*read_slot+:4]};
                lookup_occupied<=slot_occupied[read_slot];
                lookup_lane<=issue_lane;
                issue_lane<=issue_lane<<1;
                if(read_slot==N-1)issuing<=0;
                else read_slot<=read_slot+1'b1;
            end
            write_valid<=lookup_valid;
            if(lookup_valid)begin
                snapshot_word<=lookup_occupied ? stored_word : DEFAULT_WORD;
                write_lane<=lookup_lane;
            end
            if(write_valid)begin
                for(integer i=0;i<N;i++)begin
                    if(write_lane[i])begin
                        snapshot_pitch_bend[12*i+:12]<=snapshot_word[11:0];
                        snapshot_modulation[12*i+:12]<=snapshot_word[23:12];
                        snapshot_pitch_range[5*i+:5]<=snapshot_word[28:24];
                    end
                end
                if(write_lane[N-1])begin busy<=0;snapshot_valid<=1;end
            end
        end
    end
endmodule
