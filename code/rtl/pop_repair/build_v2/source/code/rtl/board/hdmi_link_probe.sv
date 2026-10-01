// Independent M2 transport probe, NOT the electronic-piano top.
// 50 MHz input -> derived 60K PLLA: serial 125 MHz, pixel 25 MHz (640x480 at 59.524 Hz).
// Fixed RGB only; no M3 renderer, no audio or MIDI. No automatic programming.
`timescale 1ns/1ps
module hdmi_link_probe (
    input logic sys_clk,
    input logic sys_rst_n,
    output wire tmds_clk_p,
    output wire tmds_clk_n,
    output wire [2:0] tmds_data_p,
    output wire [2:0] tmds_data_n,
    output wire pa_en
);
    wire serial_clk, pixel_clk, pll_lock, pixel_rst_n, serial_rst_n;
    wire hs, vs, de;
    wire [15:0] x, y;
    TMDS_PLL u_video_pll (
        .clkin(sys_clk), .lock(pll_lock),
        .clkout0(serial_clk), .clkout1(pixel_clk)
    );
    // Release the transmitter reset in its faster serializer clock domain.
    reset_sync u_serial_reset (
        .clk(serial_clk), .rst_n(sys_rst_n && pll_lock),
        .rst_sync_n(serial_rst_n)
    );
    reset_sync u_video_reset (
        .clk(pixel_clk), .rst_n(serial_rst_n),
        .rst_sync_n(pixel_rst_n)
    );
    video_scan_timing #(
        .H_ACTIVE(640), .H_FRONT(16), .H_SYNC(96), .H_BACK(48),
        .V_ACTIVE(480), .V_FRONT(10), .V_SYNC(2), .V_BACK(33),
        .H_POLARITY(1'b0), .V_POLARITY(1'b0)
    ) u_scan (
        .pixel_clk(pixel_clk), .rst_n(pixel_rst_n),
        .pixel_x(x), .pixel_y(y), .data_enable(de), .hsync(hs), .vsync(vs),
        .frame_start(), .line_start()
    );
    // Constant test colour; the IP adds control periods during blanking.
    DVI_TX_Top u_video_tx (
        .I_rst_n(serial_rst_n), .I_serial_clk(serial_clk), .I_rgb_clk(pixel_clk),
        .I_rgb_vs(vs), .I_rgb_hs(hs), .I_rgb_de(de),
        .I_rgb_r(8'h20), .I_rgb_g(8'h40), .I_rgb_b(8'h80),
        .O_tmds_clk_p(tmds_clk_p), .O_tmds_clk_n(tmds_clk_n),
        .O_tmds_data_p(tmds_data_p), .O_tmds_data_n(tmds_data_n)
    );
    // The board amplifier enable is active low. Keep audio off in this probe.
    assign pa_en = 1'b1;
endmodule
