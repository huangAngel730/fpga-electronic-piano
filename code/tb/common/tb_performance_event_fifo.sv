`timescale 1ns/1ps
module tb_performance_event_fifo;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0;
    logic button_valid = 0, button_ready;
    logic midi_valid = 0, midi_ready;
    logic event_valid, event_ready = 0;
    audio_defs_pkg::performance_event_t button_data, midi_data, event_data;
    logic [15:0] event_fifo_level, event_fifo_high_watermark;
    integer checks = 0;

    performance_event_fifo #(.DEPTH(3)) dut (.*);

    task automatic check(input bit ok, input string label);
        if (!ok) $fatal(1, "%s", label);
        checks++;
    endtask

    initial begin
        button_data = '0;
        midi_data = '0;
        repeat (3) @(negedge clk);
        check(!event_valid && !button_ready && !midi_ready &&
              event_fifo_level == 0 && event_fifo_high_watermark == 0,
              "reset state");
        rst_n = 1;
        button_valid = 1;
        midi_valid = 1;
        button_data = 64'h11;
        midi_data = 64'h22;
        #1;
        check(button_ready && !midi_ready, "first concurrent grant to button");
        @(negedge clk);
        button_data = 64'h33; // prior button event already accepted
        #1;
        check(!button_ready && midi_ready && event_fifo_level == 1,
              "second concurrent grant to MIDI");
        @(negedge clk);
        midi_valid = 0;
        #1;
        check(button_ready && event_fifo_level == 2,
              "remaining button event accepted");
        @(negedge clk);
        button_data = 64'h44;
        #1;
        check(event_fifo_level == 3 && event_fifo_high_watermark == 3 &&
              !button_ready && event_valid && event_data == 64'h11,
              "full queue backpressure preserves oldest event");
        event_ready = 1;
        #1;
        check(button_ready && event_data == 64'h11,
              "full queue permits push on concurrent pop");
        @(negedge clk);
        button_valid = 0;
        #1;
        check(event_fifo_level == 3 && event_data == 64'h22 &&
              event_fifo_high_watermark == 3, "concurrent transfer and pointer wrap");
        @(negedge clk);
        #1;
        check(event_fifo_level == 2 && event_data == 64'h33,
              "MIDI event retained in order");
        @(negedge clk);
        #1;
        check(event_fifo_level == 1 && event_data == 64'h44,
              "new button event retained after wrap");
        @(negedge clk);
        #1;
        check(event_fifo_level == 0 && !event_valid &&
              event_fifo_high_watermark == 3, "queue empty retains historical peak");
        event_ready = 0;
        button_valid = 1;
        button_data = 64'h55;
        @(negedge clk);
        button_valid = 0;
        rst_n = 0;
        @(negedge clk);
        #1;
        check(!event_valid && event_fifo_level == 0 &&
              event_fifo_high_watermark == 0, "mid-stream reset clears queue and peak");
        $display("PASS tb_performance_event_fifo checks=%0d", checks);
        $finish;
    end
    initial begin #10000; $fatal(1, "FIFO timeout"); end
endmodule
