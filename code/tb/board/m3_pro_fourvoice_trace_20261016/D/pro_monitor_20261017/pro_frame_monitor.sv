// Testbench-only passive observer. No production hierarchy or feedback.
// All ports use the caller's 40 MHz pre-NBA sampling edge. Mapping is subject
// to M2 approval; this normalized contract is not a claim about a missing top.
`timescale 1ns/1ps
module pro_frame_monitor #(parameter MAX_IDS=4096) (
    input wire clk, rst_n, pll_locked, audio_stable, pa_en,
    input wire frame_tick, cancel,
    input wire req_valid, req_ready,
    input wire [31:0] req_id,
    input wire [63:0] req_payload,
    input wire lane_tick,
    input wire [1:0] lane,
    input wire [31:0] lane_req_id,
    input wire result_valid, result_ready,
    input wire [31:0] result_id,
    input wire signed [23:0] left, right,
    input wire clipped,
    input wire commit,
    input wire [31:0] commit_id,
    input wire signed [23:0] commit_left, commit_right,
    input wire commit_clipped,
    input wire bclk, ws, din, finish,
    output reg [31:0] accepted_count=0, committed_count=0,
    output reg [31:0] canceled_count=0, max_commit_cycles=0
);
    integer cycle=0, epoch=-1, count_ids=0, k, fd=0;
    integer accepted_cycle=0, first_frame=0, last_frame=0, intervals=0;
    integer latency=0, drift=0;
    reg in_reset=0, pending=0, transferred=0, seen_first=0;
    reg req_hold=0, result_hold=0, have_frame=0, ended=0;
    reg [31:0] ids[0:MAX_IDS-1];
    reg [31:0] pending_id=0, held_req_id=0;
    reg [63:0] held_req_payload=0;
    reg [80:0] held_result=0, returned_result=0;
    reg [3:0] lanes=0;
    wire [80:0] result_tuple={result_id,left,right,clipped};
    wire [80:0] commit_tuple={commit_id,commit_left,commit_right,commit_clipped};
    string trace_path;

    task record_edge;
        begin
            $fwrite(fd,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%08x,%016x,%0d,%0d,%08x,%0d,%0d,%08x,%0d,%0d,%0d,%0d,%08x,%0d,%0d,%0d,%0d,%0d,%0d\n",
                cycle,epoch,rst_n,pll_locked,audio_stable,pa_en,frame_tick,cancel,req_valid,req_ready,req_id,req_payload,
                lane_tick,lane,lane_req_id,result_valid,result_ready,result_id,left,right,clipped,commit,commit_id,
                commit_left,commit_right,commit_clipped,bclk,ws,din);
        end
    endtask

    task fail;
        input [8*48-1:0] code;
        begin
            $display("FIRST_REJECT %0s cycle=%0d epoch=%0d request=%08x",code,cycle,epoch,pending_id);
            // Preserve the rejected edge too, including its actual public ports.
            if(fd) begin record_edge();$fflush(fd);end
            $fatal(1,"PRO_FRAME_MONITOR_REJECT");
        end
    endtask

    initial begin
        if(!$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"missing TRACE");
        fd=$fopen(trace_path,"w");
        if(!fd) $fatal(1,"cannot open trace");
        $fwrite(fd,"cycle,epoch,rst_n,pll_locked,audio_stable,pa_en,frame_tick,cancel,req_valid,req_ready,req_id,req_payload,lane_tick,lane,lane_req_id,result_valid,result_ready,result_id,left,right,clipped,commit,commit_id,commit_left,commit_right,commit_clipped,bclk,ws,din\n");
    end

    always @(posedge clk) begin
        cycle=cycle+1;
        if(ended) fail("ROWS_AFTER_FINISH");
        if(rst_n!==0 && rst_n!==1) fail("RESET_UNKNOWN");
        // A cleanup at/after the deadline cannot erase an already late request.
        if(pending && cycle-accepted_cycle>=833) fail("REQUEST_DEADLINE");
        if(!rst_n) begin
            if(pa_en!==0) fail("PA_DURING_RESET");
            if(!in_reset) begin
                epoch=epoch+1;
                if(pending) canceled_count=canceled_count+1;
            end
            in_reset=1;
            pending=0;transferred=0;seen_first=0;lanes=0;
            req_hold=0;result_hold=0;count_ids=0;
            have_frame=0;intervals=0;
        end else begin
            if(epoch<0) fail("MISSING_INITIAL_RESET");
            in_reset=0;
            if((^{pll_locked,audio_stable,pa_en,frame_tick,cancel,req_valid,req_ready,
                 lane_tick,result_valid,result_ready,commit,finish})===1'bx)
                fail("CONTROL_UNKNOWN");
            if(pa_en && (!pll_locked || !audio_stable)) fail("PA_BEFORE_SAFE");
            if(frame_tick) begin
                if(pending) fail("NEXT_FRAME_WITH_PENDING");
                if(have_frame) begin
                    if(cycle-last_frame!=833 && cycle-last_frame!=834) fail("FRAME_INTERVAL");
                    intervals=intervals+1;
                    drift=3*(cycle-first_frame)-2500*intervals;
                    // <=1 cycle phase tolerance for this bounded 40MHz/48kHz window.
                    if(drift>3 || drift< -3) fail("FRAME_AVERAGE_DRIFT");
                end else begin first_frame=cycle;have_frame=1;end
                last_frame=cycle;
            end else if(have_frame && cycle-last_frame>834 && !finish)
                fail("FRAME_STALLED");

            if(cancel) begin
                if(commit) fail("COMMIT_ON_CANCEL");
                if(pending) canceled_count=canceled_count+1;
                pending=0;transferred=0;seen_first=0;lanes=0;
                req_hold=0;result_hold=0;
            end else begin
                if(req_hold && (!req_valid || req_id!==held_req_id || req_payload!==held_req_payload))
                    fail("REQUEST_NOT_HELD");
                if(req_valid && ((^{req_id,req_payload})===1'bx)) fail("REQUEST_UNKNOWN");
                req_hold=req_valid && !req_ready;
                held_req_id=req_id;held_req_payload=req_payload;
                if(req_valid && req_ready) begin
                    if(pending) fail("OVERLAPPING_REQUEST");
                    if(count_ids>=MAX_IDS) fail("ID_HISTORY_BOUND");
                    for(k=0;k<count_ids;k=k+1)
                        if(ids[k]===req_id) fail("DUPLICATE_REQUEST_ID");
                    ids[count_ids]=req_id;count_ids=count_ids+1;
                    pending=1;pending_id=req_id;accepted_cycle=cycle;
                    transferred=0;seen_first=0;lanes=0;
                    accepted_count=accepted_count+1;
                end
                if(pending && cycle-accepted_cycle>=833) fail("REQUEST_DEADLINE");
                if(lane_tick) begin
                    if((^{lane,lane_req_id})===1'bx) fail("LANE_UNKNOWN");
                    if(!pending || transferred || lane_req_id!==pending_id) fail("LANE_OWNER");
                    if(lanes[lane]) fail("DUPLICATE_LANE");
                    lanes[lane]=1;
                end
                if(result_hold && (!result_valid || result_tuple!==held_result)) fail("RESULT_NOT_HELD");
                if(result_valid) begin
                    if((^result_tuple)===1'bx) fail("RESULT_UNKNOWN");
                    // Check at valid, including a wrong ID that prevents ready.
                    if(!pending) fail("RESULT_WITHOUT_REQUEST");
                    if(result_id!==pending_id) fail("RESULT_ID");
                    if(lanes!==4'b1111) fail("RESULT_BEFORE_FOUR_LANES");
                    if(!seen_first) seen_first=1;
                    if(result_ready) begin
                        if(transferred) fail("DUPLICATE_RESULT_TRANSFER");
                        transferred=1;returned_result=result_tuple;
                    end
                end
                result_hold=result_valid && !result_ready;
                held_result=result_tuple;
                if(commit) begin
                    if(!pending || !transferred) fail("COMMIT_WITHOUT_RETURN");
                    if(commit_tuple!==returned_result) fail("COMMIT_ID_PCM_CLIP");
                    latency=cycle-accepted_cycle;
                    if(latency>=833) fail("COMMIT_DEADLINE");
                    if(latency>max_commit_cycles) max_commit_cycles=latency;
                    committed_count=committed_count+1;
                    pending=0;transferred=0;seen_first=0;lanes=0;
                end
            end
            if(finish) begin
                if(pending || req_hold || result_hold) fail("END_UNCLOSED");
                if(accepted_count!=committed_count+canceled_count) fail("DISPOSITION_COUNTS");
                ended=1;
                $display("MONITOR_END accepts=%0d commits=%0d cancels=%0d max=%0d epochs=%0d",accepted_count,committed_count,canceled_count,max_commit_cycles,epoch+1);
            end
        end
        record_edge();
        if(ended) begin $fflush(fd);$fclose(fd);fd=0;end
    end
endmodule
