// Exhaustive real-parser mapping with independent expected packed payloads.
`timescale 1ns / 1ps
module tb_midi_controls;
    import audio_defs_pkg::*;
    logic clk = 0, rst_n = 0;
    always #10 clk = ~clk;
    logic [7:0] midi_byte = 0;
    logic midi_byte_valid = 0, midi_byte_error = 0;
    wire [1:0] event_valid;
    performance_event_t event_data [0:1];
    wire [31:0] errors [0:1], overflows [0:1];
    wire [15:0] level [0:1], peak [0:1];
    performance_event_t expected [0:19000];
    integer written = 0, received [0:1], checks = 0, value, channel_number;
    genvar instance_number;
    generate for (instance_number = 0; instance_number < 2; instance_number++) begin : sources
        midi_event_parser #(.SOURCE_ID(instance_number == 0 ? 4'd3 : 4'd12),
                            .LOCAL_FIFO_DEPTH(4), .CLK_HZ(1000)) dut (
            .clk(clk), .rst_n(rst_n), .midi_byte(midi_byte),
            .midi_byte_valid(midi_byte_valid), .midi_byte_error(midi_byte_error),
            .event_ready(1'b1), .event_valid(event_valid[instance_number]),
            .event_data(event_data[instance_number]),
            .event_fifo_level(level[instance_number]),
            .event_fifo_high_watermark(peak[instance_number]),
            .event_fifo_overflow_count(overflows[instance_number]),
            .parser_error_count(errors[instance_number])
        );
        always @(posedge clk) begin : monitor
            performance_event_t ev;
            if (rst_n && event_valid[instance_number]) begin
                if (received[instance_number] >= written)
                    $fatal(1, "unexpected source %0d event", instance_number);
                ev = expected[received[instance_number]];
                ev.source_id = instance_number == 0 ? 3 : 12;
                if (event_data[instance_number] !== ev)
                    $fatal(1, "mapping source=%0d index=%0d expected=%h got=%h",
                           instance_number, received[instance_number], ev,
                           event_data[instance_number]);
                received[instance_number]++;
                checks++;
            end
        end
    end endgenerate
    task automatic check(input logic condition, input string reason);
        checks++;
        if (condition !== 1'b1) $fatal(1, "%s at %0t", reason, $time);
    endtask
    task automatic byte_in(input logic [7:0] b, input logic bad = 0);
        @(negedge clk); midi_byte = b; midi_byte_valid = 1; midi_byte_error = bad;
        @(negedge clk); midi_byte_valid = 0; midi_byte_error = 0;
    endtask
    task automatic expect_control(input logic is_mod, input integer channel_value,
                                  input integer raw_value);
        performance_event_t ev;
        ev = '0;
        ev.event_type = is_mod ? 3'd4 : 3'd3;
        ev.channel = 4'(channel_value);
        ev.control_id = is_mod ? 8'd1 : 8'd0;
        // No call to the RTL's mapping helpers in the expectation.
        ev.control_value = is_mod ? 12'(raw_value * 32 + raw_value / 4) :
                                           12'(raw_value / 4 - 2048);
        expected[written++] = ev;
    endtask
    task automatic drain;
        repeat (8) @(negedge clk);
        check(received[0] == written && received[1] == written && event_valid == 0,
              "missing/extra final mapped event");
    endtask
    task automatic reset_dut;
        @(negedge clk); rst_n = 0;
        repeat (3) @(negedge clk); rst_n = 1;
    endtask
    initial begin
        performance_event_t ev;
        received[0] = 0; received[1] = 0;
        reset_dut();
        // Every one of the 16384 raw bends goes through the actual byte parser
        // and output handshake. All sixteen channels and two source IDs covered.
        for (value = 0; value < 16384; value++) begin
            channel_number = value % 16;
            expect_control(0, channel_number, value);
            byte_in(8'hE0 | 8'(channel_number));
            byte_in(8'(value % 128));
            if (value % 128 == 0) byte_in(8'hF8 | 8'(value / 128 % 8));
            byte_in(8'(value / 128));
        end
        drain(); check(written == 16384, "pitch full sweep count");
        for (channel_number = 0; channel_number < 16; channel_number++) begin
            byte_in(8'hB0 | 8'(channel_number));
            for (value = 0; value < 128; value++) begin
                expect_control(1, channel_number, value);
                byte_in(1); byte_in(8'hF8 | 8'(value % 8)); byte_in(8'(value));
            end
        end
        drain(); check(written == 18432, "CC1 16x128 sweep count");
        check(errors[0] == 0 && errors[1] == 0 &&
              overflows[0] == 0 && overflows[1] == 0, "clean mapping counters");
        // Pitch running status, all realtime statuses, signed boundary/center.
        byte_in(8'hEF);
        for (value = 0; value < 8; value++) begin
            expect_control(0, 15, value < 4 ? 8191 : 8192);
            byte_in(value < 4 ? 127 : 0); byte_in(8'hF8 | 8'(value));
            byte_in(value < 4 ? 63 : 64);
        end
        drain();
        // Truncation, bad UART frame, system common/SysEx cancellation.
        byte_in(8'hE1); byte_in(1); byte_in(8'hB2);
        expect_control(1, 2, 63); byte_in(1); byte_in(63); drain();
        check(errors[0] == 1 && errors[1] == 1, "truncated pitch error");
        byte_in(8'hE3); byte_in(127); byte_in(127, 1);
        byte_in(64); // no running status after a bad frame
        byte_in(8'hE3); byte_in(8'hF2); byte_in(0); byte_in(64); byte_in(1);
        byte_in(8'hE4); byte_in(8'hF0); byte_in(0); byte_in(8'hFF);
        byte_in(64); byte_in(8'hF7); byte_in(1);
        drain(); check(errors[0] == 4 && errors[1] == 4, "context cancellation errors");
        // Unsupported controls never masquerade as modulation or global panic.
        byte_in(8'hB0); byte_in(121); byte_in(0); byte_in(123); byte_in(0);
        byte_in(2); byte_in(127); drain();
        // Velocity=0 and CC64 remain literal independent payloads.
        ev = '0; ev.event_type = 1; ev.channel = 6; ev.note_number = 60;
        expected[written++] = ev;
        byte_in(8'h96); byte_in(60); byte_in(0);
        ev = '0; ev.event_type = 4; ev.channel = 6;
        ev.control_id = 6; ev.control_value = 4095; expected[written++] = ev;
        byte_in(8'hB6); byte_in(64); byte_in(127); drain();
        byte_in(8'hE0); byte_in(0); reset_dut(); byte_in(64);
        check(errors[0] == 1 && errors[1] == 1, "reset retained partial running status");
        expect_control(0, 0, 8192); byte_in(8'hE0); byte_in(0); byte_in(64);
        expect_control(1, 0, 0); byte_in(8'hB0); byte_in(1); byte_in(0); drain();
        $display("PASS tb_midi_controls pitch_raw=16384 cc1_raw=128 channels=16 sources=2 events_per_source=%0d checks=%0d",
                 written, checks);
        $finish;
    end
    initial begin #5000000; $fatal(1, "mapping timeout"); end
endmodule
