// M2 CDC-only probe. Never program this synthetic design onto a board.
`timescale 1ns/1ps
module visual_cdc_probe(
    input logic sys_clk, sys_rst_n,
    input logic [63:0] stimulus_data,
    output logic debug_tx
);
    import audio_defs_pkg::*;
    wire pixel_clk, serial_clk, pll_lock;
    wire shared_rst_n = sys_rst_n && pll_lock;
    wire [15:0] level, high_water;
    wire [31:0] dropped;
    wire drop_pulse, sys_reset_done, video_reset_done, video_valid, video_desync;
    performance_event_t accepted_data, video_data;
    logic accepted_valid;
    logic [11:0] count;
    logic [63:0] received;
    logic [5:0] bit_select;

    TMDS_PLL u_video_pll(.clkin(sys_clk),.lock(pll_lock),
                          .clkout0(serial_clk),.clkout1(pixel_clk));
    always_ff @(posedge sys_clk or negedge shared_rst_n) begin
        if (!shared_rst_n) begin
            count <= '0;
        end else begin
            count <= count+1'b1;
        end
    end
    assign accepted_valid = sys_reset_done && (count == 12'hfff);
    assign accepted_data = performance_event_t'(stimulus_data);
    visual_event_bridge #(.DEPTH(4)) u_bridge(
        .sys_clk(sys_clk),.video_clk(pixel_clk),.rst_n(shared_rst_n),
        .accepted_valid(accepted_valid),.accepted_data(accepted_data),
        .visual_queue_level(level),.visual_queue_high_watermark(high_water),
        .visual_drop_count(dropped),.visual_drop_pulse(drop_pulse),
        .sys_reset_done(sys_reset_done),.video_reset_done(video_reset_done),
        .video_valid(video_valid),.video_desync(video_desync),
        .video_ready(1'b1),.video_data(video_data)
    );
    // Every captured payload bit reaches this serialized dynamic selection.
    // Keep the whole packet live instead of an optimized-away parity result.
    always_ff @(posedge pixel_clk or negedge video_reset_done) begin
        if (!video_reset_done) begin
            received <= '0;
            bit_select <= '0;
            debug_tx <= 1'b0;
        end else begin
            if (video_valid) received <= video_data;
            bit_select <= bit_select+1'b1;
            debug_tx <= received[bit_select] ^ video_desync;
        end
    end
endmodule
