`timescale 1ns/1ps
// Standalone visual sink; never instantiates the audio engine, MIDI or TMDS.
// All inputs, including PCM and activity/config metadata, must already belong
// to pixel_clk. Future integration reuses the existing PCM observer/CDC bridge.
module piano_lissajous_candidate #(
    parameter integer POINTS_PER_FRAME=512,
    parameter integer ROI_X=192,
    parameter integer ROI_Y=112
) (
    input wire pixel_clk,pixel_rst_n, // active-low synchronous reset
    input wire enable,activity,stream_restart,
    input wire sample_valid,
    input wire [31:0] sample_seq,
    input wire signed [23:0] pcm_left,pcm_right,
    input wire stereo_mode,
    input wire [7:0] delay_samples,
    input wire [2:0] gain_shift,
    input wire [1:0] timbre_id,
    input wire [11:0] pixel_x,pixel_y,
    input wire pixel_de,frame_start,hsync_in,vsync_in,
    output wire [23:0] rgb,
    output wire mask,trace_valid,
    output wire [31:0] gap_count,point_drop_count,published_frames,
    output wire hsync_out,vsync_out,data_enable_out
);
    wire point_valid,point_restart;
    wire [7:0] point_x,point_y;
    wire [1:0] point_timbre;
    lissajous_xy_frontend u_xy(
        .clk(pixel_clk),.rst_n(pixel_rst_n),.enable(enable),.activity(activity),
        .stream_restart(stream_restart),.sample_valid(sample_valid),.sample_seq(sample_seq),
        .pcm_left(pcm_left),.pcm_right(pcm_right),.stereo_mode(stereo_mode),
        .delay_samples(delay_samples),.gain_shift(gain_shift),.timbre_id(timbre_id),
        .point_valid(point_valid),.point_x(point_x),.point_y(point_y),
        .point_timbre(point_timbre),.point_restart(point_restart),.gap_count(gap_count));
    lissajous_plotter #(.PLOT_BITS(8),.POINTS_PER_FRAME(POINTS_PER_FRAME),
                       .ROI_X(ROI_X),.ROI_Y(ROI_Y)) u_plot(
        .clk(pixel_clk),.rst_n(pixel_rst_n),.enable(enable),.activity(activity),
        .point_restart(point_restart),.point_valid(point_valid),
        .point_x(point_x),.point_y(point_y),.point_timbre(point_timbre),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.pixel_de(pixel_de),.frame_start(frame_start),
        .rgb(rgb),.mask(mask),.trace_valid(trace_valid),
        .point_drop_count(point_drop_count),.published_frames(published_frames));
    // Input sampled at N -> aligned output after N+2 (three register captures).
    logic [2:0] hs_pipe,vs_pipe,de_pipe;
    always_ff @(posedge pixel_clk)begin
        if(!pixel_rst_n)begin hs_pipe<=0;vs_pipe<=0;de_pipe<=0;end
        else begin
            hs_pipe<={hs_pipe[1:0],hsync_in};
            vs_pipe<={vs_pipe[1:0],vsync_in};
            de_pipe<={de_pipe[1:0],pixel_de};
        end
    end
    assign hsync_out=hs_pipe[2];
    assign vsync_out=vs_pipe[2];
    assign data_enable_out=de_pipe[2];
endmodule
