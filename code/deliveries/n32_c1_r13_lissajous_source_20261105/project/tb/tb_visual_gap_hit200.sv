`timescale 1ns/1ps
module tb_visual_gap_hit200;
    import audio_defs_pkg::*;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,frame=0,fire=0;
    performance_event_t ev;
    wire [31:0] valid;
    wire [223:0] notes;
    wire [319:0] top_y,end_y;
    pro_visual_live_state #(.JUDGE_Y(470)) live(
        .clk(clk),.rst_n(rst_n),.frame_start(frame),.performance_fire(fire),
        .flush(1'b0),.performance_data(ev),.video_desync(1'b0),
        .live_valid(valid),.live_note_number(notes),.live_y(top_y),.live_end_y(end_y));
    reg score_valid=0,judge_fire=0;
    reg [15:0] score_id=1;
    reg [6:0] score_note=60;
    reg [31:0] arrival=20;
    wire ready,hit_pulse;
    wire [31:0] now_frame;
    wire [1:0] score_slots,hit,miss;
    pro_visual_score_tracker #(.SLOT_COUNT(2),.HIT_WINDOW_FRAMES(12),
        .BOTTOM_EXIT_GEOMETRY(1),.STRICT_CONTACT(1)) score(
        .clk(clk),.rst_n(rst_n),.frame_start(frame),
        .score_valid(score_valid),.score_ready(ready),
        .score_note_id(score_id),.score_note_number(score_note),.score_hit_frame(arrival),
        .score_duration_valid(1'b1),.score_duration_frames(32'd30),.score_velocity(10'd640),
        .performance_fire(judge_fire),.performance_data(ev),.match_enabled(1'b1),
        .video_desync(1'b0),.current_frame(now_frame),.slot_valid(score_slots),
        .slot_hit(hit),.slot_miss(miss),
        .hit_pulse(hit_pulse));
    task automatic tick;
        @(negedge clk);frame=1;@(negedge clk);frame=0;
    endtask
    task automatic press;
        @(negedge clk);ev=make_note_event(1'b1,4'd1,4'd0,8'd60,10'd640);fire=1;
        @(negedge clk);fire=0;
    endtask
    task automatic load_score;
        @(negedge clk);score_valid=1;
        do @(posedge clk);while(!ready);
        @(negedge clk);score_valid=0;
    endtask
    initial begin
        ev='0;repeat(3)@(negedge clk);rst_n=1;
        press();tick();press();tick();
        // The released earlier C must end above the newly created C.
        for(integer a=0;a<32;a++)for(integer b=0;b<32;b++)
            if(a!=b && valid[a] && valid[b] && notes[a*7+:7]==notes[b*7+:7])
                if(!(end_y[a*10+:10]+2<=top_y[b*10+:10] ||
                     end_y[b*10+:10]+2<=top_y[a*10+:10]))
                    $fatal(1,"RETRIGGER_JOINED");
        load_score();
        while(now_frame<8)tick();
        @(negedge clk);judge_fire=1;
        @(negedge clk);judge_fire=0;
        if(hit!=0)$fatal(1,"EARLY_FLASH");
        while(now_frame<20)tick();
        // The production raster leaves hundreds of thousands of pixel clocks
        // between frame pulses.  Allow the R06 one-slot-per-clock geometry
        // refresher to publish both slots before checking the contact frame.
        repeat(3)@(posedge clk);
        #1;if(hit==0)$fatal(1,"EARLY_HIT_NOT_SHOWN_AT_CONTACT");

        // Bottom-exit retirement is performed by the same serial frame scan.
        while(now_frame<51)tick();
        repeat(3)@(posedge clk);
        #1;if(score_slots!=0)$fatal(1,"SERIAL_RETIRE_FAILED");

        // A second unplayed note must become a miss only after the inclusive
        // +/- window, and the ready/valid payload must survive serial search.
        score_id=16'd2;score_note=7'd61;arrival=now_frame+32'd2;
        load_score();
        // The hit window is inclusive through arrival+12.  Stop on that
        // exact frame for the negative check; the following tick is the
        // first frame at which a miss is allowed to publish.
        while(now_frame<arrival+12)tick();
        repeat(3)@(posedge clk);
        #1;if(miss!=0)$fatal(1,"MISS_BEFORE_WINDOW_END");
        tick();repeat(3)@(posedge clk);
        #1;if(miss==0)$fatal(1,"SERIAL_MISS_NOT_PUBLISHED");
        $display("VISUAL_GAP_HIT200_PASS");$finish;
    end
    initial begin #100000;$fatal(1,"TIMEOUT");end
endmodule
