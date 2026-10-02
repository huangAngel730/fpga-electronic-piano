// Exhaustive Program Change mapping and discrete-FIFO parser coverage.
`timescale 1ns / 1ps
module tb_midi_program_change;
    import audio_defs_pkg::*;
    logic clk = 0, rst_n = 0, ready = 0;
    always #10 clk = ~clk;
    logic [7:0] midi_byte = 0;
    logic midi_byte_valid = 0, midi_byte_error = 0;
    wire [1:0] valid;
    performance_event_t data [0:1];
    wire [15:0] level [0:1], peak [0:1];
    wire [31:0] overflows [0:1], errors [0:1];
    performance_event_t expected [0:4095];
    integer written = 0, received [0:1], checks = 0;
    integer channel_number, program_number, source_number;
    genvar instance_number;

    generate for (instance_number = 0; instance_number < 2; instance_number++) begin : sources
        midi_event_parser #(
            .LOCAL_FIFO_DEPTH(4),
            .SOURCE_ID(instance_number == 0 ? 4'd2 : 4'd13),
            .CLK_HZ(1000)
        ) dut (
            .clk(clk), .rst_n(rst_n), .midi_byte(midi_byte),
            .midi_byte_valid(midi_byte_valid), .midi_byte_error(midi_byte_error),
            .event_ready(ready), .event_valid(valid[instance_number]),
            .event_data(data[instance_number]), .event_fifo_level(level[instance_number]),
            .event_fifo_high_watermark(peak[instance_number]),
            .event_fifo_overflow_count(overflows[instance_number]),
            .parser_error_count(errors[instance_number])
        );
        always @(posedge clk) begin : monitor
            performance_event_t wanted;
            if (!rst_n) begin
                received[instance_number] = 0;
            end else if (valid[instance_number] && ready) begin
                if (received[instance_number] >= written)
                    $fatal(1, "unexpected Program event source=%0d", instance_number);
                wanted = expected[received[instance_number]];
                wanted.source_id = instance_number == 0 ? 2 : 13;
                if (data[instance_number] !== wanted)
                    $fatal(1, "Program payload source=%0d index=%0d expected=%h actual=%h",
                           instance_number, received[instance_number], wanted,
                           data[instance_number]);
                received[instance_number]++;
                checks++;
            end
        end
    end endgenerate

    task automatic check(input logic condition, input string reason);
        checks++;
        if (condition !== 1'b1) $fatal(1, "%s at %0t", reason, $time);
    endtask

    task automatic send_byte(input logic [7:0] value, input logic bad = 0);
        @(negedge clk); midi_byte = value; midi_byte_valid = 1; midi_byte_error = bad;
        @(negedge clk); midi_byte_valid = 0; midi_byte_error = 0;
    endtask

    task automatic expect_program(input integer channel_value, input integer raw_value);
        performance_event_t event_value;
        event_value = '0;
        event_value.event_type = EVENT_CONTROL_CHANGE;
        event_value.channel = 4'(channel_value);
        event_value.control_id = CTRL_VOICE_SELECT;
        event_value.control_value = 12'(raw_value);
        expected[written++] = event_value;
    endtask

    task automatic expect_note(input logic is_on, input integer channel_value,
                               input integer note_value, input integer velocity_value);
        performance_event_t event_value;
        event_value = '0;
        event_value.event_type = is_on && velocity_value != 0 ? EVENT_NOTE_ON : EVENT_NOTE_OFF;
        event_value.channel = 4'(channel_value);
        event_value.note_number = 7'(note_value);
        event_value.velocity = (10'(velocity_value) << 3) | (10'(velocity_value) >> 4);
        expected[written++] = event_value;
    endtask

    task automatic expect_control(input logic is_pitch, input integer channel_value,
                                  input integer control_value);
        performance_event_t event_value;
        event_value = '0;
        event_value.event_type = is_pitch ? EVENT_PITCH_BEND : EVENT_CONTROL_CHANGE;
        event_value.channel = 4'(channel_value);
        event_value.control_id = is_pitch ? CTRL_PITCH_BEND : CTRL_SUSTAIN;
        event_value.control_value = 12'(control_value);
        expected[written++] = event_value;
    endtask

    task automatic drain;
        integer guard;
        ready = 1;
        guard = 0;
        while ((received[0] < written || received[1] < written) && guard < 100) begin
            @(negedge clk); guard++;
        end
        repeat (3) @(negedge clk);
        check(received[0] == written && received[1] == written && valid == 0,
              "missing or duplicate Program event");
    endtask

    task automatic reset_dut;
        @(negedge clk); rst_n = 0; ready = 0; midi_byte_valid = 0;
        repeat (3) @(negedge clk);
        written = 0;
        rst_n = 1;
        repeat (2) @(negedge clk);
    endtask

    initial begin
        performance_event_t held;
        integer before_count, before_errors;
        received[0] = 0; received[1] = 0;
        reset_dut(); ready = 1;

        // All 16 channels and all 128 raw program values, including running
        // status and every realtime status interleaved before the data byte.
        for (channel_number = 0; channel_number < 16; channel_number++) begin
            send_byte(8'hC0 | 8'(channel_number));
            for (program_number = 0; program_number < 128; program_number++) begin
                expect_program(channel_number, program_number);
                send_byte(8'hF8 | 8'(program_number % 8));
                send_byte(8'(program_number));
            end
        end
        drain();
        check(written == 2048, "16x128 Program sweep count");
        check(errors[0] == 0 && errors[1] == 0 &&
              overflows[0] == 0 && overflows[1] == 0,
              "clean Program sweep diagnostics");

        // Same value is a discrete command and must be emitted every time.
        send_byte(8'hC1);
        expect_program(1, 1); send_byte(1);
        expect_program(1, 0); send_byte(0);
        expect_program(1, 127); send_byte(8'hFF); send_byte(127);
        expect_program(1, 127); send_byte(127);
        drain();

        // Channel pressure remains consumed without output. Other channel
        // message sizes remain aligned and retain their original mappings.
        before_count = written;
        send_byte(8'hD4); send_byte(1); send_byte(8'hF8); send_byte(127);
        repeat (3) @(negedge clk);
        check(received[0] == before_count && received[1] == before_count,
              "Channel Pressure emitted an event");
        expect_note(0, 5, 60, 64);
        send_byte(8'h85); send_byte(60); send_byte(64);
        expect_note(1, 6, 61, 100);
        send_byte(8'h96); send_byte(61); send_byte(100);
        expect_control(0, 7, 4095);
        send_byte(8'hB7); send_byte(64); send_byte(127);
        expect_control(1, 8, 0);
        send_byte(8'hE8); send_byte(0); send_byte(64);
        drain();

        // System common, SysEx and a bad UART byte clear Program running status.
        before_errors = errors[0];
        send_byte(8'hC2); send_byte(8'hF2); send_byte(0); send_byte(0); send_byte(7);
        send_byte(8'hC2); send_byte(8'hF0); send_byte(7); send_byte(8'hF7); send_byte(8);
        send_byte(8'hC2); send_byte(9, 1); send_byte(10);
        repeat (3) @(negedge clk);
        check(errors[0] == before_errors + 3 && errors[1] == before_errors + 3,
              "Program context cancellation error count");

        // FIFO capacity, repeated values, stable backpressure, overflow and a
        // full same-edge pop/push all use the unchanged discrete path.
        reset_dut(); ready = 0;
        send_byte(8'hC7);
        for (program_number = 0; program_number < 5; program_number++) begin
            if (program_number < 4) expect_program(7, program_number);
            send_byte(8'(program_number));
        end
        check(level[0] == 4 && level[1] == 4 && overflows[0] == 1 && overflows[1] == 1,
              "Program FIFO full or overflow accounting");
        held = data[0];
        repeat (4) begin
            @(negedge clk);
            check(valid[0] && data[0] === held && data[1].control_value == held.control_value,
                  "Program payload changed under backpressure");
        end
        expect_program(7, 127);
        @(negedge clk); midi_byte = 127; midi_byte_valid = 1; ready = 1;
        @(negedge clk); midi_byte_valid = 0;
        drain();
        check(overflows[0] == 1 && overflows[1] == 1,
              "Program full FIFO pop/push overflowed");

        // Reset removes a queued command and one-byte running status context.
        ready = 0; send_byte(8'hC0); expect_program(0, 12); send_byte(12);
        send_byte(8'hC3);
        @(negedge clk); rst_n = 0; repeat (2) @(negedge clk);
        check(!valid[0] && !valid[1] && level[0] == 0 && level[1] == 0,
              "reset retained Program FIFO data");
        written = 0; rst_n = 1; ready = 1;
        send_byte(13); repeat (2) @(negedge clk);
        check(errors[0] == 1 && errors[1] == 1,
              "reset retained Program running status");
        expect_program(15, 0); send_byte(8'hCF); send_byte(0); drain();

        for (source_number = 0; source_number < 2; source_number++)
            check(received[source_number] == written, "source Program count mismatch");
        $display("PASS tb_midi_program_change programs=2048 channels=16 sources=2 checks=%0d",
                 checks);
        $finish;
    end

    initial begin #2000000; $fatal(1, "Program Change parser timeout"); end
endmodule
