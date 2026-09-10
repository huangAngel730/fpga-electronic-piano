`timescale 1ns / 1ps

module key_debounce #(
    parameter integer CLK_FREQ_HZ = 50_000_000,
    parameter integer DEBOUNCE_MS = 10
) (
    input wire clk, input wire rst_n, input wire [7:0] keys_n,
    output reg [7:0] keys_pressed
);
    localparam integer COUNT_MAX = (CLK_FREQ_HZ / 1000) * DEBOUNCE_MS;
    localparam integer COUNT_W = (COUNT_MAX <= 1) ? 1 : $clog2(COUNT_MAX);
    reg [7:0] sync_0, sync_1, candidate;
    reg [COUNT_W-1:0] count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin sync_0 <= 8'hFF; sync_1 <= 8'hFF; end
        else begin sync_0 <= keys_n; sync_1 <= sync_0; end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            candidate <= 8'hFF; keys_pressed <= 8'h00; count <= 0;
        end else if (sync_1 != candidate) begin
            candidate <= sync_1; count <= 0;
        end else if (count < COUNT_MAX - 1) begin
            count <= count + 1'b1;
        end else begin
            keys_pressed <= ~candidate;
        end
    end
endmodule
