// T025 system status counters in the 50 MHz sys_clk domain.
// PCM latency measures accepted request edge to successful commit edge.
// A newer request cancels an unfinished older request; it is not counted.
`timescale 1ns/1ps
module system_status_counters (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        pcm_request,
    input  logic        pcm_commit,
    input  logic [31:0] button_overflow,
    input  logic [31:0] midi_overflow,
    output logic [31:0] event_fifo_overflow,
    output logic [31:0] max_processing_cycles
);
    logic [32:0] overflow_sum;
    logic [31:0] elapsed;
    logic        request_active;

    // Local input FIFOs count actual dropped events. Shared FIFO backpressure
    // never counts as loss because valid/data remain held until a handshake.
    always_comb begin
        overflow_sum = {1'b0, button_overflow} + {1'b0, midi_overflow};
        event_fifo_overflow = !rst_n ? 32'd0 :
            (overflow_sum[32] ? 32'hffff_ffff : overflow_sum[31:0]);
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            elapsed <= '0;
            request_active <= 1'b0;
            max_processing_cycles <= '0;
        end else if (pcm_request) begin
            // The frame buffer cancels the previous generation at a new
            // request. A simultaneous commit has zero elapsed cycles.
            elapsed <= '0;
            request_active <= !pcm_commit;
        end else if (request_active) begin
            if (pcm_commit) begin
                request_active <= 1'b0;
                if (elapsed == 32'hffff_ffff)
                    max_processing_cycles <= 32'hffff_ffff;
                else if (elapsed + 1'b1 > max_processing_cycles)
                    max_processing_cycles <= elapsed + 1'b1;
            end else if (elapsed != 32'hffff_ffff) begin
                elapsed <= elapsed + 1'b1;
            end
        end
    end
endmodule
