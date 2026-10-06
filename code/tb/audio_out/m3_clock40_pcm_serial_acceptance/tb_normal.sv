// Real sealed L audio chain. 40 MHz domain stimulus, not a PLL test.
`timescale 1ns/1ps
module tb_normal;
    import audio_defs_pkg::*;
    reg clk = 0, rst_n = 0, midi_rx = 1;
    always #12.5 clk = ~clk;
    wire midi_valid, midi_ready, event_valid, event_ready, button_ready;
    performance_event_t midi_data, event_data;
    wire [15:0] fifo_level, fifo_high, local_level, local_high;
    wire [31:0] uart_errors, parser_errors, overflow, voices, clip,
                underrun, frames, requests, commits, latency;
    wire signed [23:0] play_left, play_right;
    wire pending, bclk, ws, din, ready, frame_tick, midi_busy;
    integer events = 0;
    midi_input #(.CLK_HZ(40_000_000)) u_midi (
        .clk, .rst_n, .midi_rx_async(midi_rx), .event_ready(midi_ready),
        .event_valid(midi_valid), .event_data(midi_data),
        .event_fifo_level(local_level), .event_fifo_high_watermark(local_high),
        .uart_frame_error_count(uart_errors), .parser_error_count(parser_errors),
        .event_fifo_overflow_count(overflow), .midi_rx_busy(midi_busy));
    performance_event_fifo #(.DEPTH(32)) u_fifo (
        .clk, .rst_n, .button_valid(1'b0), .button_ready,
        .button_data(64'd0), .midi_valid, .midi_ready, .midi_data,
        .event_valid, .event_ready, .event_data, .event_fifo_level(fifo_level),
        .event_fifo_high_watermark(fifo_high));
    polyphonic_audio_core u_core (
        .clk, .rst_n, .event_valid, .event_ready, .event_data, .frame_tick,
        .play_left, .play_right, .pending_valid(pending),
        .active_voice_count(voices), .clip_count(clip), .audio_underrun(underrun),
        .audio_frame_count(frames), .pcm_request_count(requests),
        .pcm_commit_count(commits), .max_processing_cycles(latency));
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) u_tx (
        .clk, .rst_n, .valid(1'b1), .pcm_left(play_left), .pcm_right(play_right),
        .bclk, .lrck(ws), .din, .ready, .frame_tick);
    serial_capture monitor (
        .clk, .rst_n, .frame_tick,
        .pcm_valid(u_core.u_commit.pcm_valid), .pcm_ready(u_core.u_commit.pcm_ready),
        .pcm_id(u_core.u_commit.pcm_req_id), .request_id(u_core.sample_req_id),
        .pcm_left(u_core.u_commit.pcm_left), .pcm_right(u_core.u_commit.pcm_right),
        .play_left, .play_right, .frame_count(frames), .commit_count(commits),
        .underrun, .bclk, .ws, .din);
    task automatic byte_midi(input reg [7:0] value);
        $fdisplay(monitor.fd, "U %.3f %02h", $realtime, value);
        midi_rx = 0; #32000;
        for (integer k=0; k<8; k=k+1) begin midi_rx=value[k]; #32000; end
        midi_rx = 1; #32000;
    endtask
    task automatic note(input reg on, input integer number);
        byte_midi(on ? 8'h90 : 8'h80);
        byte_midi(8'(number)); byte_midi(on ? 8'd100 : 8'd0);
    endtask
    always @(posedge clk) if (rst_n && event_valid && event_ready) begin
        events = events + 1;
        $fdisplay(monitor.fd, "E %.3f %016h", $realtime, event_data);
    end
    initial begin
        repeat(10) @(negedge clk); rst_n = 1;
        for (integer n=0; n<4; n=n+1) note(1, 60+3*n);
        #100000;
        if (voices != 4 || events != 4) $fatal(1, "FOUR_VOICES");
        $fdisplay(monitor.fd, "SCENE %.3f FOUR %0d", $realtime, voices);
        repeat(300) @(posedge frame_tick);
        $fdisplay(monitor.fd, "SCENE %.3f OFF_BEGIN %0d", $realtime, voices);
        for (integer n=0; n<4; n=n+1) begin
            note(0, 60+3*n);
            #100000;
            $fdisplay(monitor.fd, "SCENE %.3f RELEASE%0d %0d", $realtime, n, voices);
            $fdisplay(monitor.fd, "STATE %.3f %0d %0d %0d", $realtime, n,
                      u_core.u_bank.slot_releasing, u_core.u_bank.slot_occupied);
            repeat(64) @(posedge frame_tick);
        end
        // Keep the approved 4800-sample Release duration unchanged.
        repeat(4900) @(posedge frame_tick);
        #100000;
        if (voices != 0 || events != 8 || underrun != 0 ||
            uart_errors != 0 || parser_errors != 0 || overflow != 0 || fifo_level != 0)
            $fatal(1, "NORMAL_END voices=%0d events=%0d underrun=%0d", voices, events, underrun);
        $fdisplay(monitor.fd, "SCENE %.3f SILENT %0d", $realtime, voices);
        $fdisplay(monitor.fd, "END normal %0d %0d", frames, events);
        $fclose(monitor.fd);
        $display("SIM_DONE normal frames=%0d events=%0d", frames, events); $finish;
    end
    initial begin #200000000; $fatal(1, "NORMAL_TIMEOUT"); end
endmodule
