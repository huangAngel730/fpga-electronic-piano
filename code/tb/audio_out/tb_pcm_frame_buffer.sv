`timescale 1ns/1ps
module tb_pcm_frame_buffer;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0, frame_tick = 0, calc_ready = 1;
    logic sample_req, pcm_valid = 0, pcm_ready, pending_valid;
    logic [31:0] sample_req_id, pcm_req_id = 0;
    logic signed [23:0] pcm_left = 0, pcm_right = 0;
    logic signed [23:0] play_left, play_right;
    logic [31:0] audio_frame_count, pcm_request_count;
    logic [31:0] pcm_commit_count, audio_underrun;
    integer checks = 0, errors = 0;

    pcm_frame_buffer dut (.*);

    task automatic check_result(input logic pass, input string name);
        checks++;
        if (!pass) begin errors++; $display("FAIL %s", name); end
    endtask

    task automatic frame;
        @(negedge clk); frame_tick = 1;
        @(posedge clk); #1;
        @(negedge clk); frame_tick = 0;
        #1;
    endtask

    task automatic send(input integer id, input integer left_sample,
                        input integer right_sample);
        @(negedge clk);
        pcm_req_id = id;
        pcm_left = left_sample;
        pcm_right = right_sample;
        pcm_valid = 1;
        #1;
        check_result(pcm_ready, "current generation ready");
        @(posedge clk); #1;
        @(negedge clk); pcm_valid = 0;
    endtask

    initial begin
        #2;
        check_result(!pcm_ready && !sample_req && !pending_valid, "reset handshake");
        check_result(play_left == 0 && play_right == 0 && audio_underrun == 0,
               "reset zero and no underrun");
        @(negedge clk); rst_n = 1;
        frame(); // request A: 1
        check_result(sample_req_id == 1 && play_left == 0 && audio_underrun == 0,
               "first frame silent");
        send(1, 16, -16); // A
        check_result(pending_valid && pcm_commit_count == 1, "A buffered");
        @(negedge clk); pcm_req_id = 1; pcm_valid = 1;
        #1; check_result(!pcm_ready, "full buffer backpressures");
        pcm_valid = 0;
        frame(); // consume A, request B: 2
        check_result(play_left == 16 && play_right == -16 && audio_underrun == 0,
               "A played stereo");
        send(2, 32, -32); // B
        frame(); // consume B, request 3
        check_result(play_left == 32 && play_right == -32, "B played stereo");
        repeat (3) frame(); // requests 4,5,6; B repeated three times
        check_result(play_left == 32 && play_right == -32 && audio_underrun == 3,
               "B held for three missing frames");
        @(negedge clk); pcm_req_id = 3; pcm_valid = 1;
        #1; check_result(!pcm_ready, "late result refused");
        @(negedge clk); pcm_valid = 0; // producer cancels expired generation
        send(6, 48, -48); // C from current generation
        frame();
        check_result(play_left == 48 && play_right == -48 && audio_underrun == 3,
               "C restores without extra underrun");
        check_result(audio_frame_count == 7 && pcm_request_count == 7 &&
               pcm_commit_count == 3, "frame request commit counters");
        @(negedge clk); rst_n = 0; #1;
        check_result(play_left == 0 && play_right == 0 && !pending_valid &&
               audio_underrun == 0 && audio_frame_count == 0,
               "asynchronous runtime reset clears state");
        @(negedge clk); rst_n = 1; calc_ready = 0;
        frame();
        check_result(!sample_req && pcm_request_count == 0 && audio_frame_count == 1,
               "busy calculator does not accept request");
        frame();
        check_result(audio_underrun == 0 && play_left == 0, "no pre-first underrun");
        $display("pcm_frame_buffer checks=%0d errors=%0d", checks, errors);
        if (errors) $fatal(1, "FAIL");
        $display("PASS tb_pcm_frame_buffer");
        $finish;
    end
    initial begin #100000; $fatal(1, "timeout"); end
endmodule
