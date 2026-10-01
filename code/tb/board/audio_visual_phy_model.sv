// Behavioral wiring only: never a model of physical PLL jitter or TMDS PHY.
`timescale 1ns/1ps
module TMDS_PLL(input clkin, output logic lock=0, output logic clkout0=0, clkout1=0);
    logic clock_run=1;
    initial begin #200;lock=1;end
    always begin #4;if(clock_run)clkout0=~clkout0;end
    always begin #20;if(clock_run)clkout1=~clkout1;end
endmodule
module DVI_TX_Top(input I_rst_n,I_serial_clk,I_rgb_clk,I_rgb_vs,I_rgb_hs,I_rgb_de,
    input [7:0] I_rgb_r,I_rgb_g,I_rgb_b,
    output O_tmds_clk_p,O_tmds_clk_n, output [2:0] O_tmds_data_p,O_tmds_data_n);
    assign O_tmds_clk_p=I_serial_clk;assign O_tmds_clk_n=~I_serial_clk;
    assign O_tmds_data_p={I_rgb_r[0],I_rgb_g[0],I_rgb_b[0]} & {3{I_rst_n && I_rgb_de}};
    assign O_tmds_data_n=~O_tmds_data_p;
endmodule
