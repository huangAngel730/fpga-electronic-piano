// M2 display companion for a frozen V1+CC64 audio diagnostic copy.
// Audio-accepted events are copied without backpressure. Diagnostic score and
// automatic mode alternation are not a final UI or downloaded song.
`timescale 1ns/1ps
module audio_visual_display_probe #(
    parameter integer SYS_CLK_HZ = 40_000_000,
    parameter integer MODE_PERIOD_CYCLES = SYS_CLK_HZ * 5,
    parameter integer VIDEO_FRAME_SYS_CYCLES = (SYS_CLK_HZ / 25_000) * 420,
    parameter integer DIAG_SCORE_SPACING_FRAMES = 30
) (
    input logic sys_clk,sys_rst_n,
    input wire ref_clk,
    input wire wave_audio_rst_n, wave_frame_load,
    input wire signed [23:0] wave_play_left, wave_play_right,
    output wire core_clk,
    input logic accepted_valid,
    input audio_defs_pkg::performance_event_t accepted_data,
    output wire tmds_clk_p,tmds_clk_n,
    output wire [2:0] tmds_data_p,tmds_data_n,
    output wire visual_pll_locked
);
    import audio_defs_pkg::*;
    wire serial_clk,pixel_clk,pll_lock,serial_rst_n;
    wire visual_rst_n = sys_rst_n && pll_lock;
    wire sys_reset_done,video_reset_done;
    wire [15:0] pixel_x,pixel_y;
    wire hs,vs,de,frame_start,line_start;
    wire video_valid,video_desync,video_ready;
    wire [15:0] queue_level,queue_peak;
    wire [31:0] drop_count;
    wire drop_pulse,score_ready,display_mode;
    wire control_sys_done,control_video_done;
    wire src_score_ready,src_mode_ready;
    wire video_score_valid,video_mode_pulse;
    wire [15:0] video_score_note_id;
    wire [6:0] video_score_note_number;
    wire [31:0] video_score_hit_frame,video_score_duration_frames;
    wire video_score_duration_valid;
    wire [9:0] video_score_velocity;
    logic [15:0] score_seq;
    logic mode_pending, score_pending;
    logic [31:0] diag_frame,diag_frame_cycles,score_due_frame,diag_hit_frame;
    wire [31:0] current_frame;
    wire [7:0] rgb_r,rgb_g,rgb_b;
    performance_event_t video_data;
    logic [31:0] sys_count;
    always_ff @(posedge sys_clk or negedge visual_rst_n) begin
        if (!visual_rst_n) begin
            sys_count <= 0; score_seq <= 0; mode_pending <= 0;
            score_pending<=0;diag_frame<=0;diag_frame_cycles<=0;score_due_frame<=0;diag_hit_frame<=120;
        end else begin
            if (sys_count == MODE_PERIOD_CYCLES-1) begin
                sys_count <= 0;
                mode_pending <= 1;
            end else sys_count <= sys_count + 1'b1;
            // 800*525 pixels at25MHz =16.8ms, i.e.672000 cycles at40MHz.
            // Preserve wall-clock frame time; no pixel bus CDC read.
            // Frame-reset release differs by a few cycles (<one frame).
            if(diag_frame_cycles==VIDEO_FRAME_SYS_CYCLES-1)begin
                diag_frame_cycles<=0;diag_frame<=diag_frame+1'b1;
            end else diag_frame_cycles<=diag_frame_cycles+1'b1;
            if(!score_pending && control_sys_done && diag_frame>=score_due_frame)begin
                score_pending<=1;diag_hit_frame<=diag_frame+32'd120;
            end
            if(score_pending && src_score_ready && control_sys_done)begin
                score_pending<=0;score_seq<=score_seq+1'b1;
                score_due_frame<=diag_frame+DIAG_SCORE_SPACING_FRAMES;
            end
            if (mode_pending && src_mode_ready) mode_pending <= 0;
        end
    end
    TMDS_PLL u_video_pll(.clkin(ref_clk),.lock(pll_lock),.clkout0(serial_clk),
        .clkout1(pixel_clk),.clkout2(core_clk));
    reset_sync u_serial_reset(.clk(serial_clk),.rst_n(visual_rst_n),.rst_sync_n(serial_rst_n));
    visual_event_bridge #(.DEPTH(32)) u_event_bridge(
        .sys_clk(sys_clk),.video_clk(pixel_clk),.rst_n(visual_rst_n),
        .accepted_valid(accepted_valid),.accepted_data(accepted_data),
        .visual_queue_level(queue_level),.visual_queue_high_watermark(queue_peak),
        .visual_drop_count(drop_count),.visual_drop_pulse(drop_pulse),
        .sys_reset_done(sys_reset_done),.video_reset_done(video_reset_done),
        .video_valid(video_valid),.video_desync(video_desync),
        .video_ready(video_ready),.video_data(video_data));
    visual_control_bridge u_control (
        .sys_clk(sys_clk), .pixel_clk(pixel_clk), .rst_n(visual_rst_n),
        .src_mode_valid(mode_pending), .src_mode_ready(src_mode_ready),
        .video_mode_toggle_pulse(video_mode_pulse),
        .src_score_valid(score_pending && control_sys_done), .src_score_ready(src_score_ready),
        .src_score_note_id(score_seq),
        .src_score_note_number(7'd60+{4'd0,score_seq[2:0]}),
        .src_score_hit_frame(diag_hit_frame),
        .src_score_duration_valid(score_seq[0]),
        .src_score_duration_frames(32'd30), .src_score_velocity(10'd600),
        .video_score_valid(video_score_valid), .video_score_ready(score_ready),
        .video_score_note_id(video_score_note_id),
        .video_score_note_number(video_score_note_number),
        .video_score_hit_frame(video_score_hit_frame),
        .video_score_duration_valid(video_score_duration_valid),
        .video_score_duration_frames(video_score_duration_frames),
        .video_score_velocity(video_score_velocity),
        .sys_reset_done(control_sys_done), .video_reset_done(control_video_done)
    );
    video_scan_timing u_scan(.pixel_clk(pixel_clk),.rst_n(video_reset_done && control_video_done),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.data_enable(de),
        .hsync(hs),.vsync(vs),.frame_start(frame_start),.line_start(line_start));
    m3_visualizer u_scene(
        .pixel_clk(pixel_clk),.video_rst_n(video_reset_done && control_video_done),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.data_enable(de),
        .frame_start(frame_start),.event_valid(video_valid),
        .event_data(video_data),.event_ready(video_ready),
        .video_desync(video_desync),
        .mode_toggle_pulse(video_mode_pulse),
        .score_valid(video_score_valid), .score_ready(score_ready),
        .score_note_id(video_score_note_id),
        .score_note_number(video_score_note_number),
        .score_hit_frame(video_score_hit_frame),
        .score_duration_valid(video_score_duration_valid),
        .score_duration_frames(video_score_duration_frames),
        .score_velocity(video_score_velocity),
        .display_mode(display_mode),.current_frame(current_frame),
        .rgb_r(rgb_r),.rgb_g(rgb_g),.rgb_b(rgb_b));
    // Added observation branch is never a producer/consumer of audio ready.
    wire waveform_rst_n, wave_restart, wave_sample_valid;
    wire [31:0] wave_sample_seq;
    wire signed [23:0] wave_sample_left, wave_sample_right;
    wire waveform_mask, waveform_trace_valid;
    wire [7:0] waveform_r, waveform_g, waveform_b;
    wire [31:0] waveform_gap_count, waveform_window_drop_count;
    pcm_waveform_observer_bridge u_wave_bridge (
        .audio_clk(sys_clk), .pixel_clk(pixel_clk),
        .audio_rst_n(wave_audio_rst_n),
        .display_rst_n(visual_rst_n && video_reset_done && control_video_done),
        .audio_frame_load(wave_frame_load),
        .audio_play_left(wave_play_left), .audio_play_right(wave_play_right),
        .waveform_rst_n(waveform_rst_n), .stream_restart(wave_restart),
        .sample_valid(wave_sample_valid), .sample_seq(wave_sample_seq),
        .sample_left(wave_sample_left), .sample_right(wave_sample_right),
        .observed_valid(), .observed_seq(), .observed_left(), .observed_right(),
        .observation_enqueued(), .observation_dropped(), .observation_queue_level(),
        .observation_drop_count(), .source_reset_done(), .pixel_reset_done()
    );
    pcm_waveform_candidate u_waveform (
        .pixel_clk(pixel_clk), .pixel_rst_n(waveform_rst_n),
        .sample_valid(wave_sample_valid), .sample_seq(wave_sample_seq),
        .sample_left(wave_sample_left), .sample_right(wave_sample_right),
        .stream_restart(wave_restart), .pixel_x(pixel_x), .pixel_y(pixel_y),
        .data_enable(de), .frame_start(frame_start), .waveform_enable(1'b1),
        .waveform_mask(waveform_mask), .waveform_r(waveform_r),
        .waveform_g(waveform_g), .waveform_b(waveform_b),
        .trace_valid(waveform_trace_valid), .display_gap_count(waveform_gap_count),
        .window_drop_count(waveform_window_drop_count)
    );
    // N-edge sample -> N+2 output. Match all three sampled register stages to the
    // waveform's fixed two-cycle pipeline, before the original DVI register.
    logic hs_d0, hs_d1, hs_d2, vs_d0, vs_d1, vs_d2, de_d0, de_d1, de_d2;
    logic [23:0] scene_d0, scene_d1, scene_d2;
    logic dvi_hs,dvi_vs,dvi_de;
    logic [7:0] dvi_r,dvi_g,dvi_b;
    always_ff @(posedge pixel_clk or negedge video_reset_done) begin
        if(!video_reset_done) begin
            hs_d0<=1'b1; hs_d1<=1'b1; hs_d2<=1'b1; vs_d0<=1'b1; vs_d1<=1'b1; vs_d2<=1'b1;
            de_d0<=1'b0; de_d1<=1'b0; de_d2<=1'b0; scene_d0<='0; scene_d1<='0; scene_d2<='0;
            dvi_hs<=1'b1; dvi_vs<=1'b1; dvi_de<=1'b0;
            dvi_r<='0; dvi_g<='0; dvi_b<='0;
        end else begin
            hs_d0<=hs; hs_d1<=hs_d0; hs_d2<=hs_d1; vs_d0<=vs; vs_d1<=vs_d0; vs_d2<=vs_d1;
            de_d0<=de; de_d1<=de_d0; de_d2<=de_d1;
            scene_d0<={rgb_r,rgb_g,rgb_b}; scene_d1<=scene_d0; scene_d2<=scene_d1;
            // Both RHS values correspond to the same N-3 raster input.
            dvi_hs<=hs_d2; dvi_vs<=vs_d2; dvi_de<=de_d2;
            if(waveform_mask) begin
                dvi_r<=waveform_r; dvi_g<=waveform_g; dvi_b<=waveform_b;
            end else begin
                {dvi_r,dvi_g,dvi_b}<=scene_d2;
            end
        end
    end
    DVI_TX_Top u_video_tx(.I_rst_n(serial_rst_n),.I_serial_clk(serial_clk),
        .I_rgb_clk(pixel_clk),.I_rgb_vs(dvi_vs),.I_rgb_hs(dvi_hs),.I_rgb_de(dvi_de),
        .I_rgb_r(dvi_r),.I_rgb_g(dvi_g),.I_rgb_b(dvi_b),
        .O_tmds_clk_p(tmds_clk_p),.O_tmds_clk_n(tmds_clk_n),
        .O_tmds_data_p(tmds_data_p),.O_tmds_data_n(tmds_data_n));
    assign visual_pll_locked=pll_lock;
endmodule
