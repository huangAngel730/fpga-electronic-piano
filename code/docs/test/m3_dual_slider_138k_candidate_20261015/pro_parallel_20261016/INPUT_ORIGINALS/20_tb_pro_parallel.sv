`timescale 1ns/1ps
// New defaults/FIFO/backpressure/raster increment, not Pro DUT or old 99/4.
module tb_pro_parallel;
    import audio_defs_pkg::*;
    logic sys_clk=0,pixel_clk=0,rst_n=1;
    always #12.5 sys_clk=~sys_clk;
    always #20 pixel_clk=~pixel_clk;
    logic accepted_valid=0,display_event_enable=1,mode_valid=0,score_valid=0;
    performance_event_t accepted_data='0;
    integer mutation=0,checks=0,mode_deliveries=0,seen_events=0,expected_events=0;
    integer seen_scores=0,expected_scores=0,sys_cycles=0,pixel_cycles=0;
    performance_event_t event_calendar[0:127];
    logic [97:0] score_calendar[0:15];
    wire accepted_to_dut=accepted_valid && mutation!=2;
    wire mode_ready,score_ready,display_mode,desync_latched,mode_delivered;
    wire sys_reset_done,video_reset_done,display_event_fire,score_event_fire,score_sink_ready;
    wire [15:0] queue_level,queue_high;
    performance_event_t display_event_data;
    wire [97:0] score_seen_payload;
    logic [15:0] score_note_id=0,pixel_x=0,pixel_y=0;
    logic [6:0] score_note_number=60;
    logic [31:0] score_hit_frame=0,score_duration_frames=20;
    logic score_duration_valid=1,frame_start=0,data_enable=1;
    logic [9:0] score_velocity=700;
    wire [31:0] current_frame,visual_drop_count,live_drop_count;
    wire [127:0] key_down;
    wire [7:0] live_valid,live_held,falling_valid,rgb_r,rgb_g,rgb_b;
    wire [79:0] live_top,live_end,falling_top,falling_end;
    dual_slider_pro_parallel dut(.accepted_valid(accepted_to_dut),.*);
    wire tick,frame_tick,request,pending,pcm_ready,bclk,ws,din,legacy_ready;
    wire [31:0] req_id,frames,requests,commits,underflow;
    wire signed [23:0] play_l,play_r;
    logic pcm_valid=0;
    logic [31:0] pcm_id=0;
    logic signed [23:0] left=0,right=0;
    wire calc_ready = mutation==4 ? display_event_enable : 1'b1;
    sample_tick_gen #(.PHASE_STEP(32'd5153961)) u_tick(
        .clk(sys_clk),.rst_n(rst_n),.sample_tick(tick));
    pcm_frame_buffer u_buffer(.clk(sys_clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .sample_req(request),.sample_req_id(req_id),.pcm_valid(pcm_valid),.pcm_ready(pcm_ready),
        .pcm_req_id(pcm_id),.pcm_left(left),.pcm_right(right),.play_left(play_l),.play_right(play_r),
        .pending_valid(pending),.audio_frame_count(frames),.pcm_request_count(requests),
        .pcm_commit_count(commits),.audio_underrun(underflow));
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) u_tx(.clk(sys_clk),.rst_n(rst_n),.valid(1'b1),
        .pcm_left(play_l),.pcm_right(play_r),.bclk(bclk),.lrck(ws),.din(din),
        .ready(legacy_ready),.frame_tick(frame_tick));
    always @(negedge sys_clk) begin
        if(!rst_n) begin pcm_valid=0;pcm_id=0;left=0;right=0;end
        else begin
            pcm_valid=0;
            if(request) begin
                pcm_valid=1;pcm_id=req_id;
                left=24'(req_id*12345);right=-24'(req_id*23456);
            end
        end
    end
    integer last_audio=-1,last_tick=-1,gap833=0,gap834=0,tick833=0,tick834=0;
    logic score_stalled=0;
    logic [97:0] held_score='0;
    wire [97:0] source_score={score_note_id,score_note_number,score_hit_frame,
        score_duration_valid,score_duration_frames,score_velocity};
    always @(posedge sys_clk) begin
        sys_cycles=sys_cycles+1;
        if(!rst_n) begin last_audio=-1;last_tick=-1;score_stalled=0;end
        else begin
            if(underflow!=0) begin
                if(mutation==4) $fatal(1,"REJECT AUDIO_DISPLAY_BACKPRESSURE");
                else $fatal(1,"REJECT AUDIO_UNEXPECTED_UNDERRUN");
            end
            if(score_stalled && (!score_valid || source_score!==held_score))
                $fatal(1,"REJECT SCORE_SOURCE_STABILITY");
            score_stalled=score_valid && !score_ready;held_score=source_score;
            if(frame_tick) begin
                if(last_audio>=0) begin
                    if(sys_cycles-last_audio==833)gap833=gap833+1;
                    else if(sys_cycles-last_audio==834)gap834=gap834+1;
                    else $fatal(1,"REJECT AUDIO_FRAME_CADENCE");
                end
                last_audio=sys_cycles;
            end
            if(tick) begin
                if(last_tick>=0) begin
                    if(sys_cycles-last_tick==833)tick833=tick833+1;
                    else if(sys_cycles-last_tick==834)tick834=tick834+1;
                    else $fatal(1,"REJECT SAMPLE_TICK_CADENCE");
                end
                last_tick=sys_cycles;
            end
        end
    end
    integer raster_mode=0,raster_last=-1,raster_intervals=0;
    always @(posedge pixel_clk) begin
        pixel_cycles=pixel_cycles+1;
        if(video_reset_done) begin
            if(mode_delivered)mode_deliveries=mode_deliveries+1;
            if(display_event_fire) begin
                if(seen_events>=expected_events || display_event_data!==event_calendar[seen_events])
                    $fatal(1,"REJECT EVENT_IDENTITY_ORDER index=%0d",seen_events);
                seen_events=seen_events+1;
                $display("EVENT %0d %016h",seen_events,display_event_data);
            end
            if(score_event_fire) begin
                if(seen_scores>=expected_scores || score_seen_payload!==score_calendar[seen_scores])
                    $fatal(1,"REJECT SCORE_IDENTITY_ORDER index=%0d",seen_scores);
                seen_scores=seen_scores+1;
                $display("SCORE %0d %025h",seen_scores,score_seen_payload);
            end
            if(raster_mode && frame_start) begin
                if(raster_last>=0) begin
                    if(pixel_cycles-raster_last!=420000)$fatal(1,"REJECT RASTER_FRAME_PERIOD");
                    raster_intervals=raster_intervals+1;
                end
                raster_last=pixel_cycles;
            end
        end
    end
    task check(input logic ok,input string label);
        checks=checks+1;
        if(ok!==1)$fatal(1,"REJECT %s frame=%0d mode=%0d live=%h top=%h end=%h falling=%h ft=%h fe=%h events=%0d/%0d scores=%0d/%0d queue=%0d",
            label,current_frame,display_mode,live_valid,live_top,live_end,falling_valid,falling_top,falling_end,
            seen_events,expected_events,seen_scores,expected_scores,queue_level);
        $display("CHECK %s frame=%0d audio=%0d commits=%0d queue=%0d mode=%0d live=%h top=%h end=%h falling=%h ft=%h fe=%h",
            label,current_frame,frames,commits,queue_level,display_mode,live_valid,live_top,live_end,falling_valid,falling_top,falling_end);
    endtask
    task settle; repeat(40) @(negedge pixel_clk); endtask
    task reset_all;
        @(negedge sys_clk);rst_n=0;mode_valid=0;score_valid=0;accepted_valid=0;
        frame_start=0;display_event_enable=1;
        repeat(12) @(negedge sys_clk);
        expected_events=0;seen_events=0;expected_scores=0;seen_scores=0;mode_deliveries=0;
        rst_n=1;settle();
        check(sys_reset_done && video_reset_done && !display_mode && queue_level==0 &&
            !live_valid && !falling_valid && !desync_latched,"SHARED_RESET_FLUSH");
        wait(frames>=5);@(negedge sys_clk);
    endtask
    task frame;
        integer af,ac;
        af=frames;ac=commits;
        repeat(1000) @(negedge sys_clk);
        @(negedge pixel_clk);frame_start=1;
        @(negedge pixel_clk);frame_start=0;#1;
        check(frames>af && commits>ac,"AUDIO_PROGRESS_DURING_ANIMATION");
    endtask
    task event_send(input bit on,input integer pitch,input bit remember);
        @(negedge sys_clk);
        accepted_data=make_note_event(on,4'd1,4'd0,7'(pitch),on?10'd700:10'd0);
        if(remember)begin event_calendar[expected_events]=accepted_data;expected_events=expected_events+1;end
        accepted_valid=1;@(negedge sys_clk);accepted_valid=0;
    endtask
    task drain;
        integer timeout;
        timeout=0;
        while(seen_events<expected_events && timeout<1200)begin @(negedge pixel_clk);timeout=timeout+1;end
        check(seen_events==expected_events,"EVENT_LOSS");settle();
    endtask
    task mode_command;
        integer before_delivery,timeout;
        before_delivery=mode_deliveries;timeout=0;
        do begin @(negedge sys_clk);timeout=timeout+1;end
            while((!mode_ready || ($time%200)!=25) && timeout<100);
        check(mode_ready,"MODE_READY_BOUND");
        mode_valid=1;@(negedge sys_clk);mode_valid=0;settle();
        check(mode_deliveries==before_delivery+1,"MODE_CDC_DELIVERY");
    endtask
    task score_send(input integer id,input integer hit);
        integer timeout;
        @(negedge sys_clk);score_note_id=16'(id);score_note_number=7'(36+id-100);
        score_hit_frame=32'(hit);score_duration_frames=20;score_duration_valid=1;score_velocity=700;
        score_calendar[expected_scores]=source_score; // source_score settles below
        #1;score_calendar[expected_scores]=source_score;expected_scores=expected_scores+1;
        score_valid=1;timeout=0;
        do begin @(posedge sys_clk);timeout=timeout+1;end while(!score_ready && timeout<200000);
        if(!score_ready)$fatal(1,"REJECT SCORE_READY_DEADLINE");
        @(negedge sys_clk);score_valid=0;settle();
    endtask
    integer i,offset,hit,top_expected,end_expected,af,ac,saved_current,active_pixels;
    integer x,y,f;
    initial begin
        if($value$plusargs("mutation=%d",mutation))begin end
        if(mutation==1)force dut.mode_pulse=mode_valid;
        if(mutation==3)force dut.display_mode=1'b0;
        #1;rst_n=0;reset_all();
        mode_command();check(display_mode==0,"MODE_NO_MIDFRAME_CHANGE");
        frame();check(display_mode==1,"MODE_SWITCH_STALL");
        mode_command();frame();check(display_mode==0,"MODE_RETURN_LIVE");
        // Two valid/ready commands before one frame cancel by parity.
        mode_command();mode_command();frame();check(display_mode==0,"MODE_TWO_COMMAND_PARITY");
        // Contract: mode pulse and frame_start on the same pixel edge retain
        // the old mode for that frame, then commit the request next frame.
        do @(negedge sys_clk);while(!mode_ready);
        mode_valid=1;@(negedge sys_clk);mode_valid=0;
        wait(mode_delivered);@(negedge pixel_clk);frame_start=1;
        @(negedge pixel_clk);frame_start=0;#1;
        check(display_mode==0,"MODE_SAME_EDGE_OLD_FRAME");
        frame();check(display_mode==1,"MODE_SAME_EDGE_NEXT_FRAME");
        mode_command();frame();check(display_mode==0,"MODE_SAME_EDGE_RETURN_LIVE");
        event_send(1,60,1);drain();frame();
        check(live_valid==1 && live_held==1 && live_top[9:0]==470 && live_end[9:0]==480,"DEFAULT_HELD_BAR");
        frame();check(live_top[9:0]==466 && live_end[9:0]==480,"DEFAULT_HELD_GROWTH");
        for(i=61;i<68;i=i+1)begin event_send(1,i,1);drain();end
        frame();check(live_valid==8'hff && live_held==8'hff,"EIGHT_LIVE_SLOTS");
        for(i=60;i<68;i=i+1)begin event_send(0,i,1);drain();end
        frame();check(live_held==0 && live_end[9:0]==480,"RELEASE_SNAPSHOT_BEFORE_TRANSLATION");
        frame();check(live_end[9:0]==476,"RELEASE_TRANSLATES_NEXT_SNAPSHOT");
        repeat(121)frame();check(live_valid==0,"DEFAULT_LIVE_EXIT");
        reset_all();display_event_enable=0;
        event_send(0,36,1);settle();check(queue_level==0,"ONE_EVENT_IN_FLIGHT");
        for(i=0;i<32;i=i+1)event_send(0,37+i,1);
        settle();check(queue_level==32 && queue_high==32 && visual_drop_count==0,"FIFO32_PLUS_MAILBOX_FULL");
        af=frames;ac=commits;
        repeat(5000)@(negedge sys_clk);
        check(frames>=af+5 && commits>=ac+5 && underflow==0,"DISPLAY_STALL_NO_AUDIO_BACKPRESSURE");
        mode_command();frame();check(display_mode==1,"MODE_INDEPENDENT_OF_EVENT_QUEUE");
        mode_command();frame();check(display_mode==0,"MODE_BACK_WHILE_QUEUE_FULL");
        display_event_enable=1;drain();
        check(queue_level==0 && seen_events==33 && visual_drop_count==0,"FIFO_DRAIN_ORDER_EMPTY");
        reset_all();display_event_enable=0;event_send(0,36,1);settle();
        for(i=0;i<32;i=i+1)event_send(0,37+i,1);
        event_send(0,80,0);settle();check(queue_level==32 && visual_drop_count==1,"FIFO34TH_EVENT_OVERFLOW");
        display_event_enable=1;drain();frame();
        check(desync_latched && live_valid==0 && falling_valid==0,"OVERFLOW_DESYNC_FAIL_CLOSED");
        reset_all();check(visual_drop_count==0 && queue_high==0,"RESET_CLEARS_OVERFLOW");
        mode_command();frame();check(display_mode==1,"SCORE_MODE_ACTIVE");
        hit=current_frame+120;
        for(i=100;i<108;i=i+1)score_send(i,hit);
        check(seen_scores==8 && !score_sink_ready,"EIGHT_SCORE_SLOTS_FULL");
        score_send(108,hit+200);check(!score_ready && seen_scores==8,"NINTH_SCORE_PENDING_MAILBOX");
        fork
            begin score_send(109,hit+200);end
            begin
                for(offset=1;offset<=141;offset=offset+1)begin
                    frame();
                    if(offset<=140)begin
                        end_expected=offset<120?offset*4:480;
                        top_expected=offset<20?0:(offset-20)*4;
                        if(top_expected>480)top_expected=480;
                        check(falling_valid==8'hff && falling_end[9:0]==end_expected &&
                            falling_top[9:0]==top_expected,"PREVIEW120_CONTINUOUS_INTEGER_GEOMETRY");
                    end
                    if(offset==1)check(score_valid && !score_ready,"TENTH_SCORE_HELD_UNDER_BACKPRESSURE");
                end
            end
        join
        settle();check(seen_scores==10 && score_ready && score_sink_ready,"SCORE_RECOVERY_NO_LOSS");
        check(falling_valid==0,"FIRST_EIGHT_RETIRED_FUTURE_HIDDEN");
        // Cancel accepted requests before the synchronizers can publish.
        @(negedge sys_clk);mode_valid=1;score_valid=1;accepted_valid=1;
        @(posedge sys_clk);#1;rst_n=0;reset_all();settle();
        check(mode_deliveries==0 && seen_events==0 && seen_scores==0,"INFLIGHT_RESET_NO_GHOST");
        saved_current=current_frame;active_pixels=0;raster_mode=1;raster_last=-1;raster_intervals=0;
        for(f=0;f<3;f=f+1)begin
            for(y=0;y<525;y=y+1)begin
                for(x=0;x<800;x=x+1)begin
                    @(negedge pixel_clk);pixel_x=16'(x);pixel_y=16'(y);
                    frame_start=(x==0 && y==0);data_enable=(x<640 && y<480);
                    if(data_enable)active_pixels=active_pixels+1;
                end
            end
        end
        @(negedge pixel_clk);frame_start=0;data_enable=0;#1;raster_mode=0;
        check(current_frame==saved_current+3 && raster_intervals==2 && active_pixels==921600,
            "RASTER_800X525_25MHZ_TWO_COMPLETE_INTERVALS");
        check({rgb_r,rgb_g,rgb_b}==0,"RASTER_BLANKING_BLACK");
        check(gap833>0 && gap834>0 && tick833>0 && tick834>0 && underflow==0,"REAL_AUDIO_833_834_CADENCE");
        $display("PASS PRO_PARALLEL_FIXTURE checks=%0d events=%0d scores=%0d audio_frames=%0d gaps833=%0d gaps834=%0d raster_intervals=%0d active_pixels=%0d",
            checks,seen_events,seen_scores,frames,gap833,gap834,raster_intervals,active_pixels);
        $finish;
    end
    initial begin #80000000;$fatal(1,"REJECT PRO_PARALLEL_GLOBAL_TIMEOUT");end
endmodule
