// -----------------------------------------------------------------------------
// midi_input.sv
// 标准 MIDI 数字接收链路：
//   RX -> UART 31250 8N1 -> MIDI解析 -> 离散FIFO / Pitch与CC1限速合并。
//
// 光耦或电平转换属于外部硬件；严禁把 5 V MIDI/UART 信号直接接入 FPGA。
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module midi_input_panel_candidate #(
    parameter integer     CLK_HZ           = 50_000_000,
    parameter integer     MIDI_BAUD        = 31_250,
    parameter integer     LOCAL_FIFO_DEPTH = 8,
    parameter logic [3:0] SOURCE_ID         = 4'd0,
    parameter integer     MAX_DISCRETE_BURST = 8
) (
    input  logic                               clk,
    input  logic                               rst_n,
    input  logic                               midi_rx_async,
    input  logic                               event_ready,
    output logic                               event_valid,
    output audio_defs_pkg::performance_event_t event_data,
    output logic [15:0]                        event_fifo_level,
    output logic [15:0]                        event_fifo_high_watermark,
    output logic [31:0]                        uart_frame_error_count,
    output logic [31:0]                        parser_error_count,
    output logic [31:0]                        event_fifo_overflow_count,
    output logic                               midi_rx_busy
);

    logic [7:0] uart_rx_data;
    logic       uart_rx_valid;
    logic       uart_frame_error;

    // 公共 UART 内含两级同步器并在每一位中点采样，不使用普通逻辑作时钟。
    uart_rx #(
        .CLK_HZ    (CLK_HZ),
        .BAUD      (MIDI_BAUD),
        .DATA_BITS (8)
    ) u_uart_rx (
        .clk       (clk),
        .rst_n     (rst_n),
        .rx        (midi_rx_async),
        .rx_data   (uart_rx_data),
        .rx_valid  (uart_rx_valid),
        .frame_err (uart_frame_error),
        .rx_busy   (midi_rx_busy)
    );

    midi_event_parser #(
        .LOCAL_FIFO_DEPTH (LOCAL_FIFO_DEPTH),
        .SOURCE_ID         (SOURCE_ID),
        .CLK_HZ            (CLK_HZ),
        .MAX_DISCRETE_BURST(MAX_DISCRETE_BURST),.PANEL_CONTROL_ENABLE(1'b1)
    ) u_midi_event_parser (
        .clk                       (clk),
        .rst_n                     (rst_n),
        .midi_byte                 (uart_rx_data),
        .midi_byte_valid           (uart_rx_valid),
        .midi_byte_error           (uart_frame_error),
        .event_ready               (event_ready),
        .event_valid               (event_valid),
        .event_data                (event_data),
        .event_fifo_level          (event_fifo_level),
        .event_fifo_high_watermark (event_fifo_high_watermark),
        .event_fifo_overflow_count (event_fifo_overflow_count),
        .parser_error_count        (parser_error_count)
    );

    // 帧错误只在 uart_rx_valid 同拍有效；计数饱和后不回绕，避免掩盖历史错误。
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            uart_frame_error_count <= 32'd0;
        end else if (uart_rx_valid && uart_frame_error &&
                     (uart_frame_error_count != 32'hFFFF_FFFF)) begin
            uart_frame_error_count <= uart_frame_error_count + 32'd1;
        end
    end

endmodule
