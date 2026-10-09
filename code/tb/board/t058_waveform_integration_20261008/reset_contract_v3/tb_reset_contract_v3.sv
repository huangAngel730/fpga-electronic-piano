`timescale 1ns/1ps
module tb_reset_contract_v3;
    reg audio_clk=0, pixel_clk=0;
    reg audio_run=1, pixel_run=1;
    always #12.5 if(audio_run) audio_clk=~audio_clk;
    always #20 if(pixel_run) pixel_clk=~pixel_clk;
    reg audio_raw=0, display_raw=0;
    wire audio_done,video_done,control_done;
    reset_sync audio_root(.clk(audio_clk),.rst_n(audio_raw),.rst_sync_n(audio_done));
    reset_sync video_root(.clk(pixel_clk),.rst_n(display_raw),.rst_sync_n(video_done));
    reset_sync control_root(.clk(pixel_clk),.rst_n(display_raw),.rst_sync_n(control_done));
    wire display_request=display_raw && video_done && control_done;
    wire common_request=audio_done && display_request;
    reg load=0;
    reg signed [23:0] left=0,right=0;
    wire waveform_rst,restart,valid,seen,enqueued,dropped,src_done,dst_done;
    wire [31:0] seq,observed_seq;
    wire signed[23:0] sample_left,sample_right,observed_left,observed_right;
    wire [15:0] level;
    wire [31:0] drop_count;
    pcm_waveform_observer_bridge #(.DEPTH(8)) dut(
        .audio_clk(audio_clk),.pixel_clk(pixel_clk),.audio_rst_n(audio_done),
        .display_rst_n(display_request),.audio_frame_load(load),
        .audio_play_left(left),.audio_play_right(right),
        .waveform_rst_n(waveform_rst),.stream_restart(restart),.sample_valid(valid),
        .sample_seq(seq),.sample_left(sample_left),.sample_right(sample_right),
        .observed_valid(seen),.observed_seq(observed_seq),.observed_left(observed_left),
        .observed_right(observed_right),.observation_enqueued(enqueued),
        .observation_dropped(dropped),.observation_queue_level(level),
        .observation_drop_count(drop_count),.source_reset_done(src_done),.pixel_reset_done(dst_done));
    integer checks=0,events=0,outputs=0,restarts=0,source_edges=0,pixel_edges=0;
    integer generation=0,frame_ordinal=0,period_count=0,reset_cases=0;
    integer overflow_seen=0,stop_pixel_cases=0,stop_audio_cases=0;
    reg restart_seen=0;
    reg [1:0] source_pipe=0,pixel_pipe=0;
    reg last_out=0;
    reg [31:0] last_seq=0;
    integer fd=0;
    string capture;
    // Independent exact two-edge release oracle, sampled after NBA.
    always @(negedge common_request) begin
        source_pipe=0;pixel_pipe=0;restart_seen=0;last_out=0;
        #0.001;
        if(src_done!==0 || dst_done!==0 || valid!==0 || level!==0)
            $fatal(1,"ASYNC_ASSERT_BOTH_DOMAINS");
        checks=checks+1;
    end
    always @(posedge audio_clk) begin
        if(!common_request) source_pipe=0;
        else source_pipe={source_pipe[0],1'b1};
        #0.002;
        if(src_done!==source_pipe[1]) $fatal(1,"SOURCE_TWO_EDGE_RELEASE");
        checks=checks+1;source_edges=source_edges+1;
        if(dropped) overflow_seen=overflow_seen+1;
    end
    always @(posedge pixel_clk) begin
        if(!common_request) pixel_pipe=0;
        else pixel_pipe={pixel_pipe[0],1'b1};
        #0.002;
        if(dst_done!==pixel_pipe[1]) $fatal(1,"PIXEL_TWO_EDGE_RELEASE");
        checks=checks+1;pixel_edges=pixel_edges+1;
        if(restart) begin
            if(valid) $fatal(1,"RESTART_VALID_OVERLAP");
            restart_seen=1;restarts=restarts+1;
        end
        if(valid) begin
            if(!restart_seen || !src_done || !dst_done) $fatal(1,"OUTPUT_BEFORE_LOCAL_READY");
            if(sample_left[23:12]!==generation[11:0] || sample_right!==~sample_left)
                $fatal(1,"OLD_PACKET_OR_ATOMIC_PAYLOAD");
            if(last_out && seq<=last_seq) $fatal(1,"SEQUENCE_BACKWARD");
            last_out=1;last_seq=seq;outputs=outputs+1;checks=checks+4;
        end
        if(!dst_done && (valid || restart)) $fatal(1,"OUTPUT_DURING_RESET");
    end
    always @(negedge audio_clk) begin
        load=0;
        if(audio_done && common_request && src_done) begin
            period_count=period_count+1;
            if(period_count%2==0) begin
                load=1;left={generation[11:0],frame_ordinal[11:0]};right=~left;
                frame_ordinal=frame_ordinal+1;events=events+1;
            end
        end
    end
    task automatic wait_ready;
        integer k;
        begin
            k=0;
            while(!(src_done && dst_done && restart_seen) && k<100) begin #25;k=k+1;end
            if(k==100) $fatal(1,"RESET_READY_TIMEOUT");
            repeat(25) @(negedge audio_clk);
        end
    endtask
    integer i;
    initial begin
        if(!$value$plusargs("CAPTURE=%s",capture))$fatal(1,"CAPTURE_REQUIRED");
        fd=$fopen(capture,"w");if(!fd)$fatal(1,"CAPTURE_OPEN");
        $fdisplay(fd,"META reset_hold_v3 original_RTL async_assert_local_release");
        // Force an actual assertion event at time0; no reliance on initialized registers.
        #0.1;audio_raw=1;display_raw=1;#0.1;audio_raw=0;display_raw=0;
        #80.3;audio_raw=1;display_raw=1;wait_ready();
        for(i=0;i<64;i=i+1) begin
            #(1+i%19);
            generation=generation+1;reset_cases=reset_cases+1;
            if(i%3==0) audio_raw=0;
            else if(i%3==1) display_raw=0;
            else begin audio_raw=0;display_raw=0;end
            #(53+i%13);
            audio_raw=1;display_raw=1;wait_ready();
            $fdisplay(fd,"RESET %0d %0d %0d %0d",i,generation,checks,outputs);
        end
        // Pixel stopped before display reset, audio continues, queue full/drop allowed.
        @(negedge pixel_clk);pixel_run=0;
        repeat(80) @(negedge audio_clk);
        if(drop_count==0) $fatal(1,"QUEUE_FULL_NOT_EXERCISED");
        generation=generation+1;display_raw=0;stop_pixel_cases=stop_pixel_cases+1;
        #100.3;if(src_done || dst_done || level) $fatal(1,"RESET_WHILE_PIXEL_STOPPED");
        display_raw=1;repeat(10) @(negedge audio_clk);
        if(src_done || dst_done) $fatal(1,"PREMATURE_ROOT_RELEASE_PIXEL_STOP");
        pixel_run=1;wait_ready();
        // Audio clock stopped, display-reset request still clears both sides.
        @(negedge audio_clk);audio_run=0;
        generation=generation+1;display_raw=0;stop_audio_cases=stop_audio_cases+1;
        #130.7;if(src_done || dst_done || valid || level) $fatal(1,"RESET_WHILE_AUDIO_STOPPED");
        display_raw=1;repeat(12) @(negedge pixel_clk);
        if(src_done || valid) $fatal(1,"OUTPUT_WITH_SOURCE_CLOCK_STOPPED");
        audio_run=1;wait_ready();
        // Audio-root reset while audio is stopped: destination cannot release old stream.
        @(negedge audio_clk);audio_run=0;
        generation=generation+1;audio_raw=0;stop_audio_cases=stop_audio_cases+1;
        #91.7;audio_raw=1;repeat(12) @(negedge pixel_clk);
        if(src_done || dst_done || valid) $fatal(1,"AUDIO_ROOT_STOP_RESET_LEAK");
        audio_run=1;wait_ready();
        repeat(80) @(negedge audio_clk);
        if(outputs<100 || restarts<65 || overflow_seen==0) $fatal(1,"INSUFFICIENT_COVERAGE");
        $fdisplay(fd,"END %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",checks,events,outputs,restarts,reset_cases,stop_pixel_cases,stop_audio_cases,overflow_seen,source_edges,pixel_edges);
        $fclose(fd);$display("PASS reset_contract_v3 checks=%0d outputs=%0d resets=%0d",checks,outputs,reset_cases);$finish;
    end
    initial begin #3000000;$fatal(1,"BOUNDED_TIMEOUT");end
endmodule
