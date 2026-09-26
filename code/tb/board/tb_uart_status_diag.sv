`timescale 1ns/1ps
module tb_uart_status_diag;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0, tx, report_busy;
    logic [7:0] rx_data;
    logic rx_valid, rx_error, rx_busy;
    string line = "", expected;
    uart_status_reporter #(
        .CLK_HZ(1_000_000), .BAUD(100_000),
        .REPORT_CYCLES(25_000), .CLIP_COUNT_VALID(1'b0)
    ) dut (
        .clk, .rst_n,
        .active_voice_count(32'd1), .clip_count(32'd999),
        .event_fifo_level(32'd2), .event_fifo_high_watermark(32'd3),
        .event_fifo_overflow(32'd4), .audio_underrun(32'd5),
        .max_processing_cycles(32'd6), .tx, .report_busy
    );
    uart_rx #(.CLK_HZ(1_000_000), .BAUD(100_000)) monitor (
        .clk, .rst_n, .rx(tx), .rx_data, .rx_valid,
        .frame_err(rx_error), .rx_busy
    );
    initial begin
        expected = {
            "DIAG active_voice_count=0x00000001 clip_count=0x--------",
            " event_fifo_level=0x00000002 event_fifo_high_watermark=0x00000003",
            " event_fifo_overflow=0x00000004 audio_underrun=0x00000005",
            " max_processing_cycles=0x00000006",8'h0d,8'h0a};
        repeat (5) @(negedge clk);
        rst_n = 1;
    end
    always @(posedge clk) if (rst_n && rx_valid) begin
        if (rx_error) $fatal(1,"DIAG UART frame error");
        line = {line,rx_data};
        if (rx_data == 8'h0a) begin
            if (line != expected) $fatal(1,"DIAG mismatch: %s",line);
            $display("PASS tb_uart_status_diag bytes=%0d",line.len());
            $finish;
        end
    end
    initial begin #1_000_000; $fatal(1,"DIAG timeout"); end
endmodule
