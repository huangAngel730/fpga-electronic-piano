// Synchronous true dual-port shape. No array reset or combinational data reads.
// A: published events, read-only. B: staging writes / VERIFY / UART READ.
// Same-address cross-port read/write is prohibited by the bank ownership contract.
`timescale 1ns/1ps
module pro_score_byte_lane (
    input wire clk, a_enable,
    input wire [9:0] a_address, b_address,
    input wire b_write,
    input wire [7:0] b_data,
    output reg [7:0] a_data, b_read
);
    reg [7:0] memory [0:1023];
    // Bijective address encoding: bank stays bank, lower bits are a prefix
    // XOR chain. Both ports use the same mapping. Each public index bit now
    // traverses a real decode LUT rather than a pad-to-BSRAM address shortcut;
    // no extra public read cycle, no hold exception or simulation-only delay.
    wire [9:0] a_encoded = {a_address[9], a_address[8:0] ^ a_address[9:1]};
    wire [9:0] b_encoded = {b_address[9], b_address[8:0] ^ b_address[9:1]};
    always @(posedge clk) begin
        if (a_enable) begin
`ifdef MUTANT_RAM_READ
            a_data <= memory[a_encoded ^ 10'd1];
`else
            a_data <= memory[a_encoded];
`endif
        end
    end
    always @(posedge clk) begin
        if (b_write) memory[b_encoded] <= b_data;
        // GW5AST DPB supports no-change/write-through, not read-before-write.
        // The staging controller never consumes B read data on a write cycle.
        // Holding this private output preserves every actual read transaction.
        else b_read <= memory[b_encoded];
    end
endmodule

// Ping-pong request history: current request and last successful request.
// Port A is current-body write / synchronous COPY read; port B is the
// cached-body comparison read. Raw bytes have no reset or parallel copy.
// A write-cycle read is deliberately held (GW5AST supported no-change mode).
module pro_score_request_cache (
    input wire clk,
    input wire write_enable,
    input wire [8:0] current_address, cached_address,
    input wire [7:0] write_data,
    output reg [7:0] current_data, cached_data
);
    reg [7:0] memory [0:511];
    always @(posedge clk) begin
        if (write_enable) memory[current_address] <= write_data;
        else current_data <= memory[current_address];
    end
    always @(posedge clk) begin
`ifdef MUTANT_REQUEST_HISTORY
        cached_data <= memory[cached_address ^ 9'd1];
`else
        cached_data <= memory[cached_address];
`endif
    end
endmodule
