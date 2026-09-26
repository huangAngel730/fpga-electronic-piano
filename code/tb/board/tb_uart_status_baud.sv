// Check the real 50 MHz / 115200 8N1 timing and complete first STAT line.
// REPORT_CYCLES is shortened here only to avoid simulating 250 ms idle time.
`timescale 1ns/1ps
module tb_uart_status_baud;
    localparam integer CLK_HZ = 50_000_000;
    localparam integer BAUD = 115_200;
    localparam integer DIV = (CLK_HZ + BAUD/2) / BAUD;
    logic clk = 0;
    always #10 clk = ~clk;
    logic rst_n = 0, tx, report_busy;
    logic [7:0] rx_data;
    logic rx_valid, rx_error, rx_busy;
    string received = "", expected;
    integer checks = 0;

    uart_status_reporter #(
        .CLK_HZ(CLK_HZ), .BAUD(BAUD), .REPORT_CYCLES(1000)
    ) dut (
        .clk, .rst_n,
        .active_voice_count(32'd4), .clip_count(32'd2),
        .event_fifo_level(32'd3), .event_fifo_high_watermark(32'd7),
        .event_fifo_overflow(32'd1), .audio_underrun(32'd5),
        .max_processing_cycles(32'd1024), .tx, .report_busy
    );
    uart_rx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) monitor (
        .clk, .rst_n, .rx(tx), .rx_data, .rx_valid,
        .frame_err(rx_error), .rx_busy
    );

    initial begin
        expected = {
            "STAT active_voice_count=0x00000004 clip_count=0x00000002",
            " event_fifo_level=0x00000003 event_fifo_high_watermark=0x00000007",
            " event_fifo_overflow=0x00000001 audio_underrun=0x00000005",
            " max_processing_cycles=0x00000400", 8'h0d, 8'h0a};
        repeat (5) @(negedge clk);
        if (tx !== 1'b1 || report_busy !== 1'b0)
            $fatal(1, "reset idle");
        rst_n = 1;
        @(negedge tx);  // first start bit
        repeat (DIV/2) @(posedge clk);
        #1;
        if (tx !== 1'b0) $fatal(1, "start bit shorter than half bit");
        checks++;
        repeat (DIV/2) @(posedge clk);
        #1;
        // ASCII 'S' has bit 0 = 1: the first bit boundary is after DIV clocks.
        if (tx !== 1'b1) $fatal(1, "first UART bit did not begin at DIV clocks");
        checks++;
    end

    always @(posedge clk) if (rst_n && rx_valid) begin
        if (rx_error) $fatal(1, "UART framing error");
        received = {received, rx_data};
        if (rx_data == 8'h0a) begin
            if (received != expected) $fatal(1, "50MHz/115200 STAT line mismatch");
            checks++;
            $display("PASS tb_uart_status_baud checks=%0d bytes=%0d DIV=%0d",
                     checks, received.len(), DIV);
            $finish;
        end
    end
    initial begin #23_000_000; $fatal(1, "50MHz/115200 status timeout"); end
endmodule
