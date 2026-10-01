// Standalone observability wrapper, not a production top or pin assignment.
// Keep all 256 identities addressable and observe every state bit by a scan.
module performance_control_probe(
    input logic sys_clk,sys_rst_n,accepted_valid,sample_capture,
    input logic [63:0] accepted_data,
    input logic [3:0] occupied,
    input logic [15:0] sources,channels,
    input logic [7:0] observe_index,
    output logic [15:0] observed,
    output wire valid,applied,rejected
);
    logic [31:0] cycle_id;
    always_ff @(posedge sys_clk or negedge sys_rst_n)
        if(!sys_rst_n)cycle_id<=0;else cycle_id<=cycle_id+1'b1;
    wire [47:0] pitch,mod,snap_pitch,snap_mod;
    wire [19:0] range_value,snap_range;
    wire [31:0] snap_id;
    wire [3:0] snap_occupied;
    wire [15:0] snap_sources,snap_channels;
    wire [127:0] snap_generations;
    wire [127:0] generations={cycle_id+32'd3,cycle_id+32'd2,cycle_id+32'd1,cycle_id};
    performance_control_state u_controls(.clk(sys_clk),.rst_n(sys_rst_n),
        .accepted_valid(accepted_valid),.accepted_data(accepted_data),
        .slot_occupied(occupied),.slot_source_ids(sources),.slot_channels(channels),
        .slot_generations(generations),.sample_capture(sample_capture),.sample_id(cycle_id),
        .slot_pitch_bend(pitch),.slot_modulation(mod),.slot_pitch_range(range_value),
        .snapshot_valid(valid),.snapshot_id(snap_id),.snapshot_occupied(snap_occupied),
        .snapshot_sources(snap_sources),.snapshot_channels(snap_channels),
        .snapshot_generations(snap_generations),.snapshot_pitch_bend(snap_pitch),
        .snapshot_modulation(snap_mod),.snapshot_pitch_range(snap_range),
        .control_applied(applied),.invalid_range(rejected));
    // Lower428 bits are meaningful; assignment zero-extends the high16 bits.
    wire [639:0] readback={196'd0,pitch,mod,range_value,snap_pitch,snap_mod,snap_range,
                        snap_id,snap_occupied,snap_sources,snap_channels,snap_generations};
    always_comb begin
        observed=0;
        if(observe_index<40)observed=readback[16*observe_index+:16];
    end
endmodule
