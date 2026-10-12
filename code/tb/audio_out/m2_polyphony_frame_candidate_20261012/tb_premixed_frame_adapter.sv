`timescale 1ns/1ps
// Synthetic producer transport only: no N32 sound/backend timing claim.
module tb_premixed_frame_adapter;
    logic clk=0;always #12.5 clk=~clk;
    logic rst_n=0,frame_tick=0,candidate_sample_ready=0,candidate_result_valid=0;
    logic [31:0] candidate_result_id=0;
    logic signed [23:0] candidate_left=0,candidate_right=0;
    logic candidate_clipped=0;
    wire candidate_cancel,candidate_sample_valid,candidate_result_ready;
    wire [31:0] candidate_sample_id,frame_count,frame_request_count,commit_count;
    wire [31:0] underrun_count,clip_count,current_id,committed_id;
    wire signed [23:0] play_left,play_right,committed_left,committed_right;
    wire pending_valid,commit_pulse,committed_clip,dispatched_this_frame;
    premixed_frame_adapter dut(.*);
    integer sample_accepts=0,result_accepts=0,ledger_commits=0,ledger_clips=0,cases=0;
    logic [31:0] last_sample_id,accepted_result_id;
    logic had_result=0;
    logic signed [23:0] accepted_l,accepted_r;
    logic accepted_clip;
    always @(posedge clk) begin
        if(!rst_n) begin
            sample_accepts=0;result_accepts=0;ledger_commits=0;ledger_clips=0;had_result=0;
        end else begin
            if(frame_tick) begin
                if(candidate_sample_valid || candidate_result_ready || commit_pulse)
                    $fatal(1,"FRAME_EDGE_HANDSHAKE_FORBIDDEN");
                had_result=0;
            end
            if(candidate_sample_valid && candidate_sample_ready) begin
                sample_accepts++;last_sample_id=candidate_sample_id;
            end
            if(candidate_result_valid && candidate_result_ready) begin
                result_accepts++;
                if(candidate_result_id!==last_sample_id || had_result)
                    $fatal(1,"RESULT_WITHOUT_CURRENT_REQUEST_OR_DUPLICATE");
                had_result=1;accepted_result_id=candidate_result_id;
                accepted_l=candidate_left;accepted_r=candidate_right;accepted_clip=candidate_clipped;
            end
            if(commit_pulse) begin
                if(!had_result || committed_id!==accepted_result_id || committed_id!==current_id)
                    $fatal(1,"COMMIT_WITHOUT_ACCEPTED_CURRENT_RESULT");
                if(committed_left!==accepted_l || committed_right!==accepted_r || committed_clip!==accepted_clip)
                    $fatal(1,"PREMIXED_PAYLOAD_CHANGED");
                ledger_commits++;ledger_clips+=accepted_clip;had_result=0;
                $display("COMMIT id=%0d L=%0d R=%0d clip=%0d",committed_id,committed_left,committed_right,committed_clip);
            end
            #1;
            if(commit_count!==ledger_commits || clip_count!==ledger_clips)
                $fatal(1,"COMMIT_CLIP_EXACTLY_ONCE_LEDGER");
        end
    end
    task automatic edges(input integer n);repeat(n) @(negedge clk);endtask
    task automatic frame;
        @(negedge clk);frame_tick=1;
        @(negedge clk);frame_tick=0;
    endtask
    task automatic response(input logic [31:0] id,
        input logic signed [23:0] l,r,input logic cl);
        @(negedge clk);candidate_result_id=id;candidate_left=l;candidate_right=r;
        candidate_clipped=cl;candidate_result_valid=1;
        edges(5);candidate_result_valid=0;edges(2);
    endtask
    task automatic require_one(input integer old_count);
        edges(2);
        if(sample_accepts!=old_count+1) $fatal(1,"REQUEST_NOT_EXACTLY_ONCE");
    endtask
    integer old_accept,old_commit,old_clip;
    initial begin
        edges(4);rst_n=1;edges(2);
        candidate_sample_ready=1;old_accept=sample_accepts;
        frame();require_one(old_accept);
        response(current_id,24'sd111,-24'sd222,0);
        if(commit_count!=1 || play_left!=111 || play_right!=-222) $fatal(1,"NORMAL_STEREO_COMMIT");cases++;
        candidate_sample_ready=0;frame();edges(5);
        if(!candidate_sample_valid || candidate_sample_id!==current_id) $fatal(1,"QUEUED_REQUEST_NOT_HELD");
        old_accept=sample_accepts;candidate_sample_ready=1;require_one(old_accept);
        response(current_id,24'sh7fffff,24'sh800000,1);
        if(clip_count!=1) $fatal(1,"CLIPPED_CURRENT_COMMIT");cases++;
        old_commit=commit_count;old_clip=clip_count;
        response(current_id,24'sh7fffff,24'sh800000,1);
        if(commit_count!=old_commit || clip_count!=old_clip) $fatal(1,"DUPLICATE_RESULT_ACCEPTED");cases++;
        candidate_sample_ready=0;frame();edges(3);
        old_accept=sample_accepts;
        @(negedge clk);frame_tick=1;candidate_sample_ready=1;
        @(negedge clk);frame_tick=0;require_one(old_accept);
        response(current_id,24'sd300,24'sd400,0);cases++;
        old_commit=commit_count;frame();edges(2);
        response(current_id-1,24'sd999,24'sd999,1);
        if(commit_count!=old_commit || play_left!=300 || play_right!=400)
            $fatal(1,"STALE_RESULT_OR_LEGAL_HELD_AUDIO");cases++;
        @(negedge clk);candidate_result_valid=1;candidate_result_id=current_id;
        candidate_left=888;candidate_right=888;candidate_clipped=1;frame_tick=1;
        @(negedge clk);candidate_result_valid=0;frame_tick=0;edges(3);
        if(commit_count!=old_commit || clip_count!=old_clip) $fatal(1,"FRAME_OLD_RESULT_COMMITTED");
        response(current_id,-24'sd123,24'sd456,0);cases++;
        candidate_sample_ready=0;frame();edges(3);
        @(negedge clk);rst_n=0;edges(3);candidate_result_valid=0;rst_n=1;edges(3);
        if(candidate_sample_valid || pending_valid || play_left || play_right || current_id)
            $fatal(1,"RESET_NOT_CLEAN");
        candidate_sample_ready=1;frame();edges(2);
        response(current_id,24'sd17,-24'sd19,0);
        if(commit_count!=1 || clip_count!=0) $fatal(1,"RESET_RECOVERY_COMMIT");cases++;
        $display("PASS PREMIXED_TRANSPORT cases=%0d commits=%0d clips=%0d synthetic_only=1",cases,commit_count,clip_count);
        $finish;
    end
    initial begin #1000000;$fatal(1,"TRANSPORT_WATCHDOG");end
endmodule
