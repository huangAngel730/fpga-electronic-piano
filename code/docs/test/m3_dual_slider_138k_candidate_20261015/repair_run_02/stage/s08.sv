// Isolated display-only integration. No audio ready, PCM, clocks or pin outputs.
// Shared asynchronous reset assertion is mandatory; release is local per domain.
`timescale 1ns/1ps
module dual_slider_candidate #(
    parameter integer SLOTS=8, Y_WIDTH=10, SCREEN_WIDTH=640,
    parameter integer SCREEN_HEIGHT=480, PREVIEW_FRAMES=120,
    parameter integer BASE_NOTE=36, NOTE_COUNT=49
) (
    input logic sys_clk, pixel_clk, rst_n,
    input logic accepted_valid,
    input audio_defs_pkg::performance_event_t accepted_data,
    input logic mode_valid,
    output wire mode_ready,
    input logic score_valid,
    output wire score_ready,
    input logic [15:0] score_note_id,
    input logic [6:0] score_note_number,
    input logic [31:0] score_hit_frame, score_duration_frames,
    input logic score_duration_valid,
    input logic [9:0] score_velocity,
    input logic frame_start, data_enable,
    input logic [15:0] pixel_x, pixel_y,
    output logic display_mode,
    output wire [31:0] current_frame,
    output wire [7:0] rgb_r, rgb_g, rgb_b,
    output wire [127:0] key_down,
    output wire [SLOTS-1:0] live_valid, live_held, falling_valid,
    output wire [SLOTS*Y_WIDTH-1:0] live_top, live_end, falling_top, falling_end,
    output wire [31:0] visual_drop_count, live_drop_count,
    output wire desync_latched,
    output wire mode_delivered,
    output wire sys_reset_done, video_reset_done
);
    wire event_src_done,event_dst_done,control_src_done,control_dst_done;
    wire video_event_valid,video_event_ready,video_desync,mode_pulse;
    audio_defs_pkg::performance_event_t video_event;
    wire [15:0] queue_level,queue_high;
    wire drop_pulse,video_score_valid,video_score_ready;
    wire [15:0] video_score_id;
    wire [6:0] video_score_note;
    wire [31:0] video_hit_frame,video_duration;
    wire video_duration_valid;
    wire [9:0] video_velocity;
    wire [SLOTS*7-1:0] live_note,falling_note;
    wire [SLOTS*10-1:0] live_velocity,falling_velocity;
    wire [SLOTS*Y_WIDTH-1:0] falling_distance;
    wire [SLOTS*16-1:0] falling_id;
    wire [SLOTS-1:0] falling_hit,falling_miss;
    wire hit_pulse;
    wire [6:0] hit_note;
    logic mode_request;
    assign sys_reset_done=event_src_done && control_src_done;
    assign video_reset_done=event_dst_done && control_dst_done;
    // Display-only event copy cannot backpressure the audio event consumer.
    visual_event_bridge #(.DEPTH(8)) u_events(
        .sys_clk(sys_clk),.video_clk(pixel_clk),.rst_n(rst_n),
        .accepted_valid(accepted_valid),.accepted_data(accepted_data),
        .visual_queue_level(queue_level),.visual_queue_high_watermark(queue_high),
        .visual_drop_count(visual_drop_count),.visual_drop_pulse(drop_pulse),
        .sys_reset_done(event_src_done),.video_reset_done(event_dst_done),
        .video_valid(video_event_valid),.video_desync(video_desync),
        .video_ready(video_event_ready),.video_data(video_event));
    visual_control_bridge u_control(
        .sys_clk(sys_clk),.pixel_clk(pixel_clk),.rst_n(rst_n),
        .src_mode_valid(mode_valid),.src_mode_ready(mode_ready),
        .video_mode_toggle_pulse(mode_pulse),
        .src_score_valid(score_valid),.src_score_ready(score_ready),
        .src_score_note_id(score_note_id),.src_score_note_number(score_note_number),
        .src_score_hit_frame(score_hit_frame),.src_score_duration_valid(score_duration_valid),
        .src_score_duration_frames(score_duration_frames),.src_score_velocity(score_velocity),
        .video_score_valid(video_score_valid),.video_score_ready(video_score_ready),
        .video_score_note_id(video_score_id),.video_score_note_number(video_score_note),
        .video_score_hit_frame(video_hit_frame),.video_score_duration_valid(video_duration_valid),
        .video_score_duration_frames(video_duration),.video_score_velocity(video_velocity),
        .sys_reset_done(control_src_done),.video_reset_done(control_dst_done));
    // Mode is requested through a reliable mailbox, then committed at a frame.
    assign mode_delivered=mode_pulse;
    always_ff @(posedge pixel_clk or negedge video_reset_done) begin
        if(!video_reset_done) begin mode_request<=0;display_mode<=0;end
        else begin
            if(mode_pulse) mode_request<=~mode_request;
            if(frame_start) display_mode<=mode_request;
        end
    end
    assign video_event_ready=video_reset_done;
    visual_live_state #(.SLOT_COUNT(SLOTS),.Y_WIDTH(Y_WIDTH),
        .JUDGE_Y(SCREEN_HEIGHT-10),.RISE_STEP(4)) u_live(
        .clk(pixel_clk),.rst_n(video_reset_done),.frame_start(frame_start),
        .performance_fire(video_event_valid && video_event_ready),
        .performance_data(video_event),.video_desync(video_desync),
        .key_down(key_down),.live_valid(live_valid),.live_note_number(live_note),
        .live_y(live_top),.live_end_y(live_end),.live_held(live_held),
        .live_velocity(live_velocity),.visual_slot_drop_count(live_drop_count),
        .desync_latched(desync_latched));
    visual_score_tracker #(.SLOT_COUNT(SLOTS),.FRAME_WIDTH(32),.Y_WIDTH(Y_WIDTH),
        .PREVIEW_FRAMES(PREVIEW_FRAMES),.TRAVEL_Y(SCREEN_HEIGHT),
        .HIT_WINDOW_FRAMES(6),.BOTTOM_EXIT_GEOMETRY(1'b1),
        .STRICT_CONTACT(1'b1),.RASTER_HEIGHT(SCREEN_HEIGHT)) u_falling(
        .clk(pixel_clk),.rst_n(video_reset_done),.frame_start(frame_start),
        .score_valid(video_score_valid),.score_ready(video_score_ready),
        .score_note_id(video_score_id),.score_note_number(video_score_note),
        .score_hit_frame(video_hit_frame),.score_duration_valid(video_duration_valid),
        .score_duration_frames(video_duration),.score_velocity(video_velocity),
        .performance_fire(video_event_valid && video_event_ready),
        .match_enabled(display_mode),.performance_data(video_event),
        .video_desync(video_desync),.current_frame(current_frame),
        .slot_valid(falling_valid),.slot_note_id(falling_id),.slot_note_number(falling_note),
        .slot_y(falling_distance),.slot_top_y(falling_top),.slot_end_y(falling_end),
        .slot_velocity(falling_velocity),.slot_hit(falling_hit),.slot_miss(falling_miss),
        .hit_pulse(hit_pulse),.hit_note_number(hit_note));
    // The original hit-flash FAIL is deferred, not repaired or claimed PASS.
    // This minimal candidate intentionally disables flash rendering.
    visual_scene_renderer #(.LIVE_SLOT_COUNT(SLOTS),.SCORE_SLOT_COUNT(SLOTS),
        .Y_WIDTH(Y_WIDTH),.SCREEN_WIDTH(SCREEN_WIDTH),.SCREEN_HEIGHT(SCREEN_HEIGHT),
        // Legacy renderer parameters are range-checked although drawing uses
        // SCREEN_HEIGHT-1 directly. Keep both placeholders strictly in range.
        .JUDGE_Y(SCREEN_HEIGHT-2),.KEYBOARD_TOP(SCREEN_HEIGHT-1),
        .BASE_NOTE(BASE_NOTE),.NOTE_COUNT(NOTE_COUNT)) u_renderer(
        .data_enable(video_reset_done && data_enable),.pixel_x(pixel_x),.pixel_y(pixel_y),
        .display_mode(display_mode),.desync_latched(desync_latched),.key_down(key_down),
        .flash_active(128'd0),.flash_level(256'd0),
        .live_valid(live_valid),.live_note_number(live_note),.live_y(live_top),
        .live_end_y(live_end),.live_velocity(live_velocity),
        .score_valid(falling_valid),.score_note_number(falling_note),.score_y(falling_distance),
        .score_top_y(falling_top),.score_end_y(falling_end),.score_velocity(falling_velocity),
        .score_hit(falling_hit),.score_miss(falling_miss),
        .rgb_r(rgb_r),.rgb_g(rgb_g),.rgb_b(rgb_b));
endmodule
