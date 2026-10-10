// Synchronous true dual-port shape. No array reset or combinational data reads.
// A: published events, read-only. B: staging writes / VERIFY / UART READ.
// Same-address cross-port read/write is prohibited by the bank ownership contract.
`timescale 1ns/1ps
module score_byte_lane (
    input wire clk, a_enable,
    input wire [9:0] a_address, b_address,
    input wire b_write,
    input wire [7:0] b_data,
    output reg [7:0] a_data, b_read
);
    reg [7:0] memory [0:1023];
    always @(posedge clk) begin
        if (a_enable) begin
`ifdef MUTANT_RAM_READ
            a_data <= memory[a_address ^ 10'd1];
`else
            a_data <= memory[a_address];
`endif
        end
    end
    always @(posedge clk) begin
        if (b_write) memory[b_address] <= b_data;
        // GW5AST DPB supports no-change/write-through, not read-before-write.
        // The staging controller never consumes B read data on a write cycle.
        // Holding this private output preserves every actual read transaction.
        else b_read <= memory[b_address];
    end
endmodule
