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
module tb_e4_n32;
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
    wire clipped;
    wire [3:0] audio_state,router_state;
    wire control_snapshot_valid,control_snapshot_ready;
    wire [31:0] control_snapshot_id;
    wire [N*29-1:0] control_snapshot_value;
    wire [N-1:0] control_snapshot_occupied,control_release_mask,backend_release_done_mask;
    wire [N*4-1:0] control_snapshot_sources,control_snapshot_channels;
    wire [N*32-1:0] control_snapshot_generations,control_release_generations;
    wire control_release_valid,control_release_ready;
    wire backend_release_done_valid,backend_release_done_ready;
    wire [SW-1:0] backend_release_done_slot;
    wire [31:0] backend_release_done_generation;
    logic transport_mode=0,pixel_clk=0;
    always #20 pixel_clk=~pixel_clk;
    GSR GSR(.GSRI(1'b1));
    wire t_cancel,t_sv,t_rr;
    wire [31:0] t_sid;
    wire b_cancel=transport_mode ? t_cancel : cancel;
    wire b_sv=transport_mode ? t_sv : sample_valid;
    wire [31:0] b_sid=transport_mode ? t_sid : sample_id;
    wire b_rr=transport_mode ? t_rr : result_ready;
    wire signed [23:0] play_left,play_right,committed_left,committed_right;
    wire bclk,lrck,din,frame_tick,commit_pulse,committed_clip;
    wire [31:0] frame_count,frame_request_count,commit_count,underrun_count,clip_count,committed_id;
    e4_n32_candidate #(.N(N),.RESPONSE(RESPONSE)) dut(.cancel(b_cancel),.sample_valid(b_sv),.sample_id(b_sid),.result_ready(b_rr),.*);
    m2_n32_output_transport transport (
        .clk(clk),.pixel_clk(pixel_clk),.rst_n(rst_n && transport_mode),.display_rst_n(rst_n && transport_mode),
        .candidate_cancel(t_cancel),.candidate_sample_valid(t_sv),.candidate_sample_ready(sample_ready),
        .candidate_sample_id(t_sid),.candidate_result_valid(result_valid),.candidate_result_ready(t_rr),
        .candidate_result_id(result_id),.candidate_left(left),.candidate_right(right),.candidate_clipped(clipped),
        .play_left(play_left),.play_right(play_right),.bclk(bclk),.lrck(lrck),.din(din),
        .frame_tick(frame_tick),.commit_pulse(commit_pulse),.frame_count(frame_count),
        .frame_request_count(frame_request_count),.commit_count(commit_count),.underrun_count(underrun_count),
        .clip_count(clip_count),.committed_id(committed_id),.committed_left(committed_left),
        .committed_right(committed_right),.committed_clip(committed_clip)
    );
    logic quiet_tail=0;
    function automatic integer abs_cycle();
        abs_cycle=$rtoi(($realtime+12.5)/25.0);
    endfunction
    integer cycle=0,events=0,requests=0,launches=0,advances=0,lanes=0;
    integer outputs=0,cancels=0,aborts=0,writes=0,issues=0,reads=0,firsts=0;
    integer f,k,start_cycle,watchdog;
    logic [31:0] pending_id;
    logic [N*119-1:0] previous_route;
    wire [N*119-1:0] route_tuple={ons,offs,occupied,releasing,velocities,bases,notes,sources,channels,generations};
    logic held=0,seen_result=0;
    logic [81:0] held_tuple;
    wire [81:0] result_tuple={result_id,left,right,late,clipped};
    logic [TW-1:0] stale_tag;
    always @(posedge clk) begin
        cycle=abs_cycle();
        if(rst_n && !quiet_tail) begin
            if(event_valid && event_ready) begin events=events+1;$display("I %0d %h",cycle,event_data);end
            if(b_sv && sample_ready) begin
                requests=requests+1;pending_id=b_sid;
                $display("J %0d %h",cycle,b_sid);
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
            if(b_cancel) begin cancels=cancels+1;$display("X %0d",cycle);end
            if(aborted) begin aborts=aborts+1;$display("Z %0d %0d",cycle,abort_reason);end
            if(held && !aborted && !b_cancel && (!result_valid || result_tuple!==held_tuple))
                $fatal(1,"E4_HOLD");
            held=result_valid && !b_rr && !aborted && !b_cancel;held_tuple=result_tuple;
            if(!result_valid) seen_result=0;
            if(result_valid && !seen_result && !aborted && !b_cancel) begin
                seen_result=1;firsts=firsts+1;
                $display("F %0d %h %0d %0d %0d",cycle,result_id,left,right,late);
            end
            if(publish) begin outputs=outputs+1;$display("P %0d %h %0d %0d %0d",cycle,result_id,left,right,late);end
            if(result_valid) $display("K %0d %0d %h %0d %0d %0d %0d",cycle,b_rr,result_id,left,right,clipped,late);
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
    integer epoch=0,retire_enable=0,release_before=0;
    integer tail_requests=0,tail_advances=0,done_seen=0,release_batches=0;
    logic [N-1:0] tail_done_mask=0;
    integer transport_accepts=0,transport_returns=0,transport_commits=0;
    integer last_frame=-1,request_cycle=-1,maximum_latency=0;
    logic transport_pending=0,return_pending=0;
    logic [31:0] expected_id;
    logic signed [23:0] expected_left,expected_right;
    logic expected_clip;
    logic previous_bclk=0,previous_lrck=0,pins_started=0;
    logic cancel_on_edge;
    always @(posedge clk) begin
        cancel_on_edge=rst_n && b_cancel;
        #1;if(cancel_on_edge && result_valid) $fatal(1,"E4_CANCEL");
    end
    always @(posedge clk) begin
        if(rst_n) begin
            if(b_cancel && publish) $fatal(1,"E4_CANCEL");
            if(control_release_valid && control_release_ready) begin
                release_batches=release_batches+1;
                $display("V %0d %h %h",abs_cycle(),control_release_mask,control_release_generations);
            end
            if(backend_release_done_valid) begin
                done_seen=done_seen+1;
                if(quiet_tail) tail_done_mask=tail_done_mask | backend_release_done_mask;
                $display("D %0d %h %0d %h",abs_cycle(),backend_release_done_mask,backend_release_done_slot,backend_release_done_generation);
            end
            if(quiet_tail) begin
                if(b_sv && sample_ready) tail_requests=tail_requests+1;
                if(advance) tail_advances=tail_advances+1;
            end
            if(transport_mode) begin
                if(!pins_started || bclk!==previous_bclk || lrck!==previous_lrck || frame_tick)
                    $display("S %0d %0d %0d %0d %0d %0d %0d",abs_cycle(),bclk,lrck,din,frame_tick,play_left,play_right);
                previous_bclk=bclk;previous_lrck=lrck;pins_started=1;
                if(frame_tick) begin
                    if(last_frame>=0 && abs_cycle()-last_frame!=833 && abs_cycle()-last_frame!=834)
                        $fatal(1,"E4_FRAME_CALENDAR");
                    if(transport_pending || return_pending) $fatal(1,"E4_DEADLINE_OPEN");
                    last_frame=abs_cycle();
                end
                if(b_sv && sample_ready) begin
                    if(transport_pending) $fatal(1,"E4_DUPLICATE_ACCEPT");
                    transport_pending=1;request_cycle=abs_cycle();expected_id=b_sid;
                    transport_accepts=transport_accepts+1;
                end
                if(result_valid && b_rr) begin
                    if(!transport_pending || result_id!==expected_id) $fatal(1,"E4_ID");
                    transport_pending=0;return_pending=1;
                    expected_left=left;expected_right=right;expected_clip=clipped;
                    transport_returns=transport_returns+1;
                end
                if(commit_pulse) begin
                    if(!return_pending || committed_id!==expected_id) $fatal(1,"E4_COMMIT_ID");
                    if(committed_left!==expected_left || committed_right!==expected_right || committed_clip!==expected_clip)
                        $fatal(1,"E4_TRANSPORT_PCM");
                    if(abs_cycle()-request_cycle>=833) $fatal(1,"E4_DEADLINE");
                    if(abs_cycle()-request_cycle>maximum_latency) maximum_latency=abs_cycle()-request_cycle;
                    return_pending=0;transport_commits=transport_commits+1;
                end
                if(frame_tick || (b_sv && sample_ready) || (result_valid && b_rr) || commit_pulse)
                    $display("T %0d %0d %0d %0d %0d %0d %0d %h %h %0d %0d %0d %h %0d %0d %0d",abs_cycle(),epoch,
                        frame_tick,b_sv && sample_ready,result_valid && b_rr,commit_pulse,b_cancel,b_sid,result_id,
                        left,right,clipped,committed_id,committed_left,committed_right,committed_clip);
            end
        end
    end
    task automatic settle;
        repeat(4*N+20) @(negedge clk);
    endtask
    task automatic fill;
        for(k=0;k<N;k=k+1) send(ev(0,k/16,k%16,48+k,700+k,0,0));
        settle();
        if(occupied!=={N{1'b1}}) $fatal(1,"E4_FILL");
    endtask
    task automatic tail_frame;
        launch();wait_idle();
    endtask
    initial begin
        $display("B2C %0d %0d %0d",N,RESPONSE,LONG);
        if($value$plusargs("RETIRE=%d",retire_enable)) begin end
        reset_domain();fill();
        repeat(20) frame();
        send(ev(0,0,0,100,900,0,0));settle();
        if(notes[7:0]!==8'd100 || generations[31:0]!==32'd2) $fatal(1,"E4_STEAL");
        send(ev(0,0,0,100,800,0,0));settle();
        if(generations[31:0]!==32'd3 || velocities[9:0]!==10'd800) $fatal(1,"E4_RETRIGGER");
        send(ev(4,0,0,0,0,6,4095));send(ev(1,0,0,100,0,0,0));settle();
        if(releasing[0]!==1'b0) $fatal(1,"E4_CC64_DEFER");
        frame();release_before=release_batches;send(ev(4,0,0,0,0,6,0));settle();
        if(release_batches<=release_before || control_release_valid!==1'b0)
            $fatal(1,"E4_RELEASE_ACK");
        if(releasing[0]!==1'b1) $fatal(1,"E4_CC64_RELEASE");
        repeat(3) frame();
        result_ready=0;launch();while(!result_valid) @(negedge clk);
        repeat(8) @(negedge clk);result_ready=1;wait_idle();
        result_ready=0;abort_at(-1);
        abort_at(0);abort_at(10);
        launch();repeat(4) @(negedge clk);reset_domain();epoch=epoch+1;
        if(occupied!==0 || result_valid!==0 || clipped!==0) $fatal(1,"E4_RESET");
        fill();repeat(3) frame();
        // New same-source composition uses the original 40MHz PT8211 transport.
        reset_domain();epoch=epoch+1;transport_mode=1;last_frame=-1;
        transport_pending=0;return_pending=0;previous_bclk=0;previous_lrck=0;pins_started=0;fill();
        while(transport_commits<32) @(negedge clk);
        wait_idle();
        if(transport_accepts!=transport_returns || transport_returns!=transport_commits)
            $fatal(1,"E4_TRANSPORT_END_OPEN");
        $display("TRANSPORT_END %0d %0d %0d %0d",transport_accepts,transport_returns,transport_commits,maximum_latency);
        @(negedge clk);rst_n=0;transport_mode=0;sample_valid=0;event_valid=0;
        repeat(4) @(negedge clk);reset_domain();epoch=epoch+1;
        if(retire_enable!=0) begin
            // No envelope/math shortcut: zero-level RELEASE still needs 4800 advances.
            $display("TAIL_BEGIN %0d %0d",cycle,epoch);quiet_tail=1;
            fill();
            for(k=0;k<N;k=k+1) send(ev(1,k/16,k%16,48+k,0,0,0));
            settle();
            if(releasing!=={N{1'b1}}) $fatal(1,"E4_TAIL_RELEASE");
            repeat(4802) tail_frame();settle();
            if(tail_advances<4800 || done_seen==0 || occupied!==0 || tail_done_mask!=={N{1'b1}})
                $fatal(1,"E4_RETIRE");
            $display("TAIL_END %0d %0d %0d %0d %h %h",cycle,tail_requests,tail_advances,done_seen,occupied,tail_done_mask);
            quiet_tail=0;reset_domain();epoch=epoch+1;
        end
        $display("END %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,
            events,requests,launches,advances,lanes,outputs,cancels,aborts,writes,issues,reads,firsts);
        $display("PASS E4_N%0d_ISOLATED_FROZEN_PIANO_NOT_PRO_DUT",N);$finish;
    end
    initial begin #150000000;$fatal(1,"E4_WATCHDOG");end
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
endmodule
