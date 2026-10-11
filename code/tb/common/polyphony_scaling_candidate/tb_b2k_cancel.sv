`timescale 1ns/1ps
`ifndef B2K_N
`define B2K_N 32
`endif
`ifndef B2K_RESPONSE
`define B2K_RESPONSE 1
`endif
// Short, public-port-only cancellation sweep of the unchanged hybrid candidate.
module tb_b2k_cancel;
    localparam N=`B2K_N, RESPONSE=`B2K_RESPONSE, SW=$clog2(N), TW=72+SW;
    logic clk=0,rst_n=1,cancel=0,event_valid=0,sample_valid=0,result_ready=0;
    logic [63:0] event_data=0;
    logic [31:0] sample_id=0;
    wire event_ready,sample_ready,result_valid,idle,publish,be_launch,advance,lane_valid;
    wire [SW-1:0] lane_slot;
    wire [31:0] result_id,lane_phase,lane_fcw;
    wire signed [23:0] left,right;
    integer cycle=0;
    always #12.5 clk=~clk;
    b2d_event_audio #(.N(N),.RESPONSE(RESPONSE)) dut(
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.event_valid(event_valid),
        .event_ready(event_ready),.event_data(event_data),.sample_valid(sample_valid),
        .sample_ready(sample_ready),.sample_id(sample_id),.result_valid(result_valid),
        .result_ready(result_ready),.result_id(result_id),.left(left),.right(right),
        .idle(idle),.publish(publish),.be_launch(be_launch),.advance(advance),
        .lane_valid(lane_valid),.lane_slot(lane_slot),.lane_phase(lane_phase),.lane_fcw(lane_fcw),
        .inject_valid(1'b0),.inject_tag({TW{1'b1}}),.inject_context(74'd0),
        .read_valid(1'b0),.read_slot({SW{1'b0}}));
    // PRE-NBA every edge, including reset/cancel/greedy re-admission. No hierarchy.
    always @(posedge clk) begin
        cycle=cycle+1;
        $display("T %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
            cycle,rst_n,cancel,sample_valid,sample_ready,result_valid,result_ready,
            idle,publish,be_launch,sample_id,result_id,left,right,event_valid,event_ready,
            event_data,advance,lane_valid,lane_slot,lane_phase);
        if(lane_valid) $display("FCW %0d %0d",cycle,lane_fcw);
    end
    task automatic tick(input integer count); repeat(count) @(negedge clk); endtask
    task automatic arm_note;
        event_data={3'd0,4'd1,4'd2,7'd69,10'd1023,10'd0,8'd0,12'd0,6'd0};
        event_valid=1;while(!event_ready) @(negedge clk);
        tick(1);event_valid=0;tick(40);
    endtask
    task automatic reset_domain;
        rst_n=0;cancel=0;sample_valid=0;result_ready=0;event_valid=0;
        tick(3);rst_n=1;tick(3);arm_note();
    endtask
    task automatic launch;
        sample_valid=1;while(!sample_ready) @(negedge clk);
        tick(1);sample_valid=0;sample_id=sample_id+1;
    endtask
    task automatic finish_frame;
        while(!result_valid) @(negedge clk);
        tick(2);result_ready=1;tick(1);result_ready=0;
        while(!idle) @(negedge clk);
        tick(2);
    endtask
    task automatic exercise(input integer offset, reset_case, width);
        $display("CASE %0d %0d %0d %0d",sample_id,offset,reset_case,width);
        result_ready=0;launch();tick(offset-1);
        if(reset_case) begin
            reset_domain();launch();finish_frame();
        end else begin
            cancel=1;tick(width);cancel=0;
`ifdef B2K_NEGATIVE_OBSERVE
            // Broken fences can leave an unconsumed control result forever.
            // Observe the full fault window, then reset to finish ALL scenarios.
            // This flag is for compiled negative copies only, never normal runs.
            tick(N+80);reset_domain();
`endif
            // Assert immediately, not after idle. The DUT must fence admission.
            launch();finish_frame();
        end
    endtask
    initial begin
        $display("B2K %0d %0d",N,RESPONSE);
        #1;rst_n=0;tick(1);reset_domain();
        // J-relative source boundaries, not observed internal state triggers.
        exercise(1,0,1);                  // WAIT_ROUTER
        exercise(9,0,1);                  // control request suppressed same edge
        exercise(10,0,1);                 // control read in flight
        exercise(N+10,0,1);               // control output consumption
        exercise(3*N+14,0,1);             // first OFFER suppressed
        exercise(3*N+15,0,1);             // first OFFER already accepted
        exercise(6*N+12,0,1);             // launch suppressed same edge
        exercise(6*N+13,0,1);             // Pitch in flight
        exercise(6*N+19,0,1);             // last Pitch valid drain
        exercise(6*N+20,0,1);             // ADVANCE suppressed
        exercise(6*N+21,0,1);             // phase already advanced
        exercise(6*N+26,0,1);             // first ROM_START suppressed
        exercise(6*N+27,0,1);             // ROM response outstanding
        exercise(6*N+27,0,3);             // repeated cancel cannot erase ownership
        exercise(6*N+27+RESPONSE,0,1);    // GAIN suppressed
        exercise(6*N+28+RESPONSE,0,1);    // old registered lane must remain visible
        exercise(6*N+26+2*(RESPONSE+3)+1,0,1); // later ROM slot outstanding
        exercise(10,1,1);exercise(3*N+15,1,1);
        exercise(6*N+13,1,1);exercise(6*N+27,1,1);
        tick(4);$display("END %0d",cycle);$finish;
    end
    initial begin #10000000;$fatal(1,"B2K_WATCHDOG");end
endmodule
