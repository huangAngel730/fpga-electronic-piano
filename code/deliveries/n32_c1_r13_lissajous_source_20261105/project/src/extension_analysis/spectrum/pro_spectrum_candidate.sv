`timescale 1ns/1ps

// Stage-A private integration candidate.  The audio input is observational:
// there is deliberately no ready signal back to the adopted PCM producer.
// Window RAM reads, FFT loading, power calculation, snapshot CDC and display
// prefetch are all registered/multi-cycle paths; no full-window combinational
// reduction is used.
module pro_spectrum_candidate #(
    parameter HANN_FILE = "rom/k4_spectrum_hann_q17.mem",
    parameter TWIDDLE_RE_FILE = "rom/k4_spectrum_twiddle_re_q17.mem",
    parameter TWIDDLE_IM_FILE = "rom/k4_spectrum_twiddle_im_q17.mem"
) (
    input  wire               audio_clk,
    input  wire               audio_rst_n,
    input  wire               sample_valid,
    input  wire signed [23:0] pcm_mono,
    input  wire        [31:0] sample_seq,
    input  wire        [15:0] stream_epoch,
    input  wire               stream_restart,

    input  wire               pixel_clk,
    input  wire               pixel_rst_n,
    input  wire        [15:0] pixel_x,
    input  wire        [15:0] pixel_y,
    input  wire               data_enable,
    input  wire               frame_start,
    input  wire               page_enable,

    output wire               spectrum_mask,
    output wire         [7:0] rgb_r,
    output wire         [7:0] rgb_g,
    output wire         [7:0] rgb_b,
    output wire               data_enable_out,
    output wire               page_enable_out,
    output wire        [15:0] pixel_x_out,
    output wire        [15:0] pixel_y_out,
    output wire        [31:0] generation_out,

    output wire               spectrum_available,
    output wire        [31:0] display_spectrum_id,
    output wire        [15:0] display_epoch,
    output wire        [31:0] display_first_sample_seq,
    output wire         [7:0] display_scale_id,
    output wire        [31:0] display_generation,

    output wire               monitor_result_valid,
    output wire               monitor_result_ready,
    output wire               monitor_result_first,
    output wire               monitor_result_last,
    output wire        [10:0] monitor_bin_index,
    output wire        [36:0] monitor_bin_power,
    output wire        [31:0] monitor_spectrum_id,
    output wire        [15:0] monitor_result_epoch,
    output wire        [31:0] monitor_first_sample_seq,
    output wire         [7:0] monitor_scale_id,

    output wire        [31:0] complete_window_count,
    output wire        [31:0] dropped_window_count,
    output wire        [31:0] gap_count,
    output wire        [31:0] canceled_window_count,
    output wire        [31:0] pcm_saturation_count,
    output wire        [31:0] fft_saturation_count,
    output wire        [31:0] complete_spectrum_count,
    output wire        [31:0] snapshot_drop_count,
    output wire        [31:0] display_commit_count,
    output wire        [31:0] prefetch_complete_count,
    output wire        [31:0] last_processing_cycles,
    output wire        [31:0] maximum_processing_cycles,
    output wire               candidate_busy,
    output wire               render_available,
    output wire        [31:0] cache_commit_count,
    output wire        [31:0] prefetch_abort_count,
    output wire        [31:0] generation_change_error_count
);
    localparam [1:0] SCHED_IDLE = 2'd0;
    localparam [1:0] SCHED_FEED = 2'd1;
    localparam [1:0] SCHED_WAIT_RESULT = 2'd2;

    wire window_valid;
    wire window_ready;
    wire window_bank;
    wire [31:0] window_id;
    wire [15:0] window_epoch;
    wire [31:0] window_first_sample_seq;
    reg capture_read_enable;
    reg capture_read_bank;
    reg [10:0] capture_read_index;
    wire capture_read_valid;
    wire signed [17:0] capture_read_data;
    reg capture_release_valid;
    reg capture_release_bank;
    wire [1:0] capture_bank_state0;
    wire [1:0] capture_bank_state1;
    wire [31:0] capture_restart_count;
    wire capture_saturation_sticky;
    wire [31:0] capture_blocked_cycles;
    wire [31:0] capture_protocol_errors;

    reg [1:0] scheduler_state;
    reg active_bank;
    reg [31:0] active_spectrum_id;
    reg [15:0] active_epoch;
    reg [31:0] active_first_sample_seq;
    reg [11:0] next_read_count;
    reg read_pending;
    reg [10:0] pending_read_index;
    reg sample_buffer_valid;
    reg signed [17:0] sample_buffer_data;
    reg [10:0] sample_buffer_index;
    reg [31:0] processing_cycles;
    reg [31:0] last_processing_cycles_q;
    reg [31:0] maximum_processing_cycles_q;

    wire fft_input_ready;
    wire fft_input_fire;
    wire fft_valid;
    wire fft_ready;
    wire fft_first;
    wire fft_last;
    wire [10:0] fft_bin_index;
    wire signed [17:0] fft_real;
    wire signed [17:0] fft_imag;
    wire [31:0] fft_spectrum_id;
    wire [15:0] fft_epoch;
    wire [31:0] fft_first_sample_seq;
    wire [7:0] fft_scale_id;
    wire fft_busy;
    wire [31:0] fft_accepted_window_count;
    wire [31:0] fft_emitted_spectrum_count;
    wire [31:0] fft_dropped_window_count;
    wire [31:0] fft_input_error_count;
    wire fft_saturation_sticky;
    wire [31:0] fft_blocked_cycle_count;

    wire result_valid;
    wire result_ready;
    wire result_first;
    wire result_last;
    wire [31:0] result_spectrum_id;
    wire [15:0] result_epoch;
    wire [31:0] result_first_sample_seq;
    wire [10:0] result_bin_index;
    wire [36:0] result_bin_power;
    wire [7:0] result_scale_id;
    // Hold-only identity chain on the audio-domain snapshot write address.
    // It remains combinational and therefore preserves the valid/index cycle.
    (* syn_keep=1, syn_dont_touch=1 *) wire [10:0] snapshot_bin_index_hold;
    for(genvar snapshot_index_bit=0;snapshot_index_bit<11;snapshot_index_bit=snapshot_index_bit+1) begin:g_snapshot_bin_index_hold
        (* syn_keep=1, syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=result_bin_index[snapshot_index_bit];
        for(genvar snapshot_index_stage=0;snapshot_index_stage<2;snapshot_index_stage=snapshot_index_stage+1) begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                .I0(chain[snapshot_index_stage]),.F(chain[snapshot_index_stage+1]));
        end
        assign snapshot_bin_index_hold[snapshot_index_bit]=chain[2];
    end
    wire [31:0] power_protocol_error_count;
    wire [31:0] power_dropped_spectrum_count;
    wire [31:0] power_blocked_cycle_count;

    wire snapshot_read_enable;
    wire [10:0] snapshot_read_index;
    wire snapshot_read_valid;
    wire [36:0] snapshot_read_power;
    wire [31:0] snapshot_sequence_error_count;
    wire [31:0] snapshot_metadata_error_count;
    wire [31:0] snapshot_blocked_cycle_count;
    wire [31:0] no_spectrum_frame_count;
    wire [31:0] snapshot_read_error_count;
    wire [31:0] snapshot_generation_error_count;

    assign window_ready = (scheduler_state == SCHED_IDLE) && !fft_busy;
    assign fft_input_fire = sample_buffer_valid && fft_input_ready;
    assign candidate_busy = (scheduler_state != SCHED_IDLE) || fft_busy ||
                            sample_buffer_valid || read_pending;
    assign last_processing_cycles = last_processing_cycles_q;
    assign maximum_processing_cycles = maximum_processing_cycles_q;

    assign monitor_result_valid = result_valid;
    assign monitor_result_ready = result_ready;
    assign monitor_result_first = result_first;
    assign monitor_result_last = result_last;
    assign monitor_bin_index = result_bin_index;
    assign monitor_bin_power = result_bin_power;
    assign monitor_spectrum_id = result_spectrum_id;
    assign monitor_result_epoch = result_epoch;
    assign monitor_first_sample_seq = result_first_sample_seq;
    assign monitor_scale_id = result_scale_id;

    spectrum_window_capture u_window_capture (
        .audio_clk(audio_clk),
        .audio_rst_n(audio_rst_n),
        .sample_valid(sample_valid),
        .pcm_mono(pcm_mono),
        .sample_seq(sample_seq),
        .stream_epoch(stream_epoch),
        .stream_restart(stream_restart),
        .window_valid(window_valid),
        .window_ready(window_ready),
        .window_bank(window_bank),
        .window_id(window_id),
        .window_epoch(window_epoch),
        .window_first_sample_seq(window_first_sample_seq),
        .read_enable(capture_read_enable),
        .read_bank(capture_read_bank),
        .read_index(capture_read_index),
        .read_valid(capture_read_valid),
        .read_data(capture_read_data),
        .release_valid(capture_release_valid),
        .release_bank(capture_release_bank),
        .bank_state0(capture_bank_state0),
        .bank_state1(capture_bank_state1),
        .complete_windows(complete_window_count),
        .dropped_windows(dropped_window_count),
        .gap_count(gap_count),
        .canceled_windows(canceled_window_count),
        .restart_count(capture_restart_count),
        .saturation_count(pcm_saturation_count),
        .saturation_sticky(capture_saturation_sticky),
        .blocked_cycles(capture_blocked_cycles),
        .protocol_error_count(capture_protocol_errors)
    );

    // One outstanding synchronous RAM read and one registered skid word keep
    // the capture RAM address/data path separate from FFT arithmetic.
    always @(posedge audio_clk or negedge audio_rst_n) begin
        if (!audio_rst_n) begin
            scheduler_state <= SCHED_IDLE;
            active_bank <= 1'b0;
            active_spectrum_id <= 32'd0;
            active_epoch <= 16'd0;
            active_first_sample_seq <= 32'd0;
            next_read_count <= 12'd0;
            read_pending <= 1'b0;
            pending_read_index <= 11'd0;
            sample_buffer_valid <= 1'b0;
            sample_buffer_data <= 18'sd0;
            sample_buffer_index <= 11'd0;
            capture_read_enable <= 1'b0;
            capture_read_bank <= 1'b0;
            capture_read_index <= 11'd0;
            capture_release_valid <= 1'b0;
            capture_release_bank <= 1'b0;
            processing_cycles <= 32'd0;
            last_processing_cycles_q <= 32'd0;
            maximum_processing_cycles_q <= 32'd0;
        end else begin
            capture_read_enable <= 1'b0;
            capture_release_valid <= 1'b0;

            if (scheduler_state != SCHED_IDLE && processing_cycles != 32'hffffffff)
                processing_cycles <= processing_cycles + 1'b1;

            if (capture_read_valid) begin
                sample_buffer_valid <= 1'b1;
                sample_buffer_data <= capture_read_data;
                sample_buffer_index <= pending_read_index;
                read_pending <= 1'b0;
            end

            if (fft_input_fire) begin
                sample_buffer_valid <= 1'b0;
                if (sample_buffer_index == 11'd2047) begin
                    capture_release_valid <= 1'b1;
                    capture_release_bank <= active_bank;
                    scheduler_state <= SCHED_WAIT_RESULT;
                end
            end

            case (scheduler_state)
                SCHED_IDLE: begin
                    processing_cycles <= 32'd0;
                    read_pending <= 1'b0;
                    sample_buffer_valid <= 1'b0;
                    next_read_count <= 12'd0;
                    if (window_valid && window_ready) begin
                        active_bank <= window_bank;
                        active_spectrum_id <= window_id;
                        active_epoch <= window_epoch;
                        active_first_sample_seq <= window_first_sample_seq;
                        scheduler_state <= SCHED_FEED;
                        processing_cycles <= 32'd1;
                    end
                end
                SCHED_FEED: begin
                    if (!read_pending && !sample_buffer_valid &&
                        next_read_count < 12'd2048) begin
                        capture_read_enable <= 1'b1;
                        capture_read_bank <= active_bank;
                        capture_read_index <= next_read_count[10:0];
                        pending_read_index <= next_read_count[10:0];
                        next_read_count <= next_read_count + 1'b1;
                        read_pending <= 1'b1;
                    end
                end
                SCHED_WAIT_RESULT: begin
                    if (result_valid && result_ready && result_last) begin
                        last_processing_cycles_q <= processing_cycles + 1'b1;
                        if (processing_cycles + 1'b1 > maximum_processing_cycles_q)
                            maximum_processing_cycles_q <= processing_cycles + 1'b1;
                        scheduler_state <= SCHED_IDLE;
                    end
                end
                default: scheduler_state <= SCHED_IDLE;
            endcase
        end
    end

    radix2_fft_2048 #(
        .HANN_FILE(HANN_FILE),
        .TWIDDLE_RE_FILE(TWIDDLE_RE_FILE),
        .TWIDDLE_IM_FILE(TWIDDLE_IM_FILE)
    ) u_fft (
        .audio_clk(audio_clk),
        .audio_rst_n(audio_rst_n),
        .cancel(1'b0),
        .input_valid(sample_buffer_valid),
        .input_ready(fft_input_ready),
        .input_pcm($signed({sample_buffer_data, 6'b0})),
        .input_first(sample_buffer_index == 11'd0),
        .input_last(sample_buffer_index == 11'd2047),
        .input_spectrum_id(active_spectrum_id),
        .input_epoch(active_epoch),
        .input_first_sample_seq(active_first_sample_seq),
        .fft_valid(fft_valid),
        .fft_ready(fft_ready),
        .fft_first(fft_first),
        .fft_last(fft_last),
        .fft_bin_index(fft_bin_index),
        .fft_real(fft_real),
        .fft_imag(fft_imag),
        .fft_spectrum_id(fft_spectrum_id),
        .fft_epoch(fft_epoch),
        .fft_first_sample_seq(fft_first_sample_seq),
        .fft_scale_id(fft_scale_id),
        .busy(fft_busy),
        .accepted_window_count(fft_accepted_window_count),
        .emitted_spectrum_count(fft_emitted_spectrum_count),
        .dropped_window_count(fft_dropped_window_count),
        .input_error_count(fft_input_error_count),
        .saturation_count(fft_saturation_count),
        .saturation_sticky(fft_saturation_sticky),
        .blocked_cycle_count(fft_blocked_cycle_count)
    );

    spectrum_power_stream u_power (
        .audio_clk(audio_clk),
        .audio_rst_n(audio_rst_n),
        .cancel(1'b0),
        .fft_valid(fft_valid),
        .fft_ready(fft_ready),
        .fft_first(fft_first),
        .fft_last(fft_last),
        .fft_bin_index(fft_bin_index),
        .fft_real(fft_real),
        .fft_imag(fft_imag),
        .fft_spectrum_id(fft_spectrum_id),
        .fft_epoch(fft_epoch),
        .fft_first_sample_seq(fft_first_sample_seq),
        .fft_scale_id(fft_scale_id),
        .result_valid(result_valid),
        .result_ready(result_ready),
        .result_first(result_first),
        .result_last(result_last),
        .spectrum_id(result_spectrum_id),
        .result_epoch(result_epoch),
        .first_sample_seq(result_first_sample_seq),
        .bin_index(result_bin_index),
        .bin_power(result_bin_power),
        .scale_id(result_scale_id),
        .completed_spectrum_count(complete_spectrum_count),
        .protocol_error_count(power_protocol_error_count),
        .dropped_spectrum_count(power_dropped_spectrum_count),
        .blocked_cycle_count(power_blocked_cycle_count)
    );

    spectrum_snapshot_cdc u_snapshot (
        .audio_clk(audio_clk),
        .audio_rst_n(audio_rst_n),
        .result_valid(result_valid),
        .result_ready(result_ready),
        .result_first(result_first),
        .result_last(result_last),
        .spectrum_id(result_spectrum_id),
        .result_epoch(result_epoch),
        .first_sample_seq(result_first_sample_seq),
        .bin_index(snapshot_bin_index_hold),
        .bin_power(result_bin_power),
        .scale_id(result_scale_id),
        .complete_spectrum_count(),
        .dropped_spectrum_count(snapshot_drop_count),
        .sequence_error_count(snapshot_sequence_error_count),
        .metadata_error_count(snapshot_metadata_error_count),
        .blocked_cycle_count(snapshot_blocked_cycle_count),
        .pixel_clk(pixel_clk),
        .pixel_rst_n(pixel_rst_n),
        .frame_start(frame_start),
        .read_enable(snapshot_read_enable),
        .read_index(snapshot_read_index),
        .read_valid(snapshot_read_valid),
        .read_power(snapshot_read_power),
        .display_spectrum_id(display_spectrum_id),
        .display_epoch(display_epoch),
        .display_first_sample_seq(display_first_sample_seq),
        .display_scale_id(display_scale_id),
        .display_generation(display_generation),
        .spectrum_available(spectrum_available),
        .display_commit_count(display_commit_count),
        .no_spectrum_frame_count(no_spectrum_frame_count),
        .read_error_count(snapshot_read_error_count),
        .generation_error_count(snapshot_generation_error_count)
    );

    spectrum_renderer u_renderer (
        .pixel_clk(pixel_clk),
        .pixel_rst_n(pixel_rst_n),
        .pixel_x(pixel_x),
        .pixel_y(pixel_y),
        .data_enable(data_enable),
        .frame_start(frame_start),
        .page_enable(page_enable),
        .spectrum_available(spectrum_available),
        .display_generation(display_generation),
        .snapshot_read_enable(snapshot_read_enable),
        .snapshot_read_index(snapshot_read_index),
        .snapshot_read_valid(snapshot_read_valid),
        .snapshot_read_power(snapshot_read_power),
        .spectrum_mask(spectrum_mask),
        .rgb_r(rgb_r),
        .rgb_g(rgb_g),
        .rgb_b(rgb_b),
        .data_enable_out(data_enable_out),
        .page_enable_out(page_enable_out),
        .pixel_x_out(pixel_x_out),
        .pixel_y_out(pixel_y_out),
        .generation_out(generation_out),
        .prefetch_complete_count(prefetch_complete_count),
        .prefetch_abort_count(prefetch_abort_count),
        .generation_change_error_count(generation_change_error_count),
        .render_available(render_available),
        .cache_commit_count(cache_commit_count)
    );
endmodule
