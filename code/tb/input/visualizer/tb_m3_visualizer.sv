`timescale 1ns/1ps
module tb_m3_visualizer;
    import audio_defs_pkg::*;
    localparam integer FRAME_WIDTH = 16;
    logic clk = 0, rst_n = 0;
    logic [15:0] pixel_x = 0, pixel_y = 0;
    logic data_enable = 0, frame_start = 0;
    logic event_valid = 0, event_ready;
    performance_event_t event_data = '0;
    logic video_desync = 0, mode_toggle_pulse = 0;
    logic score_valid = 0, score_ready;
    logic [15:0] score_note_id = 0;
    logic [6:0] score_note_number = 0;
    logic [FRAME_WIDTH-1:0] score_hit_frame = 0;
    logic score_duration_valid = 0;
    logic [FRAME_WIDTH-1:0] score_duration_frames = 0;
    logic [9:0] score_velocity = 0;
    logic display_mode;
    logic [FRAME_WIDTH-1:0] current_frame;
    logic [7:0] r, g, b;

    // Target-size renderer probe.  It protects the exact 640x480/49-key
    // pixel boundaries while the divider/modulo implementation is optimized.
    logic [15:0] target_x = 0, target_y = 0;
    logic target_de = 0, target_mode = 0, target_desync = 0;
    logic [127:0] target_keys = '0;
    logic [7:0] target_live_valid = '0;
    logic [55:0] target_live_note = '0;
    logic [79:0] target_live_velocity = '0;
    logic [79:0] target_live_y = '0;
    logic [79:0] target_live_end_y = '0;
    logic [7:0] target_score_valid = '0;
    logic [55:0] target_score_note = '0;
    logic [79:0] target_score_velocity = '0;
    logic [79:0] target_score_y = '0;
    logic [79:0] target_score_top_y='0,target_score_end_y='0;
    logic [7:0] target_score_hit = '0, target_score_missed = '0;
    logic [7:0] target_r, target_g, target_b;
    integer checks = 0;
    integer x_probe;
    integer expected_lane;
    integer expected_left;
    integer expected_right;
    integer expected_note;
    integer expected_pitch_class;
    logic [23:0] expected_rgb;
    always #5 clk = ~clk;

    m3_visualizer #(
        .LIVE_SLOT_COUNT(4), .SCORE_SLOT_COUNT(4),
        .FRAME_WIDTH(FRAME_WIDTH), .Y_WIDTH(6),
        .SCREEN_WIDTH(64), .SCREEN_HEIGHT(48), .JUDGE_Y(32),
        .KEYBOARD_TOP(36), .BASE_NOTE(60), .NOTE_COUNT(8),
        .PREVIEW_FRAMES(4), .HIT_WINDOW_FRAMES(1), .RISE_STEP(4)
    ) dut (
        .pixel_clk(clk), .video_rst_n(rst_n),
        .pixel_x(pixel_x), .pixel_y(pixel_y), .data_enable(data_enable),
        .frame_start(frame_start), .event_valid(event_valid),
        .event_data(event_data), .event_ready(event_ready),
        .video_desync(video_desync), .mode_toggle_pulse(mode_toggle_pulse),
        .score_valid(score_valid), .score_ready(score_ready),
        .score_note_id(score_note_id), .score_note_number(score_note_number),
        .score_hit_frame(score_hit_frame),
        .score_duration_valid(score_duration_valid),
        .score_duration_frames(score_duration_frames),
        .score_velocity(score_velocity), .display_mode(display_mode),
        .current_frame(current_frame), .rgb_r(r), .rgb_g(g), .rgb_b(b)
    );

    visual_scene_renderer #(
        .LIVE_SLOT_COUNT(8), .SCORE_SLOT_COUNT(8), .Y_WIDTH(10),
        .SCREEN_WIDTH(640), .SCREEN_HEIGHT(480), .JUDGE_Y(360),
        .KEYBOARD_TOP(400), .BASE_NOTE(36), .NOTE_COUNT(49)
    ) target_renderer (
        .pixel_x(target_x), .pixel_y(target_y), .data_enable(target_de),
        .display_mode(target_mode), .desync_latched(target_desync),
        .key_down(target_keys), .flash_active(128'd0), .live_valid(target_live_valid),
        .live_note_number(target_live_note),
        .live_velocity(target_live_velocity), .live_y(target_live_y), .live_end_y(target_live_end_y),
        .score_valid(target_score_valid),
        .score_note_number(target_score_note),
        .score_velocity(target_score_velocity), .score_y(target_score_y),
        .score_top_y(target_score_top_y),.score_end_y(target_score_end_y),
        .score_hit(target_score_hit), .score_miss(target_score_missed),
        .rgb_r(target_r), .rgb_g(target_g), .rgb_b(target_b)
    );

    task automatic pulse_frame;
        begin
            @(negedge clk); frame_start = 1;
            @(negedge clk); frame_start = 0;
        end
    endtask
    task automatic send_note(input logic is_on, input logic [6:0] note,
                             input logic [9:0] velocity);
        begin
            @(negedge clk);
            event_data = make_note_event(is_on, 4'd2, 4'd0, note, velocity);
            event_valid = 1;
            @(negedge clk); event_valid = 0;
        end
    endtask
    task automatic sample_pixel(input integer x, input integer y);
        begin pixel_x = x; pixel_y = y; #1; end
    endtask
    task automatic sample_target(input integer x, input integer y,
                                 input logic enable,
                                 input logic [23:0] expected,
                                 input string description);
        begin
            target_x = x;
            target_y = y;
            target_de = enable;
            #1;
            if ({target_r, target_g, target_b} !== expected)
                $fatal(1, "%s: got %06h expected %06h", description,
                       {target_r, target_g, target_b}, expected);
            checks = checks + 1;
        end
    endtask

    initial begin
        #2; data_enable = 1;
        sample_pixel(2, 40);
        if ({r,g,b} !== 24'h000000) $fatal(1, "reset must blank RGB");
        repeat (2) @(negedge clk); rst_n = 1; #1;
        if (!event_ready || display_mode) $fatal(1, "bad reset release");
        checks = checks + 1;

        data_enable = 0; sample_pixel(2, 40);
        if ({r,g,b} !== 24'h000000) $fatal(1, "blanking must be black");
        data_enable = 1; checks = checks + 1;

        send_note(1, 7'd60, 10'd900);
        sample_pixel(2, 40);
        if ({r,g,b} === 24'ha0e0d8) $fatal(1, "mid-frame key tearing");
        pulse_frame(); sample_pixel(2, 40);
        if ({r,g,b} !== 24'ha0e0d8) $fatal(1, "held bar not rendered");
        checks = checks + 1;

        // A second complete frame must keep the latched visual state stable.
        pulse_frame(); sample_pixel(2, 40);
        if ({r,g,b} !== 24'ha0e0d8)
            $fatal(1, "held bar changed unexpectedly across frames");
        checks = checks + 1;

        send_note(0, 7'd60, 10'd0); pulse_frame(); sample_pixel(2, 40);
        if (dut.live_held != 0) $fatal(1, "released bar still held");
        checks = checks + 1;

        @(negedge clk); mode_toggle_pulse = 1;
        @(negedge clk); mode_toggle_pulse = 0;
        if (display_mode) $fatal(1, "mode changed mid-frame");
        pulse_frame();
        if (!display_mode) $fatal(1, "score mode did not start");
        checks = checks + 1;

        @(negedge clk);
        score_note_id = 16'd7;
        score_note_number = 7'd64;
        score_hit_frame = current_frame + 4;
        score_duration_valid = 1;
        score_duration_frames = 3;
        score_velocity = 700;
        score_valid = 1;
        @(negedge clk); score_valid = 0;
        // Leading edge reaches bottom48 at hit, long tail trails by duration.
        // One frame after enqueue, this score bar spans the upper screen.
        pulse_frame(); sample_pixel(34, 9);
        if ({r,g,b} == 24'h081020) $fatal(1, "falling score note not rendered");
        checks = checks + 1;

        video_desync = 1; pulse_frame();
        if (!event_ready) $fatal(1, "desync backpressured M2 bridge");
        sample_pixel(20, 4);
        if (r < 8'h80 || g > 8'h28) $fatal(1, "desync warning missing");
        checks = checks + 1;

        @(negedge clk); rst_n = 0;
        @(posedge clk); #1;
        if ({r,g,b} !== 24'h000000 || display_mode || current_frame != 0)
            $fatal(1, "reset did not clear wrapper state");
        video_desync = 0;
        checks = checks + 1;

        // Blanking and active-area boundaries at the actual target geometry.
        sample_target(0, 0, 0, 24'h000000, "blanking at origin");
        sample_target(639, 479, 0, 24'h000000, "blanking at last pixel");
        sample_target(640, 100, 1, 24'h000000, "right of active area");
        sample_target(100, 480, 1, 24'h000000, "below active area");

        // Uneven 640/49 lane widths: preserve floor-division edge behavior.
        sample_target(0, 100, 1, 24'h18283c, "first lane line");
        sample_target(1, 100, 1, 24'h081020, "first lane interior");
        // Bottom area is background/grid now, never a keyboard or key highlight.
        for (x_probe = 0; x_probe < 640; x_probe = x_probe + 1) begin
            expected_lane = (x_probe * 49) / 640;
            expected_left = (expected_lane * 640) / 49;
            expected_rgb = (x_probe==expected_left) ? 24'h18283c : 24'h081020;
            target_keys='1;
            sample_target(x_probe,420,1,expected_rgb,"no keyboard below baseline");
        end
        target_keys='0;

        target_live_valid[0] = 1'b1;
        target_live_note[0 +: 7] = 7'd36;
        target_live_velocity[0 +: 10] = 10'd900;
        target_live_y[0 +: 10] = 10'd100;
        target_live_end_y[0 +: 10] = 10'd200;
        sample_target(1, 100, 1, 24'ha0e0d8, "scaled live-note color");
        sample_target(12, 100, 1, 24'h081020, "live-note right exclusion");
        // Higher-numbered slots retain the original draw-over priority.
        target_live_valid[7] = 1'b1;
        target_live_note[49 +: 7] = 7'd36;
        target_live_velocity[70 +: 10] = 10'd100;
        target_live_y[70 +: 10] = 10'd100;
        target_live_end_y[70 +: 10] = 10'd200;
        sample_target(1, 100, 1, 24'h3c7ca6, "slot-seven priority");
        target_live_valid = '0;

        target_mode = 1'b1;
        target_score_valid[0] = 1'b1;
        target_score_note[0 +: 7] = 7'd36;
        target_score_velocity[0 +: 10] = 10'd900;
        target_score_y[0 +: 10] = 10'd260;
        target_score_top_y[0+:10]=100;target_score_end_y[0+:10]=112;
        sample_target(1, 100, 1, 24'he080e8, "scaled score-note color");
        target_score_valid[7] = 1'b1;
        target_score_note[49 +: 7] = 7'd36;
        target_score_velocity[70 +: 10] = 10'd100;
        target_score_y[70 +: 10] = 10'd260;
        target_score_top_y[70+:10]=100;target_score_end_y[70+:10]=112;
        target_score_hit[7] = 1'b1;
        sample_target(1, 100, 1, 24'h30e870, "score slot-seven hit priority");
        target_score_hit[7] = 1'b0;
        target_score_missed[7] = 1'b1;
        sample_target(1, 100, 1, 24'he83838,
                      "score slot-seven miss priority");
        target_score_valid = '0;
        target_score_missed = '0;
        target_mode = 1'b0;

        $display("PASS tb_m3_visualizer: %0d integration checks", checks);
        $finish;
    end
    initial begin #200000; $fatal(1, "tb_m3_visualizer timeout"); end
endmodule
