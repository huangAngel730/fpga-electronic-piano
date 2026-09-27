// Top-level wiring test. Vendor IP is replaced by an explicitly NON-PHYSICAL
// clock model and a pixel-input checker. This does NOT validate TMDS encoding.
`timescale 1ns/1ps
module TMDS_PLL(output reg lock=0, output reg clkout0=0,
                output reg clkout1=0, input clkin);
    always #4 clkout0=~clkout0;
    always #20 clkout1=~clkout1;
    initial begin repeat(12) @(posedge clkin); lock=1; end
endmodule

module DVI_TX_Top (
    input I_rst_n,I_serial_clk,I_rgb_clk,I_rgb_vs,I_rgb_hs,I_rgb_de,
    input [7:0] I_rgb_r,I_rgb_g,I_rgb_b,
    output O_tmds_clk_p,O_tmds_clk_n,
    output [2:0] O_tmds_data_p,O_tmds_data_n
);
    // Port checker, not serializer. No fabricated physical TMDS evidence.
    assign O_tmds_clk_p=I_rgb_clk;
    assign O_tmds_clk_n=~I_rgb_clk;
    assign O_tmds_data_p={I_rgb_vs,I_rgb_hs,I_rgb_de};
    assign O_tmds_data_n=~O_tmds_data_p;
    integer px=0,py=0,frames=0,active_pixels=0,serial_edges=0;
    integer checked_frames=0; reg started=0;
    always @(posedge I_serial_clk) serial_edges=serial_edges+1;
    always @(negedge I_rst_n) begin
        px=0; py=0; frames=0; active_pixels=0; started=0;
    end
    always @(posedge I_rgb_clk) begin
        if(I_rst_n !== 1'b1) begin px=0;py=0;frames=0;active_pixels=0;started=0; end
        else if (started || I_rgb_de) begin
            started=1;
            if(I_rgb_de !== (px<640 && py<480) ||
               I_rgb_hs !== (!(px>=656 && px<752)) ||
               I_rgb_vs !== (!(py>=490 && py<492)))
                $fatal(1,"640x480 raster mismatch %0d,%0d",px,py);
            if({I_rgb_r,I_rgb_g,I_rgb_b}!==24'h204080)
                $fatal(1,"RGB port wiring mismatch");
            if(I_rgb_de) active_pixels=active_pixels+1;
            if(px==799) begin
                px=0;
                if(py==524) begin
                    py=0; frames=frames+1; checked_frames=checked_frames+1;
                    if(active_pixels!=307200) $fatal(1,"active pixels/frame mismatch");
                    active_pixels=0;
                end else py=py+1;
            end else px=px+1;
        end
    end
endmodule

module tb_hdmi_link_probe;
    reg sys_clk=0,sys_rst_n=0;
    wire tmds_clk_p,tmds_clk_n,pa_en;
    wire [2:0] tmds_data_p,tmds_data_n;
    hdmi_link_probe dut(.*);
    always #10 sys_clk=~sys_clk;
    integer prior_edges;
    initial begin
        #1;
        if(pa_en!==1) $fatal(1,"amplifier not disabled");
        repeat(16) @(negedge sys_clk);
        sys_rst_n=1;
        wait(dut.u_video_tx.frames==2);
        // Physical PLL remains outside this behavioural test; force loss only
        // to verify asynchronous reset assertion and local synchronous release.
        @(negedge sys_clk); force dut.pll_lock=0;
        #1; if(dut.pixel_rst_n!==0 || tmds_data_p[0]!==0)
            $fatal(1,"PLL unlock failed to blank/reset");
        repeat(8) @(negedge sys_clk);
        release dut.pll_lock;
        wait(dut.pixel_rst_n);
        repeat(100) @(negedge sys_clk);
        sys_rst_n=0;
        #1; if(dut.pixel_rst_n!==0 || pa_en!==1) $fatal(1,"external reset failed");
        repeat(8) @(negedge sys_clk);
        sys_rst_n=1;
        wait(dut.pixel_rst_n);
        @(negedge dut.pixel_clk); prior_edges=dut.u_video_tx.serial_edges;
        repeat(10) @(negedge dut.pixel_clk);
        if(dut.u_video_tx.serial_edges-prior_edges!=50)
            $fatal(1,"behavioural 5:1 clock ratio mismatch");
        $display("PASS HDMI probe wiring: 2 full 640x480 frames, reset, lock loss, PA off");
        $display("Vendor models are placeholders: no PLL/TMDS physical simulation claim");
        $finish;
    end
    initial begin #40000000; $fatal(1,"probe wiring timeout"); end
endmodule
