`timescale 1ns/1ps
module tb_visual_event_bridge;
    import audio_defs_pkg::*;
    parameter integer VIDEO_HALF = 17;
    localparam integer DEPTH = 4;
    logic sys_clk = 0, video_clk = 0, video_run = 1, rst_n = 1;
    always #10 sys_clk = ~sys_clk;
    always begin
        #(VIDEO_HALF);
        if (video_run) video_clk = ~video_clk;
        else video_clk = 0;
    end
    logic accepted_valid = 0, video_ready = 0;
    performance_event_t accepted_data = '0, video_data;
    logic [15:0] level, high_water;
    logic [31:0] drops;
    logic drop_pulse, src_up, dst_up, video_valid, video_desync;
    visual_event_bridge #(.DEPTH(DEPTH)) dut (
        .sys_clk(sys_clk), .video_clk(video_clk), .rst_n(rst_n),
        .accepted_valid(accepted_valid), .accepted_data(accepted_data),
        .visual_queue_level(level), .visual_queue_high_watermark(high_water),
        .visual_drop_count(drops), .visual_drop_pulse(drop_pulse),
        .sys_reset_done(src_up), .video_reset_done(dst_up),
        .video_valid(video_valid), .video_desync(video_desync), .video_ready(video_ready), .video_data(video_data)
    );
    performance_event_t expected [0:511];
    integer written = 0, received = 0, offered = 0, rejected = 0;
    integer checks = 0;
    performance_event_t sampled, held;
    logic was_blocked = 0, sample_valid;

    always @(negedge rst_n) begin
        written = 0;
        received = 0;
        offered = 0;
        rejected = 0;
        was_blocked = 0;
    end
    // Copy checking uses only public ports; no internal queue or state peeking.
    always @(posedge sys_clk) begin
        sampled = accepted_data;
        sample_valid = accepted_valid && src_up;
        #1;
        if (src_up && sample_valid) begin
            offered = offered + 1;
            if (drop_pulse) rejected = rejected + 1;
            else begin expected[written] = sampled; written = written + 1; end
        end
        if (src_up) begin
            if (level > DEPTH || high_water > DEPTH) $fatal(1, "queue bound");
            if (drops !== rejected) $fatal(1, "drop counter mismatch: rtl=%h scoreboard=%0d", drops, rejected);
        end
    end
    always @(posedge video_clk) begin
        if (dst_up) begin
            if (was_blocked && (!video_valid || video_data !== held))
                $fatal(1, "valid/data changed during video stall");
            if (video_valid && video_ready) begin
                if (received >= written || video_data !== expected[received])
                    $fatal(1, "event ordering/payload mismatch at %0d", received);
                received = received + 1;
            end
            was_blocked = video_valid && !video_ready;
            held = video_data;
        end else was_blocked = 0;
    end

    task automatic emit(input integer tag);
        @(negedge sys_clk);
        // Entire 64-bit word is varied, including note/control/velocity fields.
        accepted_data = 64'h1234567800000000 ^ (64'h0101020304050607 * tag);
        accepted_valid = 1;
        @(negedge sys_clk);
        accepted_valid = 0;
        accepted_data = '1;
    endtask
    task automatic flush_reset;
        @(negedge sys_clk); accepted_valid = 0; video_ready = 0; rst_n = 0;
        #3;
        if (video_valid !== 0 || level !== 0 || drops !== 0)
            $fatal(1, "async reset did not flush pending work");
        repeat (3) @(negedge sys_clk);
        rst_n = 1;
        wait (src_up && dst_up);
        @(negedge sys_clk);
    endtask
    task automatic drain;
        @(negedge video_clk); video_ready = 1;
        wait (received == written);
        repeat (12) @(negedge video_clk);
        if (video_valid || level != 0 || offered != received + rejected)
            $fatal(1, "duplicate/missing event or conservation failure");
    endtask

    initial begin
        #1; rst_n = 0;
        #60; rst_n = 1;
        wait (src_up && dst_up);
        video_ready = 1;
        for (integer i = 1; i <= 3; i = i+1) begin
            emit(i);
            wait (received == written);
        end
        drain();
        if (rejected != 0 || received != 3) $fatal(1, "normal event loss");
        checks = checks + 1;

        flush_reset();
        emit(10);
        wait(video_valid);
        repeat(8) @(negedge video_clk);
        if (received != 0) $fatal(1, "consumed while stalled");
        checks = checks + 1;
        // One stalled mailbox + four queued slots. A sixth event must drop.
        for(integer i = 11; i <= 15; i=i+1) emit(i);
        repeat(3) @(negedge sys_clk);
        if (level != DEPTH || high_water != DEPTH || drops != 1)
            $fatal(1, "full capacity/drop boundary incorrect");
        repeat(4) @(negedge video_clk);
        if (!video_desync) $fatal(1, "missing sticky overflow warning");
        checks = checks + 1;
        drain();
        checks = checks + 1;
        for(integer i = 20; i < 80; i=i+1) emit(i);
        drain();
        checks = checks + 1;

        flush_reset();
        video_run = 0;
        repeat(3) @(negedge sys_clk);
        for(integer i=100; i<110; i=i+1) emit(i);
        repeat(3) @(negedge sys_clk);
        if (offered != 10 || written != DEPTH+1 || drops != 5)
            $fatal(1, "stopped video altered source progress");
        checks = checks + 1;
        // Reset with video clock stopped must clear destination asynchronously.
        @(negedge sys_clk); rst_n=0;
        #3;
        if(video_valid || drops != 0 || level != 0) $fatal(1, "stopped-clock reset");
        repeat(3) @(negedge sys_clk);
        rst_n=1;
        repeat(4) @(negedge sys_clk);
        if(dst_up) $fatal(1, "destination released without video clock");
        video_run=1;
        wait(src_up && dst_up);
        video_ready=1;
        emit(200);
        drain();
        if(received != 1 || rejected != 0 || video_desync) $fatal(1, "stale work after reset");
        checks = checks + 1;
        flush_reset();
        emit(201);
        wait(video_valid);
        flush_reset();
        video_ready=1;
        emit(202);
        drain();
        if(received != 1) $fatal(1, "in-flight reset duplicate");
        checks=checks+1;
        $display("PASS visual_event_bridge: %0d scenarios, video_half=%0d ns",checks,VIDEO_HALF);
        $finish;
    end
    initial begin #500000; $fatal(1, "visual event bridge timeout"); end
endmodule
