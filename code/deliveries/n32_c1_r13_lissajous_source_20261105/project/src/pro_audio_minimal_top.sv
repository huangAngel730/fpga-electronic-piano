// Pro C extension working copy. Not released for board programming.
// 50 MHz reference; original audio reset and PA conversion retained.
`ifndef M3_PRO_AUDIO_MINIMAL_TOP_R10_SV
`define M3_PRO_AUDIO_MINIMAL_TOP_R10_SV
`timescale 1ns / 1ps
module pro_audio_minimal_top #(
    parameter integer AUDIO_VOICES=32
) (
    input  wire       sys_clk_50m,
    input  wire       sys_rst_n,
    input  wire [1:0] key_n,
    input  wire       midi_rx,
    output wire       i2s_bclk,
    output wire       i2s_lrck,
    output wire       i2s_din,
    output wire       pa_en,
    output wire       uart_tx,
    input  wire       ble_uart_rx,
    output wire       ble_uart_tx,
    output wire       tmds_clk_p,
    output wire       tmds_clk_n,
    output wire [2:0] tmds_data_p,
    output wire [2:0] tmds_data_n
);
    wire legacy_pa_disable;
    wire core_clk, core_rst_n, pll_locked, pixel_clk, serial_clk, sample_tick;
    wire accepted_event_valid, accepted_event_ready;
    audio_defs_pkg::performance_event_t accepted_event_data;
    // Uploaded score events are a visual timeline only.  The scheduler still
    // receives an always-ready sink so its deadline/STOP/lease state machine
    // advances, but no score event is offered to the audio core.
    wire score_event_valid, score_event_ready, unused_score_audio_ready;
    audio_defs_pkg::performance_event_t score_event_data;
    audio_defs_pkg::performance_event_t score_audio_zero_data;
    assign score_event_ready = 1'b1;
    assign score_audio_zero_data = '0;
    wire rd_req, rd_valid, committed_valid, committed_bank, full_read_verified;
    wire [8:0] rd_index;
    wire [63:0] rd_event;
    wire [9:0] committed_count;
    wire [9:0] visual_committed_count;
    wire [31:0] committed_score_id, committed_generation;
    wire [31:0] visual_score_id, visual_generation;
    wire visual_bank;
    // R09: the same identity delay for the complete published identity bus;
    // no register/latency change, and transport keeps its original signals.
    wire [74:0] published_identity={committed_bank,committed_generation,committed_score_id,committed_count};
    (* syn_keep=1, syn_dont_touch=1 *) wire [74:0] visual_identity;
    genvar identity_bit;
    generate for(identity_bit=0;identity_bit<75;identity_bit=identity_bit+1)begin:g_score_identity_hold
        LUT1 #(.INIT(2'h2)) u_identity(.I0(published_identity[identity_bit]),.F(visual_identity[identity_bit]));
    end endgenerate
    assign {visual_bank,visual_generation,visual_score_id,visual_committed_count}=visual_identity;
    wire lease_busy, command_valid, command_ready, command_done;
    wire [1:0] command_kind;
    wire [7:0] command_error, transport_error;
    wire [31:0] visual_drop_count;
    wire desync_latched;
    wire [2:0] extension_page_select;
    wire signed [23:0] adopted_pcm_left,adopted_pcm_right;
    wire extension_async_rst_n = sys_rst_n && pll_locked;
    m3_pro_audio_core_r10 #(.SOURCE_MODE(0),.AUDIO_VOICES(AUDIO_VOICES)) u_audio (
        .sys_clk(sys_clk_50m),
        .sys_rst_n(sys_rst_n),
        .key_n(key_n),
        .midi_rx(midi_rx),
        .i2s_bclk(i2s_bclk),
        .i2s_lrck(i2s_lrck),
        .i2s_din(i2s_din),
        .pa_en(legacy_pa_disable),
        .uart_tx(uart_tx),
        .tmds_clk_p(),
        .tmds_clk_n(),
        .tmds_data_p(),
        .tmds_data_n(),
        .obs_core_clk(core_clk),
        .obs_rst_n(core_rst_n),
        .obs_frame_tick(sample_tick),
        .extension_pcm_left(adopted_pcm_left),.extension_pcm_right(adopted_pcm_right),
        .extension_page_select(extension_page_select),
        .obs_event_valid(accepted_event_valid),
        .obs_event_ready(accepted_event_ready),
        .obs_event_data(accepted_event_data),
        .obs_pll_locked(pll_locked),
        .score_event_valid(1'b0),
        .score_event_ready(unused_score_audio_ready),
        .score_event_data(score_audio_zero_data),
        .extension_pixel_clk(pixel_clk),
        .extension_serial_clk(serial_clk)
    );
    pro_score_transport u_score_transport (
        .clk(core_clk), .rst_n(core_rst_n),
        .uart_rx_i(ble_uart_rx), .uart_tx_o(ble_uart_tx),
        .rd_req(rd_req), .rd_index(rd_index), .rd_valid(rd_valid), .rd_event(rd_event),
        .committed_valid(committed_valid), .committed_count(committed_count),
        .committed_score_id(committed_score_id),
        .committed_generation(committed_generation), .committed_bank(committed_bank),
        .lease_busy(lease_busy), .command_valid(command_valid), .command_kind(command_kind),
        .command_ready(command_ready), .command_done(command_done),
        .command_error(command_error), .full_read_verified(full_read_verified),
        .last_error(transport_error)
    );
    pro_score_visual u_score_visual (
        .core_clk(core_clk), .pixel_clk(pixel_clk), .serial_clk(serial_clk),
        .rst_n(extension_async_rst_n), .sample_tick(sample_tick),
        .page_select(extension_page_select),.audio_frame_load(sample_tick),
        .play_left(adopted_pcm_left),.play_right(adopted_pcm_right),
        // This is the final audio consumer handshake, never merely a source
        // request. Visual FIFO drops/desync cannot backpressure this boundary.
        .accepted_valid(accepted_event_valid && accepted_event_ready),
        .accepted_data(accepted_event_data),
        .event_valid(score_event_valid), .event_ready(score_event_ready),
        .event_data(score_event_data),
        .command_valid(command_valid), .command_kind(command_kind),
        .command_ready(command_ready), .command_done(command_done),
        .command_error(command_error),
        .committed_valid(committed_valid), .committed_count(visual_committed_count),
        .committed_score_id(visual_score_id),
        .committed_generation(visual_generation), .committed_bank(visual_bank),
        .full_read_verified(full_read_verified),
        .rd_req(rd_req), .rd_index(rd_index), .rd_valid(rd_valid), .rd_event(rd_event),
        .lease_busy(lease_busy), .tmds_clk_p(tmds_clk_p), .tmds_clk_n(tmds_clk_n),
        .tmds_data_p(tmds_data_p), .tmds_data_n(tmds_data_n),
        .visual_drop_count(visual_drop_count), .desync_latched(desync_latched)
    );
    // Same existing conversion, exactly once: Pro XPT4809 high = enabled.
    // Core retains asynchronous reset/PLL-lock shutdown and sync release.
    assign pa_en = sys_rst_n && !legacy_pa_disable;
endmodule
`endif  // M3_PRO_AUDIO_MINIMAL_TOP_R10_SV
