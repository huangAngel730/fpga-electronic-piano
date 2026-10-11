`timescale 1ns/1ps
`ifndef B2C_RESPONSE
`define B2C_RESPONSE 1
`endif
`ifndef B2C_LONG
`define B2C_LONG 0
`endif
`ifndef B2C_N
`define B2C_N 8
`endif
module tb_b2f_event_audio;
    localparam integer N=`B2C_N, SW=$clog2(N), TW=72+SW, RESPONSE=`B2C_RESPONSE, LONG=`B2C_LONG;
    logic clk=0,rst_n=0,cancel=0,event_valid=0,sample_valid=0,result_ready=1;
    always #12.5 clk=~clk;
    logic [63:0] event_data=0;
    logic [31:0] sample_id=32'hfffffffc;
    wire event_ready,sample_ready,result_valid,late,aborted,idle,fault;
    wire [1:0] abort_reason;
    wire [31:0] result_id;
    wire signed [23:0] left,right;
    logic inject_valid=0,read_valid=0;
    logic [TW-1:0] inject_tag=0; logic [73:0] inject_context=0;
    logic [SW-1:0] read_slot=0;
    wire inject_ready,read_ready,read_out_valid;
    wire [73:0] read_context;
    wire [N-1:0] ons,offs,occupied,releasing,frame_occupied;
    wire [N*10-1:0] velocities,frame_velocity;
    wire [N*32-1:0] bases,generations,frame_base,frame_gen;
    wire [N*8-1:0] notes;
    wire [N*4-1:0] sources,channels,frame_sources,frame_channels;
    wire issue_valid,issue_pedal,write_valid,write_accepted,write_injected,publish;
    wire [TW-1:0] issue_tag,write_tag; wire [73:0] issue_context,write_context;
    wire [1:0] issue_flags;
    wire [28:0] issue_control;
    wire be_launch,advance,lane_valid;
    wire [SW-1:0] lane_slot; wire [1:0] lane_table;
    wire [31:0] lane_phase,lane_fcw;
    wire signed [15:0] lane_wave;
    wire [15:0] lane_env;
    wire signed [23:0] lane_pcm;
    wire [N*16-1:0] live_env;
    wire [N*3-1:0] live_state;
    wire [N*12-1:0] frame_bend,frame_mod;
    wire [N*5-1:0] frame_range;
    b2d_event_audio #(.N(N),.RESPONSE(RESPONSE)) dut(.*);
    integer cycle=0,events=0,requests=0,launches=0,advances=0,lanes=0;
    integer outputs=0,cancels=0,aborts=0,writes=0,issues=0,reads=0,firsts=0;
    integer f,k,start_cycle,watchdog;
    logic [31:0] pending_id;
    logic [N*119-1:0] previous_route;
    wire [N*119-1:0] route_tuple={ons,offs,occupied,releasing,velocities,bases,notes,sources,channels,generations};
    logic held=0,seen_result=0;
    logic [80:0] held_tuple;
    wire [80:0] result_tuple={result_id,left,right,late};
    logic [TW-1:0] stale_tag;
    always @(posedge clk) begin
        cycle=cycle+1;
        if(rst_n) begin
            if(event_valid && event_ready) begin events=events+1;$display("I %0d %h",cycle,event_data);end
            if(sample_valid && sample_ready) begin
                requests=requests+1;pending_id=sample_id;
                $display("J %0d %h",cycle,sample_id);
            end
            if(route_tuple!==previous_route) begin
                $display("U %0d %h %h %h %h %h %h %h %h %h %h",cycle,
                    ons,offs,occupied,releasing,velocities,bases,notes,sources,channels,generations);
                previous_route=route_tuple;
            end
            if(issue_valid) begin
                issues=issues+1;stale_tag=issue_tag ^ ({{(TW-1){1'b0}},1'b1} << SW);
                $display("G %0d %h %h %h %h %0d",cycle,issue_tag,issue_context,issue_flags,issue_control,issue_pedal);
            end
            if(write_valid) begin
                writes=writes+1;
                $display("W %0d %h %h %0d %0d",cycle,write_tag,write_context,write_accepted,write_injected);
                if(write_injected && write_accepted) $fatal(1,"B2B_STALE_GENERATION_ACCEPTED");
            end
            if(be_launch) begin launches=launches+1;
                $display("C %0d %h %h %h %h %h %h %h %h %h",cycle,pending_id,frame_occupied,
                    frame_base,frame_bend,frame_mod,frame_range,frame_sources,frame_channels,frame_gen);
            end
            if(advance) begin advances=advances+1;$display("A %0d %h",cycle,pending_id);end
            if(cancel) begin cancels=cancels+1;$display("X %0d",cycle);end
            if(aborted) begin aborts=aborts+1;$display("Z %0d %0d",cycle,abort_reason);end
            if(held && !aborted && !cancel && (!result_valid || result_tuple!==held_tuple))
                $fatal(1,"B2B_OUTPUT_BACKPRESSURE_CHANGED");
            held=result_valid && !result_ready && !aborted && !cancel;held_tuple=result_tuple;
            if(!result_valid) seen_result=0;
            if(result_valid && !seen_result && !aborted && !cancel) begin
                seen_result=1;firsts=firsts+1;
                $display("F %0d %h %0d %0d %0d",cycle,result_id,left,right,late);
            end
            if(publish) begin outputs=outputs+1;$display("P %0d %h %0d %0d %0d",cycle,result_id,left,right,late);end
            #1;
            if(lane_valid) begin lanes=lanes+1;
                $display("L %0d %h %0d %h %0d %h %0d %0d %0d %0d",cycle,pending_id,lane_slot,
                    lane_phase,lane_table,lane_fcw,lane_wave,lane_env,lane_pcm,live_state[3*lane_slot+:3]);
            end
            if(read_out_valid) begin reads=reads+1;$display("Y %0d %0d %h",cycle,read_slot,read_context);end
        end
    end
    function automatic [63:0] ev(input integer typ,src,ch,note,vel,ctl,val);
        ev={3'(typ),4'(src),4'(ch),7'(note),10'(vel),10'd0,8'(ctl),12'(val),6'd0};
    endfunction
    task automatic reset_domain;
        @(negedge clk);rst_n=0;sample_valid=0;event_valid=0;cancel=0;inject_valid=0;read_valid=0;
        repeat(4) @(negedge clk);
        $display("R %0d",cycle);previous_route='x;held=0;seen_result=0;rst_n=1;result_ready=1;
    endtask
    task automatic wait_idle;
        watchdog=0;
        while(!idle) begin @(negedge clk);watchdog=watchdog+1;
            if(watchdog>1600) $fatal(1,"B2B_FINITE_DRAIN");end
    endtask
    task automatic send(input logic [63:0] word_in);
        @(negedge clk);event_data=word_in;event_valid=1;
        while(!event_ready) @(negedge clk);
        @(negedge clk);event_valid=0;
    endtask
    task automatic launch;
        @(negedge clk);sample_valid=1;
        while(!sample_ready) @(negedge clk);
        @(posedge clk);#2;start_cycle=cycle;
        @(negedge clk);sample_valid=0;sample_id=sample_id+1'b1;
    endtask
    task automatic frame;
        launch();wait_idle();
        while(cycle<start_cycle+831) @(negedge clk);
    endtask
    task automatic abort_at(input integer when_to_cancel);
        launch();
        if(when_to_cancel<0) begin
            while(!result_valid) @(negedge clk);
            repeat(8) @(negedge clk);
        end else if(when_to_cancel==0) repeat(5) @(negedge clk);
        else begin
            while(!be_launch) @(negedge clk);
            @(negedge clk);repeat(when_to_cancel-1) @(negedge clk);
        end
        cancel=1;@(negedge clk);cancel=0;result_ready=1;wait_idle();
    endtask
    initial begin
        $display("B2C %0d %0d %0d",N,RESPONSE,LONG);
        reset_domain();repeat(2) frame();
        // Cancellation of a front-end sample must NOT cancel an original
        // router pulse for an event already accepted before that sample.
        send(ev(0,8,9,69,700,0,0));launch();
        @(negedge clk);cancel=1;@(negedge clk);cancel=0;wait_idle();
        repeat(8) frame();
        send(ev(1,8,9,69,0,0,0));launch();
        while(offs==0) @(negedge clk);
        cancel=1;@(negedge clk);cancel=0;wait_idle();
        repeat(4) frame();reset_domain();
        // One identity per RAM address, including f/f; ignored range25 cannot
        // replace a valid value. Event forks must accept each word exactly once.
        for(k=0;k<256;k=k+1) begin
            send(ev(3,k/16,k%16,0,0,0,k%2 ? 2047 : 2048));
            send(ev(4,k/16,k%16,0,0,1,k*16));
            send(ev(4,k/16,k%16,0,0,4,k%25));
            send(ev(4,k/16,k%16,0,0,4,25));
            send(ev(4,k/16,k%16,0,0,6,4095));
            send(ev(4,k/16,k%16,0,0,6,0));
        end
        send(ev(0,1,2,60,255,0,0));send(ev(0,1,2,64,256,0,0));
        send(ev(0,2,2,60,512,0,0));send(ev(0,15,15,72,1023,0,0));
        for(k=4;k<N;k=k+1) send(ev(0,4+k,4+k,64+k,800+k,0,0));
        send(ev(0,1,2,60,1023,0,0)); // same identity retrigger
        send(ev(0,3,3,67,900,0,0)); // fifth live note: LRU steal
        send(ev(1,7,7,9,0,0,0)); // unmatched off
        send(ev(4,1,2,0,0,6,4095));
        send(ev(1,1,2,60,0,0,0)); // pedal-deferred
        send(ev(4,2,2,0,0,6,0)); // unrelated identity: no release
        // Real source/generation rejection through B1, not a mock engine.
        launch();while(!issue_valid) @(negedge clk);
        @(negedge clk);inject_tag=stale_tag;inject_context=0;inject_valid=1;
        @(negedge clk);inject_valid=0;wait_idle();
        repeat(24) frame();
        send(ev(4,1,2,0,0,6,0));
        send(ev(0,3,3,67,0,0,0)); // velocity-zero note-on means note-off
        repeat(16) frame();
        abort_at(0);abort_at(3);abort_at(10);abort_at(18);
        result_ready=0;abort_at(-1);
        // Hold an event through a frame. It is not accepted while sample owns
        // the router, but must subsequently dispatch without losing its word.
        launch();send(ev(0,8,9,69,700,0,0));wait_idle();frame();
        result_ready=0;launch();while(!result_valid) @(negedge clk);
        repeat(8) @(negedge clk);result_ready=1;wait_idle();
        if(LONG) repeat(5400) frame(); // actual attack/decay/sustain plus brightness windows
        // Retirement is driven by the real continuous ADSR reaching Idle.
        send(ev(5,0,0,0,0,0,0));
        for(f=0;f<(LONG ? 4900 : 32);f=f+1) frame();
        if(LONG && occupied!=0) $fatal(1,"B2B_RELEASE_NOT_RETIRED");
        // Verify committed result descriptors through the public bank port.
        for(k=0;k<N;k=k+1) begin
            @(negedge clk);read_slot=SW'(k);read_valid=1;
            while(!read_ready) @(negedge clk);
            @(negedge clk);read_valid=0;repeat(2) @(negedge clk);
        end
        launch();repeat(4) @(negedge clk);reset_domain();
        send(ev(0,0,0,69,1023,0,0));repeat(8) frame();
        result_ready=0;launch();while(!result_valid) @(negedge clk);reset_domain();
        repeat(2) frame();
        $display("END %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,
            events,requests,launches,advances,lanes,outputs,cancels,aborts,writes,issues,reads,firsts);
        $finish;
    end
    initial begin #250000000;$fatal(1,"B2B_WATCHDOG");end
endmodule
