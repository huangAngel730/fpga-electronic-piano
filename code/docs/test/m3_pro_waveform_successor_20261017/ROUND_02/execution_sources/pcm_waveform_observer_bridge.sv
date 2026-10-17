// Isolated buffered bundled-data CDC for T058; not a production integration.
// DEPTH queued words plus one stable mailbox word; all fields move atomically.
// display reset flushes ONLY this observation branch, never the audio engine.
`timescale 1ns/1ps
module pcm_waveform_observer_bridge #(
    parameter integer DEPTH = 32,
    parameter [31:0] FIRST_SEQ = 32'd0
) (
    input wire audio_clk, pixel_clk, audio_rst_n, display_rst_n,
    input wire audio_frame_load,
    input wire signed [23:0] audio_play_left, audio_play_right,
    output wire waveform_rst_n,
    output reg stream_restart,
    output reg sample_valid,
    output reg [31:0] sample_seq,
    output reg signed [23:0] sample_left, sample_right,
    output wire observed_valid,
    output wire [31:0] observed_seq,
    output wire signed [23:0] observed_left, observed_right,
    output wire observation_enqueued, observation_dropped,
    output wire [15:0] observation_queue_level,
    output reg [31:0] observation_drop_count,
    output wire source_reset_done, pixel_reset_done
);
    localparam integer PTR_W = (DEPTH <= 2) ? 1 : $clog2(DEPTH);
    localparam integer CNT_W = $clog2(DEPTH + 1);
    reg [79:0] queue [0:DEPTH-1];
    reg [PTR_W-1:0] wr_ptr, rd_ptr;
    reg [CNT_W-1:0] count;
    wire observation_async_rst_n = audio_rst_n && display_rst_n;
    wire mailbox_ready, mailbox_valid;
    wire [79:0] mailbox_data;
    reg destination_started;
    (* async_reg = "true" *) reg source_up_meta, source_up_sync;
    wire destination_ready = pixel_reset_done && source_up_sync && destination_started;
    wire pop = source_reset_done && count != 0 && mailbox_ready;
    wire space = source_reset_done && (count < DEPTH || pop);
    assign observation_enqueued = observed_valid && space;
    assign observation_dropped = source_reset_done && observed_valid && !space;
    assign observation_queue_level = count;
    assign waveform_rst_n = pixel_reset_done;

    pcm_frame_observer #(.FIRST_SEQ(FIRST_SEQ)) u_observer (
        .audio_clk(audio_clk), .audio_rst_n(audio_rst_n),
        .frame_load(audio_frame_load), .play_left(audio_play_left),
        .play_right(audio_play_right), .observed_valid(observed_valid),
        .observed_seq(observed_seq), .observed_left(observed_left),
        .observed_right(observed_right)
    );
    visual_mailbox_cdc #(.WIDTH(80)) u_mailbox (
        .src_clk(audio_clk), .dst_clk(pixel_clk), .rst_n(observation_async_rst_n),
        .src_valid(source_reset_done && count != 0), .src_ready(mailbox_ready),
        .src_data(queue[rd_ptr]), .dst_valid(mailbox_valid),
        .dst_ready(destination_ready), .dst_data(mailbox_data),
        .src_reset_done(source_reset_done), .dst_reset_done(pixel_reset_done)
    );
    function automatic [PTR_W-1:0] advance(input [PTR_W-1:0] ptr);
        if (ptr == DEPTH-1) advance = '0;
        else advance = ptr + 1'b1;
    endfunction
    always @(posedge audio_clk or negedge source_reset_done) begin
        if (!source_reset_done) begin
            wr_ptr <= '0; rd_ptr <= '0; count <= '0;
            observation_drop_count <= 32'd0;
        end else begin
            if (observation_enqueued) begin
                queue[wr_ptr] <= {observed_seq, observed_left, observed_right};
                wr_ptr <= advance(wr_ptr);
            end
            if (pop) rd_ptr <= advance(rd_ptr);
            case ({observation_enqueued, pop})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
            if (observation_dropped && observation_drop_count != 32'hffffffff)
                observation_drop_count <= observation_drop_count + 32'd1;
        end
    end
    // Shared branch reset cancels every old request/ack on both sides. The
    // observer ordinal itself resets only with audio_rst_n, not display reset.
    always @(posedge pixel_clk or negedge pixel_reset_done) begin
        if (!pixel_reset_done) begin
            source_up_meta <= 1'b0;
            source_up_sync <= 1'b0;
            destination_started <= 1'b0;
            stream_restart <= 1'b0;
            sample_valid <= 1'b0;
            sample_seq <= FIRST_SEQ;
            sample_left <= 24'sd0;
            sample_right <= 24'sd0;
        end else begin
            source_up_meta <= source_reset_done;
            source_up_sync <= source_up_meta;
            stream_restart <= 1'b0;
            sample_valid <= 1'b0;
            if (source_up_sync && !destination_started) begin
                destination_started <= 1'b1;
                stream_restart <= 1'b1;
            end else if (destination_ready && mailbox_valid) begin
                sample_valid <= 1'b1;
                {sample_seq, sample_left, sample_right} <= mailbox_data;
            end
        end
    end
`ifndef SYNTHESIS
    initial if (DEPTH < 2 || DEPTH > 32767)
        $fatal(1, "observer queue DEPTH must be in 2..32767");
`endif
endmodule
