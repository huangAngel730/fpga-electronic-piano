// Simulation-only nominal-clock model for LONG full-top equivalence.
// No analog phase/PLL LOCK/MTBF proof; original vendor PLL tested separately.
`timescale 1ns/1ps
module TMDS_PLL(output reg lock=0,output reg clkout0=0,clkout1=0,clkout2=0,input clkin);
    always #4 clkout0=~clkout0;
    always #20 clkout1=~clkout1;
    always #12.5 clkout2=~clkout2;
    initial begin #1000;lock=1;end
endmodule
