`timescale 1ns/1ps
module tb_uart_status_reporter;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0, tx, report_busy;
    logic [31:0] active_voice_count = 4, clip_count = 2;
    logic [31:0] event_fifo_level = 3, event_fifo_high_watermark = 7;
    logic [31:0] event_fifo_overflow = 1, audio_underrun = 5;
    logic [31:0] max_processing_cycles = 1024;
    logic [7:0] rx_data;
    logic rx_valid, rx_error, rx_busy;
    string received = "", expected_first, expected_second;
    integer lines = 0, checks = 0;

    uart_status_reporter #(
        .CLK_HZ(1_000_000), .BAUD(100_000), .REPORT_CYCLES(25_000)
    ) dut (.*);
    uart_rx #(.CLK_HZ(1_000_000), .BAUD(100_000)) monitor (
        .clk, .rst_n, .rx(tx), .rx_data, .rx_valid,
        .frame_err(rx_error), .rx_busy
    );

    initial begin
        expected_first = "STAT active_voice_count=0x00000004 clip_count=0x00000002"
            // Verilog adjacent strings are not concatenated implicitly.
            ;
        expected_first = {expected_first,
            " event_fifo_level=0x00000003 event_fifo_high_watermark=0x00000007",
            " event_fifo_overflow=0x00000001 audio_underrun=0x00000005",
            " max_processing_cycles=0x00000400", 8'h0d, 8'h0a};
        expected_second = {
            "STAT active_voice_count=0x00000001 clip_count=0x00000002",
            " event_fifo_level=0x00000003 event_fifo_high_watermark=0x00000007",
            " event_fifo_overflow=0x00000001 audio_underrun=0x00000005",
            " max_processing_cycles=0x00000400", 8'h0d, 8'h0a};
        repeat (5) @(negedge clk);
        if (tx !== 1'b1 || report_busy !== 1'b0)
            $fatal(1, "reset idle");
        checks++;
        rst_n = 1;
    end

    always @(posedge clk) begin
        if (!rst_n) received = "";
        else if (rx_valid) begin
        if (rx_error) $fatal(1, "UART frame error");
        received = {received, rx_data};
        if (rx_data == 8'h0a) begin
            if (lines == 0 && received != expected_first) begin
                $display("actual_len=%0d expected_len=%0d", received.len(), expected_first.len());
                for (integer k=0; k<received.len(); k++)
                    if (received[k] !== expected_first[k])
                        $display("mismatch byte[%0d] actual=%02x expected=%02x",
                                 k, received[k], expected_first[k]);
                $fatal(1, "first snapshot mismatch: %s", received);
            end
            if (lines > 0 && received != expected_second)
                $fatal(1, "second snapshot mismatch: %s", received);
            checks++;
            lines++;
            received = "";
            if (lines == 3) begin
                $display("PASS tb_uart_status_reporter checks=%0d", checks);
                $finish;
            end
        end
        end
    end

    initial begin
        wait (report_busy);
        repeat (500) @(negedge clk);
        active_voice_count = 1; // current line must use the earlier snapshot
    end
    initial begin
        wait (lines == 2);
        wait (report_busy);
        repeat (250) @(negedge clk);
        if (received.len() == 0) $fatal(1, "no partial line before reset");
        checks++;
        rst_n = 0;
        repeat (3) @(negedge clk);
        if (tx !== 1'b1 || report_busy !== 1'b0 || received.len() != 0)
            $fatal(1, "mid-line reset did not clear UART/report state");
        checks++;
        rst_n = 1;
    end
    initial begin #1_500_000; $fatal(1, "status UART timeout"); end
endmodule
