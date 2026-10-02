// Program Change through the physical 50MHz / 31250-baud midi_input chain.
`timescale 1ns / 1ps
module tb_midi_program_change_uart;
    import audio_defs_pkg::*;
    logic clk = 0, rst_n = 0, rx = 1, ready = 0;
    always #10 clk = ~clk;
    wire valid, busy;
    performance_event_t data, expected [0:15], event_value;
    wire [15:0] level, peak;
    wire [31:0] frame_errors, parse_errors, overflows;
    integer written = 0, received = 0, checks = 0;

    midi_input #(.SOURCE_ID(4'd5), .LOCAL_FIFO_DEPTH(8)) dut (
        .clk(clk), .rst_n(rst_n), .midi_rx_async(rx), .event_ready(ready),
        .event_valid(valid), .event_data(data), .event_fifo_level(level),
        .event_fifo_high_watermark(peak), .uart_frame_error_count(frame_errors),
        .parser_error_count(parse_errors), .event_fifo_overflow_count(overflows),
        .midi_rx_busy(busy)
    );

    always @(posedge clk) begin
        if (rst_n && valid && ready) begin
            if (received >= written || data !== expected[received])
                $fatal(1, "UART Program index=%0d expected=%h actual=%h",
                       received, expected[received], data);
            received++;
            checks++;
        end
    end

    task automatic check(input logic condition, input string reason);
        checks++;
        if (condition !== 1'b1) $fatal(1, "%s", reason);
    endtask

    task automatic serial_byte(input logic [7:0] value);
        @(negedge clk); rx = 0; repeat (1600) @(negedge clk);
        for (integer bit_index = 0; bit_index < 8; bit_index++) begin
            rx = value[bit_index]; repeat (1600) @(negedge clk);
        end
        rx = 1; repeat (1600) @(negedge clk);
    endtask

    task automatic expect_program(input integer channel_value, input integer raw_value);
        event_value = '0;
        event_value.event_type = EVENT_CONTROL_CHANGE;
        event_value.source_id = 5;
        event_value.channel = 4'(channel_value);
        event_value.control_id = CTRL_VOICE_SELECT;
        event_value.control_value = 12'(raw_value);
        expected[written++] = event_value;
    endtask

    initial begin
        integer guard;
        repeat (5) @(negedge clk); rst_n = 1;

        expect_program(3, 1); serial_byte(8'hC3); serial_byte(1);
        expect_program(3, 0); serial_byte(8'hF8); serial_byte(0);
        expect_program(3, 127); serial_byte(127);
        expect_program(3, 127); serial_byte(127);
        serial_byte(8'hD3); serial_byte(1); serial_byte(8'hFE); serial_byte(127);

        event_value = '0; event_value.source_id = 5; event_value.channel = 3;
        event_value.note_number = 60; event_value.velocity = 806;
        expected[written++] = event_value;
        serial_byte(8'h93); serial_byte(60); serial_byte(100);
        event_value = '0; event_value.event_type = EVENT_CONTROL_CHANGE;
        event_value.source_id = 5; event_value.channel = 3;
        event_value.control_id = CTRL_SUSTAIN; event_value.control_value = 4095;
        expected[written++] = event_value;
        serial_byte(8'hB3); serial_byte(64); serial_byte(127);
        event_value = '0; event_value.event_type = EVENT_PITCH_BEND;
        event_value.source_id = 5; event_value.channel = 3;
        event_value.control_id = CTRL_PITCH_BEND; event_value.control_value = 0;
        expected[written++] = event_value;
        serial_byte(8'hE3); serial_byte(0); serial_byte(64);

        check(level == 6, "UART Program discrete FIFO level mismatch");
        ready = 1;
        guard = 0;
        while (received < written && guard < 100000) begin
            @(negedge clk); guard++;
        end
        repeat (4) @(negedge clk);
        check(received == written && !valid, "UART Program events missing or duplicated");
        check(frame_errors == 0 && parse_errors == 0 && overflows == 0,
              "UART Program diagnostics nonzero");
        $display("PASS tb_midi_program_change_uart baud=31250 events=%0d checks=%0d",
                 received, checks);
        $finish;
    end

    initial begin #30000000; $fatal(1, "UART Program Change timeout"); end
endmodule
