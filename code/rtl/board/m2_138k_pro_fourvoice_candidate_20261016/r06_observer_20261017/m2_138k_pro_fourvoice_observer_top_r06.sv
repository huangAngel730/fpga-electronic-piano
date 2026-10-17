// R06 simulation observation surface. No package pins or physical admission.
// Capture obs_* at posedge obs_core_clk PRE_NBA and require obs_polyphonic_valid.
// Isolated Tang Mega 138K Pro board wrapper.
//
// This wrapper preserves the frozen four-voice candidate, including its
// 50 MHz -> 40/25/125 MHz PLL plan. It only adapts board-facing reset/key
// names and converts the legacy active-low amplifier enable into the Pro
// dock's active-high PA_EN convention.
//
// Reset assertion is asynchronous at the board boundary. The wrapped design
// still owns synchronized release and PLL-lock loss handling. PA_EN is forced
// low immediately while the external reset is asserted and remains low while
// the wrapped design reports its legacy amplifier-disable level.
module m2_138k_pro_fourvoice_observer_top_r06 (
    input  logic       sys_clk_50m,
    input  logic       sys_rst_n,
    input  logic [1:0] key_n,
    input  logic       midi_rx,
    output logic       i2s_bclk,
    output logic       i2s_lrck,
    output logic       i2s_din,
    output logic       pa_en,
    output logic       uart_tx,
    output wire        tmds_clk_p,
    output wire        tmds_clk_n,
    output wire [2:0]  tmds_data_p,
    output wire [2:0]  tmds_data_n,
    output wire obs_core_clk,
    output wire obs_polyphonic_valid,
    output wire obs_rst_n,
    output wire obs_frame_tick,
    output wire obs_event_valid,
    output wire obs_event_ready,
    output wire [63:0] obs_event_data,
    output wire obs_req_valid,
    output wire obs_req_ready,
    output wire obs_result_valid,
    output wire obs_result_ready,
    output wire [31:0] obs_result_id,
    output wire signed [23:0] obs_result_left,
    output wire signed [23:0] obs_result_right,
    output wire [1:0] obs_result_clip_mask,
    output wire [31:0] obs_req_id,
    output wire obs_commit,
    output wire [31:0] obs_commit_id,
    output wire signed [23:0] obs_commit_left,
    output wire signed [23:0] obs_commit_right,
    output wire obs_commit_clip,
    output wire obs_cancel,
    output wire obs_config_valid,
    output wire obs_config_ready,
    output wire signed [23:0] obs_tx_left,
    output wire signed [23:0] obs_tx_right,
    output wire obs_pll_locked,
    output wire obs_tx_sample_valid,
    output wire obs_tx_metadata_valid,
    output wire obs_tx_req_id_valid,
    output wire [31:0] obs_tx_frame_id,
    output wire [31:0] obs_tx_req_id,
    output wire [1:0] obs_tx_clip_mask,
    output wire obs_tx_clip_any,
    output wire obs_tx_hold,
    output wire obs_tx_startup_zero,
    output wire obs_metadata_error,
    output wire obs_frame_id_overflow
);
    logic legacy_pa_disable;

    // Explicit SOURCE_MODE=0 prevents fixed-tone input from posing as four voices.
    m2_fourvoice_timbre_delay_board_top_r06 #(.SOURCE_MODE(0)) u_legacy (
        .sys_clk(sys_clk_50m),
        .sys_rst_n(sys_rst_n),
        .key_n(key_n),
        .midi_rx(midi_rx),
        .i2s_bclk(i2s_bclk),
        .i2s_lrck(i2s_lrck),
        .i2s_din(i2s_din),
        .pa_en(legacy_pa_disable),
        .uart_tx(uart_tx),
        .tmds_clk_p(tmds_clk_p),
        .tmds_clk_n(tmds_clk_n),
        .tmds_data_p(tmds_data_p),
        .tmds_data_n(tmds_data_n),
        .obs_core_clk(obs_core_clk),
        .obs_polyphonic_valid(obs_polyphonic_valid),
        .obs_rst_n(obs_rst_n),
        .obs_frame_tick(obs_frame_tick),
        .obs_event_valid(obs_event_valid),
        .obs_event_ready(obs_event_ready),
        .obs_event_data(obs_event_data),
        .obs_req_valid(obs_req_valid),
        .obs_req_ready(obs_req_ready),
        .obs_result_valid(obs_result_valid),
        .obs_result_ready(obs_result_ready),
        .obs_result_id(obs_result_id),
        .obs_result_left(obs_result_left),
        .obs_result_right(obs_result_right),
        .obs_result_clip_mask(obs_result_clip_mask),
        .obs_req_id(obs_req_id),
        .obs_commit(obs_commit),
        .obs_commit_id(obs_commit_id),
        .obs_commit_left(obs_commit_left),
        .obs_commit_right(obs_commit_right),
        .obs_commit_clip(obs_commit_clip),
        .obs_cancel(obs_cancel),
        .obs_config_valid(obs_config_valid),
        .obs_config_ready(obs_config_ready),
        .obs_tx_left(obs_tx_left),
        .obs_tx_right(obs_tx_right),
        .obs_pll_locked(obs_pll_locked),
        .obs_tx_sample_valid(obs_tx_sample_valid),
        .obs_tx_metadata_valid(obs_tx_metadata_valid),
        .obs_tx_req_id_valid(obs_tx_req_id_valid),
        .obs_tx_frame_id(obs_tx_frame_id),
        .obs_tx_req_id(obs_tx_req_id),
        .obs_tx_clip_mask(obs_tx_clip_mask),
        .obs_tx_clip_any(obs_tx_clip_any),
        .obs_tx_hold(obs_tx_hold),
        .obs_tx_startup_zero(obs_tx_startup_zero),
        .obs_metadata_error(obs_metadata_error),
        .obs_frame_id_overflow(obs_frame_id_overflow)
    );

    // Pro Dock XPT4809: high = enabled, low = shutdown.
    // legacy_pa_disable: high = disabled, low = enabled.
    assign pa_en = sys_rst_n && !legacy_pa_disable;
endmodule
