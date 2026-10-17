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
module m2_138k_pro_fourvoice_candidate_top (
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
    output wire [2:0]  tmds_data_n
);
    logic legacy_pa_disable;

    m2_fourvoice_timbre_delay_board_top u_legacy (
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
        .tmds_data_n(tmds_data_n)
    );

    // Pro Dock XPT4809: high = enabled, low = shutdown.
    // legacy_pa_disable: high = disabled, low = enabled.
    assign pa_en = sys_rst_n && !legacy_pa_disable;
endmodule
