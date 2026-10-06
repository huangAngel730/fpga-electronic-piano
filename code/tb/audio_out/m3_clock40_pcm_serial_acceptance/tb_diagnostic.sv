// Explicit diagnostic fixture, NOT UART-produced music/algorithm evidence.
`timescale 1ns/1ps
module tb_diagnostic;
    reg clk=0, rst_n=0, pcm_valid=0;
    always #12.5 clk=~clk;
    reg signed [23:0] pcm_left=0, pcm_right=0;
    reg [31:0] pcm_id=0;
    wire pcm_ready, request, pending, frame_tick, bclk, ws, din, ready;
    wire [31:0] request_id, frames, requests, commits, underrun;
    wire signed [23:0] play_left, play_right;
    integer offered=0, skipped=0;
    function automatic integer vector(input integer index);
        case(index % 24)
          0:vector=0; 1:vector=1; 2:vector=-1;
          3:vector=127; 4:vector=128; 5:vector=129;
          6:vector=-127; 7:vector=-128; 8:vector=-129;
          9:vector=8388607; 10:vector=8388479; 11:vector=8388480;
          12:vector=-8388608; 13:vector=-8388481; 14:vector=-8388480;
          15:vector=256; 16:vector=-256; 17:vector=8448;
          18:vector=-12544; 19:vector=32767; 20:vector=-32768;
          21:vector=1234567; 22:vector=-2345678; 23:vector=7654321;
        endcase
    endfunction
    pcm_frame_buffer u_buffer (
        .clk, .rst_n, .frame_tick, .calc_ready(1'b1),
        .sample_req(request), .sample_req_id(request_id), .pcm_valid, .pcm_ready,
        .pcm_req_id(pcm_id), .pcm_left, .pcm_right, .play_left, .play_right,
        .pending_valid(pending), .audio_frame_count(frames),
        .pcm_request_count(requests), .pcm_commit_count(commits), .audio_underrun(underrun));
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) u_tx (
        .clk, .rst_n, .valid(1'b1), .pcm_left(play_left), .pcm_right(play_right),
        .bclk, .lrck(ws), .din, .ready, .frame_tick);
    serial_capture monitor (
        .clk, .rst_n, .frame_tick, .pcm_valid, .pcm_ready, .pcm_id, .request_id,
        .pcm_left, .pcm_right, .play_left, .play_right,
        .frame_count(frames), .commit_count(commits), .underrun, .bclk, .ws, .din);
    always @(negedge clk) if (rst_n) begin
        if (pcm_valid && !pcm_ready) pcm_valid=0; // preceding posedge committed
        if (request) begin
            if (offered == 12 && skipped < 3) begin
                skipped=skipped+1;
                $fdisplay(monitor.fd, "G %.3f %0d %0d", $realtime, request_id, skipped);
            end else begin
                pcm_id=request_id;
                pcm_left=24'(vector(offered));
                pcm_right=24'(vector(offered+7));
                $fdisplay(monitor.fd, "D %.3f %0d %0d %0d %0d", $realtime,
                          offered, pcm_id, $signed(pcm_left), $signed(pcm_right));
                pcm_valid=1;
                offered=offered+1;
            end
        end
    end
    initial begin
        repeat(10) @(negedge clk); rst_n=1;
        wait(frames >= 40);
        // Finish only after the last complete physical stereo word pair.
        @(posedge ws); @(negedge ws); #1000;
        if (underrun != 3 || skipped != 3 || offered < 24)
            $fatal(1, "DIAG_END underrun=%0d", underrun);
        $fdisplay(monitor.fd, "END diagnostic %0d %0d", frames, skipped);
        $fclose(monitor.fd);
        $display("SIM_DONE diagnostic frames=%0d underrun=%0d", frames, underrun); $finish;
    end
    initial begin #2000000; $fatal(1, "DIAGNOSTIC_TIMEOUT"); end
endmodule
