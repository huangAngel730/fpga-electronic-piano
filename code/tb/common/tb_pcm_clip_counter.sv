`timescale 1ns/1ps
module tb_pcm_clip_counter;
    logic clk=0;
    always #5 clk=~clk;
    logic rst_n=1, frame_tick=0, calc_ready=1, pcm_valid=0;
    logic [31:0] pcm_req_id=0, sample_req_id;
    logic sample_req, pcm_ready, pending_valid;
    logic [95:0] voices_left=0, voices_right=0;
    wire signed [23:0] mixed_left, mixed_right;
    wire clip_left,clip_right,clip_any;
    wire signed [23:0] play_left,play_right;
    wire [31:0] audio_frame_count,pcm_request_count,pcm_commit_count,audio_underrun;
    wire [31:0] clip_count;
    wire [2:0] small_count;
    integer checks=0;
    pcm_mixer_4voice mixer (
        .voices_left(voices_left),.voices_right(voices_right),
        .mixed_left(mixed_left),.mixed_right(mixed_right),
        .clip_left(clip_left),.clip_right(clip_right),.clip_any(clip_any)
    );
    pcm_frame_buffer buffer_dut (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .sample_req(sample_req),.sample_req_id(sample_req_id),
        .pcm_valid(pcm_valid),.pcm_ready(pcm_ready),.pcm_req_id(pcm_req_id),
        .pcm_left(mixed_left),.pcm_right(mixed_right),.play_left(play_left),
        .play_right(play_right),.pending_valid(pending_valid),
        .audio_frame_count(audio_frame_count),.pcm_request_count(pcm_request_count),
        .pcm_commit_count(pcm_commit_count),.audio_underrun(audio_underrun)
    );
    pcm_clip_counter dut (.*);
    pcm_clip_counter #(.COUNTER_WIDTH(3)) tiny (
        .clk(clk),.rst_n(rst_n),.pcm_valid(pcm_valid),
        .pcm_ready(pcm_ready),.clip_any(clip_any),.clip_count(small_count)
    );
    task automatic check(input logic ok,input string name);
        checks++;
        if(ok!==1'b1) $fatal(1,"FAIL %s",name);
    endtask
    task automatic frame;
        @(negedge clk); frame_tick=1;
        @(posedge clk); #1;
        @(negedge clk); frame_tick=0;
    endtask
    task automatic offer(input logic [31:0] req,
                         input logic [95:0] left_voices,
                         input logic [95:0] right_voices,
                         input logic should_accept);
        @(negedge clk);
        pcm_req_id=req;voices_left=left_voices;voices_right=right_voices;
        pcm_valid=1;
        #1;
        check(pcm_ready==should_accept,"handshake readiness");
        @(posedge clk); #1;
        @(negedge clk);pcm_valid=0;
    endtask
    // Each 24-bit slice is one independent voice. Four peaks sum to MAX+1.
    localparam logic [95:0] CLIP_POS={4{24'd2097152}};
    localparam logic [95:0] CLIP_NEG={4{24'sh9fffff}};
    initial begin
        #1;rst_n=0;
        #1;
        check(clip_count==0 && small_count==0,"reset clears counters");
        repeat(3) @(negedge clk);
        rst_n=1;
        // No frame request exists: even clipped valid data cannot be counted.
        offer(0,CLIP_POS,0,0);
        check(clip_count==0 && pcm_commit_count==0,"idle offer ignored");
        frame(); // generation 1
        offer(1,CLIP_POS,0,1);
        check(clip_left && !clip_right && clip_count==1 && pcm_commit_count==1,
              "left clip exactly once on first commit");
        offer(1,CLIP_POS,0,0);
        check(clip_count==1,"pending full and repeated valid do not recount");
        frame(); // generation 2
        offer(1,CLIP_POS,CLIP_NEG,0);
        check(clip_count==1,"stale generation discarded");
        offer(2,0,CLIP_NEG,1);
        check(!clip_left && clip_right && clip_count==2,
              "right-only clip counts once");
        frame(); // generation 3
        @(negedge clk);
        pcm_req_id=3;pcm_valid=1;voices_left=CLIP_POS;
        frame_tick=1;
        #1;check(!pcm_ready,"frame tick blocks simultaneous commit");
        @(posedge clk);#1;
        @(negedge clk);frame_tick=0;pcm_valid=0;
        check(clip_count==2,"no count at blocked frame edge");
        frame(); // generation 5 (frame edge above generated 4)
        offer(4,CLIP_POS,0,0);
        check(clip_count==2,"late result after new frame discarded");
        offer(5,{{3{24'd0}},24'd1},{{3{24'd0}},24'd2},1);
        check(clip_count==2 && pcm_commit_count==3 && !clip_any,
              "nonclipped commit not counted");
        // Fill 3-bit counter, then prove it saturates. 32-bit counter follows
        // the number of accepted clipped stereo samples without wrap.
        for(integer i=0;i<10;i++) begin
            frame();
            offer(sample_req_id,CLIP_POS,CLIP_NEG,1);
            check(clip_left && clip_right,"both channels clipped");
            check(clip_count==i+3,"32-bit counter counts committed frames");
            if(i>=4)check(small_count==3'b111,"3-bit counter saturates");
        end
        check(pcm_commit_count==13,"buffer and clip counters aligned");
        @(negedge clk);rst_n=0;#1;
        check(clip_count==0 && small_count==0 && pcm_commit_count==0,
              "asynchronous reset clears PCM and clip counters");
        repeat(3) @(negedge clk);rst_n=1;
        frame();
        offer(sample_req_id,CLIP_POS,0,1);
        check(clip_count==1 && small_count==1,
              "post-reset clip restarts from one");
        $display("PASS tb_pcm_clip_counter checks=%0d",checks);
        $finish;
    end
    initial begin #1000000; $fatal(1,"clip counter timeout"); end
endmodule
