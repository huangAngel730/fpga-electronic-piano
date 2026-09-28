`timescale 1ns/1ps
module tb_pcm_frame_link;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0;
    logic valid = 1'b1, legacy_ready;
    logic bclk, lrck, din, frame_tick;
    logic sample_req, pcm_valid = 0, pcm_ready, pending_valid;
    logic [31:0] sample_req_id, pcm_req_id = 0;
    logic signed [23:0] pcm_left = 0, pcm_right = 0;
    logic signed [23:0] play_left, play_right;
    logic [31:0] audio_frame_count, pcm_request_count;
    logic [31:0] pcm_commit_count, audio_underrun;
    logic calc_ready = 1'b1;

    i2s_tx #(.ACC_BITS(8), .BCLK_PHASE_STEP(8'd32)) tx (
        .clk, .rst_n, .valid, .pcm_left(play_left), .pcm_right(play_right),
        .bclk, .lrck, .din, .ready(legacy_ready), .frame_tick
    );
    pcm_frame_buffer buffer_dut (.*);

    // Black-box serial decoder: sample DIN on BCLK rising edges, independent
    // of any slot counter or PCM register inside either DUT.
    integer half_edges = 0, decoded_count = 0;
    logic ws_prev = 0, ws_seen = 0;
    logic [31:0] slot_bits = 0;
    logic [15:0] last_right = 0;
    logic [15:0] seen_left [0:31];
    logic [15:0] seen_right [0:31];
    always @(posedge bclk) if (rst_n) begin
        if (!ws_seen) begin ws_prev = lrck; ws_seen = 1; end
        if (lrck !== ws_prev) begin
            half_edges = 0;
            slot_bits = '0;
            ws_prev = lrck;
        end
        slot_bits = {slot_bits[30:0], din};
        half_edges++;
        // Finish at the final BCK rising edge, before the next frame request.
        if (half_edges == 32) begin
            if (lrck == 1'b0) last_right = slot_bits[15:0];
            else begin
                if (decoded_count < 32) begin
                    seen_left[decoded_count] = slot_bits[15:0];
                    seen_right[decoded_count] = last_right;
                end
                decoded_count++;
            end
        end
    end
    always @(negedge rst_n) begin
        ws_seen = 0;
        half_edges = 0;
        slot_bits = '0;
    end

    task automatic commit(input integer l, input integer r);
        @(negedge clk);
        pcm_req_id = sample_req_id;
        pcm_left = l;
        pcm_right = r;
        pcm_valid = 1;
        #1;
        if (!pcm_ready) $fatal(1, "current frame not ready");
        @(posedge clk); #1;
        @(negedge clk); pcm_valid = 0;
    endtask

    integer i, found = 0;
    logic c_consumed = 0;
    // Third committed sample C is accepted for playback at a frame boundary.
    // Record underruns here; serial decoding completes at the NEXT boundary.
    always @(posedge clk) if (rst_n && frame_tick && pending_valid &&
                            play_left == 24'sd12288 && play_right == -24'sd12288) begin
        #1;
        if (audio_underrun !== 32'd3 || pcm_commit_count !== 32'd3)
            $fatal(1, "incorrect injected missed frames at C consumption: %0d/%0d",
                   audio_underrun, pcm_commit_count);
        c_consumed = 1;
    end
    initial begin
        repeat (4) @(negedge clk);
        rst_n = 1;
        @(posedge sample_req); commit(24'sd4096, -24'sd4096); // A: +16/-16
        @(posedge sample_req); commit(24'sd8192, -24'sd8192); // B: +32/-32
        repeat (4) @(posedge sample_req); // request IDs 3..6; miss frames 4..6
        commit(24'sd12288, -24'sd12288); // C: +48/-48
        // The physical half-frame boundaries are taken from WS. C becomes
        // visible one full serial frame after consumption; check the injected
        // three underruns at consumption and the subsequent miss separately.
        while (!found && decoded_count < 12) begin
            @(posedge bclk); #1;
            for (i = 0; i + 5 < decoded_count && i + 5 < 32; i++) begin
                if (seen_left[i] == 16'd16 && seen_right[i] == 16'hfff0 &&
                    seen_left[i+1] == 16'd32 && seen_right[i+1] == 16'hffe0 &&
                    seen_left[i+2] == 16'd32 && seen_left[i+3] == 16'd32 &&
                    seen_left[i+4] == 16'd32 &&
                    seen_right[i+2] == 16'hffe0 &&
                    seen_right[i+3] == 16'hffe0 &&
                    seen_right[i+4] == 16'hffe0 &&
                    seen_left[i+5] == 16'd48 && seen_right[i+5] == 16'hffd0)
                    found = 1;
            end
        end
        if (!found) begin
            for (i = 0; i < decoded_count && i < 32; i++)
                $display("decoded[%0d] = %h / %h", i, seen_left[i], seen_right[i]);
            $fatal(1, "A B B B B C not found in LSBJ output");
        end
        // C's last serial bit is seen after the following frame boundary;
        // without a subsequent submission, that is ONE additional genuine
        // underrun, not part of the injected three missed frames.
        if (!c_consumed || audio_underrun != 4 || pcm_commit_count != 3 ||
            audio_frame_count != 8)
            $fatal(1, "incorrect consume/decode boundary: consumed=%0d underrun=%0d commit=%0d frame=%0d",
                   c_consumed, audio_underrun, pcm_commit_count, audio_frame_count);
        $display("PASS tb_pcm_frame_link: stereo LSBJ A B B B B C; injected_underrun=3; final_underrun=4");
        $finish;
    end
    initial begin #500000; $fatal(1, "timeout"); end
endmodule
