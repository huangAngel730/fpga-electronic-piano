// NEW diagnostic producer only; original buffer/tick/PT8211 transmitter are read-only.
// Capture at posedge pre-NBA: these are values consumed by the original RTL.
`timescale 1ns/1ps
module tb_public_serial;
    reg clk=0, rst_n=1;
    always #12.5 clk=~clk;
    wire frame_tick, sample_tick, request, pending, pcm_ready;
    wire bclk, ws, din, legacy_ready;
    wire [31:0] req_id, frames, requests, commits, underflow;
    wire signed [23:0] play_l, play_r;
    reg pcm_valid=0, clip=0;
    reg [31:0] pcm_id=0;
    reg signed [23:0] left=0, right=0;
    integer cycle=0, epoch=0, fd, delay_left=-1, hold_left=0;
    reg stale_phase=0;
    function automatic integer vector(input integer n);
        case (n%16)
            0:vector=0; 1:vector=8388607; 2:vector=-8388608;
            3:vector=127; 4:vector=128; 5:vector=129;
            6:vector=-127; 7:vector=-128; 8:vector=-129;
            9:vector=8388480; 10:vector=8388479; 11:vector=-8388481;
            12:vector=1234567; 13:vector=-2345678;
            14:vector=7654321; 15:vector=-6543210;
        endcase
    endfunction
    sample_tick_gen #(.PHASE_STEP(32'd5153961)) tick (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick));
    pcm_frame_buffer buffer (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick), .calc_ready(1'b1),
        .sample_req(request), .sample_req_id(req_id), .pcm_valid(pcm_valid),
        .pcm_ready(pcm_ready), .pcm_req_id(pcm_id), .pcm_left(left), .pcm_right(right),
        .play_left(play_l), .play_right(play_r), .pending_valid(pending),
        .audio_frame_count(frames), .pcm_request_count(requests),
        .pcm_commit_count(commits), .audio_underrun(underflow));
`ifdef WRONG_STEREO
    wire signed [23:0] serial_l=play_r, serial_r=play_l;
`else
    wire signed [23:0] serial_l=play_l, serial_r=play_r;
`endif
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) tx (
        .clk(clk), .rst_n(rst_n), .valid(1'b1), .pcm_left(serial_l), .pcm_right(serial_r),
        .bclk(bclk), .lrck(ws), .din(din), .ready(legacy_ready), .frame_tick(frame_tick));
    // Intentional underruns 8/9, stale identity 12, and post-commit valid HOLD.
    // clip is synthetic source metadata, NOT an original buffer clip output.
    always @(negedge clk) begin
        if (!rst_n) begin
            pcm_valid=0; pcm_id=0; left=0; right=0; clip=0;
            delay_left=-1; hold_left=0; stale_phase=0;
        end else begin
            if (hold_left>0) begin
                hold_left=hold_left-1;
                if (hold_left==0) begin
                    if (stale_phase) begin
                        pcm_id=req_id; stale_phase=0; hold_left=6;
                    end else pcm_valid=0;
                end
            end
            if (delay_left>=0) begin
                if (delay_left==0) begin
                    pcm_valid=1; pcm_id=req_id;
                    left=24'(vector(req_id+epoch)); right=24'(vector(req_id+epoch+7));
                    clip=(req_id%17==0); hold_left=6;
                    if (req_id==12) begin pcm_id=req_id-1; stale_phase=1; hold_left=16; end
                    delay_left=-1;
                end else delay_left=delay_left-1;
            end
            if (request && !(epoch==1 && (req_id==8 || req_id==9))) delay_left=8;
        end
    end
    always @(posedge clk) begin
        cycle=cycle+1;
        $fdisplay(fd,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
            cycle,epoch,rst_n,sample_tick,frame_tick,request,req_id,pcm_valid,pcm_ready,
            pcm_id,$signed(left),$signed(right),clip,pending,$signed(play_l),$signed(play_r),
            frames,requests,commits,underflow,bclk,ws,din);
    end
    initial begin
        fd=$fopen("capture.csv","w");
        if (!fd) $fatal(1,"CAPTURE_OPEN");
        $fdisplay(fd,"C_PCM_SERIAL_PUBLIC_V1,NEW_MODULE_RTL_FIXTURE,40000000,PRE_NBA,PT8211_LSBJ");
        // Make the initial asynchronous assertion an actual edge before capture.
        #1; rst_n=0;
        repeat(12) @(negedge clk); epoch=1; rst_n=1;
        wait(frames==72); @(negedge clk); rst_n=0;
        repeat(12) @(negedge clk); epoch=2; rst_n=1;
        wait(frames==72); @(negedge clk);
        $fdisplay(fd,"END,%0d",cycle); $fclose(fd);
        $display("C_MODULE_FIXTURE_PASS epochs=2 frames_per_epoch=72"); $finish;
    end
    initial begin #4000000; $fatal(1,"C_MODULE_FIXTURE_TIMEOUT"); end
endmodule
