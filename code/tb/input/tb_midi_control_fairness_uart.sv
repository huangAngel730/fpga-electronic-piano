// Real 50MHz / 31250-baud UART coverage for the bounded control scheduler.
`timescale 1ns / 1ps
module tb_midi_control_fairness_uart;
    import audio_defs_pkg::*;
    logic clk = 0, rst_n = 0, rx = 1, ready = 0;
    always #10 clk = ~clk;
    wire valid, busy;
    performance_event_t data;
    performance_event_t observed [0:31];
    wire [15:0] level, peak;
    wire [31:0] frame_errors, parse_errors, overflows;
    integer count = 0, checks = 0;

    midi_input #(
        .SOURCE_ID(4'd9),
        .LOCAL_FIFO_DEPTH(16),
        .MAX_DISCRETE_BURST(8)
    ) dut (
        .clk(clk), .rst_n(rst_n), .midi_rx_async(rx), .event_ready(ready),
        .event_valid(valid), .event_data(data), .event_fifo_level(level),
        .event_fifo_high_watermark(peak), .uart_frame_error_count(frame_errors),
        .parser_error_count(parse_errors), .event_fifo_overflow_count(overflows),
        .midi_rx_busy(busy)
    );

    always @(posedge clk) begin
        if (rst_n && valid && ready) begin
            if (count >= 32) $fatal(1, "UART fairness capture overflow");
            observed[count++] = data;
        end
    end

    task automatic check(input logic condition, input string reason);
        checks++;
        if (condition !== 1'b1) $fatal(1, "%s count=%0d level=%0d", reason, count, level);
    endtask

    task automatic serial_byte(input logic [7:0] value);
        @(negedge clk); rx = 0; repeat (1600) @(negedge clk);
        for (integer bit_index = 0; bit_index < 8; bit_index++) begin
            rx = value[bit_index]; repeat (1600) @(negedge clk);
        end
        rx = 1; repeat (1600) @(negedge clk);
    endtask

    task automatic serial_note(input integer note_value);
        serial_byte(8'h90); serial_byte(8'(note_value)); serial_byte(8'd100);
    endtask

    initial begin
        integer index, guard;
        repeat (5) @(negedge clk); rst_n = 1;

        for (index = 0; index < 10; index++) serial_note(48 + index);
        serial_byte(8'hC1); serial_byte(8'd7);
        serial_byte(8'hB0); serial_byte(8'd64); serial_byte(8'd127);
        serial_byte(8'h80); serial_byte(8'd48); serial_byte(8'd64);
        serial_byte(8'hE2); serial_byte(8'd0); serial_byte(8'd80);
        serial_byte(8'hB3); serial_byte(8'd1); serial_byte(8'd100);
        check(level == 13 && !valid == 0,
              "real UART did not preload discrete and control traffic");

        ready = 1;
        guard = 0;
        while (count < 15 && guard < 200000) begin
            @(negedge clk); guard++;
        end
        check(count == 15, "real UART finite ready opportunities lost events");
        check(observed[8].event_type == EVENT_PITCH_BEND &&
              observed[8].channel == 2 && observed[8].source_id == 9,
              "real UART Pitch missed bounded grant");
        check(observed[14].event_type == EVENT_CONTROL_CHANGE &&
              observed[14].control_id == CTRL_MODULATION &&
              observed[14].channel == 3 && observed[14].source_id == 9,
              "real UART CC1 latest event missing");
        check(observed[11].event_type == EVENT_CONTROL_CHANGE &&
              observed[11].control_id == CTRL_VOICE_SELECT &&
              observed[11].control_value == 7 && observed[11].channel == 1,
              "real UART Program Change payload/order changed");
        check(observed[12].event_type == EVENT_CONTROL_CHANGE &&
              observed[12].control_id == CTRL_SUSTAIN,
              "real UART CC64 discrete order changed");
        check(observed[13].event_type == EVENT_NOTE_OFF,
              "real UART Program-to-Note order changed");
        check(frame_errors == 0 && parse_errors == 0 && overflows == 0,
              "real UART diagnostics were nonzero");
        $display("PASS tb_midi_control_fairness_uart baud=31250 events=%0d checks=%0d",
                 count, checks);
        $finish;
    end

    initial begin #30000000; $fatal(1, "real UART fairness timeout"); end
endmodule
