// Byte-level CC64 parser regression. Independent expected 64-bit payloads.
`timescale 1ns / 1ps
module tb_midi_cc64;
    import audio_defs_pkg::*;
    localparam logic [3:0] SOURCE_ID = 4'd9;
    logic clk = 0, rst_n = 0;
    always #10 clk = ~clk;
    logic [7:0] midi_byte = 0;
    logic midi_byte_valid = 0, midi_byte_error = 0, event_ready = 0;
    wire event_valid;
    performance_event_t event_data;
    wire [15:0] level, high_water;
    wire [31:0] overflows, errors;
    midi_event_parser #(.LOCAL_FIFO_DEPTH(4), .SOURCE_ID(SOURCE_ID)) dut (
        .clk(clk), .rst_n(rst_n), .midi_byte(midi_byte),
        .midi_byte_valid(midi_byte_valid), .midi_byte_error(midi_byte_error),
        .event_ready(event_ready), .event_valid(event_valid), .event_data(event_data),
        .event_fifo_level(level), .event_fifo_high_watermark(high_water),
        .event_fifo_overflow_count(overflows), .parser_error_count(errors)
    );
    performance_event_t expected [0:4095];
    performance_event_t held;
    integer write_index = 0, read_index = 0, checks = 0;
    integer channel_index, raw_value, before_count;

    task automatic check(input logic condition, input string reason);
        checks = checks + 1;
        if (condition !== 1'b1) $fatal(1, "%s at %0t", reason, $time);
    endtask
    task automatic expect_cc(input logic [3:0] channel_value,
                             input logic [6:0] value);
        performance_event_t ev;
        begin
            ev = '0;
            ev.event_type = 3'd4;
            ev.source_id = SOURCE_ID;
            ev.channel = channel_value;
            ev.control_id = 8'd6;
            ev.control_value = (12'(value) << 5) | (12'(value) >> 2);
            expected[write_index] = ev;
            write_index = write_index + 1;
        end
    endtask
    task automatic expect_note(input logic is_on, input logic [3:0] channel_value,
                               input logic [6:0] note, value);
        performance_event_t ev;
        begin
            ev = '0;
            ev.event_type = is_on && value != 0 ? 3'd0 : 3'd1;
            ev.source_id = SOURCE_ID;
            ev.channel = channel_value;
            ev.note_number = note;
            ev.velocity = (10'(value) << 3) | (10'(value) >> 4);
            expected[write_index] = ev;
            write_index = write_index + 1;
        end
    endtask
    task automatic send_byte(input logic [7:0] value, input logic bad);
        @(negedge clk);
        midi_byte = value; midi_byte_valid = 1; midi_byte_error = bad;
        @(negedge clk);
        midi_byte_valid = 0; midi_byte_error = 0;
    endtask
    task automatic drain;
        @(negedge clk); event_ready = 1;
        repeat (10) @(negedge clk);
        check(read_index == write_index && !event_valid, "missing/duplicate event");
    endtask
    always @(posedge clk) begin
        if (rst_n && event_valid && event_ready) begin
            check(read_index < write_index, "unexpected event");
            check(event_data === expected[read_index], "64-bit CC/note payload mismatch");
            read_index = read_index + 1;
        end
    end
    initial begin
        repeat (3) @(negedge clk); rst_n = 1; event_ready = 1;
        // All channels and all raw values, running status and every realtime byte.
        for (channel_index = 0; channel_index < 16; channel_index = channel_index + 1) begin
            send_byte(8'hB0 | 8'(channel_index), 0);
            for (raw_value = 0; raw_value < 128; raw_value = raw_value + 1) begin
                expect_cc(4'(channel_index), 7'(raw_value));
                send_byte(8'h40, 0);
                send_byte(8'hF8 | 8'(raw_value % 8), 0);
                send_byte(8'(raw_value), 0);
            end
        end
        drain();
        check(read_index == 2048 && errors == 0 && overflows == 0,
              "all-channel sweep count/counters");

        // CC2/CC123 do not output; following running CC64 stays aligned.
        before_count = read_index;
        send_byte(8'hB3, 0); send_byte(8'h02, 0); send_byte(8'h7F, 0);
        send_byte(8'h7B, 0); send_byte(8'h00, 0);
        check(read_index == before_count, "unsupported CC emitted event");
        expect_cc(3, 64); send_byte(8'h40, 0); send_byte(8'h40, 0); drain();
        // Incomplete CC replaced by Note On; Note On velocity zero remains OFF.
        send_byte(8'hB0, 0); send_byte(8'h40, 0);
        send_byte(8'h92, 0);
        expect_note(1, 2, 60, 127); send_byte(60, 0); send_byte(127, 0);
        expect_note(1, 2, 60, 0); send_byte(60, 0); send_byte(0, 0);
        drain(); check(errors == 1, "truncated CC must record parser error");
        // SysEx/system-common cancels CC running status; no accidental pedal.
        send_byte(8'hB0, 0); send_byte(8'hF0, 0);
        send_byte(8'h40, 0); send_byte(8'hF8, 0); send_byte(8'h7F, 0);
        send_byte(8'hF7, 0);
        send_byte(8'hB0, 0); send_byte(8'hF2, 0);
        send_byte(8'h40, 0); send_byte(8'h7F, 0);
        send_byte(8'h40, 0); check(errors == 2, "system-common running status cancellation");
        // Bad value drops incomplete CC and requires a new status.
        send_byte(8'hB0, 0); send_byte(8'h40, 0); send_byte(8'h7F, 1);
        expect_cc(0, 63);
        send_byte(8'hB0, 0); send_byte(8'h40, 0); send_byte(8'h3F, 0); drain();

        // CC64 FIFO backpressure, capacity and overflow: retain first four.
        @(negedge clk); event_ready = 0;
        send_byte(8'hB7, 0);
        for (raw_value = 0; raw_value < 5; raw_value = raw_value + 1) begin
            if (raw_value < 4) expect_cc(7, 7'(raw_value));
            send_byte(8'h40, 0); send_byte(8'(raw_value), 0);
        end
        check(level == 4 && high_water == 4 && overflows == 1, "CC FIFO full/overflow");
        held = event_data;
        repeat (4) begin
            @(negedge clk); check(event_valid && event_data === held, "CC payload unstable under stall");
        end
        // Full FIFO same-edge dequeue/enqueue must keep the new CC.
        expect_cc(7, 127); send_byte(8'h40, 0);
        @(negedge clk); midi_byte = 127; midi_byte_valid = 1; event_ready = 1;
        @(negedge clk); midi_byte_valid = 0;
        drain(); check(overflows == 1, "simultaneous CC FIFO pop/push overflowed");

        // Reset with a queued CC and half message clears both contexts.
        @(negedge clk); event_ready = 0;
        send_byte(8'hB0, 0); send_byte(8'h40, 0); send_byte(127, 0);
        send_byte(8'h40, 0);
        @(negedge clk); rst_n = 0;
        repeat (2) @(negedge clk);
        check(!event_valid && level == 0 && overflows == 0 && errors == 0,
              "reset left CC or parser context pending");
        rst_n = 1; event_ready = 1;
        send_byte(0, 0); check(errors == 1, "reset preserved running status");
        expect_cc(15, 0); send_byte(8'hBF, 0); send_byte(8'h40, 0); send_byte(0, 0);
        drain();
        $display("PASS tb_midi_cc64 events=%0d checks=%0d channels=16 raw_values=128", read_index, checks);
        $finish;
    end
    initial begin #1000000; $fatal(1, "CC64 parser timeout"); end
endmodule
