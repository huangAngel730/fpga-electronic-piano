// B1 single-port transport fixture. NOT any of the seven frozen sound ROMs.
// One outstanding synchronous read; response at LATENCY clocks after acceptance.
// Empty means no pending read AND no held response, not merely out_valid==0.
// Drain blocks new reads and consumes the eventual response regardless of ready.
module b1_tagged_rom #(
    parameter integer TW=74,
    parameter integer LATENCY=1
) (
    input wire clk, rst_n, drain,
    input wire in_valid,
    output wire in_ready,
    input wire [7:0] in_addr,
    input wire [TW-1:0] in_tag,
    output wire out_valid,
    input wire out_ready,
    output reg [15:0] out_data,
    output reg [TW-1:0] out_tag,
    output wire empty
);
    reg occupied;
    reg [31:0] remaining;
    reg [15:0] table_data [0:255];
    integer i;
    initial begin
        for (i=0; i<256; i=i+1) table_data[i] = (i*257) ^ 16'h5a3c;
    end
    assign in_ready = rst_n && !occupied && !drain;
    assign out_valid = occupied && remaining==0;
    assign empty = !occupied;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            occupied <= 0;
            remaining <= 0;
            out_data <= 0;
            out_tag <= 0;
        end else begin
            if (in_valid && in_ready) begin
                occupied <= 1;
                remaining <= LATENCY-1;
                out_data <= table_data[in_addr];
                out_tag <= in_tag;
            end else if (occupied && remaining!=0) remaining <= remaining-1'b1;
            else if (out_valid && (out_ready || drain)) occupied <= 0;
        end
    end
endmodule
