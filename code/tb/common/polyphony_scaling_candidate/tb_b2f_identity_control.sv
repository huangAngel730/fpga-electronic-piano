`timescale 1ns/1ps
// N8 successor. Only public snapshot and real B1 bank ports are observed.
// One 40MHz domain, asynchronous reset asserted / released on falling edge.
module tb_b2f_identity_control;
    localparam N=8, SW=3;
    localparam [28:0] DEFAULT_WORD={5'd2,12'd0,12'd0};
    logic clk=0,rst_n=0,event_valid=0,request_valid=0,snapshot_ready=0;
    always #12.5 clk=~clk;
    logic [63:0] event_data=0;
    logic [31:0] request_id=0;
    logic [N-1:0] slot_occupied=0;
    logic [N*4-1:0] slot_source_ids=0,slot_channels=0;
    logic [N*32-1:0] slot_generations=0;
    wire event_ready,request_ready,snapshot_valid;
    wire [31:0] snapshot_id;
    wire [N-1:0] snapshot_occupied;
    wire [N*4-1:0] snapshot_sources,snapshot_channels;
    wire [N*32-1:0] snapshot_generations;
    wire [N*12-1:0] snapshot_pitch_bend,snapshot_modulation;
    wire [N*5-1:0] snapshot_pitch_range;
    b2d_control_snapshot #(.N(N)) controls(.*,.control_applied(),.invalid_range());
    logic cfg_we=0,ctl_we=0,rd_en=0;
    logic [SW-1:0] cfg_slot=0,rd_slot=0;
    wire [7:0] identity={snapshot_sources[4*cfg_slot+:4],snapshot_channels[4*cfg_slot+:4]};
    wire [28:0] ctl_value={snapshot_pitch_range[5*cfg_slot+:5],
                          snapshot_modulation[12*cfg_slot+:12],snapshot_pitch_bend[12*cfg_slot+:12]};
    wire initialized,rd_valid;
    wire [28:0] rd_control;
    wire [39:0] rd_identity;
    wire [1:0] rd_flags;
    b1_statebank #(.N(N),.CW(74)) bank(
        .clk(clk),.rst_n(rst_n),.clear(1'b0),.cfg_we(cfg_we),.cfg_slot(cfg_slot),
        .cfg_identity({identity,snapshot_generations[32*cfg_slot+:32]}),
        .cfg_flags({1'b0,snapshot_occupied[cfg_slot]}),.cfg_context(74'd0),
        .ctl_we(ctl_we),.ctl_identity(identity),.ctl_value(ctl_value),.ctl_pedal(1'b0),
        .initialized(initialized),.rd_en(rd_en),.rd_slot(rd_slot),.rd_valid(rd_valid),
        .rd_identity(rd_identity),.rd_flags(rd_flags),.rd_context(),.rd_control(rd_control),.rd_pedal(),
        .result_we(1'b0),.result_slot(3'd0),.result_context(74'd0),.publish(1'b0));
    logic [28:0] expected [0:255];
    logic [28:0] frozen [0:N-1];
    logic [N-1:0] frozen_occupied;
    logic [N*4-1:0] frozen_sources,frozen_channels;
    logic [N*32-1:0] frozen_generations;
    logic [31:0] frozen_id;
    integer cases=0,reads=0,cycle=0;
    always @(posedge clk) cycle=cycle+1;
    function automatic [63:0] ev(input integer typ,src,ch,ctl,val);
        ev={3'(typ),4'(src),4'(ch),7'd0,10'd0,10'd0,8'(ctl),12'(val),6'd0};
    endfunction
    task automatic golden_event(input integer typ,src,ch,ctl,val);
        integer id;
        id=src*16+ch;
        if(typ==3 && ctl==0) expected[id][11:0]=12'(val);
        if(typ==4 && ctl==1) expected[id][23:12]=12'(val);
        if(typ==4 && ctl==4 && val<=24) expected[id][28:24]=5'(val);
    endtask
    task automatic reset_domain;
        @(negedge clk);rst_n=0;event_valid=0;request_valid=0;snapshot_ready=0;
        cfg_we=0;ctl_we=0;rd_en=0;
        for(integer i=0;i<256;i=i+1) expected[i]=DEFAULT_WORD;
        repeat(3) @(negedge clk);
        if(snapshot_valid || request_ready || event_ready || initialized) $fatal(1,"B2F_RESET_NOT_FENCED");
        rst_n=1;
    endtask
    task automatic send(input integer typ,src,ch,ctl,val);
        @(negedge clk);event_data=ev(typ,src,ch,ctl,val);event_valid=1;
        while(!event_ready) @(negedge clk);
        @(posedge clk);golden_event(typ,src,ch,ctl,val);
        @(negedge clk);event_valid=0;
    endtask
    task automatic freeze_expected;
        frozen_occupied=slot_occupied;frozen_sources=slot_source_ids;frozen_channels=slot_channels;
        frozen_generations=slot_generations;frozen_id=request_id;
        for(integer i=0;i<N;i=i+1)
            frozen[i]=expected[{slot_source_ids[4*i+:4],slot_channels[4*i+:4]}];
    endtask
    task automatic request(input integer simultaneous);
        @(negedge clk);request_id=request_id+1;request_valid=1;
        if(simultaneous) begin event_data=ev(3,15,15,0,1234);event_valid=1;end
        while(!request_ready) @(negedge clk);
        if(simultaneous && !event_ready) $fatal(1,"B2F_SAME_EDGE_NOT_ACCEPTED");
        @(posedge clk);
        if(simultaneous) golden_event(3,15,15,0,1234);
        freeze_expected();
        @(negedge clk);request_valid=0;event_valid=0;
    endtask
    task automatic check_snapshot;
        while(!snapshot_valid) @(negedge clk);
        if(snapshot_id!==frozen_id || snapshot_occupied!==frozen_occupied ||
           snapshot_sources!==frozen_sources || snapshot_channels!==frozen_channels ||
           snapshot_generations!==frozen_generations) $fatal(1,"B2F_SNAPSHOT_IDENTITY");
`ifndef B2D_MUTANT_MASK_IDLE_CONTROL
        for(integer i=0;i<N;i=i+1)
            if({snapshot_pitch_range[5*i+:5],snapshot_modulation[12*i+:12],snapshot_pitch_bend[12*i+:12]}!==frozen[i])
                $fatal(1,"B2F_IDENTITY_CONTROL_CLOBBER case=%0d lane=%0d",cases,i);
`endif
    endtask
    task automatic bank_check;
        check_snapshot();
        // Last duplicate identity writes last, exactly as in the real wrapper.
        for(integer i=0;i<N;i=i+1) begin
            @(negedge clk);cfg_slot=SW'(i);ctl_we=1;
            @(negedge clk);ctl_we=0;cfg_we=1;
            @(negedge clk);cfg_we=0;
        end
        if(!initialized) $fatal(1,"B2F_BANK_NOT_INITIALIZED");
        for(integer i=0;i<N;i=i+1) begin
            @(negedge clk);rd_slot=SW'(i);rd_en=1;
            @(posedge clk);#1;
            if(!rd_valid || rd_flags!=={1'b0,frozen_occupied[i]} || rd_control!==frozen[i] ||
               rd_identity!=={frozen_sources[4*i+:4],frozen_channels[4*i+:4],frozen_generations[32*i+:32]})
                $fatal(1,"B2F_BANK_CONTROL_CLOBBER case=%0d lane=%0d actual=%h",cases,i,rd_control);
            reads=reads+1;
            $display("BANK %0d %0d %h %h %h",cycle,i,rd_identity,rd_flags,rd_control);
            @(negedge clk);rd_en=0;
        end
        cases=cases+1;$display("CASE %0d mask=%h",cases,frozen_occupied);
        @(negedge clk);snapshot_ready=1;@(negedge clk);snapshot_ready=0;
    endtask
    task automatic capture;
        request(0);bank_check();
    endtask
    initial begin
        for(integer i=0;i<N;i=i+1) slot_generations[32*i+:32]=32'(i+1);
        slot_source_ids[12+:4]=15;slot_channels[12+:4]=15;
        slot_source_ids[28+:4]=15;slot_channels[28+:4]=15;
        reset_domain();slot_occupied=8'h88;capture(); // uninitialized identity defaults
        send(3,15,15,0,2047);send(4,15,15,1,4080);send(4,15,15,4,5);
        send(4,15,15,4,25);capture(); // invalid range must not damage previous value
        slot_occupied=8'h08;capture(); // slot7 retires first
        slot_occupied=8'h88;capture(); // both active again
        slot_occupied=8'h80;capture(); // slot3 retires first
        // Same source / different channel, and different source / same channel.
        slot_source_ids[12+:4]=10;slot_channels[12+:4]=2;
        slot_source_ids[28+:4]=10;slot_channels[28+:4]=3;slot_occupied=8'h88;
        send(3,10,2,0,500);send(4,10,2,1,1111);send(4,10,2,4,7);
        send(3,10,3,0,3000);send(4,10,3,1,2222);send(4,10,3,4,12);capture();
        slot_source_ids[28+:4]=4;slot_channels[28+:4]=2;
        send(3,4,2,0,900);capture();
        slot_source_ids[28+:4]=15;slot_channels[28+:4]=14;capture(); // untouched f/e
        slot_source_ids[12+:4]=15;slot_channels[12+:4]=15;
        slot_channels[28+:4]=15;request(1);bank_check(); // update accepted on request edge
        // Busy event is backpressured; old snapshot stays atomic, next one sees update.
        request(0);
        @(negedge clk);event_data=ev(4,15,15,1,777);event_valid=1;
        repeat(2) begin @(negedge clk);if(event_ready) $fatal(1,"B2F_BUSY_ACCEPTED_EVENT");end
        while(!event_ready) @(negedge clk);
        @(posedge clk);golden_event(4,15,15,1,777);
        @(negedge clk);event_valid=0;
        repeat(4) begin
            check_snapshot();if(request_ready) $fatal(1,"B2F_HELD_SNAPSHOT_OVERWRITE");
            @(negedge clk);
        end
        bank_check();capture(); // next snapshot contains 777; held one did not change
        request(0);repeat(2) @(negedge clk);reset_domain();
        repeat(N+2) @(negedge clk);if(snapshot_valid) $fatal(1,"B2F_RESET_BUSY_LEAK");
        capture(); // logical defaults despite stale physical RAM
        send(4,15,15,1,333);request(0);check_snapshot();reset_domain();capture();
        $display("B2F_IDENTITY_CONTROL_PASS cases=%0d bank_reads=%0d",cases,reads);$finish;
    end
    initial begin #1000000;$fatal(1,"B2F_IDENTITY_WATCHDOG");end
endmodule
