// Short public-port transport test only. Frozen N32 math is not re-certified.
// No public clipped exists in b2d: tying the proposed metadata low here does
// NOT verify clipping or authorize production connection.
`timescale 1ns/1ps
module tb_n32_frame_interface;
    import audio_defs_pkg::*;
    logic clk=0, rst_n=0, frame_tick=0;
    always #12.5 clk=~clk;
    logic event_valid=0, read_valid=0;
    logic [63:0] event_data=0;
    wire event_ready, sample_valid, sample_ready, result_valid, result_ready;
    wire cancel, idle, fault, late, publish;
    wire [31:0] sample_id, result_id;
    wire signed [23:0] raw_left, raw_right, play_left, play_right;
    wire commit_pulse, pending_valid;
    wire [31:0] frame_count, frame_request_count, commit_count, underrun_count, clip_count;
    wire [31:0] current_id, committed_id;
    wire signed [23:0] committed_left, committed_right;
    wire committed_clip, dispatched;
    wire [31:0] occupied;
    b2d_event_audio #(.N(32),.RESPONSE(1)) backend(
        .clk(clk),.rst_n(rst_n),.cancel(cancel),
        .event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .sample_valid(sample_valid),.sample_ready(sample_ready),.sample_id(sample_id),
        .result_valid(result_valid),.result_ready(result_ready),.result_id(result_id),
        .left(raw_left),.right(raw_right),.late(late),.idle(idle),.fault(fault),.publish(publish),
        .inject_valid(1'b0),.inject_tag(77'd0),.inject_context(74'd0),
        .read_valid(read_valid),.read_slot(5'd0),.occupied(occupied));
`ifdef M2_N32_MUTANT_ZERO_PCM
    wire signed [23:0] forwarded_left=24'sd0;
`else
    wire signed [23:0] forwarded_left=raw_left;
`endif
    premixed_frame_adapter adapter(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.candidate_cancel(cancel),
        .candidate_sample_valid(sample_valid),.candidate_sample_ready(sample_ready),
        .candidate_sample_id(sample_id),.candidate_result_valid(result_valid),
        .candidate_result_ready(result_ready),.candidate_result_id(result_id),
        .candidate_left(forwarded_left),.candidate_right(raw_right),.candidate_clipped(1'b0),
        .play_left(play_left),.play_right(play_right),.pending_valid(pending_valid),
        .commit_pulse(commit_pulse),.frame_count(frame_count),.frame_request_count(frame_request_count),
        .commit_count(commit_count),.underrun_count(underrun_count),.clip_count(clip_count),
        .current_id(current_id),.committed_id(committed_id),.committed_left(committed_left),
        .committed_right(committed_right),.committed_clip(committed_clip),.dispatched_this_frame(dispatched));
    integer cycle=0, accepted=0, results=0, commits=0, cancels=0, nonzero=0;
    logic expected_pending=0;
    logic [31:0] expected_id=0;
    logic signed [23:0] expected_left=0, expected_right=0;
    always @(posedge clk) begin
        cycle=cycle+1;
        if(!rst_n) expected_pending=0;
        else begin
            if(frame_tick) begin
                cancels=cancels+1; expected_pending=0;
                if(sample_valid && sample_ready || result_valid && result_ready || commit_pulse)
                    $fatal(1,"N32_FRAME_EDGE_HANDSHAKE");
            end
            if(sample_valid && sample_ready) begin
                accepted=accepted+1; $display("J %0d %h",cycle,sample_id);
                if(read_valid) $fatal(1,"N32_READ_BLOCK_BROKEN");
            end
            if(result_valid && result_ready) begin
                results=results+1; expected_pending=1;
                expected_id=result_id; expected_left=raw_left; expected_right=raw_right;
                if(late) $fatal(1,"N32_SHORT_FIXTURE_LATE");
                if(raw_left!=0 || raw_right!=0) nonzero=nonzero+1;
                $display("P %0d %h %0d %0d",cycle,result_id,raw_left,raw_right);
            end
            if(commit_pulse) begin
                if(!expected_pending || committed_id!==expected_id ||
                    committed_left!==expected_left || committed_right!==expected_right)
                    $fatal(1,"N32_PUBLIC_PCM_TRANSPORT_MISMATCH");
                if(committed_clip) $fatal(1,"N32_CLIP_METADATA_NOT_AVAILABLE");
                expected_pending=0; commits=commits+1;
                $display("K %0d %h %0d %0d",cycle,committed_id,committed_left,committed_right);
            end
            if(fault) $fatal(1,"N32_DRAIN_FAULT");
        end
        if(cycle>8000) $fatal(1,"N32_TEST_WATCHDOG");
    end
    task automatic pulse_frame;
        @(negedge clk);frame_tick=1;
        @(negedge clk);frame_tick=0;
    endtask
    task automatic await_commit(input integer target);
        integer w;
        begin
            w=0;
            while(commits<target) begin
                @(negedge clk);w=w+1;
                if(w>700) $fatal(1,"N32_CURRENT_RESULT_HANDSHAKE_TIMEOUT");
            end
        end
    endtask
    task automatic await_idle;
        integer w;
        begin
            w=0;
            while(!idle) begin @(negedge clk);w=w+1;
                if(w>150) $fatal(1,"N32_CANCEL_DRAIN_TIMEOUT");end
        end
    endtask
    integer baseline;
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        // source1/channel0 A4, velocity900, zero pitch/modulation.
        @(negedge clk);event_data={EVENT_NOTE_ON,4'd1,4'd0,7'd69,10'd900,10'd0,8'd0,12'd0,6'd0};event_valid=1;
        while(!event_ready) @(negedge clk);
        @(negedge clk);event_valid=0;
        repeat(20) @(negedge clk);
        if(occupied==0) $fatal(1,"N32_NOTE_NOT_ALLOCATED");
        pulse_frame();await_commit(1);await_idle();
        repeat(480) @(negedge clk);
        pulse_frame();await_commit(2);await_idle();
        // Read ownership delays dispatch, but the adapter must retain request.
        @(negedge clk);read_valid=1;baseline=accepted;
        pulse_frame();repeat(12) @(negedge clk);
        if(accepted!=baseline || !sample_valid) $fatal(1,"N32_QUEUED_READ_BLOCK");
        read_valid=0;await_commit(3);await_idle();
        // Cancel an actually dispatched, incomplete transaction, then recover.
        pulse_frame();while(!dispatched) @(negedge clk);
        repeat(45) @(negedge clk);baseline=commits;
        pulse_frame();await_commit(baseline+1);await_idle();
        // Shared reset clears both sides and restores ID1, silent PCM.
        @(negedge clk);rst_n=0;repeat(4) @(negedge clk);rst_n=1;
        repeat(4) @(negedge clk);baseline=commits;
        pulse_frame();await_commit(baseline+1);await_idle();
        if(current_id!==32'd1 || commit_count!==32'd1 ||
           play_left!==24'd0 || play_right!==24'd0 || clip_count!==32'd0)
            $fatal(1,"N32_RESET_RECOVERY_PAYLOAD");
        if(nonzero==0 || results!=commits || commits!=5 || accepted!=6)
            $fatal(1,"N32_INTERFACE_COVERAGE_COUNTS");
        $display("END accepted=%0d results=%0d commits=%0d nonzero=%0d frame_edges=%0d",accepted,results,commits,nonzero,cancels);
        $display("PASS N32_PUBLIC_FRAME_INTERFACE CLIP_UNVERIFIED MATH_NOT_REPLAYED");
        $finish;
    end
endmodule
