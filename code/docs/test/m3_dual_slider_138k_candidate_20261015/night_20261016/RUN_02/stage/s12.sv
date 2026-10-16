// Diagnostic PCM producer, original audio and display modules, no synth/board.
`timescale 1ns/1ps
module tb_slider_audio_coexist;
    import audio_defs_pkg::*;
    logic sys_clk=0, pixel_clk=0, rst_n=1;
    always #12.5 sys_clk=~sys_clk;
    always #20 pixel_clk=~pixel_clk;
    logic accepted_valid=0, mode_valid=0, score_valid=0, frame_start=0;
    performance_event_t accepted_data='0;
    wire mode_ready, score_ready;
    logic [15:0] score_note_id=1, pixel_x=4, pixel_y=52;
    logic [6:0] score_note_number=60;
    logic [31:0] score_hit_frame=0, score_duration_frames=4;
    logic score_duration_valid=1, data_enable=1;
    logic [9:0] score_velocity=700;
    wire display_mode,desync_latched,mode_delivered,sys_reset_done,video_reset_done;
    wire [31:0] current_frame,visual_drop_count,live_drop_count;
    wire [127:0] key_down;
    wire [3:0] live_valid,live_held,falling_valid;
    wire [31:0] live_top,live_end,falling_top,falling_end;
    wire [7:0] rgb_r,rgb_g,rgb_b;
    dual_slider_candidate #(.SLOTS(4),.Y_WIDTH(8),.SCREEN_WIDTH(128),
        .SCREEN_HEIGHT(64),.PREVIEW_FRAMES(8),.BASE_NOTE(60),.NOTE_COUNT(8)) visual(.*);
    wire frame_tick, tick, request, pending, pcm_ready;
    wire bclk, ws, din, legacy_ready;
    wire [31:0] req_id,frames,requests,commits,underflow;
    wire signed [23:0] play_l,play_r;
    logic pcm_valid=0,clip=0;
    logic [31:0] pcm_id=0;
    logic signed [23:0] left=0,right=0;
    integer cycle=0,epoch=0,fd,vfd,mutation=0,delay_left=-1,hold_left=0;
    integer checks=0,deliveries=0;
    logic stale_phase=0;
    logic [1:0] serial_pipe=0;
    wire signed [23:0] serial_l = mutation==2 ? play_r : play_l;
    wire signed [23:0] serial_r = mutation==2 ? play_l : play_r;
    wire serial_valid = !(mutation==4 && display_mode);
    wire observed_din = mutation==3 ? serial_pipe[1] : din;
    sample_tick_gen #(.PHASE_STEP(32'd5153961)) u_tick(
        .clk(sys_clk),.rst_n(rst_n),.sample_tick(tick));
    pcm_frame_buffer u_buffer(
        .clk(sys_clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(1'b1),
        .sample_req(request),.sample_req_id(req_id),.pcm_valid(pcm_valid),
        .pcm_ready(pcm_ready),.pcm_req_id(pcm_id),.pcm_left(left),.pcm_right(right),
        .play_left(play_l),.play_right(play_r),.pending_valid(pending),
        .audio_frame_count(frames),.pcm_request_count(requests),
        .pcm_commit_count(commits),.audio_underrun(underflow));
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) u_tx(
        .clk(sys_clk),.rst_n(rst_n),.valid(serial_valid),.pcm_left(serial_l),.pcm_right(serial_r),
        .bclk(bclk),.lrck(ws),.din(din),.ready(legacy_ready),.frame_tick(frame_tick));
    // Faults affect only this TB's wiring/producer; original RTL is unchanged.
    always @(posedge bclk or negedge rst_n)
        if(!rst_n) serial_pipe<=0; else serial_pipe<={serial_pipe[0],din};
    function automatic integer vector(input integer n);
        case(n%16)
            0:vector=0; 1:vector=8388607; 2:vector=-8388608;
            3:vector=127; 4:vector=128; 5:vector=129;
            6:vector=-127; 7:vector=-128; 8:vector=-129;
            9:vector=8388480; 10:vector=8388479; 11:vector=-8388481;
            12:vector=1234567; 13:vector=-2345678;
            14:vector=7654321; 15:vector=-6543210;
        endcase
    endfunction
    always @(negedge sys_clk) begin
        if(!rst_n) begin
            pcm_valid=0;pcm_id=0;left=0;right=0;clip=0;
            delay_left=-1;hold_left=0;stale_phase=0;
        end else begin
            if(hold_left>0) begin
                hold_left=hold_left-1;
                if(hold_left==0) begin
                    if(stale_phase) begin pcm_id=req_id;stale_phase=0;hold_left=6;end
                    else pcm_valid=0;
                end
            end
            if(delay_left>=0) begin
                if(delay_left==0) begin
                    pcm_valid=1;pcm_id=req_id;left=24'(vector(req_id+epoch));
                    right=24'(vector(req_id+epoch+7));clip=(req_id%17==0);hold_left=6;
                    if(req_id==12) begin pcm_id=req_id-1;stale_phase=1;hold_left=16;end
                    delay_left=-1;
                end else delay_left=delay_left-1;
            end
            // Drop after display motion has finished so the independent audio
            // checker, rather than the display progress assertion, rejects it.
            if(request && !(mutation==1 && epoch==1 && req_id==48)) delay_left=8;
        end
    end
    always @(posedge sys_clk) begin
        cycle=cycle+1;
        $fdisplay(fd,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
            cycle,epoch,rst_n,tick,frame_tick,request,req_id,pcm_valid,pcm_ready,
            pcm_id,$signed(left),$signed(right),clip,pending,$signed(play_l),$signed(play_r),
            frames,requests,commits,underflow,bclk,ws,observed_din);
    end
    always @(posedge pixel_clk)
        if(video_reset_done && mode_delivered) deliveries<=deliveries+1;
    task check(input logic ok,input string name);
        checks=checks+1;
        if(ok!==1) $fatal(1,"REJECT %s epoch=%0d frame=%0d",name,epoch,current_frame);
        $display("CHECK %s epoch=%0d",name,epoch);
        $fdisplay(vfd,"CHECK,%0d,%0d,%s,%0d,%0d,%0d,%0d",cycle,epoch,name,frames,commits,current_frame,display_mode);
    endtask
    task settle; repeat(30) @(negedge pixel_clk); endtask
    task frame;
        integer af,ac;
        af=frames;ac=commits;
        repeat(1000) @(negedge sys_clk);
        @(negedge pixel_clk);frame_start=1;
        @(negedge pixel_clk);frame_start=0;#1;
        check(frames>af && commits>ac,"PCM_COMMIT_AND_FRAME_DURING_MOVEMENT");
        $fdisplay(vfd,"FRAME,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",cycle,epoch,current_frame,display_mode,
            live_valid,live_held,live_top[7:0],live_end[7:0],falling_valid,falling_end[7:0]);
    endtask
    task note(input bit on);
        @(negedge sys_clk);accepted_data=make_note_event(on,4'd1,4'd0,7'd60,on?10'd700:10'd0);accepted_valid=1;
        @(negedge sys_clk);accepted_valid=0;settle();
    endtask
    task mode_command;
        do @(negedge sys_clk);while(!mode_ready || ($time%200)!=25);
        mode_valid=1;@(negedge sys_clk);mode_valid=0;settle();
    endtask
    task display_sequence;
        integer old_end,old_fall,delivered;
        check(sys_reset_done && video_reset_done && display_mode==0 && live_valid==0 && falling_valid==0,
            "RESET_RELEASE_NO_DISPLAY_GHOST");
        note(1);frame();old_end=live_top[7:0];frame();
        check(live_held==1 && live_top[7:0]<old_end,"HELD_RISE_WITH_REAL_AUDIO");
        note(0);old_end=live_end[7:0];frame();
        check(live_held==0 && live_end[7:0]<old_end,"RELEASE_RISE_WITH_REAL_AUDIO");
        delivered=deliveries;mode_command();
        check(deliveries==delivered+1 && display_mode==0,"MODE_MAILBOX_DELIVERED_PENDING_FRAME");
        frame();check(display_mode==1,"FALLING_MODE_WITH_REAL_AUDIO");
        @(negedge sys_clk);score_hit_frame=current_frame+6;score_note_id=16'(epoch);score_valid=1;
        do @(posedge sys_clk);while(!score_ready);
        @(negedge sys_clk);score_valid=0;settle();
        frame();old_fall=falling_end[7:0];frame();
        check(falling_valid==1 && falling_end[7:0]>old_fall,"FALLING_MOVES_WITH_REAL_AUDIO");
        repeat(12) frame();check(falling_valid==0,"FALLING_EXIT_WITH_REAL_AUDIO");
        mode_command();frame();check(display_mode==0,"SWITCH_BACK_WITH_REAL_AUDIO");
        check(visual_drop_count==0 && live_drop_count==0 && !desync_latched,"NO_DISPLAY_DROP_DESYNC");
    endtask
    initial begin
        if($value$plusargs("mutation=%d",mutation)) begin end
        fd=$fopen("capture.csv","w");vfd=$fopen("visual.csv","w");
        if(!fd || !vfd) $fatal(1,"CAPTURE_OPEN");
        $fdisplay(fd,"C_PCM_SERIAL_PUBLIC_V1,NEW_MODULE_RTL_FIXTURE,40000000,PRE_NBA,PT8211_LSBJ");
        $fdisplay(vfd,"D_AUDIO_VISUAL_COEXIST_V1,ACCELERATED_DISPLAY_FRAMES,40000000,25000000");
        #1;rst_n=0;repeat(12) @(negedge sys_clk);epoch=1;rst_n=1;settle();
        display_sequence();
        wait(frames==96);wait(request); // real outstanding PCM request at reset
        @(negedge sys_clk);mode_valid=1;
        @(posedge sys_clk);#1;rst_n=0;mode_valid=0;
        $display("RESET outstanding_request=1 epoch=1");
        repeat(12) @(negedge sys_clk);epoch=2;rst_n=1;settle();
        display_sequence();
        wait(frames==96);@(negedge sys_clk);
        $fdisplay(fd,"END,%0d",cycle);$fclose(fd);
        $fdisplay(vfd,"END,%0d",checks);$fclose(vfd);
        $display("PASS D_AUDIO_VISUAL_COEXIST checks=%0d",checks);$finish;
    end
    initial begin #5000000;$fatal(1,"REJECT COEXIST_TIMEOUT");end
endmodule
