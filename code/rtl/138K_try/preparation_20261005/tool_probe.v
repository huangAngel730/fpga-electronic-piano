// Offline tool support probe only. Never program this design on a board.
// 50 MHz clock; active-low synchronous reset; 8-bit wrapping counter.
module tool_probe(input wire sys_clk, input wire rst_n, output wire tick);
    reg [7:0] count;
    always @(posedge sys_clk) begin
        if (!rst_n) count <= 8'd0;
        else count <= count + 8'd1;
    end
    assign tick = count[7];
endmodule
