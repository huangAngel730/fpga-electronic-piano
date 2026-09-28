// T025 full-top DIAG black-box check: real MIDI bytes -> live U15 UART text.
// Fast-clock simulation verifies telemetry plumbing, not audio sample rate.
`timescale 1ns/1ps
module tb_t025_top_diag;
    localparam integer MIDI_BIT_CYCLES = 32; // 1MHz / 31250
    logic sys_clk = 0;
    always #500 sys_clk = ~sys_clk;
    logic sys_rst_n = 0;
    logic [1:0] key_n = 2'b11;
    logic midi_rx = 1;
    logic i2s_bclk, i2s_lrck, i2s_din, pa_en, uart_tx;
    logic [7:0] rx_data;
    logic rx_valid, frame_err, rx_busy;
    string line = "";
    integer lines = 0, checks = 0, fields;
    logic [31:0] voices, level, watermark, overflow, underrun, processing;

    electronic_piano_top #(.CLK_HZ(1_000_000), .DEBOUNCE_CNT(1000)) dut (
        .sys_clk, .sys_rst_n, .key_n, .midi_rx,
        .i2s_bclk, .i2s_lrck, .i2s_din, .pa_en, .uart_tx
    );
    // Shorten only reporting interval to allow two snapshots in this test.
    defparam dut.u_uart_status_reporter.REPORT_CYCLES = 25_000;
    uart_rx #(.CLK_HZ(1_000_000), .BAUD(115_200)) monitor (
        .clk(sys_clk), .rst_n(sys_rst_n), .rx(uart_tx),
        .rx_data, .rx_valid, .frame_err, .rx_busy
    );
    task automatic check(input logic ok, input string label);
        if (ok !== 1'b1) $fatal(1,"T025 top DIAG: %s",label);
        checks++;
    endtask
    task automatic send_byte(input logic [7:0] value);
        @(negedge sys_clk); midi_rx = 0;
        repeat (MIDI_BIT_CYCLES) @(negedge sys_clk);
        for (integer k=0;k<8;k++) begin
            midi_rx = value[k];
            repeat (MIDI_BIT_CYCLES) @(negedge sys_clk);
        end
        midi_rx = 1;
        repeat (MIDI_BIT_CYCLES) @(negedge sys_clk);
    endtask
    always @(posedge sys_clk) if (sys_rst_n && rx_valid) begin
        check(!frame_err,"decoded U15 byte has no UART framing error");
        line = {line,rx_data};
        if (rx_data == 8'h0a) begin
            check(line.len() == 213,"fixed-length DIAG line including CRLF");
            fields = $sscanf(line,
                "DIAG active_voice_count=0x%h clip_count=0x-------- event_fifo_level=0x%h event_fifo_high_watermark=0x%h event_fifo_overflow=0x%h audio_underrun=0x%h max_processing_cycles=0x%h",
                voices,level,watermark,overflow,underrun,processing);
            check(fields == 6,"six numeric fields and unavailable clip marker");
            check(voices == (lines == 0 ? 1 : 0),"live voice follows MIDI Note On/Off");
            check(level == 0 && watermark >= 1 && watermark <= 32,
                  "public event FIFO drained and peak observed");
            check(overflow == 0,"no event source dropped a MIDI event");
            check(processing > 0,"request to PCM commit peak is live");
            $display("DIAG line %0d: voice=%0d level=%0d high=%0d overflow=%0d underrun=%0d processing=%0d",
                     lines, voices, level, watermark, overflow, underrun, processing);
            lines++;
            line = "";
        end
    end
    initial begin
        repeat (5) @(negedge sys_clk);
        check(pa_en === 1'b1,"reset disables amplifier");
        sys_rst_n = 1;
        repeat (5) @(negedge sys_clk);
        send_byte(8'h90); send_byte(8'h3c); send_byte(8'h64);
        wait(lines == 1);
        send_byte(8'h80); send_byte(8'h3c); send_byte(8'h00);
        wait(lines == 2);
        sys_rst_n = 0;
        repeat (5) @(negedge sys_clk);
        check(pa_en === 1'b1 && uart_tx === 1'b1,"reset mutes amp and UART idles");
        $display("PASS tb_t025_top_diag checks=%0d lines=%0d",checks,lines);
        $finish;
    end
    initial begin #100_000_000; $fatal(1,"T025 top DIAG timeout lines=%0d",lines); end
endmodule
