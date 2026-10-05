// M3 visualization wrapper. M2 owns clocks/CDC/TMDS/top-level integration.
`timescale 1ns/1ps
module m3_visualizer #(
    parameter integer LIVE_SLOT_COUNT = 8,
    parameter integer SCORE_SLOT_COUNT = 8,
    parameter integer FRAME_WIDTH = 32,
    parameter integer Y_WIDTH = 10,
    parameter integer SCREEN_WIDTH = 640,
    parameter integer SCREEN_HEIGHT = 480,
    parameter integer JUDGE_Y = 400,
    parameter integer KEYBOARD_TOP = 410,
    parameter integer BASE_NOTE = 36,
    parameter integer NOTE_COUNT = 49,
    parameter integer PREVIEW_FRAMES = 120,
    parameter integer HIT_WINDOW_FRAMES = 6,
    parameter integer RISE_STEP = 4
) (
    input logic pixel_clk,
    input logic video_rst_n,
    input logic [15:0] pixel_x,
    input logic [15:0] pixel_y,
    input logic data_enable,
    input logic frame_start,
    input logic event_valid,
    input audio_defs_pkg::performance_event_t event_data,
    output logic event_ready,
    input logic video_desync,
    input logic mode_toggle_pulse,
    input logic score_valid,
    output logic score_ready,
    input logic [15:0] score_note_id,
    input logic [6:0] score_note_number,
    input logic [FRAME_WIDTH-1:0] score_hit_frame,
    input logic score_duration_valid,
    input logic [FRAME_WIDTH-1:0] score_duration_frames,
    input logic [9:0] score_velocity,
    output logic display_mode,
    output logic [FRAME_WIDTH-1:0] current_frame,
    output logic [7:0] rgb_r,
    output logic [7:0] rgb_g,
    output logic [7:0] rgb_b
);
    logic mode_request;
    logic performance_fire;
    logic [127:0] key_down;
    logic [LIVE_SLOT_COUNT-1:0] live_valid;
    logic [(LIVE_SLOT_COUNT*7)-1:0] live_note_number;
    logic [(LIVE_SLOT_COUNT*Y_WIDTH)-1:0] live_y;
    logic [(LIVE_SLOT_COUNT*10)-1:0] live_velocity;
    logic live_desync_latched;
    logic [SCORE_SLOT_COUNT-1:0] score_slot_valid;
    logic [(SCORE_SLOT_COUNT*16)-1:0] score_slot_note_id;
    logic [(SCORE_SLOT_COUNT*7)-1:0] score_slot_note_number;
    logic [(SCORE_SLOT_COUNT*Y_WIDTH)-1:0] score_slot_y;
    logic [(SCORE_SLOT_COUNT*10)-1:0] score_slot_velocity;
    logic [SCORE_SLOT_COUNT-1:0] score_slot_hit;
    logic [SCORE_SLOT_COUNT-1:0] score_slot_miss;

    always_comb begin
        event_ready = video_rst_n;
        performance_fire = event_valid && event_ready;
    end

    always_ff @(posedge pixel_clk or negedge video_rst_n) begin
        if (!video_rst_n) begin
            mode_request <= 1'b0;
            display_mode <= 1'b0;
        end else begin
            if (mode_toggle_pulse) mode_request <= ~mode_request;
            if (frame_start) display_mode <= mode_request;
        end
    end

    visual_live_state #(
        .SLOT_COUNT(LIVE_SLOT_COUNT), .Y_WIDTH(Y_WIDTH),
        .JUDGE_Y(JUDGE_Y), .RISE_STEP(RISE_STEP)
    ) u_live_state (
        .clk(pixel_clk), .rst_n(video_rst_n), .frame_start(frame_start),
        .performance_fire(performance_fire), .performance_data(event_data),
        .video_desync(video_desync), .key_down(key_down),
        .live_valid(live_valid), .live_note_number(live_note_number),
        .live_y(live_y), .live_velocity(live_velocity),
        .desync_latched(live_desync_latched)
    );

    visual_score_tracker #(
        .SLOT_COUNT(SCORE_SLOT_COUNT), .FRAME_WIDTH(FRAME_WIDTH),
        .Y_WIDTH(Y_WIDTH), .PREVIEW_FRAMES(PREVIEW_FRAMES),
        .TRAVEL_Y(JUDGE_Y), .HIT_WINDOW_FRAMES(HIT_WINDOW_FRAMES)
    ) u_score_tracker (
        .clk(pixel_clk), .rst_n(video_rst_n), .frame_start(frame_start),
        .score_valid(score_valid), .score_ready(score_ready),
        .score_note_id(score_note_id), .score_note_number(score_note_number),
        .score_hit_frame(score_hit_frame),
        .score_duration_valid(score_duration_valid),
        .score_duration_frames(score_duration_frames),
        .score_velocity(score_velocity),
        .performance_fire(performance_fire), .performance_data(event_data),
        .video_desync(video_desync), .current_frame(current_frame),
        .slot_valid(score_slot_valid), .slot_note_id(score_slot_note_id),
        .slot_note_number(score_slot_note_number), .slot_y(score_slot_y),
        .slot_velocity(score_slot_velocity), .slot_hit(score_slot_hit),
        .slot_miss(score_slot_miss)
    );

    visual_scene_renderer #(
        .LIVE_SLOT_COUNT(LIVE_SLOT_COUNT),
        .SCORE_SLOT_COUNT(SCORE_SLOT_COUNT), .Y_WIDTH(Y_WIDTH),
        .SCREEN_WIDTH(SCREEN_WIDTH), .SCREEN_HEIGHT(SCREEN_HEIGHT),
        .JUDGE_Y(JUDGE_Y), .KEYBOARD_TOP(KEYBOARD_TOP),
        .BASE_NOTE(BASE_NOTE), .NOTE_COUNT(NOTE_COUNT)
    ) u_renderer (
        .data_enable(video_rst_n && data_enable),
        .pixel_x(pixel_x), .pixel_y(pixel_y), .display_mode(display_mode),
        .desync_latched(live_desync_latched), .key_down(key_down),
        .live_valid(live_valid), .live_note_number(live_note_number),
        .live_y(live_y), .live_velocity(live_velocity),
        .score_valid(score_slot_valid),
        .score_note_number(score_slot_note_number), .score_y(score_slot_y),
        .score_velocity(score_slot_velocity), .score_hit(score_slot_hit),
        .score_miss(score_slot_miss), .rgb_r(rgb_r), .rgb_g(rgb_g), .rgb_b(rgb_b)
    );

    // note_id is kept by the score tracker for same-note instances even though
    // the first renderer only needs pitch, position and judgement color.
    logic unused_score_note_id;
    assign unused_score_note_id = ^score_slot_note_id;
endmodule
