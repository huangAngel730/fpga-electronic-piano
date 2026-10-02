// Bounded Pitch/CC1 scheduling over a continuously non-empty discrete FIFO.
`timescale 1ns / 1ps
module tb_midi_control_fairness #(
    parameter integer CLK_HZ = 8_000
);
    import audio_defs_pkg::*;
    localparam integer INTERVAL = (CLK_HZ + 999) / 1000;
    localparam integer MAX_BURST = 8;

    logic clk = 0, rst_n = 0;
    always #10 clk = ~clk;
    logic [7:0] midi_byte = 0;
    logic midi_byte_valid = 0, midi_byte_error = 0, ready = 0;
    wire valid;
    performance_event_t data;
    wire [15:0] level, peak;
    wire [31:0] overflows, errors;
    performance_event_t observed [0:63];
    performance_event_t previous_data;
    integer count = 0, cycle = 0, checks = 0;
    integer last_control_cycle = -INTERVAL;
    logic previous_stalled = 0;

    midi_event_parser #(
        .LOCAL_FIFO_DEPTH(16),
        .SOURCE_ID(4'd6),
        .CLK_HZ(CLK_HZ),
        .MAX_DISCRETE_BURST(MAX_BURST)
    ) dut (
        .clk(clk), .rst_n(rst_n), .midi_byte(midi_byte),
        .midi_byte_valid(midi_byte_valid), .midi_byte_error(midi_byte_error),
        .event_ready(ready), .event_valid(valid), .event_data(data),
        .event_fifo_level(level), .event_fifo_high_watermark(peak),
        .event_fifo_overflow_count(overflows), .parser_error_count(errors)
    );

    task automatic check(input logic condition, input string reason);
        checks++;
        if (condition !== 1'b1)
            $fatal(1, "%s cycle=%0d count=%0d level=%0d", reason, cycle, count, level);
    endtask

    always @(posedge clk) begin
        cycle++;
        if (!rst_n) begin
            count = 0;
            previous_stalled = 0;
            last_control_cycle = cycle - INTERVAL;
        end else begin
            if (previous_stalled)
                check(valid && data === previous_data,
                      "payload changed while valid was stalled");
            previous_stalled = valid && !ready;
            previous_data = data;
            if (valid && ready) begin
                check(count < 64, "capture overflow");
                observed[count++] = data;
                if (data.event_type == EVENT_PITCH_BEND ||
                    (data.event_type == EVENT_CONTROL_CHANGE &&
                     data.control_id == CTRL_MODULATION)) begin
                    check(cycle - last_control_cycle >= INTERVAL,
                          "aggregate control rate exceeded 1kHz");
                    last_control_cycle = cycle;
                end
            end
        end
    end

    task automatic byte_in(input logic [7:0] value);
        @(negedge clk); midi_byte = value; midi_byte_valid = 1;
        @(negedge clk); midi_byte_valid = 0;
    endtask

    task automatic note_on(input integer note_value);
        byte_in(8'h90); byte_in(8'(note_value)); byte_in(8'd100);
    endtask

    task automatic pitch(input integer raw);
        byte_in(8'hE0); byte_in(8'(raw % 128)); byte_in(8'(raw / 128));
    endtask

    task automatic reset_dut;
        @(negedge clk); rst_n = 0; ready = 0;
        midi_byte_valid = 0; midi_byte_error = 0;
        repeat (3) @(negedge clk);
        rst_n = 1;
        repeat (2) @(negedge clk);
    endtask

    task automatic wait_count(input integer expected_count, input integer guard_limit);
        integer guard;
        guard = 0;
        while (count < expected_count && guard < guard_limit) begin
            @(negedge clk); guard++;
        end
        check(count == expected_count, "expected event did not arrive");
    endtask

    initial begin
        performance_event_t held;
        integer index;

        // Keep twelve discrete events in the real FIFO. The pending Pitch must
        // be the ninth successful handshake, while FIFO order remains intact.
        reset_dut();
        for (index = 0; index < 10; index++) note_on(60 + index);
        byte_in(8'hB0); byte_in(8'd64); byte_in(8'd127);
        byte_in(8'h80); byte_in(8'd60); byte_in(8'd64);
        pitch(8192 + 400);
        check(level == 12 && overflows == 0, "preloaded discrete FIFO mismatch");
        ready = 1;
        wait_count(13, 200 + INTERVAL);
        check(observed[8].event_type == EVENT_PITCH_BEND &&
              observed[8].control_value == midi_bend_to_12bit(14'(8192 + 400)),
              "control was starved beyond eight discrete handshakes");
        for (index = 0; index < 8; index++)
            check(observed[index].event_type == EVENT_NOTE_ON &&
                  observed[index].note_number == 60 + index,
                  "discrete order changed before bounded grant");
        check(observed[9].event_type == EVENT_NOTE_ON &&
              observed[9].note_number == 68,
              "discrete FIFO did not resume after control grant");
        check(observed[10].event_type == EVENT_NOTE_ON &&
              observed[10].note_number == 69,
              "second trailing Note changed order");
        check(observed[11].event_type == EVENT_CONTROL_CHANGE &&
              observed[11].control_id == CTRL_SUSTAIN,
              "CC64 order changed by bounded scheduler");
        check(observed[12].event_type == EVENT_NOTE_OFF &&
              observed[12].note_number == 60,
              "Note Off order changed by bounded scheduler");

        // On the eighth discrete handshake, update the selected Pitch slot.
        // The lock must capture that newest value, not stale pending data.
        reset_dut();
        for (index = 0; index < 8; index++) note_on(72 + index);
        pitch(8192);
        ready = 1;
        wait_count(7, 100);
        ready = 0;
        byte_in(8'hE0);
        byte_in(8'd0);
        @(negedge clk); midi_byte = 8'd127; midi_byte_valid = 1; ready = 1;
        @(negedge clk); midi_byte_valid = 0; ready = 0;
        check(count == 8, "eighth discrete handshake was not completed");
        check(valid && data.event_type == EVENT_PITCH_BEND &&
              data.control_value == midi_bend_to_12bit(14'h3F80),
              "same-cycle newest Pitch value was not locked");
        held = data;
        pitch(0);
        check(valid && data === held,
              "new control update rewrote a stalled locked event");
        ready = 1;
        wait_count(10, INTERVAL + 100);
        check(observed[8].control_value == midi_bend_to_12bit(14'h3F80),
              "locked newest Pitch was not delivered");
        check(observed[9].control_value == midi_bend_to_12bit(14'd0),
              "post-lock latest Pitch did not survive coalescing");
        check(errors == 0 && overflows == 0,
              "unexpected parser or FIFO diagnostics");

        $display("PASS tb_midi_control_fairness clk_hz=%0d interval=%0d checks=%0d",
                 CLK_HZ, INTERVAL, checks);
        $finish;
    end

    initial begin #5000000; $fatal(1, "bounded scheduler timeout"); end
endmodule
