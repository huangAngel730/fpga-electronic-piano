`timescale 1ns/1ps
// Public control snapshot -> actual B1 identity bank, no hierarchical forcing.
module tb_m2_n8_identity_alias;
    localparam N=8,SW=3;
    logic clk=0,rst_n=0,event_valid=0,request_valid=0,snapshot_ready=0;
    always #12.5 clk=~clk;
    logic [63:0] event_data=0;
    logic [N-1:0] slot_occupied=0;
    logic [4*N-1:0] slot_source_ids=0,slot_channels=0;
    logic [32*N-1:0] slot_generations=0;
    wire event_ready,request_ready,snapshot_valid;
    wire [31:0] snapshot_id;
    wire [N-1:0] snapshot_occupied;
    wire [4*N-1:0] snapshot_sources,snapshot_channels;
    wire [32*N-1:0] snapshot_generations;
    wire [12*N-1:0] snapshot_pitch_bend,snapshot_modulation;
    wire [5*N-1:0] snapshot_pitch_range;
    b2c_control_snapshot #(.N(N)) controls(
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .request_valid(request_valid),.request_ready(request_ready),.request_id(32'd7),
        .slot_occupied(slot_occupied),.slot_source_ids(slot_source_ids),.slot_channels(slot_channels),
        .slot_generations(slot_generations),.snapshot_valid(snapshot_valid),.snapshot_ready(snapshot_ready),
        .snapshot_id(snapshot_id),.snapshot_occupied(snapshot_occupied),.snapshot_sources(snapshot_sources),
        .snapshot_channels(snapshot_channels),.snapshot_generations(snapshot_generations),
        .snapshot_pitch_bend(snapshot_pitch_bend),.snapshot_modulation(snapshot_modulation),
        .snapshot_pitch_range(snapshot_pitch_range),.control_applied(),.invalid_range());
    logic cfg_we=0,ctl_we=0,rd_en=0;
    logic [SW-1:0] cfg_slot=0,rd_slot=0;
    wire [7:0] identity={snapshot_sources[4*cfg_slot+:4],snapshot_channels[4*cfg_slot+:4]};
    wire [28:0] ctl_value={snapshot_pitch_range[5*cfg_slot+:5],
                          snapshot_modulation[12*cfg_slot+:12],snapshot_pitch_bend[12*cfg_slot+:12]};
    wire initialized,rd_valid;
    wire [28:0] rd_control;
    wire [1:0] rd_flags;
    b1_statebank #(.N(N),.CW(74)) bank(
        .clk(clk),.rst_n(rst_n),.clear(1'b0),.cfg_we(cfg_we),.cfg_slot(cfg_slot),
        .cfg_identity({identity,32'd1}),.cfg_flags({1'b0,snapshot_occupied[cfg_slot]}),.cfg_context(74'd0),
        .ctl_we(ctl_we),.ctl_identity(identity),.ctl_value(ctl_value),.ctl_pedal(1'b0),
        .initialized(initialized),.rd_en(rd_en),.rd_slot(rd_slot),.rd_valid(rd_valid),
        .rd_identity(),.rd_flags(rd_flags),.rd_context(),.rd_control(rd_control),.rd_pedal(),
        .result_we(1'b0),.result_slot(SW'(0)),.result_context(74'd0),.publish(1'b0));
    integer k,mode;
    task automatic send(input integer typ,ctl,value_in);
        @(negedge clk);event_data={3'(typ),4'hf,4'hf,7'd0,10'd0,10'd0,8'(ctl),12'(value_in),6'd0};event_valid=1;
        while(!event_ready) @(negedge clk);
        @(negedge clk);event_valid=0;
    endtask
    task automatic read_check(input integer lane);
        @(negedge clk);rd_slot=SW'(lane);rd_en=1;
        @(posedge clk);#1;
        if(!rd_valid || !rd_flags[0] || rd_control!={5'd5,12'd4080,12'd2047})
            $fatal(1,"N8_ACTIVE_IDENTITY_CONTROL_CLOBBER mode=%0d lane=%0d actual=%h",mode,lane,rd_control);
        @(negedge clk);rd_en=0;
    endtask
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        send(3,0,2047);send(4,1,4080);send(4,4,5);
        slot_source_ids[12+:4]=15;slot_channels[12+:4]=15;
        slot_source_ids[28+:4]=15;slot_channels[28+:4]=15;
        for(mode=0;mode<3;mode=mode+1) begin
            @(negedge clk);slot_occupied=mode==0 ? 8'h08 : mode==1 ? 8'h80 : 8'h88;
            request_valid=1;while(!request_ready) @(negedge clk);
            @(negedge clk);request_valid=0;
            while(!snapshot_valid) @(negedge clk);
            for(k=0;k<N;k=k+1) begin
                @(negedge clk);cfg_slot=SW'(k);ctl_we=1;
                @(negedge clk);ctl_we=0;cfg_we=1;
                @(negedge clk);cfg_we=0;
            end
            if(!initialized) $fatal(1,"B2D_BANK_NOT_INITIALIZED");
            if(slot_occupied[3]) read_check(3);
            if(slot_occupied[7]) read_check(7);
            $display("IDENTITY_ALIAS_CASE_PASS mode=%0d mask=%h",mode,slot_occupied);
            @(negedge clk);snapshot_ready=1;@(negedge clk);snapshot_ready=0;
        end
        $display("N8_IDENTITY_ALIAS_PASS cases=3 active_reads=4");$finish;
    end
    initial begin #1000000;$fatal(1,"B2D_ALIAS_WATCHDOG");end
endmodule
