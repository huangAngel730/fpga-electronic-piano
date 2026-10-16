`timescale 1ns/1ps
// L0 candidate wiring only: frozen real M1 frame core -> frozen PT8211 TX.
// Does NOT replace the frozen R05 TB, MIDI parser/board top, clock PLL or STA.
// Caller supplies already synchronized 40 MHz clk/rst_n and 64-bit events.
module m3_r05_observed_frame_candidate #(
    parameter TRACE_FILE="r05_public.jsonl"
)(
    input wire clk, rst_n,
    input wire event_valid,
    output wire event_ready,
    input wire [63:0] event_data,
    input wire config_valid,
    output wire config_ready,
    input wire config_enable,
    input wire [15:0] config_delay_samples,
    input wire [14:0] config_dry_gain, config_wet_gain, config_feedback,
    output wire i2s_bclk, i2s_ws, i2s_din,
    output wire request_accept, commit_pulse,
    output wire [31:0] request_id, committed_id,
    output wire signed [23:0] committed_left, committed_right,
    output wire committed_clip
);
    wire frame_tick, pending_valid, i2s_ready;
    wire signed [23:0] play_left,play_right;
    wire [31:0] active_voice_count,clip_count,audio_underrun;
    wire [31:0] audio_frame_count,pcm_request_count,pcm_commit_count,max_processing_cycles;
    m2_fourvoice_timbre_delay_frame_core core(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),
        .event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .config_valid(config_valid),.config_ready(config_ready),
        .config_enable(config_enable),.config_delay_samples(config_delay_samples),
        .config_dry_gain(config_dry_gain),.config_wet_gain(config_wet_gain),
        .config_feedback(config_feedback),.play_left(play_left),.play_right(play_right),
        .pending_valid(pending_valid),.commit_pulse(commit_pulse),
        .active_voice_count(active_voice_count),.clip_count(clip_count),
        .audio_underrun(audio_underrun),.audio_frame_count(audio_frame_count),
        .pcm_request_count(pcm_request_count),.pcm_commit_count(pcm_commit_count),
        .max_processing_cycles(max_processing_cycles),
        .request_accept(request_accept),.request_id(request_id),.committed_id(committed_id),
        .committed_left(committed_left),.committed_right(committed_right),
        .committed_clip(committed_clip)
    );
    i2s_tx #(.ACC_BITS(32),.BCLK_PHASE_STEP(32'd659706977),
             .PCM_WIDTH(24),.DAC_WIDTH(16)) serial_tx(
        .clk(clk),.rst_n(rst_n),.valid(1'b1),
        .pcm_left(play_left),.pcm_right(play_right),
        .bclk(i2s_bclk),.lrck(i2s_ws),.din(i2s_din),
        .ready(i2s_ready),.frame_tick(frame_tick)
    );
    m3_r05_public_observer #(.TRACE_FILE(TRACE_FILE)) observer(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),
        .request_accept(request_accept),.request_id(request_id),.commit_pulse(commit_pulse),
        .committed_id(committed_id),.committed_left(committed_left),.committed_right(committed_right),
        .committed_clip(committed_clip),.pending_valid(pending_valid),
        .play_left(play_left),.play_right(play_right),.clip_count(clip_count),
        .audio_underrun(audio_underrun),.i2s_bclk(i2s_bclk),.i2s_ws(i2s_ws),.i2s_din(i2s_din)
    );
endmodule
