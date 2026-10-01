// -----------------------------------------------------------------------------
// tb_midi_input.sv
// UART 31250 + MIDI 解析器 + 本地 FIFO 的自动 PASS/FAIL 集成测试。
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module tb_midi_input;

    import audio_defs_pkg::*;

    localparam integer CLK_HZ           = 1_000_000;
    localparam integer MIDI_BAUD        = 31_250;
    localparam integer UART_DIV         = CLK_HZ / MIDI_BAUD;
    localparam integer CLK_PERIOD_NS    = 1_000;
    localparam integer BIT_PERIOD_NS    = CLK_PERIOD_NS * UART_DIV;
    localparam integer LOCAL_FIFO_DEPTH = 4;
    localparam logic [3:0] SOURCE_ID     = 4'd2;

    logic                               clk;
    logic                               rst_n;
    logic                               midi_rx_async;
    logic                               event_ready;
    logic                               event_valid;
    performance_event_t                 event_data;
    logic [15:0]                        event_fifo_level;
    logic [15:0]                        event_fifo_high_watermark;
    logic [31:0]                        uart_frame_error_count;
    logic [31:0]                        parser_error_count;
    logic [31:0]                        event_fifo_overflow_count;
    logic                               midi_rx_busy;

    performance_event_t expected_events [0:63];
    integer expected_write_index;
    integer expected_read_index;
    integer received_count;
    integer check_count;
    integer error_count;

    midi_input #(
        .CLK_HZ           (CLK_HZ),
        .MIDI_BAUD        (MIDI_BAUD),
        .LOCAL_FIFO_DEPTH (LOCAL_FIFO_DEPTH),
        .SOURCE_ID         (SOURCE_ID)
    ) dut (
        .clk                       (clk),
        .rst_n                     (rst_n),
        .midi_rx_async             (midi_rx_async),
        .event_ready               (event_ready),
        .event_valid               (event_valid),
        .event_data                (event_data),
        .event_fifo_level          (event_fifo_level),
        .event_fifo_high_watermark (event_fifo_high_watermark),
        .uart_frame_error_count    (uart_frame_error_count),
        .parser_error_count        (parser_error_count),
        .event_fifo_overflow_count (event_fifo_overflow_count),
        .midi_rx_busy              (midi_rx_busy)
    );

    initial begin
        clk = 1'b0;
        forever #(CLK_PERIOD_NS / 2) clk = ~clk;
    end

    function automatic performance_event_t expected_note_event(
        input logic       is_note_on,
        input logic [3:0] channel_value,
        input logic [6:0] note_value,
        input logic [6:0] velocity_7bit
    );
        performance_event_t result;
        logic [9:0] velocity_10bit;
        begin
            velocity_10bit       = {velocity_7bit, velocity_7bit[6:4]};
            result               = '0;
            result.event_type    = (is_note_on && (velocity_7bit != 7'd0)) ?
                                   EVENT_NOTE_ON : EVENT_NOTE_OFF;
            result.source_id     = SOURCE_ID;
            result.channel       = channel_value;
            result.note_number   = note_value;
            result.velocity      = velocity_10bit;
            expected_note_event  = result;
        end
    endfunction

    task automatic check_value(
        input logic  condition,
        input string description
    );
        begin
            check_count = check_count + 1;
            if (!condition) begin
                error_count = error_count + 1;
                $display("ERROR: %s, time=%0t", description, $time);
            end
        end
    endtask

    task automatic add_expected(
        input logic       is_note_on,
        input logic [3:0] channel_value,
        input logic [6:0] note_value,
        input logic [6:0] velocity_7bit
    );
        begin
            expected_events[expected_write_index] = expected_note_event(
                is_note_on, channel_value, note_value, velocity_7bit
            );
            expected_write_index = expected_write_index + 1;
        end
    endtask

    // 发送真实 8N1 串行波形：低起始位、LSB 优先的 8 位数据、高停止位。
    task automatic send_midi_byte(input logic [7:0] byte_value);
        integer bit_index;
        begin
            @(negedge clk);
            midi_rx_async = 1'b0;
            repeat (UART_DIV) @(negedge clk);

            for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
                midi_rx_async = byte_value[bit_index];
                repeat (UART_DIV) @(negedge clk);
            end

            midi_rx_async = 1'b1;
            repeat (UART_DIV) @(negedge clk);
        end
    endtask

    // 在停止位采样点保持低电平制造帧错误，随后及时释放，避免连带假帧。
    task automatic send_bad_stop_byte(input logic [7:0] byte_value);
        integer bit_index;
        begin
            @(negedge clk);
            midi_rx_async = 1'b0;
            repeat (UART_DIV) @(negedge clk);

            for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
                midi_rx_async = byte_value[bit_index];
                repeat (UART_DIV) @(negedge clk);
            end

            midi_rx_async = 1'b0;
            #((BIT_PERIOD_NS * 6) / 10);
            midi_rx_async = 1'b1;
            #(BIT_PERIOD_NS * 2);
        end
    endtask

    task automatic wait_until_received(input integer target_count);
        integer timeout_count;
        begin
            timeout_count = 0;
            while ((received_count < target_count) && (timeout_count < 200)) begin
                @(negedge clk);
                timeout_count = timeout_count + 1;
            end
            check_value(received_count == target_count,
                        "timed out waiting for MIDI events");
        end
    endtask

    // 只在 ready/valid 真正握手时比较事件。
    always @(posedge clk) begin
        if (rst_n && event_valid && event_ready) begin
            if (expected_read_index >= expected_write_index) begin
                error_count = error_count + 1;
                $display("ERROR: unexpected event 0x%016h, time=%0t",
                         event_data, $time);
            end else if (event_data !== expected_events[expected_read_index]) begin
                error_count = error_count + 1;
                $display("ERROR: event mismatch at index %0d", expected_read_index);
                $display("       expected=0x%016h actual=0x%016h",
                         expected_events[expected_read_index], event_data);
            end
            expected_read_index = expected_read_index + 1;
            received_count      = received_count + 1;
        end
    end

    initial begin
        integer              received_before;
        logic [31:0]         parser_errors_before;
        logic [31:0]         frame_errors_before;
        performance_event_t  held_event;
        performance_event_t  cc_expected;

        rst_n                     = 1'b0;
        midi_rx_async             = 1'b1;
        event_ready               = 1'b0;
        expected_write_index      = 0;
        expected_read_index       = 0;
        received_count            = 0;
        check_count               = 0;
        error_count               = 0;

        // [1] Reset state.
        repeat (5) @(negedge clk);
        check_value(event_valid == 1'b0, "reset must clear event_valid");
        check_value(event_data == '0, "reset must clear visible event_data");
        check_value(event_fifo_level == 16'd0, "reset must clear FIFO level");
        check_value(event_fifo_high_watermark == 16'd0,
                    "reset must clear FIFO high watermark");
        check_value(uart_frame_error_count == 32'd0,
                    "reset must clear UART error count");
        check_value(parser_error_count == 32'd0,
                    "reset must clear parser error count");
        check_value(event_fifo_overflow_count == 32'd0,
                    "reset must clear overflow count");
        rst_n       = 1'b1;
        event_ready = 1'b1;
        repeat (3) @(negedge clk);

        // [2] Note On: channel 1 on the cable is channel field 0.
        add_expected(1'b1, 4'd0, 7'd60, 7'd100);
        send_midi_byte(8'h90);
        send_midi_byte(8'h3C);
        send_midi_byte(8'h64);
        wait_until_received(1);

        // [3] Explicit Note Off preserves its release velocity.
        add_expected(1'b0, 4'd0, 7'd60, 7'd64);
        send_midi_byte(8'h80);
        send_midi_byte(8'h3C);
        send_midi_byte(8'h40);
        wait_until_received(2);

        // [4] Note On velocity zero must become Note Off.
        add_expected(1'b1, 4'd0, 7'd62, 7'd0);
        send_midi_byte(8'h90);
        send_midi_byte(8'h3E);
        send_midi_byte(8'h00);
        wait_until_received(3);

        // [5] Running Status carries two successive notes on MIDI channel 2.
        add_expected(1'b1, 4'd1, 7'd60, 7'd32);
        add_expected(1'b1, 4'd1, 7'd64, 7'd80);
        send_midi_byte(8'h91);
        send_midi_byte(8'h3C);
        send_midi_byte(8'h20);
        send_midi_byte(8'h40);
        send_midi_byte(8'h50);
        wait_until_received(5);

        // [6] Real-time clock F8 may be inserted between note and velocity.
        add_expected(1'b1, 4'd0, 7'd65, 7'd127);
        send_midi_byte(8'h90);
        send_midi_byte(8'h41);
        send_midi_byte(8'hF8);
        send_midi_byte(8'h7F);
        wait_until_received(6);

        // [7] Unsupported Control Change is consumed, including its own
        // Running Status, without producing an event or desynchronizing notes.
        received_before = received_count;
        send_midi_byte(8'hB0);
        send_midi_byte(8'h01);
        send_midi_byte(8'h7F);
        send_midi_byte(8'h41);
        send_midi_byte(8'h01);
        repeat (5) @(negedge clk);
        check_value(received_count == received_before,
                    "unsupported channel message produced an event");
        add_expected(1'b1, 4'd0, 7'd67, 7'd80);
        send_midi_byte(8'h90);
        send_midi_byte(8'h43);
        send_midi_byte(8'h50);
        wait_until_received(7);

        // [8] System Common consumes its declared bytes. Extra data without a
        // status is illegal and increments the parser counter once.
        parser_errors_before = parser_error_count;
        send_midi_byte(8'hF2);
        send_midi_byte(8'h01);
        send_midi_byte(8'h02);
        send_midi_byte(8'h03);
        repeat (3) @(negedge clk);
        check_value(parser_error_count == parser_errors_before + 32'd1,
                    "stray data byte must increment parser error count");

        // [9] A new status recovers from a truncated message and records it.
        parser_errors_before = parser_error_count;
        send_midi_byte(8'h90);
        send_midi_byte(8'h45);
        send_midi_byte(8'h80);
        add_expected(1'b0, 4'd0, 7'd69, 7'd32);
        send_midi_byte(8'h45);
        send_midi_byte(8'h20);
        wait_until_received(8);
        check_value(parser_error_count == parser_errors_before + 32'd1,
                    "truncated message must increment parser error count");

        // [10] SysEx bytes and interleaved real-time bytes are skipped until F7.
        received_before = received_count;
        send_midi_byte(8'hF0);
        send_midi_byte(8'h01);
        send_midi_byte(8'h02);
        send_midi_byte(8'hF8);
        send_midi_byte(8'h03);
        send_midi_byte(8'hF7);
        repeat (5) @(negedge clk);
        check_value(received_count == received_before,
                    "SysEx payload produced an event");
        add_expected(1'b1, 4'd0, 7'd72, 7'd127);
        send_midi_byte(8'h90);
        send_midi_byte(8'h48);
        send_midi_byte(8'h7F);
        wait_until_received(9);

        // [11] Backpressure: four events fill the local FIFO, the fifth is
        // counted as overflow, and the visible head remains stable.
        event_ready = 1'b0;
        add_expected(1'b1, 4'd0, 7'd48, 7'd64);
        add_expected(1'b1, 4'd0, 7'd49, 7'd64);
        add_expected(1'b1, 4'd0, 7'd50, 7'd64);
        add_expected(1'b1, 4'd0, 7'd51, 7'd64);
        send_midi_byte(8'h90);
        send_midi_byte(8'h30);
        send_midi_byte(8'h40);
        send_midi_byte(8'h31);
        send_midi_byte(8'h40);
        send_midi_byte(8'h32);
        send_midi_byte(8'h40);
        send_midi_byte(8'h33);
        send_midi_byte(8'h40);
        send_midi_byte(8'h34);
        send_midi_byte(8'h40);
        repeat (3) @(negedge clk);
        check_value(event_fifo_level == LOCAL_FIFO_DEPTH,
                    "four queued notes must fill the local FIFO");
        check_value(event_fifo_high_watermark == LOCAL_FIFO_DEPTH,
                    "FIFO high watermark must reach four");
        check_value(event_fifo_overflow_count == 32'd1,
                    "fifth queued note must increment overflow count");
        check_value(event_valid == 1'b1,
                    "full FIFO must keep event_valid asserted");
        held_event = event_data;
        repeat (5) begin
            @(negedge clk);
            check_value(event_data == held_event,
                        "event_data changed while ready was low");
        end
        event_ready = 1'b1;
        wait_until_received(13);
        repeat (3) @(negedge clk);
        check_value(event_valid == 1'b0,
                    "overflowed fifth note must not appear later");

        // [12] A bad UART stop bit increments only the frame counter and resets
        // partial parser context. A following correct message must recover.
        frame_errors_before = uart_frame_error_count;
        received_before     = received_count;
        send_bad_stop_byte(8'h90);
        repeat (5) @(negedge clk);
        check_value(uart_frame_error_count == frame_errors_before + 32'd1,
                    "bad stop bit must increment UART frame error count");
        check_value(received_count == received_before,
                    "bad UART frame produced an event");
        add_expected(1'b1, 4'd0, 7'd76, 7'd100);
        send_midi_byte(8'h90);
        send_midi_byte(8'h4C);
        send_midi_byte(8'h64);
        wait_until_received(14);

        // [13] Runtime reset clears queued data, parser state, and all counters.
        event_ready = 1'b0;
        send_midi_byte(8'h90);
        send_midi_byte(8'h55);
        send_midi_byte(8'h40);
        repeat (3) @(negedge clk);
        check_value(event_valid == 1'b1, "pre-reset event was not queued");
        rst_n = 1'b0;
        repeat (3) @(negedge clk);
        check_value(event_valid == 1'b0, "runtime reset did not clear event_valid");
        check_value(event_data == '0, "runtime reset did not clear event_data");
        check_value(event_fifo_level == 16'd0,
                    "runtime reset did not clear FIFO level");
        check_value(event_fifo_high_watermark == 16'd0,
                    "runtime reset did not clear high watermark");
        check_value(uart_frame_error_count == 32'd0,
                    "runtime reset did not clear frame errors");
        check_value(parser_error_count == 32'd0,
                    "runtime reset did not clear parser errors");
        check_value(event_fifo_overflow_count == 32'd0,
                    "runtime reset did not clear overflow count");

        check_value(expected_read_index == expected_write_index,
                    "not all expected events were received");

        // [14] CC64 over the real UART path, including running status and F8.
        // Expected fields are built independently from the public helper.
        rst_n = 1'b1;
        repeat (3) @(negedge clk);
        for (integer cc_index = 0; cc_index < 4; cc_index = cc_index + 1) begin
            cc_expected = '0;
            cc_expected.event_type = EVENT_CONTROL_CHANGE;
            cc_expected.source_id = SOURCE_ID;
            cc_expected.channel = 4'd15;
            cc_expected.control_id = CTRL_SUSTAIN;
            case (cc_index)
                0: cc_expected.control_value = 12'd0;
                1: cc_expected.control_value = 12'd2031;
                2: cc_expected.control_value = 12'd2064;
                3: cc_expected.control_value = 12'd4095;
            endcase
            expected_events[expected_write_index] = cc_expected;
            expected_write_index = expected_write_index + 1;
        end
        event_ready = 1'b1;
        send_midi_byte(8'hBF);
        send_midi_byte(8'h40); send_midi_byte(8'h00);
        send_midi_byte(8'h40); send_midi_byte(8'h3F);
        send_midi_byte(8'h40); send_midi_byte(8'hF8); send_midi_byte(8'h40);
        send_midi_byte(8'h40); send_midi_byte(8'h7F);
        wait_until_received(18);
        check_value(expected_read_index == expected_write_index,
                    "UART CC64 boundary events were not received");

        if (error_count == 0) begin
            $display("PASS: tb_midi_input completed %0d checks", check_count);
        end else begin
            $display("FAIL: tb_midi_input found %0d error(s)", error_count);
            $fatal(1);
        end
        $finish;
    end

    initial begin
        #(BIT_PERIOD_NS * 1000);
        $display("FAIL: tb_midi_input timeout");
        $fatal(1);
    end

endmodule
