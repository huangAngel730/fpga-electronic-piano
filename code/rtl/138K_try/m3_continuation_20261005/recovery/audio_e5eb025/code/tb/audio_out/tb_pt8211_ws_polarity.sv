// PT8211 V1.7 page 4: WS low loads RCH; WS high loads LCH.
// Diagnostic test independent of the project's legacy low=left convention.
`timescale 1ns/1ps
module tb_pt8211_ws_polarity;
    logic clk = 0;
    always #10 clk = ~clk; // 50 MHz
    logic rst_n = 0;
    logic bclk, lrck, din, ready, frame_tick;
    logic signed [23:0] pcm_left = 24'sd8448;   // +0x0021 after >>8
    logic signed [23:0] pcm_right = -24'sd12544; // -0x0031 after >>8

    i2s_tx #(.ACC_BITS(8), .BCLK_PHASE_STEP(8'd32)) dut (
        .clk, .rst_n, .valid(1'b1), .pcm_left, .pcm_right,
        .bclk, .lrck, .din, .ready, .frame_tick
    );

    logic ws_seen = 0;
    logic ws_prev = 0;
    logic [31:0] word_bits = 0;
    integer edge_count = 0;
    integer halves = 0;
    integer checks = 0;
    integer errors = 0;

    // Capture DIN on the rising BCK edge used by the physical DAC. A WS
    // transition closes the preceding 32-bit word; the last 16 bits are PCM.
    always @(posedge bclk) if (rst_n) begin
        if (!ws_seen) begin
            ws_prev = lrck;
            ws_seen = 1;
        end
        if (lrck !== ws_prev) begin
            if (halves >= 4) begin // Ignore startup before the PCM register loads.
                if (edge_count != 32) begin
                    $display("FAIL WS interval: %0d BCK edges", edge_count);
                    errors = errors + 1;
                end else if (ws_prev == 1'b0) begin
                    checks = checks + 1;
                    if (word_bits[15:0] !== 16'hffcf) begin
                        $display("FAIL WS=0 / physical RCH: got %h, expected ffcf",
                                 word_bits[15:0]);
                        errors = errors + 1;
                    end
                end else begin
                    checks = checks + 1;
                    if (word_bits[15:0] !== 16'h0021) begin
                        $display("FAIL WS=1 / physical LCH: got %h, expected 0021",
                                 word_bits[15:0]);
                        errors = errors + 1;
                    end
                end
            end
            halves = halves + 1;
            edge_count = 0;
            word_bits = 0;
            ws_prev = lrck;
        end
        word_bits = {word_bits[30:0], din};
        edge_count = edge_count + 1;
        if (halves == 10) begin
            if (errors != 0 || checks < 4)
                $fatal(1, "PT8211 channel polarity FAIL: errors=%0d checks=%0d", errors, checks);
            $display("PASS PT8211 WS polarity: %0d physical-channel checks", checks);
            $finish;
        end
    end

    initial begin
        #100 rst_n = 1;
        #300000 $fatal(1, "PT8211 channel polarity test timeout");
    end
endmodule
