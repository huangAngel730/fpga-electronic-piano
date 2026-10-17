// Isolated E2 wiring candidate, not a production top or a physical CDC proof.
// Audio 40 MHz, pixel 25 MHz; active-low reset, async assert/local sync release.
// Display reset flushes observation only. Audio has no ready/backpressure port.
`timescale 1ns/1ps
module m3_pro_fixed_left_waveform (
    input wire audio_clk, pixel_clk, audio_rst_n, display_rst_n,
    input wire audio_frame_load,
    input wire signed [23:0] audio_play_left, audio_play_right,
    input wire [15:0] pixel_x, pixel_y,
    input wire data_enable, frame_start, waveform_enable,
    output wire waveform_mask,
    output wire [7:0] waveform_r, waveform_g, waveform_b,
    output wire trace_valid,
    output wire [31:0] display_gap_count, window_drop_count,
    output wire waveform_rst_n, stream_restart, sample_valid,
    output wire [31:0] sample_seq,
    output wire signed [23:0] sample_left, sample_right,
    output wire observed_valid,
    output wire [31:0] observed_seq,
    output wire signed [23:0] observed_left, observed_right,
    output wire observation_enqueued, observation_dropped,
    output wire [15:0] observation_queue_level,
    output wire [31:0] observation_drop_count,
    output wire source_reset_done, pixel_reset_done
);
    pcm_waveform_observer_bridge #(.DEPTH(32)) u_bridge (
        .audio_clk(audio_clk), .pixel_clk(pixel_clk),
        .audio_rst_n(audio_rst_n), .display_rst_n(display_rst_n),
        .audio_frame_load(audio_frame_load),
        .audio_play_left(audio_play_left), .audio_play_right(audio_play_right),
        .waveform_rst_n(waveform_rst_n), .stream_restart(stream_restart),
        .sample_valid(sample_valid), .sample_seq(sample_seq),
        .sample_left(sample_left), .sample_right(sample_right),
        .observed_valid(observed_valid), .observed_seq(observed_seq),
        .observed_left(observed_left), .observed_right(observed_right),
        .observation_enqueued(observation_enqueued),
        .observation_dropped(observation_dropped),
        .observation_queue_level(observation_queue_level),
        .observation_drop_count(observation_drop_count),
        .source_reset_done(source_reset_done), .pixel_reset_done(pixel_reset_done)
    );
    // Named connections allow black-box fault injection in the isolated TB.
    // These aliases are unconditionally straight connections in this source.
    wire render_valid = sample_valid;
    wire [31:0] render_seq = sample_seq;
    wire signed [23:0] render_left = sample_left;
    wire signed [23:0] render_right = sample_right;
    wire render_frame_start = frame_start;
    wire render_rst_n = waveform_rst_n;
    pcm_waveform_candidate u_waveform (
        .pixel_clk(pixel_clk), .pixel_rst_n(render_rst_n),
        .sample_valid(render_valid), .sample_seq(render_seq),
        .sample_left(render_left), .sample_right(render_right),
        .stream_restart(stream_restart), .pixel_x(pixel_x), .pixel_y(pixel_y),
        .data_enable(data_enable), .frame_start(render_frame_start),
        .waveform_enable(waveform_enable), .waveform_mask(waveform_mask),
        .waveform_r(waveform_r), .waveform_g(waveform_g), .waveform_b(waveform_b),
        .trace_valid(trace_valid), .display_gap_count(display_gap_count),
        .window_drop_count(window_drop_count)
    );
endmodule
