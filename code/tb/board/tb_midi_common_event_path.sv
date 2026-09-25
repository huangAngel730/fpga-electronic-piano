`timescale 1ns/1ps
module tb_midi_common_event_path;
    import audio_defs_pkg::*;
    logic clk = 0;
    always #5 clk = ~clk;  // 1 MHz for short simulation
    logic rst_n = 0, midi_rx = 1;
    logic midi_valid, midi_ready, button_valid = 0, button_ready;
    logic event_valid, event_ready = 0;
    performance_event_t midi_data, button_data, event_data;
    logic [15:0] midi_level, midi_peak, level, peak;
    logic [31:0] frame_errors, parser_errors, midi_overflow;
    logic midi_busy;
    integer checks = 0;

    midi_input #(.CLK_HZ(1_000_000), .SOURCE_ID(4'd0)) source (
        .clk, .rst_n, .midi_rx_async(midi_rx), .event_ready(midi_ready),
        .event_valid(midi_valid), .event_data(midi_data),
        .event_fifo_level(midi_level), .event_fifo_high_watermark(midi_peak),
        .uart_frame_error_count(frame_errors), .parser_error_count(parser_errors),
        .event_fifo_overflow_count(midi_overflow), .midi_rx_busy(midi_busy)
    );
    performance_event_fifo #(.DEPTH(32)) common_fifo (
        .clk, .rst_n,
        .button_valid, .button_ready, .button_data,
        .midi_valid, .midi_ready, .midi_data,
        .event_valid, .event_ready, .event_data,
        .event_fifo_level(level), .event_fifo_high_watermark(peak)
    );

    task automatic send_byte(input logic [7:0] value);
        @(negedge clk); midi_rx = 0;
        repeat (32) @(negedge clk);
        for (integer i=0; i<8; i++) begin
            midi_rx = value[i];
            repeat (32) @(negedge clk);
        end
        midi_rx = 1;
        repeat (32) @(negedge clk);
    endtask
    task automatic check(input bit ok, input string reason);
        if (!ok) $fatal(1, "%s", reason);
        checks++;
    endtask
    initial begin
        button_data = '0;
        repeat (4) @(negedge clk);
        check(!event_valid && !midi_ready && level == 0, "reset idle");
        rst_n = 1;
        send_byte(8'h90);
        send_byte(8'h3c);
        send_byte(8'h64);
        @(negedge clk);
        check(level == 1 && event_valid && event_data.note_number == 7'd60 &&
              event_data.event_type == EVENT_NOTE_ON && event_data.source_id == 0 &&
              event_data.velocity == midi_velocity_to_10bit(7'd100),
              "MIDI note and velocity passed into shared FIFO");
        button_data = make_note_event(1'b1, 4'd1, 4'd0, 7'd69, 10'd512);
        button_valid = 1;
        @(negedge clk); button_valid = 0;
        #1;
        check(level == 2 && peak == 2 && midi_level == 0,
              "button and MIDI retained without drop");
        check(event_valid && event_data.note_number == 7'd60, "MIDI first");
        event_ready = 1;
        @(negedge clk);
        check(event_valid && event_data == button_data,
              "button event follows MIDI event");
        @(negedge clk);
        check(!event_valid && level == 0 && peak == 2 && frame_errors == 0 &&
              parser_errors == 0 && midi_overflow == 0, "drained with no errors");
        $display("PASS tb_midi_common_event_path checks=%0d", checks);
        $finish;
    end
    initial begin #1_000_000; $fatal(1, "MIDI path timeout"); end
endmodule
