// Real25MHz raster sampling. Input hit is an already-proven tracker notice;
// this test isolates immediate activation vs unavoidable scan visibility.
`timescale 1ns/1ps
module tb_flash_scan_latency;
    logic clk=0;always #20 clk=~clk;
    logic rst_n=0,enabled=1,clear=0,hit_pulse=0;
    logic [6:0] hit_note_number=60;
    wire [127:0] active;
    wire [255:0] levels;
    wire [15:0] x,y;
    wire de,hs,vs,frame_start,line_start;
    wire [7:0] r,g,b;
    integer cycle=0,frames=0,observed_core=0,observed_white=0,observed_yellow=0;
    integer checks=0,before_core=0,activation_cycle=0,last_visible_cycle=0;
    logic [23:0] last_visible_rgb=0;
    visual_hit_flash #(.BASE_NOTE(60),.NOTE_COUNT(8),.FLASH_FRAMES(4)) flash(
        .clk(clk),.rst_n(rst_n),.frame_start(frame_start),.enabled(enabled),.clear(clear),
        .hit_pulse(hit_pulse),.hit_note_number(hit_note_number),.flash_active(active),.flash_level(levels));
    video_scan_timing #(.H_ACTIVE(64),.H_FRONT(4),.H_SYNC(8),.H_BACK(4),
        .V_ACTIVE(48),.V_FRONT(4),.V_SYNC(2),.V_BACK(10)) raster(
        .pixel_clk(clk),.rst_n(rst_n),.pixel_x(x),.pixel_y(y),.data_enable(de),
        .hsync(hs),.vsync(vs),.frame_start(frame_start),.line_start(line_start));
    visual_scene_renderer #(.LIVE_SLOT_COUNT(1),.SCORE_SLOT_COUNT(1),.Y_WIDTH(6),
        .SCREEN_WIDTH(64),.SCREEN_HEIGHT(48),.JUDGE_Y(32),.KEYBOARD_TOP(36),
        .BASE_NOTE(60),.NOTE_COUNT(8)) renderer(
        .data_enable(de),.pixel_x(x),.pixel_y(y),.display_mode(1'b1),.desync_latched(1'b0),
        .key_down(128'd0),.flash_active(active),.flash_level(levels),
        .live_valid(1'b0),.live_note_number(7'd0),.live_y(6'd0),.live_end_y(6'd0),.live_velocity(10'd0),
        .score_valid(1'b0),.score_note_number(7'd0),.score_y(6'd0),.score_top_y(6'd0),.score_end_y(6'd0),
        .score_velocity(10'd0),.score_hit(1'b0),.score_miss(1'b0),.rgb_r(r),.rgb_g(g),.rgb_b(b));
    // Observe pixels at the edge a real output register would capture them;
    // never modify already-observed framebuffer values after a midframe hit.
    always @(posedge clk)begin
        cycle++;
        if(rst_n && frame_start)frames++;
        if(rst_n && de && x==4 && y==47)begin
            last_visible_cycle=cycle;last_visible_rgb={r,g,b};
            if({r,g,b}==24'hffffe0)begin observed_white++;observed_core++;end
            if({r,g,b}==24'hffd060)begin observed_yellow++;observed_core++;end
        end
    end
    task automatic check(input logic ok,input string label_text);
        checks++;if(ok!==1)$fatal(1,"scan feedback %s cycle=%0d frame=%0d x/y=%0d/%0d",label_text,cycle,frames,x,y);
    endtask
    task automatic activate;
        @(negedge clk);hit_pulse=1;activation_cycle=cycle+1;
        @(negedge clk);hit_pulse=0;#1;
        check(active[60] && levels[120+:2]==3,"notice activates in one clock without frame_start");
    endtask
    initial begin
        repeat(2)@(negedge clk);rst_n=1;
        // Before bottom scan: bright core is visible later in the same frame.
        wait(x==0 && y==42);before_core=observed_core;activate();
        wait(x==5 && y==47);#1;
        check(observed_core==before_core+1 && observed_white==1,"hit before scan visible white in current frame");
        check(last_visible_cycle>activation_cycle,"physical pixel seen at subsequent raster position");
        // Clear, then hit after the final active line was scanned. Hardware
        // cannot repaint the past; activation is immediate but seen next scan.
        wait(x==0 && y==48);@(negedge clk);clear=1;
        @(negedge clk);clear=0;#1;check(!active[60],"clear immediate");
        before_core=observed_core;activate();
        wait(x==0 && y==0);#1;
        check(observed_core==before_core,"no retroactive pixel on frame boundary");
        wait(x==5 && y==47);#1;
        check(observed_core==before_core+1 && observed_yellow==1,"postscan hit appears on next bottom scan at decayed level");
        check(last_visible_cycle-activation_cycle>1000 && last_visible_cycle-activation_cycle<80*64,
              "scan delay positive and bounded by one complete raster");
        // Notify on actual frame_start: hit branch wins over countdown so first
        // bottom scan sees full strength, not a decremented initial phase.
        clear=1;@(negedge clk);clear=0;
        wait(x==0 && y==0);@(negedge clk);hit_pulse=1;
        @(negedge clk);hit_pulse=0;#1;
        check(active[60] && levels[120+:2]==3,"same-boundary notification retains peak");
        wait(x==5 && y==47);#1;check(observed_white==2,"boundary hit peak visible at bottom");
        enabled=0;@(posedge clk);#2;check(active==0,"disable discards every decay stage");
        rst_n=0;@(negedge clk);#1;check(active==0,"reset clears");
        $display("PASS flash scan timing: %0d checks immediate-register vs actual-raster visibility distinguished",checks);$finish;
    end
    initial begin #1000000;$fatal(1,"scan timing timeout");end
endmodule
