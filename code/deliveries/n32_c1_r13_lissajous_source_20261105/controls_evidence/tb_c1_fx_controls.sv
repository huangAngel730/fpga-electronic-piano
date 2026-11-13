`timescale 1ns/1ps
module tb_c1_fx_controls;
    import audio_defs_pkg::*;
    localparam logic [7:0] CTRL_K2_INSTRUMENT = 8'd18;
    logic clk = 0;
    always #12.5 clk = ~clk;
    logic rst_n = 0;
    logic [7:0] midi_byte = 0;
    logic midi_byte_valid = 0, midi_byte_error = 0;
    logic event_ready = 1;
    wire event_valid;
    performance_event_t event_data;
    wire [2:0] page_select;
    wire [31:0] overflow_count;
    performance_event_t received [0:511];
    integer count = 0;
    integer checked = 0;
    integer instrument = 0;

    midi_event_parser #(.CLK_HZ(40_000_000)) u_parser (
        .clk(clk), .rst_n(rst_n), .midi_byte(midi_byte),
        .midi_byte_valid(midi_byte_valid), .midi_byte_error(midi_byte_error),
        .event_ready(event_ready), .event_valid(event_valid), .event_data(event_data),
        .event_fifo_level(), .event_fifo_high_watermark(),
        .event_fifo_overflow_count(overflow_count), .parser_error_count()
    );
    pro_midi_page_controls u_pages (
        .clk(clk), .rst_n(rst_n), .midi_byte(midi_byte),
        .midi_byte_valid(midi_byte_valid), .midi_byte_error(midi_byte_error),
        .page_select(page_select)
    );

    always @(posedge clk)
        if (rst_n && event_valid && event_ready) begin
            received[count] = event_data;
            count = count + 1;
        end

    task automatic send_byte(input logic [7:0] data, input logic bad = 0);
        @(negedge clk);
        midi_byte = data;
        midi_byte_error = bad;
        midi_byte_valid = 1;
        @(negedge clk);
        midi_byte_valid = 0;
        midi_byte_error = 0;
    endtask

    task automatic cc(input logic [7:0] number, input logic [7:0] value);
        send_byte(number);
        send_byte(value);
    endtask

    task automatic check_event(input logic [7:0] id, input logic [11:0] value);
        repeat (3) @(negedge clk);
        if (checked >= count)
            $fatal(1, "missing event %0d id=%0d value=%0d", checked, id, value);
        if (received[checked].event_type !== EVENT_CONTROL_CHANGE ||
            received[checked].control_id !== id ||
            received[checked].channel !== 4'd3 ||
            received[checked].control_value !== value)
            $fatal(1, "event %0d expected id=%0d value=%0d got id=%0d value=%0d",
                   checked, id, value, received[checked].control_id,
                   received[checked].control_value);
        checked = checked + 1;
    endtask

    task automatic check_page(input logic [2:0] expected);
        if (page_select !== expected)
            $fatal(1, "expected page %0d got %0d", expected, page_select);
    endtask

    initial begin
        repeat (3) @(negedge clk);
        check_page(0);
        rst_n = 1;
        send_byte(8'hB3);
        cc(74, 127);
        check_page(4);
        for (integer value = 0; value < 128; value = value + 1) begin
            case (value)
                26, 51, 76, 101: instrument = instrument + 1;
                default: ;
            endcase
            cc(91, 8'(value));
            check_event(CTRL_K2_INSTRUMENT, 12'(instrument));
            check_page(4);
        end
        for (integer value = 0; value < 128; value = value + 1) begin
            cc(7, 8'(value));
            check_event(CTRL_VOLUME, 12'(value * 32 + value / 4));
            if (received[checked-1].control_value[11:5] !== 7'(value))
                $fatal(1, "CC7 raw value lost: %0d", value);
            check_page(4);
        end

        cc(71, 0);   check_page(0);
        cc(71, 60);  check_page(0);
        cc(71, 61);  check_page(1);
        cc(71, 127); check_page(1);
        for (integer value = 0; value < 128; value = value + 1) begin
            cc(74, 8'(value));
            check_page(value <= 40 ? 3'd2 : value <= 80 ? 3'd3 : 3'd4);
        end
        cc(71, 127); check_page(1);
        if (count != checked)
            $fatal(1, "display controls generated audio events");

        // Realtime may interrupt a message. Repeating the same absolute
        // value must enqueue another selection, including while stalled.
        event_ready = 0;
        send_byte(91);
        send_byte(8'hF8);
        send_byte(31);
        cc(91, 31);
        repeat (2) @(negedge clk);
        if (count != checked || !event_valid || event_data.control_value !== 12'd1)
            $fatal(1, "stalled K2 FIFO head invalid");
        event_ready = 1;
        check_event(CTRL_K2_INSTRUMENT, 12'd1);
        check_event(CTRL_K2_INSTRUMENT, 12'd1);

        // Error and system messages clear running status and do not change
        // the selected page or enqueue a fabricated K1/K2 event.
        send_byte(91);
        send_byte(127, 1);
        cc(71, 0);
        cc(91, 0);
        send_byte(8'hF0);
        cc(71, 0);
        cc(91, 0);
        send_byte(8'hF7);
        send_byte(8'hF2);
        cc(91, 0);
        check_page(1);
        if (count != checked)
            $fatal(1, "invalid message generated an event");

        send_byte(8'hC3);
        send_byte(4);
        check_event(CTRL_VOICE_SELECT, 12'd4);
        send_byte(127);
        check_event(CTRL_VOICE_SELECT, 12'd127);
        check_page(1);

        send_byte(8'hB3);
        send_byte(71);
        rst_n = 0;
        repeat (3) @(negedge clk);
        check_page(0);
        rst_n = 1;
        send_byte(127);
        repeat (3) @(negedge clk);
        check_page(0);
        if (count != checked || overflow_count != 0)
            $fatal(1, "unexpected event or FIFO overflow");
        $display("PASS C1_FX_CONTROLS CC91=128 CC7=128 CC74=128 events=%0d",
                 checked);
        $finish;
    end

    initial begin
        #160000;
        $fatal(1, "watchdog");
    end
endmodule
