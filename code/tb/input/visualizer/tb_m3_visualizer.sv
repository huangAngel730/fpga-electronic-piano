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
    integer checks = 0;
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
        if ({r,g,b} === 24'h20c8e8) $fatal(1, "mid-frame key tearing");
        pulse_frame(); sample_pixel(2, 40);
        if ({r,g,b} !== 24'h20c8e8) $fatal(1, "pressed key not highlighted");
        checks = checks + 1;

        send_note(0, 7'd60, 10'd0); pulse_frame(); sample_pixel(2, 40);
        if ({r,g,b} === 24'h20c8e8) $fatal(1, "released key stayed highlighted");
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
        // current=4, hit=7, preview=4 gives relative y=24, therefore
        // screen y=JUDGE_Y-relative_y=8.
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
        $display("PASS tb_m3_visualizer: %0d integration checks", checks);
        $finish;
    end
    initial begin #200000; $fatal(1, "tb_m3_visualizer timeout"); end
endmodule
