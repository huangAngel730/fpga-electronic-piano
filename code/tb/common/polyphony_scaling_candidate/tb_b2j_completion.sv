`timescale 1ns/1ps
`ifndef B2J_N
`define B2J_N 32
`endif
`ifndef B2J_RESPONSE
`define B2J_RESPONSE 1
`endif
// New public-port observation only. Functional sources are not modified.
module tb_b2j_completion;
    localparam N=`B2J_N, RESPONSE=`B2J_RESPONSE, SW=$clog2(N), TW=72+SW;
    logic clk=0, rst_n=1, cancel=0, event_valid=0, sample_valid=0;
    logic result_ready=0, inject_valid=0, read_valid=0;
    logic [63:0] event_data=0;
    logic [31:0] sample_id=0;
    wire event_ready,sample_ready,result_valid,idle,publish,be_launch;
    wire [31:0] result_id;
    wire signed [23:0] left,right;
    integer cycle=0;
    always #12.5 clk=~clk;
    b2d_event_audio #(.N(N),.RESPONSE(RESPONSE)) dut(
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.event_valid(event_valid),
        .event_ready(event_ready),.event_data(event_data),.sample_valid(sample_valid),
        .sample_ready(sample_ready),.sample_id(sample_id),.result_valid(result_valid),
        .result_ready(result_ready),.result_id(result_id),.left(left),.right(right),
        .idle(idle),.publish(publish),.be_launch(be_launch),
        .inject_valid(inject_valid),.inject_tag({TW{1'b1}}),.inject_context(74'd0),
        .read_valid(read_valid),.read_slot({SW{1'b0}}));
    // Every edge, PRE-NBA. No hierarchy probes, force, or expected RTL values.
    always @(posedge clk) begin
        cycle=cycle+1;
        $display("T %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
            cycle,rst_n,cancel,sample_valid,sample_ready,result_valid,result_ready,
            idle,inject_valid,read_valid,publish,be_launch,sample_id,result_id,left,right,event_ready);
    end
    task automatic tick(input integer count);
        repeat(count) @(negedge clk);
    endtask
    task automatic reset_domain;
        rst_n=0;cancel=0;sample_valid=0;inject_valid=0;read_valid=0;result_ready=0;
        tick(3);rst_n=1;tick(3);
    endtask
    task automatic launch;
        sample_valid=1;
        while(!sample_ready) @(negedge clk);
        @(negedge clk);sample_valid=0;sample_id=sample_id+1;
    endtask
    task automatic complete(input integer hold_cycles, block_cycles);
        result_ready=0;launch();
        while(!result_valid) @(negedge clk);
        tick(hold_cycles);inject_valid=(block_cycles!=0);result_ready=1;
        tick(1);tick(block_cycles);inject_valid=0;
        while(!idle) @(negedge clk);
        tick(2);
    endtask
    task automatic cancel_hold(input integer repeat_cancel);
        result_ready=0;launch();
        while(!result_valid) @(negedge clk);
        tick(2);cancel=1;tick(repeat_cancel);cancel=0;
        while(!idle) @(negedge clk);
        tick(2);
    endtask
    initial begin
        $display("B2J %0d %0d",N,RESPONSE);
        #1;rst_n=0; // actual asynchronous assertion before first observed edge
        tick(1);reset_domain();
        // One actual note, then quiescent router during each measured frame.
        event_data={3'd0,4'd1,4'd2,7'd69,10'd1023,10'd0,8'd0,12'd0,6'd0};
        event_valid=1;while(!event_ready) @(negedge clk);
        tick(1);event_valid=0;tick(40);
        complete(0,0);complete(8,0);complete(31,0);complete(0,7);
        // Public readback blocks admission, not idle. No extra frame accepted.
        read_valid=1;tick(3);read_valid=0;tick(2);
        complete(0,0);cancel_hold(1);cancel_hold(3);complete(0,0);
        // Whole-domain reset at HOLD and during an injection-blocked drain.
        result_ready=0;launch();while(!result_valid) @(negedge clk);
        tick(2);reset_domain();complete(0,0);
        result_ready=0;launch();while(!result_valid) @(negedge clk);
        inject_valid=1;result_ready=1;tick(3);reset_domain();complete(0,0);
        cancel=1;tick(1);cancel=0;tick(4);complete(0,0);tick(4);
        $display("END %0d",cycle);$finish;
    end
    initial begin #1000000;$fatal(1,"B2J_WATCHDOG");end
endmodule
