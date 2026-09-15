`timescale 1ns/1ps

module tb_button_event_converter;

    import audio_defs_pkg::*;

    localparam integer BUTTON_COUNT       = 2;
    localparam integer LOCAL_FIFO_DEPTH   = 4;
    localparam time    CLK_HALF_PERIOD_NS = 10;

    logic                        clk;
    logic                        rst_n;
    logic [BUTTON_COUNT-1:0]     button_press_pulse;
    logic [BUTTON_COUNT-1:0]     button_release_pulse;
    logic                        event_ready;
    logic                        event_valid;
    performance_event_t          event_data;
    logic [31:0]                 overflow_count;

    performance_event_t expected_events [0:63];
    integer expected_write_index;
    integer expected_read_index;
    integer received_count;
    integer error_count;

    button_event_converter #(
        .BUTTON_COUNT       (BUTTON_COUNT),
        .LOCAL_FIFO_DEPTH   (LOCAL_FIFO_DEPTH),
        .BASE_NOTE_NUMBER   (60),
        .NOTE_STEP          (2),
        .SOURCE_ID          (4'd0),
        .CHANNEL            (4'd0),
        .NOTE_ON_VELOCITY   (10'd512)
    ) dut (
        .clk                 (clk),
        .rst_n               (rst_n),
        .button_press_pulse  (button_press_pulse),
        .button_release_pulse(button_release_pulse),
        .event_ready         (event_ready),
        .event_valid         (event_valid),
        .event_data          (event_data),
        .overflow_count      (overflow_count)
    );

    initial begin
        clk = 1'b0;
        forever #CLK_HALF_PERIOD_NS clk = ~clk;
    end

    function automatic performance_event_t expected_note_event(
        input logic [2:0] event_type_value,
        input logic [6:0] note_number_value
    );
        performance_event_t expected_event;
        begin
            expected_event             = '0;
            expected_event.event_type  = event_type_value;
            expected_event.source_id   = 4'd0;
            expected_event.channel     = 4'd0;
            expected_event.note_number = note_number_value;
            expected_event.velocity    =
                (event_type_value == EVENT_NOTE_ON) ? 10'd512 : 10'd0;
            expected_note_event        = expected_event;
        end
    endfunction

    task automatic check_value(
        input logic  condition,
        input string description
    );
        begin
            if (!condition) begin
                error_count = error_count + 1;
                $display("ERROR: %s, time=%0t", description, $time);
            end
        end
    endtask

    task automatic add_expected(
        input logic [2:0] event_type_value,
        input logic [6:0] note_number_value
    );
        begin
            expected_events[expected_write_index] =
                expected_note_event(event_type_value, note_number_value);
            expected_write_index = expected_write_index + 1;
        end
    endtask

    task automatic drive_pulses(
        input logic [BUTTON_COUNT-1:0] press_value,
        input logic [BUTTON_COUNT-1:0] release_value
    );
        begin
            @(negedge clk);
            button_press_pulse   = press_value;
            button_release_pulse = release_value;
            @(negedge clk);
            button_press_pulse   = {BUTTON_COUNT{1'b0}};
            button_release_pulse = {BUTTON_COUNT{1'b0}};
        end
    endtask

    task automatic wait_until_received(
        input integer target_count
    );
        integer timeout_count;
        begin
            timeout_count = 0;
            while ((received_count < target_count) && (timeout_count < 40)) begin
                @(negedge clk);
                timeout_count = timeout_count + 1;
            end
            check_value(received_count == target_count, "timed out waiting for events");
        end
    endtask

    // 在上升沿、DUT 非阻塞赋值生效前检查真正发生的握手。
    always @(posedge clk) begin
        if (rst_n && event_valid && event_ready) begin
            if (expected_read_index >= expected_write_index) begin
                error_count = error_count + 1;
                $display("ERROR: unexpected event 0x%016h, time=%0t", event_data, $time);
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
        performance_event_t held_event;
        integer              received_before_reset;

        rst_n                 = 1'b0;
        button_press_pulse    = {BUTTON_COUNT{1'b0}};
        button_release_pulse  = {BUTTON_COUNT{1'b0}};
        event_ready           = 1'b0;
        expected_write_index  = 0;
        expected_read_index   = 0;
        received_count        = 0;
        error_count           = 0;

        // 用例 1：复位清除发送状态和溢出计数。
        repeat (3) @(negedge clk);
        check_value(event_valid == 1'b0, "reset must clear event_valid");
        check_value(event_data == '0, "reset must clear visible event_data");
        check_value(overflow_count == 32'd0, "reset must clear overflow_count");
        rst_n       = 1'b1;
        event_ready = 1'b1;

        // 用例 2：按键 0 产生 Note On 60，松开产生 Note Off 60。
        add_expected(EVENT_NOTE_ON, 7'd60);
        drive_pulses(2'b01, 2'b00);
        wait_until_received(1);
        add_expected(EVENT_NOTE_OFF, 7'd60);
        drive_pulses(2'b00, 2'b01);
        wait_until_received(2);

        // 用例 3：按键 1 的映射应为 MIDI 62。
        add_expected(EVENT_NOTE_ON, 7'd62);
        add_expected(EVENT_NOTE_OFF, 7'd62);
        drive_pulses(2'b10, 2'b00);
        drive_pulses(2'b00, 2'b10);
        wait_until_received(4);

        // 用例 4：两键同时按下时，按编号从小到大输出两个独立事件。
        add_expected(EVENT_NOTE_ON, 7'd60);
        add_expected(EVENT_NOTE_ON, 7'd62);
        drive_pulses(2'b11, 2'b00);
        wait_until_received(6);

        // 用例 5：反压期间 valid 和 data 必须保持稳定。
        event_ready = 1'b0;
        add_expected(EVENT_NOTE_OFF, 7'd60);
        add_expected(EVENT_NOTE_OFF, 7'd62);
        drive_pulses(2'b00, 2'b11);
        @(negedge clk);
        check_value(event_valid == 1'b1, "backpressure must keep event_valid asserted");
        held_event = event_data;
        repeat (4) begin
            @(negedge clk);
            check_value(event_valid == 1'b1, "event_valid changed during backpressure");
            check_value(event_data == held_event, "event_data changed during backpressure");
        end
        check_value(received_count == 6, "event transferred while ready was low");
        event_ready = 1'b1;
        wait_until_received(8);

        // 用例 6：填满四项本地 FIFO 后按进入顺序排空。
        event_ready = 1'b0;
        add_expected(EVENT_NOTE_ON, 7'd60);
        add_expected(EVENT_NOTE_ON, 7'd62);
        drive_pulses(2'b11, 2'b00);
        add_expected(EVENT_NOTE_OFF, 7'd60);
        add_expected(EVENT_NOTE_OFF, 7'd62);
        drive_pulses(2'b00, 2'b11);
        check_value(overflow_count == 32'd0, "four queued events must not overflow");
        event_ready = 1'b1;
        wait_until_received(12);

        // 用例 7：FIFO 已满时新增两个事件，必须累计两个溢出而非静默丢弃。
        event_ready = 1'b0;
        add_expected(EVENT_NOTE_ON, 7'd60);
        add_expected(EVENT_NOTE_ON, 7'd62);
        drive_pulses(2'b11, 2'b00);
        add_expected(EVENT_NOTE_OFF, 7'd60);
        add_expected(EVENT_NOTE_OFF, 7'd62);
        drive_pulses(2'b00, 2'b11);
        drive_pulses(2'b11, 2'b00);
        @(negedge clk);
        check_value(overflow_count == 32'd2, "overflow counter must count dropped events");
        event_ready = 1'b1;
        wait_until_received(16);
        repeat (3) @(negedge clk);
        check_value(event_valid == 1'b0, "overflowed events must not appear later");

        // 用例 8：有待发送事件时复位，FIFO 和溢出计数都必须清空。
        event_ready = 1'b0;
        drive_pulses(2'b11, 2'b00);
        @(negedge clk);
        check_value(event_valid == 1'b1, "pre-reset event was not queued");
        received_before_reset = received_count;
        rst_n = 1'b0;
        repeat (2) @(negedge clk);
        check_value(event_valid == 1'b0, "reset did not clear queued events");
        check_value(event_data == '0, "reset did not clear event_data");
        check_value(overflow_count == 32'd0, "reset did not clear overflow_count again");
        check_value(received_count == received_before_reset, "event transferred during reset");

        if (error_count == 0) begin
            $display("PASS: tb_button_event_converter completed all checks");
        end else begin
            $display("FAIL: tb_button_event_converter found %0d error(s)", error_count);
            $fatal(1);
        end

        $finish;
    end

endmodule
