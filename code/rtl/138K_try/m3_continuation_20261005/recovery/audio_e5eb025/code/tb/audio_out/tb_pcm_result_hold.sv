`timescale 1ns/1ps
module tb_pcm_result_hold;
    logic clk=0;
    always #5 clk=~clk;
    logic rst_n=1,frame_tick=0,calc_ready=1,downstream_stall=0;
    logic result_valid=0,result_ready,pcm_valid,pcm_ready,buffer_ready,sink_valid;
    logic [31:0] result_req_id=0,sample_req_id,pcm_req_id;
    logic [95:0] voices_left=0,voices_right=0;
    wire signed [23:0] result_left,result_right,pcm_left,pcm_right,play_left,play_right;
    wire clip_left,clip_right,result_clip_any,pcm_clip_any,sample_req,pending_valid;
    wire [31:0] audio_frame_count,pcm_request_count,pcm_commit_count;
    wire [31:0] audio_underrun,clip_count;
    integer checks=0;
    localparam logic [95:0] POS={4{24'd2097152}};
    localparam logic [95:0] NEG={4{24'sh9fffff}};

    pcm_mixer_4voice mixer (
        .voices_left(voices_left),.voices_right(voices_right),
        .mixed_left(result_left),.mixed_right(result_right),
        .clip_left(clip_left),.clip_right(clip_right),.clip_any(result_clip_any)
    );
    assign sink_valid = pcm_valid && !downstream_stall;
    assign pcm_ready = buffer_ready && !downstream_stall;
    pcm_result_hold hold_dut (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .current_req_id(sample_req_id),.result_valid(result_valid),
        .result_ready(result_ready),.result_req_id(result_req_id),
        .result_left(result_left),.result_right(result_right),
        .result_clip_any(result_clip_any),
        .pcm_valid(pcm_valid),.pcm_ready(pcm_ready),
        .pcm_req_id(pcm_req_id),.pcm_left(pcm_left),.pcm_right(pcm_right),
        .pcm_clip_any(pcm_clip_any)
    );
    pcm_frame_buffer buffer_dut (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),
        .calc_ready(calc_ready),.sample_req(sample_req),
        .sample_req_id(sample_req_id),.pcm_valid(sink_valid),
        .pcm_ready(buffer_ready),.pcm_req_id(pcm_req_id),
        .pcm_left(pcm_left),.pcm_right(pcm_right),
        .play_left(play_left),.play_right(play_right),.pending_valid(pending_valid),
        .audio_frame_count(audio_frame_count),.pcm_request_count(pcm_request_count),
        .pcm_commit_count(pcm_commit_count),.audio_underrun(audio_underrun)
    );
    pcm_clip_counter counter_dut (
        .clk(clk),.rst_n(rst_n),.pcm_valid(pcm_valid),
        .pcm_ready(pcm_ready),.clip_any(pcm_clip_any),.clip_count(clip_count)
    );
    task automatic check(input logic ok,input string message);
        checks++;
        if(ok!==1'b1) $fatal(1,"FAIL %s (id=%0d clips=%0d commits=%0d)",
                             message,sample_req_id,clip_count,pcm_commit_count);
    endtask
    task automatic frame;
        @(negedge clk);frame_tick=1;
        @(posedge clk);#1;
        @(negedge clk);frame_tick=0;
        #1;
    endtask
    task automatic offer(input logic [31:0] req,
                         input logic [95:0] left_words,right_words,
                         input logic expected_ready);
        @(negedge clk);
        result_req_id=req;voices_left=left_words;voices_right=right_words;
        result_valid=1;
        #1;check(result_ready==expected_ready,"result ready and generation");
        @(posedge clk);#1;
        @(negedge clk);result_valid=0;
    endtask
    task automatic settle;
        @(posedge clk);#1;
        @(negedge clk);
    endtask
    initial begin
        #1;rst_n=0;#1;
        check(!pcm_valid && !result_ready && clip_count==0 &&
              pcm_left==0 && pcm_right==0,"power-on reset silence");
        repeat(3) @(negedge clk);rst_n=1;
        offer(0,POS,NEG,0);
        check(!pcm_valid && clip_count==0,"no request cannot create PCM");
        frame(); // request 1
        check(sample_req_id==1 && sample_req,"first request generated");
        offer(1,POS,0,1);
        check(pcm_valid && pcm_req_id==1 && pcm_left==24'sh7fffff &&
              pcm_right==0 && pcm_clip_any,"stereo PCM/clip captured atomically");
        voices_left=0;voices_right=NEG;
        #1;check(pcm_left==24'sh7fffff && pcm_right==0 && pcm_clip_any,
                 "producer changes cannot alter registered PCM/clip");
        settle();
        check(!pcm_valid && pending_valid && clip_count==1 &&
              pcm_commit_count==1,"one buffer commit counted once");
        offer(1,0,NEG,0);
        check(!pcm_valid && clip_count==1,"duplicate result refused");
        frame(); // request 2 and consume A
        downstream_stall=1;
        offer(2,0,NEG,1);
        check(pcm_valid && !pcm_ready && pcm_clip_any &&
              pcm_right==24'sh800000,"held right clip is backpressured");
        voices_left=POS;voices_right=0;
        repeat(3) begin
            settle();
            check(pcm_valid && !pcm_ready && pcm_left==0 &&
                  pcm_right==24'sh800000 && pcm_clip_any && clip_count==1,
                  "held result stable through stall");
        end
        frame(); // request 3, discard held generation 2
        check(!pcm_valid && !pcm_clip_any && clip_count==1 &&
              pcm_commit_count==1 && play_left==24'sh7fffff,
              "expired result not submitted or counted");
        downstream_stall=0;
        offer(2,POS,NEG,0);
        check(!pcm_valid && clip_count==1,"late generation refused");
        offer(3,POS,NEG,1);
        check(pcm_valid && pcm_clip_any && pcm_req_id==3,
              "new generation captured");
        settle();
        check(clip_count==2 && pcm_commit_count==2 && pending_valid &&
              !pcm_valid,"both clipped channels count one sample");
        frame(); // request 4 and consume B
        offer(4,POS,0,1);
        check(pcm_valid && pcm_clip_any,"result held before next boundary");
        frame_tick=1; // offer() returned at negedge; no commit edge yet
        #1;check(!pcm_ready,"same-edge frame disallows commit");
        @(posedge clk);#1;
        @(negedge clk);frame_tick=0;
        check(!pcm_valid && clip_count==2 && pcm_commit_count==2,
              "frame edge discard has no clip increment");
        // Frame edge above made request 5.
        offer(5,{{3{24'd0}},24'd7},{{3{24'd0}},24'd8},1);
        check(pcm_valid && !pcm_clip_any,"nonclipped result captured");
        settle();
        check(clip_count==2 && pcm_commit_count==3,
              "nonclipped commit does not count");
        offer(5,POS,0,0);
        check(!pcm_valid,"same generation cannot submit twice");
        @(negedge clk);rst_n=0;#1;
        check(!pcm_valid && !pcm_clip_any && !pending_valid &&
              clip_count==0 && pcm_commit_count==0 &&
              pcm_left==0 && pcm_right==0,
              "asynchronous reset clears PCM/clip/counters");
        repeat(3) @(negedge clk);rst_n=1;
        calc_ready=0; frame();
        offer(sample_req_id,POS,NEG,0);
        check(!sample_req && clip_count==0 && pcm_commit_count==0,
              "rejected frame request cannot open producer window");
        calc_ready=1; frame();
        offer(sample_req_id,POS,0,1);settle();
        check(clip_count==1 && pcm_commit_count==1,
              "post-reset generation starts cleanly");
        $display("PASS tb_pcm_result_hold checks=%0d",checks);
        $finish;
    end
    initial begin #100000; $fatal(1,"result hold timeout"); end
endmodule
