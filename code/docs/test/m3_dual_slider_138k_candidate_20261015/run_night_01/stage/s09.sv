`timescale 1ns/1ps
module tb_dual_slider;
    import audio_defs_pkg::*;
    logic sys_clk=0,pixel_clk=0,rst_n=0;
    always #12.5 sys_clk=~sys_clk; // 40 MHz fixture
    always #20 pixel_clk=~pixel_clk; // unrelated 25 MHz fixture
    logic accepted_valid=0,mode_valid=0,score_valid=0,frame_start=0;
    performance_event_t accepted_data='0;
    wire mode_ready,score_ready;
    logic [15:0] score_note_id=1, pixel_x=4,pixel_y=63;
    logic [6:0] score_note_number=60;
    logic [31:0] score_hit_frame=0,score_duration_frames=4;
    logic score_duration_valid=1,data_enable=1;
    logic [9:0] score_velocity=700;
    wire display_mode,desync_latched,mode_delivered,sys_reset_done,video_reset_done;
    wire [31:0] current_frame,visual_drop_count,live_drop_count;
    wire [127:0] key_down;
    wire [3:0] live_valid,live_held,falling_valid;
    wire [31:0] live_top,live_end,falling_top,falling_end;
    wire [7:0] rgb_r,rgb_g,rgb_b;
    integer checks=0,deliveries=0,frame_cycles=0,audio_frames=0,last_audio=-1;
    integer mutation=0,expect_frame,expected_top,expected_end,offset;
    logic [31:0] acc=0;
    wire [32:0] phase_sum={1'b0,acc}+33'd5153961; // round(2^32*48000/40MHz)
    logic audio_enable=0,audio_underrun=0;
    logic [31:0] saved_top;
    logic saved_mode;
    dual_slider_candidate #(.SLOTS(4),.Y_WIDTH(8),.SCREEN_WIDTH(128),
        .SCREEN_HEIGHT(64),.PREVIEW_FRAMES(8),.BASE_NOTE(60),.NOTE_COUNT(8)) dut(.*);
    task check(input logic ok,input string name);
        checks=checks+1;
        if(ok!==1) $fatal(1,"REJECT %s checks=%0d frame=%0d",name,checks,current_frame);
        $display("CHECK %s",name);
    endtask
    // Independent audio scheduling fixture, not a synth/PCM/I2S implementation.
    always @(posedge sys_clk) begin
        if(!rst_n) begin acc<=0;frame_cycles<=0;audio_frames<=0;last_audio<=-1;end
        else if(audio_enable) begin
            frame_cycles<=frame_cycles+1;
            acc<=phase_sum[31:0];
            if(phase_sum[32]) begin
                if(last_audio>=0 && frame_cycles-last_audio!=833 && frame_cycles-last_audio!=834)
                    $fatal(1,"REJECT AUDIO_INTERVAL");
                if(audio_underrun) $fatal(1,"REJECT AUDIO_UNDERRUN");
                last_audio<=frame_cycles;audio_frames<=audio_frames+1;
            end
        end
    end
    always @(posedge pixel_clk) if(video_reset_done && mode_delivered) deliveries<=deliveries+1;
    task wait_video;
        repeat(30) @(negedge pixel_clk);
    endtask
    task frame;
        @(negedge pixel_clk);frame_start=1;
        @(negedge pixel_clk);frame_start=0;#1;
        $display("FRAME %0d mode=%b live=%h held=%h top=%h end=%h falling=%h ft=%h fe=%h audio=%0d",
            current_frame,display_mode,live_valid,live_held,live_top,live_end,
            falling_valid,falling_top,falling_end,audio_frames);
    endtask
    task note(input bit on,input integer source,input integer channel,input integer pitch,input integer vel);
        @(negedge sys_clk);
        accepted_data=make_note_event(on,4'(source),4'(channel),7'(pitch),10'(vel));
        accepted_valid=1;
        @(negedge sys_clk);accepted_valid=0;wait_video();
    endtask
    task mode_command;
        // Deliberate source pulse [t=25,t=50] modulo 200ns: between pixel edges
        // t=20 and60. A raw wrong-domain wire loses it; the mailbox must not.
        do @(negedge sys_clk);while(!mode_ready || ($time%200)!=25);
        mode_valid=1;@(negedge sys_clk);mode_valid=0;wait_video();
    endtask
    task reset_all;
        rst_n=0;frame_start=0;mode_valid=0;accepted_valid=0;score_valid=0;
        repeat(5) @(negedge sys_clk);rst_n=1;wait_video();
    endtask
    initial begin
        if($value$plusargs("mutation=%d",mutation)) begin end
        // Only TB fault injection. Production candidate contains no bypass flags.
        if(mutation==1) force dut.mode_pulse=0;
        if(mutation==2) force dut.mode_pulse=mode_valid;
        if(mutation==3) force dut.u_falling.current_frame=0;
        if(mutation==4) audio_underrun=1;
        reset_all();audio_enable=1;
        check(sys_reset_done && video_reset_done,"RESET_LOCAL_RELEASE");
        check(display_mode==0 && live_valid==0 && falling_valid==0,"RESET_EMPTY_LIVE_MODE");
        note(1,1,0,60,700);frame();
        check(live_valid==1 && live_held==1 && live_top[7:0]==54 && live_end[7:0]==64,"HELD_START_AT_BOTTOM");
        frame();check(live_top[7:0]==50 && live_end[7:0]==64,"HELD_LENGTH_GROWS");
        pixel_y=52;#1;check({rgb_r,rgb_g,rgb_b}!=24'h081020,"LIVE_RENDERER_REAL_PIXEL");
        // Same pitch from keyboard and MIDI must keep distinct held instances.
        note(1,0,0,60,600);frame();
        check(live_held==3 && key_down[60],"MULTISOURCE_SAME_NOTE_TWO_BARS");
        note(0,1,0,60,0);frame();
        check(live_held==2 && key_down[60],"NOTE_OFF_PRESERVES_OTHER_SOURCE");
        frame();check(live_end[7:0]==60 && live_end[15:8]==64,"RELEASED_BAR_TRANSLATES_ONLY_OWN_INSTANCE");
        note(1,0,1,60,500);frame();
        check(live_held==6,"CHANNEL_IDENTITY_DISTINCT");
        note(1,0,0,60,0);frame();
        check(live_held==4 && key_down[60],"ZERO_VELOCITY_RELEASE_IDENTITY");
        note(0,0,1,60,0);frame();frame();
        check(live_held==0 && !key_down[60],"FINAL_IDENTITY_RELEASES_KEY");
        repeat(20) frame();check(live_valid==0,"RELEASE_EXIT_RECLAIM");
        saved_mode=display_mode;mode_command();
        check(deliveries==1,"MODE_CDC_DELIVERY");
        check(display_mode==saved_mode,"MODE_NO_MIDFRAME_SWITCH");
        frame();check(display_mode==1,"MODE_SWITCH_ON_FRAME");
        // Original absolute frame/duration contract, no score time redefinition.
        @(negedge sys_clk);score_hit_frame=current_frame+6;expect_frame=score_hit_frame;
        score_valid=1;do @(posedge sys_clk);while(!score_ready);
        @(negedge sys_clk);score_valid=0;wait_video();
        for(offset=-5;offset<=6;offset=offset+1) begin
            frame();
            check(current_frame==expect_frame+offset,"FALLING_FRAME_PROGRESS");
            expected_end=offset>=0 ? 64 : 64+8*offset;
            expected_top=offset>=4 ? 64 : 32+8*offset;
            if(expected_top<0) expected_top=0;
            check(falling_valid==1 && falling_top[7:0]==expected_top && falling_end[7:0]==expected_end,
                "FALLING_CONTINUOUS_INTEGER_ORACLE");
        end
        frame();check(falling_valid==0,"FALLING_SLOT_EXIT_AFTER_WINDOW");
        mode_command();check(deliveries==2,"SECOND_MODE_CDC_DELIVERY");
        frame();check(display_mode==0,"SWITCH_BACK_LIVE");
        data_enable=0;#1;check({rgb_r,rgb_g,rgb_b}==0,"BLANKING_BLACK");data_enable=1;
        // Guarantee audio fixture includes many real 833/834 system intervals.
        repeat(50000) @(negedge sys_clk);
        check(audio_frames>=50,"AUDIO_FIXTURE_CONCURRENT_CADENCE");
        note(1,2,0,61,800);frame();check(live_valid!=0,"BEFORE_RESET_ACTIVE");
        reset_all();check(display_mode==0 && live_valid==0 && falling_valid==0 && visual_drop_count==0,
            "RESET_FLUSHES_BOTH_CDC_AND_GEOMETRY");
        $display("PASS DUAL_SLIDER_ISOLATED checks=%0d",checks);$finish;
    end
    initial begin #5000000;$fatal(1,"REJECT TB_TIMEOUT");end
endmodule
