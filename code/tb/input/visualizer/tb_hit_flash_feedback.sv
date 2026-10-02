// Strict contact contract: actual published frame geometry, immediate notice,
// fixed palette decay, and raster scan latency. Pixel clock is real25MHz.
`timescale 1ns/1ps
module tb_hit_flash_feedback;
    import audio_defs_pkg::*;
    logic pixel_clk=0;always #20 pixel_clk=~pixel_clk;
    logic video_rst_n=0,data_enable=1,frame_start=0,event_valid=0,event_ready;
    logic [15:0] pixel_x=1,pixel_y=47;
    performance_event_t event_data='0;
    logic video_desync=0,mode_toggle_pulse=0;
    logic score_valid=0,score_ready;
    logic [15:0] score_note_id=0;
    logic [6:0] score_note_number=60;
    logic [15:0] score_hit_frame=0,score_duration_frames=0;
    logic score_duration_valid=0;
    logic [9:0] score_velocity=600;
    wire display_mode;
    wire [15:0] current_frame;
    wire [7:0] rgb_r,rgb_g,rgb_b;
    integer checks=0,hits=0,cycle=0,max_notice_latency=0,max_event_latency=0;
    integer pending_note[0:127],pending_cycle[0:127],pending_size=0;
    integer notice_cycles[0:127],event_cycles[0:127];
    logic [15:0] stamp;
    integer before_hits;
    m3_visualizer #(.FRAME_WIDTH(16),.Y_WIDTH(6),.SCREEN_WIDTH(64),.SCREEN_HEIGHT(48),
        .BASE_NOTE(60),.NOTE_COUNT(8),.JUDGE_Y(32),.KEYBOARD_TOP(36),
        .PREVIEW_FRAMES(4),.HIT_WINDOW_FRAMES(2),.HIT_FLASH_FRAMES(4)) dut(.*);

    always @(posedge pixel_clk)begin
        cycle++;
        if(event_valid && event_ready && event_data.event_type==EVENT_NOTE_ON && event_data.velocity!=0)
            event_cycles[event_data.note_number]=cycle;
        #1;
        if(video_rst_n && display_mode && !dut.clear_flash)begin
            // A registered hit notification must be reflected in visible
            // output within two pixel clocks, even without any frame_start.
            for(integer q=0;q<pending_size;q++)begin
                if(cycle-pending_cycle[q]>=1 && !dut.flash_active[pending_note[q]])
                    $fatal(1,"hit notice activation deadline failed");
                if(dut.flash_active[pending_note[q]])begin
                    if(cycle-pending_cycle[q]>max_notice_latency)max_notice_latency=cycle-pending_cycle[q];
                    if(cycle-event_cycles[pending_note[q]]>max_event_latency)
                        max_event_latency=cycle-event_cycles[pending_note[q]];
                end
            end
            pending_size=0;
            if(dut.hit_pulse)begin
                hits++;
                notice_cycles[dut.hit_note_number]=cycle;
                pending_note[0]=dut.hit_note_number;pending_cycle[0]=cycle;pending_size=1;
            end
        end else pending_size=0;
    end
    task automatic check(input logic ok,input string label_text);
        checks++;
        if(ok!==1'b1)$fatal(1,"strict contact %s frame=%d hits=%d active=%h",label_text,current_frame,hits,dut.flash_active);
    endtask
    task automatic frame;
        @(negedge pixel_clk);frame_start=1;
        @(negedge pixel_clk);frame_start=0;#1;
    endtask
    task automatic reset_all;
        @(negedge pixel_clk);video_rst_n=0;event_valid=0;score_valid=0;frame_start=0;
        video_desync=0;mode_toggle_pulse=0;
        @(negedge pixel_clk);video_rst_n=1;#1;
    endtask
    task automatic set_mode;
        @(negedge pixel_clk);mode_toggle_pulse=1;
        @(negedge pixel_clk);mode_toggle_pulse=0;
        frame();@(negedge pixel_clk);#1;
    endtask
    task automatic score(input logic [6:0] pitch,input logic [15:0] at_frame,input logic [15:0] id);
        @(negedge pixel_clk);score_note_number=pitch;score_hit_frame=at_frame;
        score_note_id=id;score_duration_valid=1;score_duration_frames=12;score_valid=1;
        do @(posedge pixel_clk);while(!score_ready);
        @(negedge pixel_clk);score_valid=0;#1;
    endtask
    task automatic note(input logic [6:0] pitch,input logic [2:0] typ,input logic [9:0] vel);
        @(negedge pixel_clk);event_data='0;event_data.event_type=typ;
        event_data.note_number=pitch;event_data.velocity=vel;event_valid=1;
        @(negedge pixel_clk);event_valid=0;
        @(negedge pixel_clk);#1;
    endtask
    task automatic boundary_note(input logic [6:0] pitch);
        @(negedge pixel_clk);frame_start=1;event_valid=1;
        event_data=make_note_event(1,2,0,pitch,700);
        @(negedge pixel_clk);frame_start=0;event_valid=0;
        // notice registered at boundary, active on following edge
        @(negedge pixel_clk);#1;
    endtask
    task automatic sample(input integer x,y,input logic de,input logic [23:0] expected);
        pixel_x=x;pixel_y=y;data_enable=de;#1;
        if({rgb_r,rgb_g,rgb_b}!==expected)
            $display("PIXEL %0d,%0d actual=%h expected=%h",x,y,{rgb_r,rgb_g,rgb_b},expected);
        check({rgb_r,rgb_g,rgb_b}===expected,"palette/bottom/clipping/blanking");
    endtask
    initial begin
        for(integer n=0;n<128;n++)begin event_cycles[n]=0;notice_cycles[n]=0;end
        reset_all();set_mode();check(display_mode,"enter falling mode");
        stamp=current_frame+2;score(60,stamp,1);
        before_hits=hits;note(60,EVENT_NOTE_ON,700);
        check(hits==before_hits && !dut.u_score_tracker.judged_mem[0],"two frames early ignored, no judged pollution");
        frame();check(current_frame==stamp-1,"precontact frame");
        note(60,EVENT_NOTE_ON,700);
        check(hits==before_hits && !dut.u_score_tracker.judged_mem[0],"one frame early not cached");
        frame();repeat(3)@(negedge pixel_clk);
        check(current_frame==stamp && dut.score_end_y[0+:6]==48,"actual leading edge hits bottom at score frame");
        check(hits==before_hits && !dut.flash_active[60],"early held key never automatically flashes at arrival");
        note(61,EVENT_NOTE_ON,700);note(60,EVENT_NOTE_OFF,0);
        note(60,EVENT_CONTROL_CHANGE,700);note(60,EVENT_NOTE_ON,0);
        check(hits==before_hits && !dut.u_score_tracker.judged_mem[0],"wrong/off/CC/zero ignored without poison");
        note(60,EVENT_NOTE_ON,700);
        check(hits==before_hits+1 && dut.flash_active[60] && dut.flash_level[120+:2]==3,"mid-frame correct NoteOn immediately bright");
        sample(4,47,1,24'hffffe0);sample(0,44,1,24'h80e8ff);
        sample(4,20,1,24'h30e870);sample(4,48,1,24'h000000);
        sample(64,47,1,24'h000000);sample(4,47,0,24'h000000);data_enable=1;
        note(60,EVENT_NOTE_ON,700);check(hits==before_hits+1,"same score instance hits at most once");
        frame();check(dut.flash_level[120+:2]==2,"next frame decays from bright to yellow");sample(4,47,1,24'hffd060);sample(0,44,1,24'h4080b0);
        frame();check(dut.flash_level[120+:2]==1,"third phase low");sample(4,47,1,24'hb06820);
        frame();check(dut.flash_level[120+:2]==0 && dut.flash_active[60],"fourth phase faint");sample(4,47,1,24'h503010);
        frame();check(!dut.flash_active[60],"four-phase feedback extinguishes");

        // Exact final pixel clock of the preceding frame: cannot queue that
        // NoteOn for the future hit. A new same-boundary event is required.
        reset_all();set_mode();stamp=current_frame+1;score(60,stamp,10);
        before_hits=hits;
        @(negedge pixel_clk);event_valid=1;event_data=make_note_event(1,2,0,60,700);
        @(posedge pixel_clk);#2;
        check(hits==before_hits && !dut.u_score_tracker.judged_mem[0],"last pixel event of previous frame ignored");
        @(negedge pixel_clk);frame_start=1;event_valid=0;
        @(negedge pixel_clk);frame_start=0;repeat(2)@(negedge pixel_clk);#1;
        check(current_frame==stamp && hits==before_hits && !dut.flash_active[60],"immediate next boundary cannot replay early event");
        // Fresh epoch: a genuinely new event on the actual arrival edge.
        reset_all();set_mode();stamp=current_frame+1;score(60,stamp,11);
        boundary_note(60);
        check(current_frame==stamp && dut.score_end_y[0+:6]==48 && hits==before_hits+1 && dut.flash_active[60],"same-boundary event uses postNBA visible frame");
        frame();before_hits=hits;note(60,EVENT_NOTE_ON,700);check(hits==before_hits,"past frame cannot repeat trigger");

        reset_all();set_mode();stamp=current_frame+1;score(62,stamp,20);
        frame();frame();before_hits=hits;note(62,EVENT_NOTE_ON,700);
        check(hits==before_hits && !dut.flash_active[62],"one frame late ignored even if long strip contacts bottom");
        check(dut.u_score_tracker.miss_mem[0],"strict miss after contact frame");

        // Same-pitch earlier allocated future neighbor is not eligible. Only
        // the actual-contact slot participates in selection, not abs<=window.
        reset_all();set_mode();stamp=current_frame+1;
        score(63,stamp+1,30);score(63,stamp,31);score(64,stamp,32);
        before_hits=hits;boundary_note(63);
        check(hits==before_hits+1 && dut.u_score_tracker.hit_mem[1] && !dut.u_score_tracker.judged_mem[0],"same pitch future low slot cannot steal contact");
        note(64,EVENT_NOTE_ON,700);
        check(dut.flash_active[63] && dut.flash_active[64],"two pitches hit nearly together");
        frame();note(63,EVENT_NOTE_ON,700);
        check(dut.u_score_tracker.hit_mem[0] && dut.flash_level[126+:2]==3,"next scored instance refreshes its pitch");
        check(dut.flash_level[128+:2]==2,"other pitch decays independently");

        // Repeated note_id while instance retained is consumed, not rearmed.
        reset_all();set_mode();stamp=current_frame+1;
        score(65,stamp,40);score(65,stamp,40);
        check(!dut.u_score_tracker.slot_used_mem[1],"duplicate active score ID has no second slot");
        before_hits=hits;boundary_note(65);note(65,EVENT_NOTE_ON,700);
        check(hits==before_hits+1,"duplicate active score ID fires once");

        // Same-time distinct instances retain low slot priority and fire one
        // notification per freshly accepted NoteOn, never unsolicited.
        reset_all();set_mode();stamp=current_frame+1;
        score(66,stamp,50);score(66,stamp,51);boundary_note(66);
        check(dut.u_score_tracker.hit_mem[0] && !dut.u_score_tracker.judged_mem[1],"same contact time chooses low unjudged slot");
        before_hits=hits;note(66,EVENT_NOTE_ON,700);
        check(hits==before_hits+1 && dut.u_score_tracker.hit_mem[1],"second NoteOn chooses remaining instance");
        note(0,EVENT_ALL_NOTES_OFF,0);check(dut.flash_active==0,"clear extinguishes immediately");

        reset_all();set_mode();score(67,current_frame,60);note(67,EVENT_NOTE_ON,700);
        sample(63,47,1,24'h80e8ff);check(dut.flash_active[67],"last pitch clips bright halo at screen edge");
        video_desync=1;@(negedge pixel_clk);#1;check(dut.flash_active==0,"desync clears feedback");
        video_desync=0;frame();score(60,current_frame,61);note(60,EVENT_NOTE_ON,700);
        check(dut.flash_active==0,"latched desync prevents flash");
        reset_all();set_mode();score(60,current_frame,62);note(60,EVENT_NOTE_ON,700);
        set_mode();check(!display_mode && dut.flash_active==0,"leave mode clears feedback");
        score(61,current_frame,63);before_hits=hits;note(61,EVENT_NOTE_ON,700);
        check(hits==before_hits && !dut.u_score_tracker.judged_mem[1],"live mode does not accept score contact");
        // Consecutive accepted pixel cycles must carry independent hit notes
        // through the registered notification pipeline without waiting a frame.
        reset_all();set_mode();stamp=current_frame+1;
        score(60,stamp,70);score(61,stamp,71);
        before_hits=hits;
        @(negedge pixel_clk);frame_start=1;event_valid=1;event_data=make_note_event(1,2,0,60,700);
        @(negedge pixel_clk);frame_start=0;event_data=make_note_event(1,2,0,61,700);
        @(negedge pixel_clk);event_valid=0;
        @(negedge pixel_clk);#1;
        check(hits==before_hits+2 && dut.flash_active[60] && dut.flash_active[61],"consecutive pixel-clock hits preserved");
        // New mode is the one published on a frame boundary, not the previous
        // display_mode. Entering contact can hit; leaving contact cannot.
        reset_all();stamp=current_frame+1;score(62,stamp,72);
        @(negedge pixel_clk);mode_toggle_pulse=1;
        @(negedge pixel_clk);mode_toggle_pulse=0;
        before_hits=hits;boundary_note(62);
        check(display_mode && hits==before_hits+1 && dut.flash_active[62],"enter-mode boundary uses actual new display frame");
        score(63,current_frame+1,73);
        @(negedge pixel_clk);mode_toggle_pulse=1;
        @(negedge pixel_clk);mode_toggle_pulse=0;
        before_hits=hits;boundary_note(63);
        check(!display_mode && hits==before_hits && dut.flash_active==0,"exit-mode boundary refuses score hit");
        video_rst_n=0;@(negedge pixel_clk);#1;check(dut.flash_active==0 && !dut.hit_pulse,"reset clears notice and brightness");
        check(max_notice_latency<=2 && max_event_latency<=2,"pixel-clock latency bounds");
        $display("PASS strict contact feedback: %0d checks %0d hits notice_to_active_max=%0d event_to_active_max=%0d pixel clocks",checks,hits,max_notice_latency,max_event_latency);
        $finish;
    end
    initial begin #500000;$fatal(1,"strict flash timeout");end
endmodule
