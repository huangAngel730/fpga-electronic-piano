// Simulation fixture only: frequency-correct clocks, no physical PLL/phase proof.
`timescale 1ns/1ps
module TMDS_PLL(input clkin, init_clk, output reg clkout0=0,
    output reg clkout1=0, output reg clkout2=0, output reg lock=0);
    always #4 clkout0=~clkout0;
    always #20 clkout1=~clkout1;
    always #12.5 clkout2=~clkout2;
    initial begin repeat(12) @(posedge clkin); lock=1; end
endmodule
