`timescale 1ns/1ps
// Shared final-playback FFT engine. No K3 selection, new observer or audio ready.
// Either endpoint reset asserts both private domains; local synchronous release.
// Registered renderer2 + alignment3 = exactly5 input pixel captures.
module k4_spectrum_engine #(
    parameter HANN_FILE="rom/k4_spectrum_hann_q17.mem",
    parameter TWIDDLE_RE_FILE="rom/k4_spectrum_twiddle_re_q17.mem",
    parameter TWIDDLE_IM_FILE="rom/k4_spectrum_twiddle_im_q17.mem"
) (
    input wire core_clk,
    input wire core_rst_n,
    input wire pixel_clk,
    input wire pixel_rst_n,
    input wire sample_valid,
    input wire [31:0] sample_seq,
    input wire signed [23:0] pcm_mono,
    input wire [15:0] pixel_x,
    input wire [15:0] pixel_y,
    input wire data_enable,
    input wire frame_start,
    input wire view_enable,
    output wire spectrum_mask,
    output wire [23:0] spectrum_rgb,
    output wire data_enable_out,
    output wire view_enable_out,
    output wire [15:0] pixel_x_out,
    output wire [15:0] pixel_y_out,
    output wire [31:0] render_generation,
    output wire snapshot_available,
    output wire render_available,
    output wire [31:0] display_spectrum_id,
    output wire [15:0] display_epoch,
    output wire [31:0] display_first_sample_seq,
    output wire [7:0] display_scale_id,
    output wire [31:0] display_generation,
    output wire monitor_result_valid,
    output wire monitor_result_ready,
    output wire monitor_result_first,
    output wire monitor_result_last,
    output wire [10:0] monitor_bin_index,
    output wire [36:0] monitor_bin_power,
    output wire [31:0] monitor_spectrum_id,
    output wire [15:0] monitor_result_epoch,
    output wire [31:0] monitor_first_sample_seq,
    output wire [7:0] monitor_scale_id,
    output wire [31:0] complete_window_count,
    output wire [31:0] dropped_window_count,
    output wire [31:0] gap_count,
    output wire [31:0] canceled_window_count,
    output wire [31:0] pcm_saturation_count,
    output wire [31:0] fft_saturation_count,
    output wire [31:0] complete_spectrum_count,
    output wire [31:0] snapshot_drop_count,
    output wire [31:0] last_processing_cycles,
    output wire [31:0] maximum_processing_cycles,
    output wire [31:0] display_commit_count,
    output wire [31:0] prefetch_complete_count,
    output wire [31:0] prefetch_abort_count,
    output wire [31:0] generation_change_error_count,
    output wire [31:0] cache_commit_count,
    output wire candidate_busy,
    output wire source_reset_done,
    output wire pixel_reset_done
);
    wire private_async_rst_n=core_rst_n && pixel_rst_n;
    k4_spectrum_reset_sync u_core_reset(.clk(core_clk),.async_rst_n(private_async_rst_n),.reset_done(source_reset_done));
    k4_spectrum_reset_sync u_pixel_reset(.clk(pixel_clk),.async_rst_n(private_async_rst_n),.reset_done(pixel_reset_done));
    wire mask2,de2,view2;
    wire [7:0] r2,g2,b2;
    wire [15:0] x2,y2;
    wire [31:0] generation2;
    pro_spectrum_candidate #(.HANN_FILE(HANN_FILE),
        .TWIDDLE_RE_FILE(TWIDDLE_RE_FILE),.TWIDDLE_IM_FILE(TWIDDLE_IM_FILE)) u_candidate (
        .audio_clk(core_clk),
        .audio_rst_n(source_reset_done),
        .sample_valid(sample_valid),
        .pcm_mono(pcm_mono),
        .sample_seq(sample_seq),
        .stream_epoch(16'd0),
        .stream_restart(1'b0),
        .pixel_clk(pixel_clk),
        .pixel_rst_n(pixel_reset_done),
        .pixel_x(pixel_x),
        .pixel_y(pixel_y),
        .data_enable(data_enable),
        .frame_start(frame_start),
        .page_enable(view_enable),
        .spectrum_mask(mask2),
        .rgb_r(r2),
        .rgb_g(g2),
        .rgb_b(b2),
        .data_enable_out(de2),
        .page_enable_out(view2),
        .pixel_x_out(x2),
        .pixel_y_out(y2),
        .generation_out(generation2),
        .spectrum_available(snapshot_available),
        .display_spectrum_id(display_spectrum_id),
        .display_epoch(display_epoch),
        .display_first_sample_seq(display_first_sample_seq),
        .display_scale_id(display_scale_id),
        .display_generation(display_generation),
        .monitor_result_valid(monitor_result_valid),
        .monitor_result_ready(monitor_result_ready),
        .monitor_result_first(monitor_result_first),
        .monitor_result_last(monitor_result_last),
        .monitor_bin_index(monitor_bin_index),
        .monitor_bin_power(monitor_bin_power),
        .monitor_spectrum_id(monitor_spectrum_id),
        .monitor_result_epoch(monitor_result_epoch),
        .monitor_first_sample_seq(monitor_first_sample_seq),
        .monitor_scale_id(monitor_scale_id),
        .complete_window_count(complete_window_count),
        .dropped_window_count(dropped_window_count),
        .gap_count(gap_count),
        .canceled_window_count(canceled_window_count),
        .pcm_saturation_count(pcm_saturation_count),
        .fft_saturation_count(fft_saturation_count),
        .complete_spectrum_count(complete_spectrum_count),
        .snapshot_drop_count(snapshot_drop_count),
        .display_commit_count(display_commit_count),
        .prefetch_complete_count(prefetch_complete_count),
        .last_processing_cycles(last_processing_cycles),
        .maximum_processing_cycles(maximum_processing_cycles),
        .candidate_busy(candidate_busy),
        .render_available(render_available),
        .cache_commit_count(cache_commit_count),
        .prefetch_abort_count(prefetch_abort_count),
        .generation_change_error_count(generation_change_error_count)
    );
    reg [90:0] align3[0:2];
    integer k;
    always @(posedge pixel_clk or negedge pixel_reset_done) begin
        if (!pixel_reset_done) begin
            for(k=0;k<3;k=k+1) align3[k]<=0;
        end else begin
            align3[0]<={mask2,r2,g2,b2,de2,view2,x2,y2,generation2};
            align3[1]<=align3[0]; align3[2]<=align3[1];
        end
    end
    assign {spectrum_mask,spectrum_rgb,data_enable_out,view_enable_out,
            pixel_x_out,pixel_y_out,render_generation}=align3[2];
endmodule
