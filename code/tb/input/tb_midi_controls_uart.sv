// Physical UART bit timing -> real midi_input output, 50MHz / 31250 / 1kHz.
`timescale 1ns / 1ps
module tb_midi_controls_uart;
    import audio_defs_pkg::*;
    logic clk = 0, rst_n = 0, rx = 1, ready = 1;
    always #10 clk = ~clk;
    wire valid, busy;
    performance_event_t data, expected [0:31], ev;
    wire [15:0] level, peak;
    wire [31:0] frame_errors, parse_errors, overflows;
    integer written = 0, count = 0, cycle = 0, last_control = -50000;
    integer checks = 0;
    midi_input #(.SOURCE_ID(4'd5), .LOCAL_FIFO_DEPTH(4)) dut (
        .clk(clk), .rst_n(rst_n), .midi_rx_async(rx), .event_ready(ready),
        .event_valid(valid), .event_data(data), .event_fifo_level(level),
        .event_fifo_high_watermark(peak), .uart_frame_error_count(frame_errors),
        .parser_error_count(parse_errors), .event_fifo_overflow_count(overflows),
        .midi_rx_busy(busy)
    );
    always @(posedge clk) begin
        cycle++;
        if (rst_n && valid && ready) begin
            if (count >= written || data !== expected[count])
                $fatal(1, "UART event index=%0d expected=%h actual=%h", count, expected[count], data);
            if (data.event_type == 3 || (data.event_type == 4 && data.control_id == 1)) begin
                if (cycle - last_control < 50000) $fatal(1, "UART aggregate 1kHz limit failed");
                last_control = cycle;
                checks++;
            end
            count++; checks++;
        end
    end
    task automatic serial_byte(input logic [7:0] b);
        @(negedge clk); rx = 0; repeat (1600) @(negedge clk);
        for (integer bit_index = 0; bit_index < 8; bit_index++) begin
            rx = b[bit_index]; repeat (1600) @(negedge clk);
        end
        rx = 1; repeat (1600) @(negedge clk);
    endtask
    task automatic expect_control(input logic mod_value, input integer channel_value, raw);
        ev = '0; ev.source_id = 5; ev.channel = 4'(channel_value);
        ev.event_type = mod_value ? 4 : 3; ev.control_id = mod_value ? 1 : 0;
        ev.control_value = mod_value ? 12'(raw*32+raw/4) : 12'(raw/4-2048);
        expected[written++] = ev;
    endtask
    task automatic wait_received;
        integer guard;
        guard = 0;
        while (count < written && guard < 150000) begin @(negedge clk); guard++; end
        if (count != written) $fatal(1, "UART expected event missing");
    endtask
    initial begin
        repeat (5) @(negedge clk); rst_n = 1;
        expect_control(0, 15, 0); serial_byte(8'hEF); serial_byte(0); serial_byte(0); wait_received();
        expect_control(0, 15, 8192); serial_byte(0); serial_byte(8'hF8); serial_byte(64); wait_received();
        expect_control(0, 15, 16383); serial_byte(127); serial_byte(127); wait_received();
        expect_control(1, 7, 0); serial_byte(8'hB7); serial_byte(1); serial_byte(0); wait_received();
        expect_control(1, 7, 127); serial_byte(1); serial_byte(8'hFF); serial_byte(127); wait_received();
        // Repeated CC1 and unsupported CC121/123 do not generate output.
        serial_byte(1); serial_byte(127); serial_byte(121); serial_byte(0);
        serial_byte(123); serial_byte(0);
        ev = '0; ev.source_id = 5; ev.channel = 7; ev.event_type = 4;
        ev.control_id = 6; ev.control_value = 4095; expected[written++] = ev;
        serial_byte(64); serial_byte(127); wait_received();
        ev = '0; ev.source_id = 5; ev.channel = 7; ev.note_number = 60;
        ev.velocity = 806; expected[written++] = ev;
        serial_byte(8'h97); serial_byte(60); serial_byte(100); wait_received();
        ev.event_type = 1; ev.velocity = 0; expected[written++] = ev;
        serial_byte(60); serial_byte(0); wait_received();
        repeat (51000) @(negedge clk);
        if (count != written || valid || frame_errors != 0 || parse_errors != 0 || overflows != 0)
            $fatal(1, "UART final counters/duplicates");
        checks++;
        $display("PASS tb_midi_controls_uart clk_hz=50000000 baud=31250 events=%0d checks=%0d", count, checks);
        $finish;
    end
    initial begin #100000000; $fatal(1, "real UART controls timeout"); end
endmodule
