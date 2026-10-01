// Queue contract tested at accelerated parameters AND real 50MHz/1kHz.
`timescale 1ns / 1ps
module tb_midi_control_queue #(
    parameter integer CLK_HZ = 64_000
);
    import audio_defs_pkg::*;
    localparam integer INTERVAL = (CLK_HZ + 999) / 1000;
    logic clk = 0, rst_n = 0;
    always #10 clk = ~clk;
    logic [7:0] midi_byte = 0;
    logic midi_byte_valid = 0, midi_byte_error = 0, ready = 0;
    wire valid;
    performance_event_t data;
    wire [15:0] level, peak;
    wire [31:0] overflows, errors;
    midi_event_parser #(.LOCAL_FIFO_DEPTH(4), .SOURCE_ID(4'd11), .CLK_HZ(CLK_HZ)) dut (
        .clk(clk), .rst_n(rst_n), .midi_byte(midi_byte),
        .midi_byte_valid(midi_byte_valid), .midi_byte_error(midi_byte_error),
        .event_ready(ready), .event_valid(valid), .event_data(data),
        .event_fifo_level(level), .event_fifo_high_watermark(peak),
        .event_fifo_overflow_count(overflows), .parser_error_count(errors)
    );
    performance_event_t observed [0:127], previous_data;
    integer count = 0, cycle = 0, last_control_cycle = -INTERVAL;
    integer checks = 0, control_checks = 0, ch, v;
    logic previous_stalled = 0;
    task automatic check(input logic condition, input string reason);
        checks++;
        if (condition !== 1'b1) $fatal(1, "%s cycle=%0d count=%0d", reason, cycle, count);
    endtask
    always @(posedge clk) begin
        cycle++;
        if (!rst_n) begin
            previous_stalled = 0;
            count = 0;
            last_control_cycle = cycle - INTERVAL;
        end else begin
            if (previous_stalled)
                check(valid && data === previous_data, "ready/valid payload changed while stalled");
            previous_stalled = valid && !ready;
            previous_data = data;
            if (valid && ready) begin
                check(count < 128, "capture overflow");
                observed[count++] = data;
                check(data.source_id == 11 && data.reserved == 0, "source/reserved changed");
                if (data.event_type == 3 || (data.event_type == 4 && data.control_id == 1)) begin
                    check(cycle - last_control_cycle >= INTERVAL,
                          "aggregate Pitch/CC1 handshake rate exceeds 1kHz");
                    check(data.note_number == 0 && data.velocity == 0 && data.expression == 0,
                          "control unused fields nonzero");
                    last_control_cycle = cycle;
                    control_checks++;
                end
            end
        end
    end
    task automatic byte_in(input logic [7:0] b);
        @(negedge clk); midi_byte = b; midi_byte_valid = 1;
        @(negedge clk); midi_byte_valid = 0;
    endtask
    task automatic pitch(input integer channel_value, raw);
        byte_in(8'hE0 | 8'(channel_value)); byte_in(8'(raw % 128)); byte_in(8'(raw / 128));
    endtask
    task automatic mod_wheel(input integer channel_value, raw);
        byte_in(8'hB0 | 8'(channel_value)); byte_in(1); byte_in(8'(raw));
    endtask
    task automatic reset_dut;
        @(negedge clk); rst_n = 0; ready = 0;
        repeat (3) @(negedge clk); rst_n = 1;
    endtask
    task automatic wait_count(input integer expected_count);
        integer guard;
        guard = 0;
        while (count < expected_count && guard < 35 * INTERVAL + 500) begin
            @(negedge clk); guard++;
        end
        check(count == expected_count, "final values failed to arrive");
    endtask
    task automatic quiet(input integer expected_count);
        repeat (INTERVAL + 12) @(negedge clk);
        check(count == expected_count && !valid, "unexpected duplicate/pending event");
    endtask
    initial begin
        performance_event_t held, ev;
        logic [31:0] seen;
        integer index;
        reset_dut();
        pitch(0, 8192); repeat (3) @(negedge clk);
        held = data;
        check(valid && held.control_value == 0, "center pitch not presented");
        // Lock first event while newer unsent values coalesce independently.
        for (v = 0; v < 20; v++) pitch(0, v * 600);
        pitch(0, 16383);
        check(valid && data === held && level == 0 && overflows == 0,
              "control flood overwrote presented event or consumed FIFO");
        @(negedge clk); ready = 1; wait_count(2); quiet(2);
        ev = observed[0]; check(ev.control_value == 0, "locked center lost");
        ev = observed[1]; check(ev.control_value == 2047 && ev.channel == 0,
                               "latest pitch not delivered");

        reset_dut(); pitch(0, 8192); repeat (3) @(negedge clk); held = data;
        byte_in(8'h90); byte_in(60); byte_in(100);
        byte_in(8'hB0); byte_in(64); byte_in(0);
        byte_in(8'h80); byte_in(60); byte_in(64);
        for (v = 0; v < 20; v++) begin pitch(0, v); mod_wheel(0, v); end
        pitch(0, 0); mod_wheel(0, 127);
        check(data === held && level == 3 && peak == 3 && overflows == 0,
              "mixed control traffic swallowed Note/CC64 or overflowed FIFO");
        @(negedge clk); ready = 1; wait_count(6); quiet(6);
        ev = observed[1]; check(ev.event_type == 0 && ev.note_number == 60 &&
                               ev.velocity == 806, "mixed note-on order/payload");
        ev = observed[2]; check(ev.event_type == 4 && ev.control_id == 6 &&
                               ev.control_value == 0, "mixed CC64 order/payload");
        ev = observed[3]; check(ev.event_type == 1 && ev.note_number == 60 &&
                               ev.velocity == 516, "mixed note-off order/payload");
        ev = observed[4]; check(ev.event_type == 4 && ev.control_id == 1 &&
                               ev.control_value == 4095, "latest CC1 after discrete FIFO");
        ev = observed[5]; check(ev.event_type == 3 && ev.control_value == 12'h800,
                               "latest negative pitch after mixed traffic");

        reset_dut(); ready = 1; mod_wheel(3, 0); wait_count(1);
        for (v = 0; v < 10; v++) mod_wheel(3, 0);
        quiet(1); // first zero emitted once, not mistaken for initialized state
        reset_dut(); mod_wheel(3, 10); repeat (3) @(negedge clk); held = data;
        mod_wheel(3, 20); mod_wheel(3, 10); // cancel unsent excursion
        @(negedge clk); ready = 1; wait_count(1); quiet(1);
        ev = observed[0]; check(ev.channel == 3 && ev.control_value == 322,
                               "same-item in-flight CC1 duplicate/reversion");
        @(negedge clk); ready = 0;
        mod_wheel(3, 20); repeat (INTERVAL + 3) @(negedge clk); held = data;
        mod_wheel(3, 21); mod_wheel(3, 30);
        check(valid && data === held, "CC1 update altered immutable presentation");
        @(negedge clk); ready = 1; wait_count(3); quiet(3);
        ev = observed[1]; check(ev.control_value == 645, "locked CC1 20 not delivered");
        ev = observed[2]; check(ev.control_value == 967, "latest CC1 30 not delivered");
        mod_wheel(3, 30); quiet(3);
        // Last sent A -> unpresented B -> A cancels B under FIFO blockage.
        @(negedge clk); ready = 0;
        byte_in(8'h90); byte_in(60); byte_in(1);
        mod_wheel(3, 31); mod_wheel(3, 30);
        @(negedge clk); ready = 1; wait_count(4); quiet(4);

        // Every one of 32 keys retains its own latest value. Block selection
        // with a discrete event until all channels and both items are pending.
        reset_dut(); byte_in(8'h90); byte_in(60); byte_in(1);
        for (ch = 0; ch < 16; ch++) begin
            pitch(ch, ch * 100); mod_wheel(ch, ch);
            pitch(ch, 8192 + ch * 4); mod_wheel(ch, 127 - ch);
        end
        @(negedge clk); ready = 1; wait_count(33); quiet(33);
        seen = 0;
        for (index = 1; index < 33; index++) begin
            ev = observed[index];
            check(ev.event_type == 3 || (ev.event_type == 4 && ev.control_id == 1),
                  "wrong type in all-channel pending set");
            ch = ev.channel;
            if (ev.event_type == 3) begin
                check(ev.control_id == 0 && ev.control_value == ch, "pitch crossed channels");
                check(!seen[2*ch], "duplicate pending pitch"); seen[2*ch] = 1;
            end else begin
                check(ev.control_value == (127-ch)*32 + (127-ch)/4, "CC1 crossed channels");
                check(!seen[2*ch+1], "duplicate pending CC1"); seen[2*ch+1] = 1;
            end
        end
        check(seen == 32'hffffffff && overflows == 0, "pending keys lost or unfairly scheduled");

        // Finite discrete capacity is unchanged; controls never consume it.
        reset_dut();
        for (v = 0; v < 5; v++) begin
            byte_in(8'h90); byte_in(8'(60+v)); byte_in(1);
            pitch(0, v);
        end
        check(level == 4 && peak == 4 && overflows == 1, "discrete overflow accounting changed");
        // Reset cancels stalled Note, pending controls and half MIDI message.
        byte_in(8'hE0); byte_in(0); reset_dut();
        check(!valid && level == 0 && overflows == 0 && errors == 0, "reset queue state");
        byte_in(64); check(errors == 1, "reset running status survived");
        // Also reset an actually presented, stalled control with newer pending
        // values; neither the locked old event nor its latest successor survives.
        pitch(9, 0); repeat (3) @(negedge clk);
        check(valid && data.event_type == 3, "reset case has no locked control");
        pitch(9, 16383); mod_wheel(9, 127);
        byte_in(8'hE9); byte_in(1); reset_dut();
        ready = 1; quiet(0);
        check(errors == 0 && overflows == 0, "control reset left diagnostic state");
        ready = 1; mod_wheel(3, 0); pitch(0, 8192); wait_count(2); quiet(2);
        $display("PASS tb_midi_control_queue clk_hz=%0d min_interval_cycles=%0d checks=%0d control_handshakes=%0d",
                 CLK_HZ, INTERVAL, checks, control_checks);
        $finish;
    end
    initial begin #200000000; $fatal(1, "queue/rate timeout"); end
endmodule
