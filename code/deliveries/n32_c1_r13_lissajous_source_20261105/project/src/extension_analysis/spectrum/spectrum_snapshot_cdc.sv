`timescale 1ns/1ps

// Complete-spectrum dual-clock snapshot store.
//
// Audio ownership: FREE -> WRITE -> PENDING.  Pixel ownership changes only at
// frame_start: PENDING -> FRONT.  The prior FRONT is released only after the
// acknowledgement has crossed back to audio_clk.  The 1025 RAM words are
// never synchronized bit by bit; only stable bank metadata crosses with the
// toggle request/acknowledgement handshake.
module spectrum_snapshot_cdc (
    input  wire        audio_clk,
    input  wire        audio_rst_n,

    input  wire        result_valid,
    output wire        result_ready,
    input  wire        result_first,
    input  wire        result_last,
    input  wire [31:0] spectrum_id,
    input  wire [15:0] result_epoch,
    input  wire [31:0] first_sample_seq,
    input  wire [10:0] bin_index,
    input  wire [36:0] bin_power,
    input  wire [7:0]  scale_id,

    output reg  [31:0] complete_spectrum_count,
    output reg  [31:0] dropped_spectrum_count,
    output reg  [31:0] sequence_error_count,
    output reg  [31:0] metadata_error_count,
    output reg  [31:0] blocked_cycle_count,

    input  wire        pixel_clk,
    input  wire        pixel_rst_n,
    input  wire        frame_start,
    input  wire        read_enable,
    input  wire [10:0] read_index,
    output reg         read_valid,
    output wire [36:0] read_power,

    output reg  [31:0] display_spectrum_id,
    output reg  [15:0] display_epoch,
    output reg  [31:0] display_first_sample_seq,
    output reg  [7:0]  display_scale_id,
    output reg  [31:0] display_generation,
    output reg         spectrum_available,
    output reg  [31:0] display_commit_count,
    output reg  [31:0] no_spectrum_frame_count,
    output reg  [31:0] read_error_count,
    output reg  [31:0] generation_error_count
);

    localparam [10:0] LAST_BIN = 11'd1024;

    // Two complete physical banks.  Each array has one audio write port and
    // one pixel read port.  The ownership protocol prevents a bank from being
    // written while it is FRONT.
    reg [36:0] spectrum_bank0 [0:1024];
    reg [36:0] spectrum_bank1 [0:1024];
    reg [36:0] bank0_read_data_pixel;
    reg [36:0] bank1_read_data_pixel;
    reg        read_zero_pixel;

    reg        collecting_audio;
    reg        rejecting_audio;
    reg        write_bank_audio;
    reg [10:0] expected_bin_audio;
    reg [31:0] collect_spectrum_id_audio;
    reg [15:0] collect_epoch_audio;
    reg [31:0] collect_first_seq_audio;
    reg [7:0]  collect_scale_id_audio;

    reg        front_valid_audio;
    reg        front_bank_audio;
    reg        pending_waiting_audio;
    reg        published_bank_audio;
    reg [31:0] published_spectrum_id_audio;
    reg [15:0] published_epoch_audio;
    reg [31:0] published_first_seq_audio;
    reg [7:0]  published_scale_id_audio;
    reg [31:0] published_generation_audio;
    reg [31:0] next_generation_audio;
    reg        req_toggle_audio;

    (* async_reg="true" *) reg ack_sync_audio_1;
    (* async_reg="true" *) reg ack_sync_audio_2;
    reg ack_sync_audio_3;
    (* async_reg="true" *) reg ack_accepted_sync_audio_1;
    (* async_reg="true" *) reg ack_accepted_sync_audio_2;
    (* async_reg="true" *) reg pixel_up_audio_1;
    (* async_reg="true" *) reg pixel_up_audio_2;

    (* async_reg="true" *) reg req_sync_pixel_1;
    (* async_reg="true" *) reg req_sync_pixel_2;
    reg req_sync_pixel_3;
    reg bank_sync_pixel_1;
    reg bank_sync_pixel_2;
    reg [31:0] spectrum_id_sync_pixel_1;
    reg [31:0] spectrum_id_sync_pixel_2;
    reg [15:0] epoch_sync_pixel_1;
    reg [15:0] epoch_sync_pixel_2;
    reg [31:0] first_seq_sync_pixel_1;
    reg [31:0] first_seq_sync_pixel_2;
    reg [7:0]  scale_sync_pixel_1;
    reg [7:0]  scale_sync_pixel_2;
    reg [31:0] generation_sync_pixel_1;
    reg [31:0] generation_sync_pixel_2;
    (* async_reg="true" *) reg audio_up_pixel_1;
    (* async_reg="true" *) reg audio_up_pixel_2;
    reg        ack_toggle_pixel;
    reg        ack_accepted_pixel;
    reg        pending_pixel;
    reg        front_bank_pixel;
    reg [31:0] expected_generation_pixel;

    wire selected_write_bank;
    assign selected_write_bank = front_valid_audio ? ~front_bank_audio : 1'b0;
    assign result_ready = pixel_up_audio_2 && !pending_waiting_audio;

    // Keep each spectrum bank in the canonical simple-dual-port form: one
    // audio-clock write port and one pixel-clock synchronous read port.  The
    // control FSM never assigns the arrays directly, so Gowin can infer BSRAM
    // instead of expanding 2*1025*37 bits into flip-flops and deep muxes.
    wire accepted_first_bin = result_valid && result_ready &&
                              !rejecting_audio && !collecting_audio &&
                              result_first && !result_last &&
                              (bin_index == 11'd0);
    wire accepted_following_bin = result_valid && result_ready &&
                                  !rejecting_audio && collecting_audio &&
                                  (spectrum_id == collect_spectrum_id_audio) &&
                                  (result_epoch == collect_epoch_audio) &&
                                  (first_sample_seq == collect_first_seq_audio) &&
                                  (scale_id == collect_scale_id_audio) &&
                                  !result_first &&
                                  (bin_index == expected_bin_audio) &&
                                  (result_last == (bin_index == LAST_BIN));
    wire spectrum_write_enable = accepted_first_bin || accepted_following_bin;
    wire spectrum_write_bank = accepted_first_bin ? selected_write_bank :
                                                    write_bank_audio;

    always @(posedge audio_clk) begin
        if (spectrum_write_enable && !spectrum_write_bank)
            spectrum_bank0[bin_index] <= bin_power;
    end

    always @(posedge audio_clk) begin
        if (spectrum_write_enable && spectrum_write_bank)
            spectrum_bank1[bin_index] <= bin_power;
    end

    always @(posedge pixel_clk) begin
        if (read_enable && (read_index <= LAST_BIN)) begin
            bank0_read_data_pixel <= spectrum_bank0[read_index];
            bank1_read_data_pixel <= spectrum_bank1[read_index];
        end
    end

    assign read_power = read_zero_pixel ? 37'd0 :
                        (front_bank_pixel ? bank1_read_data_pixel :
                                            bank0_read_data_pixel);

    // Audio-domain collector and producer side of the handshake.
    always @(posedge audio_clk or negedge audio_rst_n) begin
        if (!audio_rst_n) begin
            collecting_audio              <= 1'b0;
            rejecting_audio               <= 1'b0;
            write_bank_audio               <= 1'b0;
            expected_bin_audio             <= 11'd0;
            collect_spectrum_id_audio      <= 32'd0;
            collect_epoch_audio            <= 16'd0;
            collect_first_seq_audio        <= 32'd0;
            collect_scale_id_audio         <= 8'd0;
            front_valid_audio              <= 1'b0;
            front_bank_audio               <= 1'b0;
            pending_waiting_audio          <= 1'b0;
            published_bank_audio           <= 1'b0;
            published_spectrum_id_audio    <= 32'd0;
            published_epoch_audio          <= 16'd0;
            published_first_seq_audio      <= 32'd0;
            published_scale_id_audio       <= 8'd0;
            published_generation_audio     <= 32'd0;
            next_generation_audio          <= 32'd1;
            req_toggle_audio               <= 1'b0;
            ack_sync_audio_1               <= 1'b0;
            ack_sync_audio_2               <= 1'b0;
            ack_sync_audio_3               <= 1'b0;
            ack_accepted_sync_audio_1      <= 1'b0;
            ack_accepted_sync_audio_2      <= 1'b0;
            pixel_up_audio_1               <= 1'b0;
            pixel_up_audio_2               <= 1'b0;
            complete_spectrum_count        <= 32'd0;
            dropped_spectrum_count         <= 32'd0;
            sequence_error_count           <= 32'd0;
            metadata_error_count           <= 32'd0;
            blocked_cycle_count            <= 32'd0;
        end else begin
            ack_sync_audio_1 <= ack_toggle_pixel;
            ack_sync_audio_2 <= ack_sync_audio_1;
            // The third ack stage trails the two-stage bundled acceptance
            // flag, so the producer never infers FRONT ownership from a
            // generation-rejected snapshot.
            ack_sync_audio_3 <= ack_sync_audio_2;
            ack_accepted_sync_audio_1 <= ack_accepted_pixel;
            ack_accepted_sync_audio_2 <= ack_accepted_sync_audio_1;
            pixel_up_audio_1 <= pixel_rst_n;
            pixel_up_audio_2 <= pixel_up_audio_1;

            if (result_valid && !result_ready)
                blocked_cycle_count <= blocked_cycle_count + 1'b1;

            // A display-only reset cancels private snapshot work and aligns
            // the toggle handshake.  It never drives audio_rst_n or upstream.
            if (!pixel_up_audio_2) begin
                if (collecting_audio || rejecting_audio || pending_waiting_audio)
                    dropped_spectrum_count <= dropped_spectrum_count + 1'b1;
                collecting_audio          <= 1'b0;
                rejecting_audio           <= 1'b0;
                pending_waiting_audio      <= 1'b0;
                front_valid_audio          <= 1'b0;
                req_toggle_audio           <= 1'b0;
                published_generation_audio <= 32'd0;
                next_generation_audio      <= 32'd1;
            end else begin
                if (pending_waiting_audio &&
                    (ack_sync_audio_3 == req_toggle_audio)) begin
                    pending_waiting_audio <= 1'b0;
                    if (ack_accepted_sync_audio_2) begin
                        front_valid_audio <= 1'b1;
                        front_bank_audio  <= published_bank_audio;
                    end
                end

                if (result_valid && result_ready) begin
                    if (rejecting_audio) begin
                        if (result_last)
                            rejecting_audio <= 1'b0;
                    end else if (!collecting_audio) begin
                        if (!result_first || result_last ||
                            (bin_index != 11'd0)) begin
                            sequence_error_count   <= sequence_error_count + 1'b1;
                            dropped_spectrum_count <= dropped_spectrum_count + 1'b1;
                            rejecting_audio        <= !result_last;
                        end else begin
                            collecting_audio         <= 1'b1;
                            write_bank_audio          <= selected_write_bank;
                            expected_bin_audio        <= 11'd1;
                            collect_spectrum_id_audio <= spectrum_id;
                            collect_epoch_audio       <= result_epoch;
                            collect_first_seq_audio   <= first_sample_seq;
                            collect_scale_id_audio    <= scale_id;
                        end
                    end else if ((spectrum_id != collect_spectrum_id_audio) ||
                                 (result_epoch != collect_epoch_audio) ||
                                 (first_sample_seq != collect_first_seq_audio) ||
                                 (scale_id != collect_scale_id_audio)) begin
                        metadata_error_count   <= metadata_error_count + 1'b1;
                        dropped_spectrum_count <= dropped_spectrum_count + 1'b1;
                        collecting_audio       <= 1'b0;
                        rejecting_audio        <= !result_last;
                    end else if (result_first ||
                                 (bin_index != expected_bin_audio) ||
                                 (result_last != (bin_index == LAST_BIN))) begin
                        sequence_error_count   <= sequence_error_count + 1'b1;
                        dropped_spectrum_count <= dropped_spectrum_count + 1'b1;
                        collecting_audio       <= 1'b0;
                        rejecting_audio        <= !result_last;
                    end else begin
                        if (bin_index == LAST_BIN) begin
                            collecting_audio           <= 1'b0;
                            complete_spectrum_count     <= complete_spectrum_count + 1'b1;
                            pending_waiting_audio       <= 1'b1;
                            published_bank_audio        <= write_bank_audio;
                            published_spectrum_id_audio <= collect_spectrum_id_audio;
                            published_epoch_audio       <= collect_epoch_audio;
                            published_first_seq_audio   <= collect_first_seq_audio;
                            published_scale_id_audio    <= collect_scale_id_audio;
                            published_generation_audio  <= next_generation_audio;
                            next_generation_audio       <= next_generation_audio + 1'b1;
                            req_toggle_audio            <= ~req_toggle_audio;
                        end else begin
                            expected_bin_audio <= expected_bin_audio + 1'b1;
                        end
                    end
                end
            end
        end
    end

    // Pixel-domain synchronizers, frame-boundary commit, and one-cycle RAM
    // read response.  Metadata is stable for the entire pending handshake.
    always @(posedge pixel_clk or negedge pixel_rst_n) begin
        if (!pixel_rst_n) begin
            req_sync_pixel_1             <= 1'b0;
            req_sync_pixel_2             <= 1'b0;
            req_sync_pixel_3             <= 1'b0;
            bank_sync_pixel_1            <= 1'b0;
            bank_sync_pixel_2            <= 1'b0;
            spectrum_id_sync_pixel_1     <= 32'd0;
            spectrum_id_sync_pixel_2     <= 32'd0;
            epoch_sync_pixel_1           <= 16'd0;
            epoch_sync_pixel_2           <= 16'd0;
            first_seq_sync_pixel_1       <= 32'd0;
            first_seq_sync_pixel_2       <= 32'd0;
            scale_sync_pixel_1           <= 8'd0;
            scale_sync_pixel_2           <= 8'd0;
            generation_sync_pixel_1      <= 32'd0;
            generation_sync_pixel_2      <= 32'd0;
            audio_up_pixel_1             <= 1'b0;
            audio_up_pixel_2             <= 1'b0;
            ack_toggle_pixel             <= 1'b0;
            ack_accepted_pixel           <= 1'b0;
            pending_pixel                <= 1'b0;
            front_bank_pixel             <= 1'b0;
            expected_generation_pixel    <= 32'd1;
            display_spectrum_id          <= 32'd0;
            display_epoch                <= 16'd0;
            display_first_sample_seq     <= 32'd0;
            display_scale_id             <= 8'd0;
            display_generation           <= 32'd0;
            spectrum_available           <= 1'b0;
            display_commit_count         <= 32'd0;
            no_spectrum_frame_count      <= 32'd0;
            read_error_count             <= 32'd0;
            generation_error_count       <= 32'd0;
            read_valid                   <= 1'b0;
            read_zero_pixel              <= 1'b1;
        end else begin
            req_sync_pixel_1         <= req_toggle_audio;
            req_sync_pixel_2         <= req_sync_pixel_1;
            // The third request stage intentionally trails the two-stage
            // bundled metadata synchronizers by one pixel clock.
            req_sync_pixel_3         <= req_sync_pixel_2;
            bank_sync_pixel_1        <= published_bank_audio;
            bank_sync_pixel_2        <= bank_sync_pixel_1;
            spectrum_id_sync_pixel_1 <= published_spectrum_id_audio;
            spectrum_id_sync_pixel_2 <= spectrum_id_sync_pixel_1;
            epoch_sync_pixel_1       <= published_epoch_audio;
            epoch_sync_pixel_2       <= epoch_sync_pixel_1;
            first_seq_sync_pixel_1   <= published_first_seq_audio;
            first_seq_sync_pixel_2   <= first_seq_sync_pixel_1;
            scale_sync_pixel_1       <= published_scale_id_audio;
            scale_sync_pixel_2       <= scale_sync_pixel_1;
            generation_sync_pixel_1  <= published_generation_audio;
            generation_sync_pixel_2  <= generation_sync_pixel_1;
            audio_up_pixel_1         <= audio_rst_n;
            audio_up_pixel_2         <= audio_up_pixel_1;

            read_valid      <= read_enable;
            read_zero_pixel <= !read_enable || !spectrum_available ||
                               (read_index > LAST_BIN);
            if (!audio_up_pixel_2) begin
                ack_toggle_pixel          <= 1'b0;
                ack_accepted_pixel        <= 1'b0;
                pending_pixel             <= 1'b0;
                spectrum_available        <= 1'b0;
                display_generation        <= 32'd0;
                expected_generation_pixel <= 32'd1;
            end else begin
                if (req_sync_pixel_3 != ack_toggle_pixel)
                    pending_pixel <= 1'b1;

                // Consume only the third request stage. Metadata2 has a
                // complete extra pixel cycle before frame-boundary commit.
                // A request at this boundary can wait until the next frame.
                if (frame_start) begin
                    if (pending_pixel ||
                        (req_sync_pixel_3 != ack_toggle_pixel)) begin
                        if (generation_sync_pixel_2 ==
                            expected_generation_pixel) begin
                            front_bank_pixel         <= bank_sync_pixel_2;
                            display_spectrum_id      <= spectrum_id_sync_pixel_2;
                            display_epoch            <= epoch_sync_pixel_2;
                            display_first_sample_seq <= first_seq_sync_pixel_2;
                            display_scale_id         <= scale_sync_pixel_2;
                            display_generation       <= generation_sync_pixel_2;
                            spectrum_available       <= 1'b1;
                            display_commit_count     <= display_commit_count + 1'b1;
                            expected_generation_pixel <=
                                expected_generation_pixel + 1'b1;
                            ack_accepted_pixel <= 1'b1;
                        end else begin
                            generation_error_count <= generation_error_count + 1'b1;
                            expected_generation_pixel <=
                                generation_sync_pixel_2 + 1'b1;
                            ack_accepted_pixel <= 1'b0;
                        end
                        ack_toggle_pixel <= req_sync_pixel_3;
                        pending_pixel    <= 1'b0;
                    end else if (!spectrum_available) begin
                        no_spectrum_frame_count <= no_spectrum_frame_count + 1'b1;
                    end
                end

                if (read_enable) begin
                    if (!spectrum_available || (read_index > LAST_BIN)) begin
                        read_error_count <= read_error_count + 1'b1;
                    end
                end
            end
        end
    end

endmodule
