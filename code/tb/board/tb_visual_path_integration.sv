// M2-only independent connection test. M3 modules are compiled unchanged.
// Video-only PLL loss flushes both bridge domains before any new handshake.
`timescale 1ns/1ps
module tb_visual_path_integration;
    import audio_defs_pkg::*;
    logic sys_clk = 0, pixel_clk = 0;
    always #5 sys_clk = ~sys_clk;       // 100 MHz test clock; not board timing
    always #10 pixel_clk = ~pixel_clk; // 50 MHz test clock; not board timing
    logic sys_rst_n = 0, pll_locked = 0;
    wire shared_rst_n = sys_rst_n && pll_locked;
    logic accepted_valid = 0;
    performance_event_t accepted_data = '0;
    wire [15:0] queue_level, queue_peak;
    wire [31:0] drop_count;
    wire drop_pulse, sys_reset_done, video_reset_done;
    wire bridge_valid, bridge_desync;
    wire performance_event_t bridge_data;
    logic video_stall = 0;
    wire renderer_ready;
    wire bridge_ready = renderer_ready && !video_stall;
    wire renderer_valid = bridge_valid && !video_stall;
    wire [15:0] x, y;
    wire data_enable, hs, vs, frame_start, line_start;
    logic mode_toggle = 0;
    logic score_valid = 0;
    wire score_ready;
    logic [15:0] score_note_id = 0;
    logic [6:0] score_note_number = 0;
    logic [15:0] score_hit_frame = 0, score_duration_frames = 0;
    logic score_duration_valid = 0;
    logic [9:0] score_velocity = 0;
    wire display_mode;
    wire [15:0] current_frame;
    wire [7:0] r, g, b;
    integer accepted_count = 0, delivered_count = 0, frame_count = 0;
    integer checks = 0;

    visual_event_bridge #(.DEPTH(4)) bridge (
        .sys_clk(sys_clk), .video_clk(pixel_clk), .rst_n(shared_rst_n),
        .accepted_valid(accepted_valid), .accepted_data(accepted_data),
        .visual_queue_level(queue_level), .visual_queue_high_watermark(queue_peak),
        .visual_drop_count(drop_count), .visual_drop_pulse(drop_pulse),
        .sys_reset_done(sys_reset_done), .video_reset_done(video_reset_done),
        .video_valid(bridge_valid), .video_desync(bridge_desync),
        .video_ready(bridge_ready), .video_data(bridge_data)
    );
    video_scan_timing #(
        .H_ACTIVE(64), .H_FRONT(2), .H_SYNC(2), .H_BACK(2),
        .V_ACTIVE(48), .V_FRONT(2), .V_SYNC(2), .V_BACK(2)
    ) scan (
        .pixel_clk(pixel_clk), .rst_n(video_reset_done),
        .pixel_x(x), .pixel_y(y), .data_enable(data_enable),
        .hsync(hs), .vsync(vs), .frame_start(frame_start), .line_start(line_start)
    );
    m3_visualizer #(
        .LIVE_SLOT_COUNT(4), .SCORE_SLOT_COUNT(4),
        .FRAME_WIDTH(16), .Y_WIDTH(6),
        .SCREEN_WIDTH(64), .SCREEN_HEIGHT(48), .JUDGE_Y(32),
        .KEYBOARD_TOP(36), .BASE_NOTE(60), .NOTE_COUNT(8),
        .PREVIEW_FRAMES(4), .HIT_WINDOW_FRAMES(1), .RISE_STEP(4)
    ) scene (
        .pixel_clk(pixel_clk), .video_rst_n(video_reset_done),
        .pixel_x(x), .pixel_y(y), .data_enable(data_enable),
        .frame_start(frame_start),
        .event_valid(renderer_valid), .event_data(bridge_data),
        .event_ready(renderer_ready), .video_desync(bridge_desync),
        .mode_toggle_pulse(mode_toggle),
        .score_valid(score_valid), .score_ready(score_ready),
        .score_note_id(score_note_id), .score_note_number(score_note_number),
        .score_hit_frame(score_hit_frame),
        .score_duration_valid(score_duration_valid),
        .score_duration_frames(score_duration_frames),
        .score_velocity(score_velocity),
        .display_mode(display_mode), .current_frame(current_frame),
        .rgb_r(r), .rgb_g(g), .rgb_b(b)
    );

    always @(posedge sys_clk) if (shared_rst_n && sys_reset_done && accepted_valid)
        accepted_count <= accepted_count + 1;
    always @(posedge pixel_clk) begin
        if (shared_rst_n && video_reset_done) begin
            if (bridge_valid && bridge_ready) delivered_count <= delivered_count + 1;
            if (frame_start) frame_count <= frame_count + 1;
        end
    end

    task automatic send_note(input logic is_on, input logic [3:0] source,
                             input logic [6:0] note);
        begin
            @(negedge sys_clk);
            accepted_data = make_note_event(is_on, source, 4'd0, note, 10'd700);
            accepted_valid = 1'b1;
            @(negedge sys_clk);
            accepted_valid = 1'b0;
        end
    endtask
    task automatic check_pixel(input integer px, input integer py,
                               input logic [23:0] expected);
        begin
            do @(negedge pixel_clk); while (!(video_reset_done && x == px && y == py));
            if ({r,g,b} !== expected)
                $fatal(1, "pixel (%0d,%0d) expected %h got %h",px,py,expected,{r,g,b});
            checks = checks + 1;
        end
    endtask
    task automatic next_frame;
        begin
            do @(negedge pixel_clk); while (!frame_start);
            @(negedge pixel_clk); // sampled frame_start on the intervening edge
        end
    endtask

    initial begin
        #3_000_000;
        $fatal(1,"visual integration timeout: accepted=%0d delivered=%0d frames=%0d",accepted_count,delivered_count,frame_count);
    end
    initial begin
        repeat(4) @(negedge sys_clk);
        sys_rst_n = 1;
        pll_locked = 1;
        wait(sys_reset_done && video_reset_done);
        next_frame();
        checks = checks + 1;

        // Stalled video must not stall a real accepted audio event.
        video_stall = 1;
        send_note(1, 4'd2, 7'd60);
        repeat(20) @(negedge sys_clk);
        if (accepted_count != 1 || delivered_count != 0 || drop_count != 0)
            $fatal(1,"video stalled audio acceptance or silently delivered event");
        checks = checks + 1;
        video_stall = 0;
        wait(delivered_count == 1);
        repeat(6) @(negedge pixel_clk);
        if (delivered_count != 1 || bridge_data.note_number != 7'd60)
            $fatal(1,"bridge duplicated or corrupted accepted Note On");
        checks = checks + 1;
        next_frame();
        check_pixel(2, 40, 24'h20c8e8); // key lights only on coherent next frame

        send_note(0, 4'd2, 7'd60);
        wait(delivered_count == 2);
        next_frame();
        check_pixel(2, 40, 24'he8e8dc);
        if (accepted_count != 2 || delivered_count != 2)
            $fatal(1,"note transfer count differs: %0d/%0d",accepted_count, delivered_count);
        checks = checks + 1;

        // The UI mode request is already in pixel clock domain in this test.
        @(negedge pixel_clk); mode_toggle = 1;
        @(negedge pixel_clk); mode_toggle = 0;
        if (display_mode) $fatal(1,"mode changed inside a frame");
        next_frame();
        if (!display_mode) $fatal(1,"mode did not change at frame boundary");
        checks = checks + 1;

        // Score is already on the pixel side. This checks the bridge/scan/
        // renderer wiring, not an unfrozen score CDC or linger policy.
        @(negedge pixel_clk);
        if (!score_ready) $fatal(1,"score receiver not ready");
        score_note_id = 16'd7;
        score_note_number = 7'd64;
        score_hit_frame = current_frame + 4;
        score_duration_valid = 1;
        score_duration_frames = 3;
        score_velocity = 10'd700;
        score_valid = 1;
        @(negedge pixel_clk); score_valid = 0;
        next_frame();
        do @(negedge pixel_clk); while (!(x == 34 && y == 9));
        if ({r,g,b} === 24'h081020 || {r,g,b} === 24'h000000)
            $fatal(1,"score note not rendered after next frame");
        checks = checks + 1;

        // PLL loss asserts the same reset to the system/video sides.
        video_stall = 1;
        send_note(1,4'd3,7'd64);
        repeat(4) @(negedge sys_clk);
        @(negedge sys_clk); pll_locked = 0;
        repeat(4) @(negedge pixel_clk);
        if (video_reset_done || sys_reset_done || bridge_valid || display_mode ||
            {r,g,b} !== 24'h000000)
            $fatal(1,"PLL loss did not flush both domains");
        checks = checks + 1;
        @(negedge sys_clk); pll_locked = 1;
        video_stall = 0;
        wait(sys_reset_done && video_reset_done);
        repeat(20) @(negedge pixel_clk);
        if (bridge_valid || delivered_count != 2)
            $fatal(1,"stale event replayed after PLL relock");
        checks = checks + 1;
        send_note(1,4'd3,7'd64);
        wait(delivered_count == 3);
        next_frame();
        if (accepted_count != 4 || delivered_count != 3)
            $fatal(1,"new event failed after relock: %0d/%0d",accepted_count,delivered_count);
        checks = checks + 1;

        // Overfill the display-only queue: audio acceptance must continue,
        // and M3 must visibly reject stale drawing state after desync.
        video_stall = 1;
        repeat (8) send_note(1, 4'd4, 7'd60);
        repeat (6) @(negedge sys_clk);
        if (accepted_count != 12 || drop_count == 0)
            $fatal(1,"video overfill stalled audio or hid drops");
        checks = checks + 1;
        video_stall = 0;
        wait(bridge_desync);
        next_frame();
        check_pixel(20, 4, 24'hff2828);
        $display("PASS visual_path_integration: %0d checks; 12 accepted audio events, %0d displayed, %0d display-only drops", checks, delivered_count, drop_count);
        $finish;
    end
endmodule
