// Metadata-only isolated successor: untouched backend/ROM, public-port ledger.
// Two frontends on identical events/requests; reference clipped is NOT public.
`timescale 1ns/1ps
module tb_n32_clipped_successor;
    import audio_defs_pkg::*;
    logic clk=0,rst_n=0,frame_tick=0,event_valid=0,allow_result=0;
    always #12.5 clk=~clk;
    logic [63:0] event_data=0;
    wire event_ready,ref_event_ready,sample_valid,sample_ready,ref_sample_ready;
    wire result_valid,ref_valid,adapter_ready,result_ready;
    wire [31:0] sample_id,result_id,ref_id;
    wire signed [23:0] left,right,ref_left,ref_right;
    wire clipped,late,ref_late,idle,ref_idle,fault,ref_fault,cancel,publish,ref_publish;
    wire lane_valid,ref_lane_valid;
    wire [4:0] lane_slot,ref_lane_slot;
    wire signed [23:0] lane_pcm,ref_lane_pcm;
    wire advance,ref_advance;
    wire [31:0] occupied,ref_occupied;
    assign result_ready=adapter_ready && allow_result;
    b2d_event_audio_clipped #(.N(32),.RESPONSE(1)) candidate(
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .sample_valid(sample_valid),.sample_ready(sample_ready),.sample_id(sample_id),
        .result_valid(result_valid),.result_ready(result_ready),.result_id(result_id),.left(left),.right(right),
        .clipped(clipped),.late(late),.idle(idle),.fault(fault),.publish(publish),.occupied(occupied),
        .lane_valid(lane_valid),.lane_slot(lane_slot),.lane_pcm(lane_pcm),.advance(advance),
        .inject_valid(1'b0),.inject_tag(77'd0),.inject_context(74'd0),.read_valid(1'b0),.read_slot(5'd0));
    b2d_event_audio #(.N(32),.RESPONSE(1)) original(
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.event_valid(event_valid),.event_ready(ref_event_ready),.event_data(event_data),
        .sample_valid(sample_valid),.sample_ready(ref_sample_ready),.sample_id(sample_id),
        .result_valid(ref_valid),.result_ready(result_ready),.result_id(ref_id),.left(ref_left),.right(ref_right),
        .late(ref_late),.idle(ref_idle),.fault(ref_fault),.publish(ref_publish),.occupied(ref_occupied),
        .lane_valid(ref_lane_valid),.lane_slot(ref_lane_slot),.lane_pcm(ref_lane_pcm),.advance(ref_advance),
        .inject_valid(1'b0),.inject_tag(77'd0),.inject_context(74'd0),.read_valid(1'b0),.read_slot(5'd0));
    wire commit,pending,commit_clip;
    wire [31:0] committed_id,clip_count,commit_count,current_id;
    wire signed [23:0] committed_left,committed_right,play_left,play_right;
    premixed_frame_adapter transport(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.candidate_cancel(cancel),
        .candidate_sample_valid(sample_valid),.candidate_sample_ready(sample_ready),.candidate_sample_id(sample_id),
        .candidate_result_valid(result_valid && allow_result),.candidate_result_ready(adapter_ready),
        .candidate_result_id(result_id),.candidate_left(left),.candidate_right(right),.candidate_clipped(clipped),
        .play_left(play_left),.play_right(play_right),.pending_valid(pending),.commit_pulse(commit),
        .commit_count(commit_count),.clip_count(clip_count),.current_id(current_id),.committed_id(committed_id),
        .committed_left(committed_left),.committed_right(committed_right),.committed_clip(commit_clip));
    integer cycle=0,requests=0,results=0,commits=0,clip_commits=0,positive=0,negative=0;
    integer held_edges=0,cancelled_clip=0,events=0;
    logic signed [31:0] lane_total=0;
    logic [31:0] lane_mask=0;
    logic expected_clip=0,expected_pending=0;
    logic [31:0] expected_id;
    logic signed [23:0] expected_left,expected_right;
    logic was_held=0;
    logic [80:0] held_payload;
    wire [80:0] payload={result_id,left,right,clipped};
    always @(posedge clk) begin
        cycle=cycle+1;
        if(!rst_n) begin lane_total=0;lane_mask=0;expected_pending=0;was_held=0;end
        else begin
            if({event_ready,sample_ready,result_valid,result_id,left,right,late,idle,occupied,
                lane_valid,lane_slot,lane_pcm,advance,publish} !==
               {ref_event_ready,ref_sample_ready,ref_valid,ref_id,ref_left,ref_right,ref_late,ref_idle,ref_occupied,
                ref_lane_valid,ref_lane_slot,ref_lane_pcm,ref_advance,ref_publish})
                $fatal(1,"CLIP_SUCCESSOR_CHANGED_ORIGINAL_PUBLIC_BEHAVIOR");
            if(fault || ref_fault) $fatal(1,"CLIP_DRAIN_FAULT");
            if(event_valid && event_ready) events=events+1;
            if(sample_valid && sample_ready) begin
                requests=requests+1;lane_total=0;lane_mask=0;expected_pending=0;
            end
            if(lane_valid) begin
                lane_total=lane_total+$signed(lane_pcm);
                lane_mask[lane_slot]=1;
            end
            expected_clip=lane_total>32'sd8388607 || lane_total< -32'sd8388608;
            if(result_valid && !frame_tick) begin
                if(lane_mask!==32'hffffffff || clipped!==expected_clip)
                    $fatal(1,"PUBLIC_CLIPPED_NOT_EXACT_WIDE_SUM");
            end
            if(was_held && !frame_tick && (!result_valid || payload!==held_payload))
                $fatal(1,"CLIPPED_ID_PCM_HOLD_CHANGED");
            was_held=result_valid && !result_ready && !frame_tick;held_payload=payload;
            if(was_held) held_edges=held_edges+1;
            if(result_valid && result_ready && !frame_tick) begin
                results=results+1;expected_pending=1;
                expected_id=result_id;expected_left=left;expected_right=right;
                $display("P %0d %h %0d %0d clip=%0d wide=%0d",cycle,result_id,left,right,clipped,lane_total);
            end
            if(commit) begin
                if(!expected_pending || committed_id!==expected_id || committed_left!==expected_left ||
                   committed_right!==expected_right || commit_clip!==expected_clip)
                    $fatal(1,"CLIP_COMMIT_METADATA_MISMATCH");
                commits=commits+1;expected_pending=0;
                if(commit_clip) begin
                    clip_commits=clip_commits+1;
                    if(committed_left==24'sh7fffff) positive=positive+1;
                    if(committed_left==24'sh800000) negative=negative+1;
                end
            end
            if(frame_tick) begin expected_pending=0;was_held=0;end
        end
        #1;
        if(rst_n && !frame_tick && clip_count!==clip_commits)
            $fatal(1,"CLIP_COUNT_ONLY_SUCCESSFUL_COMMIT_ONCE");
        if(frame_tick && clipped!==0) $fatal(1,"CLIPPED_NOT_CLEARED_ON_CANCEL");
        if(!rst_n && clipped!==0) $fatal(1,"CLIPPED_NOT_CLEARED_ON_RESET");
    end
    task automatic pulse_frame;
        @(negedge clk);frame_tick=1;
        @(negedge clk);frame_tick=0;
    endtask
    task automatic wait_result;
        integer watchdog;
        begin watchdog=0;
            while(!result_valid) begin @(negedge clk);watchdog=watchdog+1;
                if(watchdog>700) $fatal(1,"CLIP_RESULT_TIMEOUT");end
        end
    endtask
    integer k,old_commits,frame_start;
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        for(k=0;k<32;k=k+1) begin
            @(negedge clk);event_data={EVENT_NOTE_ON,4'(k/16),4'(k%16),7'd81,10'd1023,10'd0,8'd0,12'd0,6'd0};event_valid=1;
            while(!event_ready) @(negedge clk);
            @(negedge clk);event_valid=0;
        end
        repeat(30) @(negedge clk);
        if(occupied!==32'hffffffff) $fatal(1,"CLIP_FIXTURE_NOT_32_ACTIVE");
        for(k=0;k<96;k=k+1) begin
            allow_result=0;pulse_frame();frame_start=cycle;wait_result();
            // One actual clipped HOLD result is cancelled, not counted.
            if(clipped && cancelled_clip==0) begin
                repeat(4) @(negedge clk);old_commits=commits;
                pulse_frame();cancelled_clip=cancelled_clip+1;frame_start=cycle;
                if(commits!=old_commits || clipped!==0) $fatal(1,"CANCELLED_CLIP_COUNTED_OR_HELD");
                wait_result();
            end
            repeat(4) @(negedge clk);
            old_commits=commits;allow_result=1;
            while(commits==old_commits) @(negedge clk);
            // Holding result_valid cannot cause extra clip growth after commit.
            repeat(4) @(negedge clk);
            while(cycle<frame_start+832) @(negedge clk);
        end
        if(events!=32 || results!=96 || commits!=96 || requests!=97 || cancelled_clip!=1 ||
           positive==0 || negative==0 || held_edges<96*4 || clip_commits!=positive+negative)
            $fatal(1,"CLIP_REAL_SATURATION_COVERAGE_MISSING");
        $display("END events=%0d requests=%0d results=%0d commits=%0d positive=%0d negative=%0d held=%0d cancelled_clip=%0d clip_count=%0d",events,requests,results,commits,positive,negative,held_edges,cancelled_clip,clip_count);
        // Assert shared reset with a nonzero prior clip ledger.
        @(negedge clk);rst_n=0;clip_commits=0;
        repeat(4) @(negedge clk);
        if(clip_count!==0 || clipped!==0) $fatal(1,"CLIP_RESET_LEDGER_NOT_ZERO");
        $display("PASS N32_CLIPPED_METADATA ORIGINAL_PUBLIC_EQUIVALENT NO_NEW_SOUND_MATH");$finish;
    end
    initial begin #3ms;$fatal(1,"CLIP_TB_GLOBAL_TIMEOUT");end
endmodule
