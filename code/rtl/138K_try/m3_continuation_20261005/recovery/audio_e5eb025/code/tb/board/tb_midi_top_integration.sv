// End-to-end physical MIDI RX pin -> decoder -> shared FIFO -> voice.
`timescale 1ns/1ps
module tb_midi_top_integration;
    localparam integer BIT_CYCLES = 1600; // 50 MHz / 31250 baud
    logic sys_clk = 0;
    always #10 sys_clk = ~sys_clk;
    logic sys_rst_n = 0;
    logic [1:0] key_n = 2'b11;
    logic midi_rx = 1;
    logic i2s_bclk, i2s_lrck, i2s_din, pa_en, uart_tx;
    integer checks = 0;

    electronic_piano_top dut (
        .sys_clk, .sys_rst_n, .key_n, .midi_rx,
        .i2s_bclk, .i2s_lrck, .i2s_din, .pa_en, .uart_tx
    );

    // Accelerate only audio frames for lifecycle test; UART remains actual 50MHz/31250.
    defparam dut.u_i2s_tx.ACC_BITS=8;
    defparam dut.u_i2s_tx.BCLK_PHASE_STEP=8'd255;

    task automatic check(input bit ok, input string reason);
        if (!ok) $fatal(1, "%s", reason);
        checks++;
    endtask

    task automatic send_byte(input logic [7:0] value);
        @(negedge sys_clk); midi_rx = 0;
        repeat (BIT_CYCLES) @(negedge sys_clk);
        for (integer i=0; i<8; i++) begin
            midi_rx = value[i];
            repeat (BIT_CYCLES) @(negedge sys_clk);
        end
        midi_rx = 1;
        repeat (BIT_CYCLES) @(negedge sys_clk);
    endtask

    initial begin
        repeat (5) @(negedge sys_clk);
        check(pa_en === 1'b1, "power amp disabled in reset");
        sys_rst_n = 1;
        repeat (5) @(negedge sys_clk);
        check(!dut.voice_active && !dut.shared_event_valid &&
              dut.event_fifo_level == 0, "idle with MIDI RX high");

        send_byte(8'h90); send_byte(8'h3c); send_byte(8'h64);
        repeat (30) @(negedge sys_clk);
        check(dut.voice_active && dut.voice_note == 7'd60,
              "MIDI Note On reaches voice through common FIFO");
        check(dut.event_fifo_high_watermark > 0 &&
              dut.event_fifo_level == 0 && dut.midi_event_overflow == 0,
              "shared FIFO drained and no input drop");

        send_byte(8'h80); send_byte(8'h3c); send_byte(8'h00);
        repeat (5) @(negedge sys_clk);
        check(dut.voice_active, "MIDI Note Off keeps actual Release tail occupied");
        wait(dut.status_active_voice_count==0);
        repeat(3)@(negedge sys_clk);
        check(!dut.voice_active, "Release completion retires voice");
        check(dut.event_fifo_level == 0 && dut.midi_event_overflow == 0,
              "shared FIFO clean after MIDI Note Off");

        sys_rst_n = 0;
        repeat (4) @(negedge sys_clk);
        check(pa_en === 1'b1 && !dut.voice_active &&
              dut.event_fifo_level == 0 && dut.event_fifo_high_watermark == 0,
              "reset clears voice and event counters");
        $display("PASS tb_midi_top_integration checks=%0d", checks);
        $finish;
    end
    initial begin #50_000_000; $fatal(1, "MIDI top timeout"); end
endmodule
