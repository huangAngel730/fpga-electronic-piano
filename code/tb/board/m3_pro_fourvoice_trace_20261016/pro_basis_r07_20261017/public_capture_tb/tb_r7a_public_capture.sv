`timescale 1ns/1ps
// Source-only integration TB. Execution requires separate M2 admission.
module tb_r7a_public_capture #(
    parameter string CAPTURE_ID="",
    parameter string PLAN_STOP_ID="",
    parameter string BYTE_PLAN="bytes.drv", RESET_PLAN="reset.drv", READY_PLAN="ready.drv",
    parameter longint STOP_DRIVER_CYCLE=0,
    parameter longint EXPECTED_FINISH_CORE_CYCLE=-1,
    parameter longint MAX_CORE_SAMPLES=0,
    parameter longint MAX_SIM_TIME_PS=0
);
    logic sys_clk_50m=0, driver_clk_40m=0, finish_requested=0;
    wire sys_rst_n, midi_rx, driver_ready_not_connected, capture_done;
    wire obs_core_clk;
    wire obs_polyphonic_valid;
    wire obs_rst_n;
    wire obs_frame_tick;
    wire obs_event_valid;
    wire obs_event_ready;
    wire [63:0] obs_event_data;
    wire obs_req_valid;
    wire obs_req_ready;
    wire obs_result_valid;
    wire obs_result_ready;
    wire [31:0] obs_result_id;
    wire signed [23:0] obs_result_left;
    wire signed [23:0] obs_result_right;
    wire [1:0] obs_result_clip_mask;
    wire [31:0] obs_req_id;
    wire obs_commit;
    wire [31:0] obs_commit_id;
    wire signed [23:0] obs_commit_left;
    wire signed [23:0] obs_commit_right;
    wire obs_commit_clip;
    wire obs_cancel;
    wire obs_config_valid;
    wire obs_config_ready;
    wire signed [23:0] obs_tx_left;
    wire signed [23:0] obs_tx_right;
    wire obs_pll_locked;
    wire obs_tx_sample_valid;
    wire obs_tx_metadata_valid;
    wire obs_tx_req_id_valid;
    wire [31:0] obs_tx_frame_id;
    wire [31:0] obs_tx_req_id;
    wire [1:0] obs_tx_clip_mask;
    wire obs_tx_clip_any;
    wire obs_tx_hold;
    wire obs_tx_startup_zero;
    wire obs_metadata_error;
    wire obs_frame_id_overflow;
    wire i2s_bclk;
    wire i2s_lrck;
    wire i2s_din;
    wire pa_en;
    wire uart_tx;
    always #10 sys_clk_50m=~sys_clk_50m;
    // R6-2 plan uses this independent external stimulus timebase. Observed
    // core cycles remain the actual obs_core_clk count, not driver cycles.
    always #12.5 driver_clk_40m=~driver_clk_40m;

    midi_public_port_driver #(.CLK_HZ(40_000_000),.MIDI_BAUD(31_250),
        .BYTE_PLAN(BYTE_PLAN),.RESET_PLAN(RESET_PLAN),.READY_PLAN(READY_PLAN),
        .EVENT_LOG("driver_aux_not_authoritative.log")) u_driver (
        .clk(driver_clk_40m),.sys_rst_n(sys_rst_n),.midi_rx(midi_rx),
        .event_ready(driver_ready_not_connected),
        .event_valid(obs_event_valid && obs_event_ready),.event_data(obs_event_data));

    m2_138k_pro_fourvoice_observer_top_r06 dut (
        .sys_clk_50m(sys_clk_50m),.sys_rst_n(sys_rst_n),.key_n(2'b11),.midi_rx(midi_rx),
        .i2s_bclk(i2s_bclk),.i2s_lrck(i2s_lrck),.i2s_din(i2s_din),.pa_en(pa_en),.uart_tx(uart_tx),
        .tmds_clk_p(),.tmds_clk_n(),.tmds_data_p(),.tmds_data_n(),
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
        .obs_frame_id_overflow(obs_frame_id_overflow));

    r7a_public_observer #(.CAPTURE_ID(CAPTURE_ID),.PLAN_STOP_ID(PLAN_STOP_ID),
        .EXPECTED_FINISH_CORE_CYCLE(EXPECTED_FINISH_CORE_CYCLE),.MAX_CORE_SAMPLES(MAX_CORE_SAMPLES)) u_capture (
        .sys_rst_n(sys_rst_n),.finish_requested(finish_requested),.capture_done(capture_done),
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
        .obs_frame_id_overflow(obs_frame_id_overflow),
        .i2s_bclk(i2s_bclk),
        .i2s_lrck(i2s_lrck),
        .i2s_din(i2s_din),
        .pa_en(pa_en),
        .uart_tx(uart_tx));

    initial begin
        if (STOP_DRIVER_CYCLE<=0 || MAX_SIM_TIME_PS<=0) $fatal(1,"FROZEN_STOP_AND_WATCHDOG_REQUIRED");
        repeat (STOP_DRIVER_CYCLE) @(posedge driver_clk_40m);
        @(negedge driver_clk_40m);
        // Stable before the next PRE_NBA core sample, including coincident clocks.
        @(negedge obs_core_clk); finish_requested=1;
        wait(capture_done);
        #1; $finish;
    end
    initial begin
        if (MAX_SIM_TIME_PS>0) begin
            #(MAX_SIM_TIME_PS/1000.0); $fatal(1,"CAPTURE_ABSOLUTE_WATCHDOG");
        end
    end
endmodule
