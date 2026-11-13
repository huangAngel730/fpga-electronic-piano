// Explicit simulation boundary: tests RGB/CDC/raster, not vendor serialization.
module Pro_DVI_TX_Top(input I_rst_n,I_serial_clk,I_rgb_clk,I_rgb_vs,I_rgb_hs,I_rgb_de,
    input [7:0] I_rgb_r,I_rgb_g,I_rgb_b,
    output O_tmds_clk_p,O_tmds_clk_n,output [2:0] O_tmds_data_p,O_tmds_data_n);
    assign O_tmds_clk_p=I_rgb_clk;assign O_tmds_clk_n=~I_rgb_clk;
    assign O_tmds_data_p=I_rst_n ? {I_rgb_r[7],I_rgb_g[7],I_rgb_b[7]} : 0;
    assign O_tmds_data_n=~O_tmds_data_p;
endmodule
