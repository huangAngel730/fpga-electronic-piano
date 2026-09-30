// T025 full-top STAT black-box check: real MIDI bytes -> live U15 UART text.
// Fast-clock simulation verifies telemetry plumbing, not audio sample rate.
`timescale 1ns/1ps
module tb_t025_top_stat;
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
    logic [31:0] clips, voices, level, watermark, overflow, underrun, processing;
    logic injected=0;
    integer commits_before;

    electronic_piano_top #(.CLK_HZ(1_000_000), .DEBOUNCE_CNT(1000)) dut (
        .sys_clk, .sys_rst_n, .key_n, .midi_rx,
        .i2s_bclk, .i2s_lrck, .i2s_din, .pa_en, .uart_tx
    );
    defparam dut.u_i2s_tx.ACC_BITS=8;
    defparam dut.u_i2s_tx.BCLK_PHASE_STEP=8'd255;
    // Shorten only reporting interval to allow two snapshots in this test.
    defparam dut.u_uart_status_reporter.REPORT_CYCLES = 25_000;
    uart_rx #(.CLK_HZ(1_000_000), .BAUD(115_200)) monitor (
        .clk(sys_clk), .rst_n(sys_rst_n), .rx(uart_tx),
        .rx_data, .rx_valid, .frame_err, .rx_busy
    );
    task automatic check(input logic ok, input string label);
        if (ok !== 1'b1) $fatal(1,"T025 top STAT: %s",label);
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
            check(line.len() == 213,"fixed-length STAT line including CRLF");
            fields = $sscanf(line,
                "STAT active_voice_count=0x%h clip_count=0x%h event_fifo_level=0x%h event_fifo_high_watermark=0x%h event_fifo_overflow=0x%h audio_underrun=0x%h max_processing_cycles=0x%h",
                voices,clips,level,watermark,overflow,underrun,processing);
            check(fields == 7,"seven numeric fields");
            check(voices <= 4,"single note lifecycle includes Release tail");
            if(lines==0)check(voices==4,"first STAT shows four concurrent MIDI identities");
            check(level == 0 && watermark >= 1 && watermark <= 32,
                  "public event FIFO drained and peak observed");
            check(clips == 0 || (injected && clips==1),"clip count originates from accepted saturated PCM");
            check(underrun==0,"no audio underrun during normal telemetry");
            check(overflow == 0,"no event source dropped a MIDI event");
            check(processing > 0,"request to PCM commit peak is live");
            $display("STAT line %0d: voice=%0d level=%0d high=%0d overflow=%0d underrun=%0d processing=%0d",
                     lines, voices, level, watermark, overflow, underrun, processing);
            $display("UART_RECORD %s",line);
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
        send_byte(8'h90); send_byte(8'h40); send_byte(8'h52);
        send_byte(8'h90); send_byte(8'h43); send_byte(8'h46);
        send_byte(8'h90); send_byte(8'h48); send_byte(8'h5a);
        wait(lines == 1);
        send_byte(8'h80); send_byte(8'h3c); send_byte(8'h00);
        send_byte(8'h80); send_byte(8'h40); send_byte(8'h00);
        send_byte(8'h80); send_byte(8'h43); send_byte(8'h00);
        send_byte(8'h80); send_byte(8'h48); send_byte(8'h00);
        wait(dut.status_active_voice_count == 0);
        wait(lines >= 2 && voices == 0);
        // Explicit fault injection on arithmetic inputs, never a normal sound claim.
        wait(dut.g_polyphonic.u_audio_core.bank_valid);
        @(negedge sys_clk);commits_before=dut.pcm_commit_count;
        injected=1;
        force dut.g_polyphonic.u_audio_core.voices=96'h2dc6c02dc6c02dc6c02dc6c0;
        wait(dut.pcm_commit_count==commits_before+1);
        @(negedge sys_clk);release dut.g_polyphonic.u_audio_core.voices;
        check(dut.status_clip_count==1,"one fault-injected accepted stereo clip counted");
        wait(clips==1);
        check(voices==0,"post-Release UART snapshot contains zero occupied voices");
        sys_rst_n = 0;
        repeat (5) @(negedge sys_clk);
        check(pa_en === 1'b1 && uart_tx === 1'b1,"reset mutes amp and UART idles");
        check(dut.status_clip_count==0,"reset clears clip counter");
        $display("PASS tb_t025_top_stat checks=%0d lines=%0d",checks,lines);
        $finish;
    end
    initial begin #4_000_000_000; $fatal(1,"T025 top STAT timeout lines=%0d",lines); end
endmodule
