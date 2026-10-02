// M2 independent resource/internalSTA probe; NEVER PROGRAM generated FS.
// Small external scan interface, arbitrary payload can address all256 states.
// Same wrapper/observed payload for baseline and sequential candidates.
module control_snapshot_timing_probe #(
    parameter integer SERIALIZED=1
)(
    input logic sys_clk,sys_rst_n,
    input logic scan_load,
    input logic [15:0] scan_data,
    input logic drive_event,drive_request,drive_ready,
    input logic [4:0] observe_index,
    output logic [15:0] observed,
    output wire event_ready,request_ready,snapshot_valid,
    output wire control_applied,invalid_range
);
    wire rst_n;
    reset_sync u_reset(.clk(sys_clk),.rst_n(sys_rst_n),.rst_sync_n(rst_n));
    logic [259:0] stimulus;
    always_ff @(posedge sys_clk or negedge rst_n)
        if(!rst_n)stimulus<=0;
        else if(scan_load)stimulus<={stimulus[243:0],scan_data};
    // Identical observation wrapper for both variants. Seven-tap cyclic XOR
    // is invertible for260 bits (gcd(7,260)=1), so ALL input payloads remain
    // reachable. Avoid direct shiftFF->labelFF copies dominating hold analysis.
    // This is a probe input generator, not a production input encoding scheme.
    wire [259:0] decoded;
    for(genvar i=0;i<260;i++)begin:g_probe_decode
        assign decoded[i]=stimulus[i]^stimulus[(i+1)%260]^stimulus[(i+2)%260]^
            stimulus[(i+3)%260]^stimulus[(i+4)%260]^stimulus[(i+5)%260]^stimulus[(i+6)%260];
    end
    wire [63:0] event_data=decoded[63:0];
    wire [31:0] request_id=decoded[95:64];
    wire [3:0] occupied=decoded[99:96];
    wire [15:0] sources=decoded[115:100],channels=decoded[131:116];
    wire [127:0] generations=decoded[259:132];
    wire [31:0] sid;
    wire [3:0] soccupied;
    wire [15:0] ssources,schannels;
    wire [127:0] sgenerations;
    wire [47:0] pitch,mod;
    wire [19:0] range_value;
    if(SERIALIZED)begin:g_serial
        performance_control_snapshot u_controls(
            .clk(sys_clk),.rst_n(rst_n),.event_valid(drive_event),.event_ready(event_ready),.event_data(event_data),
            .request_valid(drive_request),.request_ready(request_ready),.request_id(request_id),
            .slot_occupied(occupied),.slot_source_ids(sources),.slot_channels(channels),.slot_generations(generations),
            .snapshot_valid(snapshot_valid),.snapshot_ready(drive_ready),.snapshot_id(sid),
            .snapshot_occupied(soccupied),.snapshot_sources(ssources),.snapshot_channels(schannels),
            .snapshot_generations(sgenerations),.snapshot_pitch_bend(pitch),.snapshot_modulation(mod),
            .snapshot_pitch_range(range_value),.control_applied(control_applied),.invalid_range(invalid_range));
    end else begin:g_parallel
        logic pending;
        assign event_ready=rst_n;
        assign request_ready=rst_n && (!pending || drive_ready);
        assign snapshot_valid=pending;
        always_ff @(posedge sys_clk or negedge rst_n)
            if(!rst_n)pending<=0;
            else if(drive_request&&request_ready)pending<=1;
            else if(pending&&drive_ready)pending<=0;
        performance_control_state u_controls(
            .clk(sys_clk),.rst_n(rst_n),.accepted_valid(drive_event&&event_ready),.accepted_data(event_data),
            .slot_occupied(occupied),.slot_source_ids(sources),.slot_channels(channels),.slot_generations(generations),
            .sample_capture(drive_request&&request_ready),.sample_id(request_id),
            .slot_pitch_bend(),.slot_modulation(),.slot_pitch_range(),.snapshot_valid(),.snapshot_id(sid),
            .snapshot_occupied(soccupied),.snapshot_sources(ssources),.snapshot_channels(schannels),
            .snapshot_generations(sgenerations),.snapshot_pitch_bend(pitch),.snapshot_modulation(mod),
            .snapshot_pitch_range(range_value),.control_applied(control_applied),.invalid_range(invalid_range));
    end
    wire [319:0] readback={8'd0,sid,soccupied,ssources,schannels,sgenerations,pitch,mod,range_value};
    always_comb begin
        observed=0;
        if(observe_index<20)observed=readback[16*observe_index+:16];
    end
endmodule
