// M2 parameterized raster timing. No PLL, TMDS encoder, pixel renderer or pins.
// Defaults describe candidate 640x480 geometry only, NOT a frozen HDMI mode.
// Input pixel_clk is an actual clock; rst_n is already synchronized to it.
`timescale 1ns/1ps
module video_scan_timing #(
    parameter integer H_ACTIVE = 640, H_FRONT = 16, H_SYNC = 96, H_BACK = 48,
    parameter integer V_ACTIVE = 480, V_FRONT = 10, V_SYNC = 2, V_BACK = 33,
    parameter bit H_POLARITY = 1'b0, V_POLARITY = 1'b0
) (
    input logic pixel_clk, rst_n,
    output logic [15:0] pixel_x, pixel_y,
    output logic data_enable, hsync, vsync, frame_start, line_start
);
    localparam integer H_TOTAL = H_ACTIVE + H_FRONT + H_SYNC + H_BACK;
    localparam integer V_TOTAL = V_ACTIVE + V_FRONT + V_SYNC + V_BACK;
    always_ff @(posedge pixel_clk or negedge rst_n) begin
        if (!rst_n) begin
            pixel_x <= '0;
            pixel_y <= '0;
        end else if (pixel_x == H_TOTAL-1) begin
            pixel_x <= '0;
            if (pixel_y == V_TOTAL-1) pixel_y <= '0;
            else pixel_y <= pixel_y + 1'b1;
        end else pixel_x <= pixel_x + 1'b1;
    end
    always_comb begin
        data_enable = rst_n && pixel_x < H_ACTIVE && pixel_y < V_ACTIVE;
        hsync = !H_POLARITY;
        vsync = !V_POLARITY;
        if (rst_n && pixel_x >= H_ACTIVE + H_FRONT &&
            pixel_x < H_ACTIVE + H_FRONT + H_SYNC) hsync = H_POLARITY;
        if (rst_n && pixel_y >= V_ACTIVE + V_FRONT &&
            pixel_y < V_ACTIVE + V_FRONT + V_SYNC) vsync = V_POLARITY;
        line_start = rst_n && pixel_x == 0;
        frame_start = line_start && pixel_y == 0;
    end
`ifndef SYNTHESIS
    initial begin
        if (H_ACTIVE < 1 || V_ACTIVE < 1 || H_SYNC < 1 || V_SYNC < 1 ||
            H_FRONT < 0 || H_BACK < 0 || V_FRONT < 0 || V_BACK < 0 ||
            H_TOTAL > 65536 || V_TOTAL > 65536)
            $fatal(1, "invalid video geometry");
    end
`endif
endmodule
