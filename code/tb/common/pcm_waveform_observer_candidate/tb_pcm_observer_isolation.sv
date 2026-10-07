`timescale 1ns/1ps
module tb_pcm_observer_isolation;
    parameter integer DEPTH=32;
    parameter [31:0] FIRST_SEQ=0;
    reg audio_clk=0,pixel_clk=0,pixel_run=1;
    reg audio_rst_n=0,display_rst_n=0;
    always #12.5 audio_clk=~audio_clk;
    initial begin #7; forever begin #20;if(pixel_run)pixel_clk=~pixel_clk;else pixel_clk=0;end end
    wire frame_load,ref_frame;
    wire signed [23:0] play_left,play_right,ref_left,ref_right;
    wire req,ref_req,ready,ref_ready,pending,ref_pending;
    wire [31:0] req_id,ref_req_id,frames,ref_frames,requests,ref_requests,commits,ref_commits,underruns,ref_underruns;
    reg pcm_valid=0;
    reg [31:0] pcm_id=0;
    reg signed [23:0] pcm_left=0,pcm_right=0;
    wire bclk,ws,din,ref_bclk,ref_ws,ref_din;
    pcm_frame_buffer a_buffer(.clk(audio_clk),.rst_n(audio_rst_n),.frame_tick(frame_load),.calc_ready(1'b1),
        .sample_req(req),.sample_req_id(req_id),.pcm_valid(pcm_valid),.pcm_ready(ready),.pcm_req_id(pcm_id),
        .pcm_left(pcm_left),.pcm_right(pcm_right),.play_left(play_left),.play_right(play_right),
        .pending_valid(pending),.audio_frame_count(frames),.pcm_request_count(requests),
        .pcm_commit_count(commits),.audio_underrun(underruns));
    pcm_frame_buffer b_buffer(.clk(audio_clk),.rst_n(audio_rst_n),.frame_tick(ref_frame),.calc_ready(1'b1),
        .sample_req(ref_req),.sample_req_id(ref_req_id),.pcm_valid(pcm_valid),.pcm_ready(ref_ready),.pcm_req_id(pcm_id),
        .pcm_left(pcm_left),.pcm_right(pcm_right),.play_left(ref_left),.play_right(ref_right),
        .pending_valid(ref_pending),.audio_frame_count(ref_frames),.pcm_request_count(ref_requests),
        .pcm_commit_count(ref_commits),.audio_underrun(ref_underruns));
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) a_tx(.clk(audio_clk),.rst_n(audio_rst_n),.valid(1'b1),
        .pcm_left(play_left),.pcm_right(play_right),.bclk(bclk),.lrck(ws),.din(din),.ready(),.frame_tick(frame_load));
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) b_tx(.clk(audio_clk),.rst_n(audio_rst_n),.valid(1'b1),
        .pcm_left(ref_left),.pcm_right(ref_right),.bclk(ref_bclk),.lrck(ref_ws),.din(ref_din),.ready(),.frame_tick(ref_frame));
    integer fd, branch_epoch=0, audio_epoch=0;
    reg [31:0] ordinal=FIRST_SEQ;
    integer adopts=0, observations=0, outputs=0, restarts=0;
    wire seen_valid, enqueued, dropped, src_done, dst_done;
    wire [31:0] seen_seq, drop_count;
    wire signed [23:0] seen_left, seen_right;
    wire [15:0] level;
    wire wave_rst, restart, out_valid;
    wire [31:0] out_seq;
    wire signed [23:0] out_left, out_right;
    pcm_waveform_observer_bridge #(.DEPTH(DEPTH), .FIRST_SEQ(FIRST_SEQ)) dut (
        .audio_clk(audio_clk), .pixel_clk(pixel_clk),
        .audio_rst_n(audio_rst_n), .display_rst_n(display_rst_n),
        .audio_frame_load(frame_load), .audio_play_left(play_left),
        .audio_play_right(play_right), .waveform_rst_n(wave_rst),
        .stream_restart(restart), .sample_valid(out_valid),
        .sample_seq(out_seq), .sample_left(out_left), .sample_right(out_right),
        .observed_valid(seen_valid), .observed_seq(seen_seq),
        .observed_left(seen_left), .observed_right(seen_right),
        .observation_enqueued(enqueued), .observation_dropped(dropped),
        .observation_queue_level(level), .observation_drop_count(drop_count),
        .source_reset_done(src_done), .pixel_reset_done(dst_done)
    );
    always @(posedge audio_clk) if (fd && audio_rst_n) begin
        if (frame_load) begin
            $fdisplay(fd,"A %0t %0d %0d %0d %0d %0d",$time,
                branch_epoch,audio_epoch,ordinal,$signed(play_left),$signed(play_right));
            ordinal=ordinal+1; adopts=adopts+1;
        end
        if (seen_valid) begin
            $fdisplay(fd,"O %0t %0d %0d %0d %0d %0d %0d %0d",$time,
                branch_epoch,audio_epoch,seen_seq,$signed(seen_left),$signed(seen_right),enqueued,dropped);
            observations=observations+1;
        end
    end
    always @(posedge pixel_clk) if (fd) begin
        if (restart) begin
            $fdisplay(fd,"R %0t %0d %0d",$time,branch_epoch,audio_epoch);
            restarts=restarts+1;
        end
        if (out_valid) begin
            $fdisplay(fd,"D %0t %0d %0d %0d %0d %0d",$time,
                branch_epoch,audio_epoch,out_seq,$signed(out_left),$signed(out_right));
            outputs=outputs+1;
        end
        if (restart && out_valid) $fatal(1,"restart and valid overlap");
        if (!wave_rst && out_valid) $fatal(1,"valid during waveform reset");
    end
    task automatic reset_branch(input integer kind);
        begin
            branch_epoch=branch_epoch+1;
            if (kind==2) begin audio_epoch=audio_epoch+1; ordinal=FIRST_SEQ; audio_rst_n=0; end
            else display_rst_n=0;
            $fdisplay(fd,"Z %0t %0d %0d %0d",$time,branch_epoch,audio_epoch,kind);
            repeat(8) @(negedge audio_clk);
            if(kind==2) audio_rst_n=1; else display_rst_n=1;
        end
    endtask
    initial begin #300000000; $fatal(1,"HARNESS_TIMEOUT"); end

    integer compared_cycles=0,skip_requests=0,target=400;
    string capture_path;
    // Producer depends only on the audio buffer request, not display state.
    always @(negedge audio_clk) begin
        pcm_valid=0;
        if(audio_rst_n && req) begin
            if ((req_id>=35 && req_id<=37) || (req_id>=201 && req_id<=203))
                skip_requests=skip_requests+1;
            else begin
                pcm_valid=1;pcm_id=req_id;
                if(req_id<5) begin pcm_left=0;pcm_right=0;end
                else if(req_id==5) begin pcm_left=24'sh7fffff;pcm_right=24'sh800000;end
                else if(req_id==6) begin pcm_left=-128;pcm_right=127;end
                else begin pcm_left=24'((req_id*7919)^32'h800000);pcm_right=24'((req_id*104729)^32'h123456);end
            end
        end
    end
    always @(posedge audio_clk) if(audio_rst_n) begin
        compared_cycles=compared_cycles+1;
        if ({play_left,play_right,req,req_id,ready,pending,frames,requests,commits,underruns,frame_load,bclk,ws,din}
            !== {ref_left,ref_right,ref_req,ref_req_id,ref_ready,ref_pending,ref_frames,ref_requests,ref_commits,ref_underruns,ref_frame,ref_bclk,ref_ws,ref_din})
            $fatal(1,"AUDIO_DIFFERENCE");
    end
    initial begin
        if(!$value$plusargs("CAPTURE=%s",capture_path))$fatal(1,"missing capture");
        fd=$fopen(capture_path,"w");if(!fd)$fatal(1,"capture file");
        $fdisplay(fd,"META 1 isolation %0d %0d %0d",DEPTH,FIRST_SEQ,target);
        $fdisplay(fd,"Z %0t 0 0 0",$time);
        repeat(8)@(negedge audio_clk);audio_rst_n=1;display_rst_n=1;
        wait(frames==60);@(negedge audio_clk);pixel_run=0;$fdisplay(fd,"C %0t pixel_stop",$time);
        wait(frames==130);@(negedge audio_clk);reset_branch(1); // reset while destination clock is stopped
        wait(frames==140);@(negedge audio_clk);pixel_run=1;$fdisplay(fd,"C %0t pixel_resume",$time);
        wait(frames==180);@(negedge audio_clk);reset_branch(1);
        wait(frames==target);@(negedge audio_clk);
        // Stop new serial-frame loads only by resetting the TEST audio source;
        // first drain observation packets, preserving running audio for comparison.
        repeat(2400)@(negedge audio_clk);
        $fdisplay(fd,"AUDIO %0d %0d %0d %0d %0d %0d",compared_cycles,frames,requests,commits,underruns,skip_requests);
        $fdisplay(fd,"STAT %0t %0d %0d %0d",$time,branch_epoch,level,drop_count);
        $fdisplay(fd,"END %0d %0d %0d %0d",adopts,observations,outputs,restarts);
        $fclose(fd);fd=0;$display("HARNESS COMPLETE isolation comparisons=%0d",compared_cycles);$finish;
    end
endmodule
