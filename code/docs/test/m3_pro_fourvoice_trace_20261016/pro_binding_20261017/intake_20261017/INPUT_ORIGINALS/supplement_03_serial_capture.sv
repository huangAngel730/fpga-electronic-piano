// Observer only: sample physical BCLK/WS/DIN; never read a DUT shift register.
`timescale 1ns/1ps
module serial_capture (
    input wire clk, rst_n, frame_tick,
    input wire pcm_valid, pcm_ready,
    input wire [31:0] pcm_id, request_id,
    input wire signed [23:0] pcm_left, pcm_right, play_left, play_right,
    input wire [31:0] frame_count, commit_count, underrun,
    input wire bclk, ws, din
);
    integer fd, adoption = 0, halves = 0, edges = 0;
    reg synchronized = 0, prior_ws = 0;
    reg [31:0] bits = 0;
    realtime first_edge = 0, last_edge = 0;
    initial begin
        fd = $fopen("capture.txt", "w");
        if (!fd) $fatal(1, "CAPTURE_OPEN");
    end
    // Pre-NBA values are exactly those seen by the buffer and sender.
    always @(posedge clk) if (rst_n) begin
        if (pcm_valid && pcm_ready) begin
            if ($isunknown({pcm_id, request_id, pcm_left, pcm_right}))
                $fatal(1, "UNKNOWN_HANDSHAKE");
            $fdisplay(fd, "H %.3f %0d %0d %0d %0d", $realtime,
                      pcm_id, request_id, $signed(pcm_left), $signed(pcm_right));
        end
        if (frame_tick) begin
            adoption = adoption + 1;
            if ($isunknown({request_id, play_left, play_right}))
                $fatal(1, "UNKNOWN_ADOPTION");
            $fdisplay(fd, "A %.3f %0d %0d %0d %0d", $realtime,
                      adoption, request_id, $signed(play_left), $signed(play_right));
            #1;
            $fdisplay(fd, "V %.3f %0d %0d %0d %0d", $realtime,
                      adoption, frame_count, commit_count, underrun);
        end
    end
    // Wait for a physical WS transition, explicitly discarding the partial
    // reset half-slot. Each later WS transition terminates the preceding word.
    always @(posedge bclk) if (rst_n) begin
        if ($isunknown({ws, din})) $fatal(1, "UNKNOWN_SERIAL");
        if (!synchronized) begin
            if (ws != prior_ws) begin
                synchronized = 1;
                edges = 0;
                bits = 0;
                prior_ws = ws;
            end
        end else if (ws != prior_ws) begin
            if (edges != 32) $fatal(1, "SLOT_LENGTH edges=%0d", edges);
            halves = halves + 1;
            $fdisplay(fd, "S %.3f %0d %0d %0d %08h %.3f %.3f", $realtime,
                      halves, prior_ws, edges, bits, first_edge, last_edge);
            prior_ws = ws;
            edges = 0;
            bits = 0;
        end
        if (synchronized) begin
            if (edges == 0) first_edge = $realtime;
            last_edge = $realtime;
            bits = {bits[30:0], din};
            edges = edges + 1;
        end
    end
endmodule
