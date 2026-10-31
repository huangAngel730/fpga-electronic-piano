// M2 R6-2 diagnostic candidate. No output feeds the audio production path.
// Single core clock; rst_n asynchronously asserts and is released upstream.
// Observe outputs at POSEDGE_PRE_NBA, the same edge as i2s_tx adoption.
// frame_tick is i2s_tx.frame_start; tx_valid is that transmitter's valid input.
// Epoch belongs to the independent capture RESET_EDGES log: every stored
// tuple here is invalidated on rst_n, never given a fabricated hardware epoch.
// FRAME_ID_WIDTH defaults to the unchanged 32-bit ordinal. A narrower value
// makes saturation reachable in the isolated boundary TB; it does not narrow
// request IDs or the public 32-bit ordinal port. Not a physical admission.
module m2_r06_tx_identity_sidecar #(
    parameter integer FRAME_ID_WIDTH = 32
) (
    input  logic               clk,
    input  logic               rst_n,
    input  logic               frame_tick,
    input  logic               tx_valid,
    input  logic               result_valid,
    input  logic               result_ready,
    input  logic [31:0]        result_id,
    input  logic [1:0]         result_clip_mask,
    input  logic               commit_pulse,
    input  logic [31:0]        commit_id,
    input  logic signed [23:0] commit_left,
    input  logic signed [23:0] commit_right,
    input  logic               buffer_pending_valid,
    input  logic signed [23:0] play_left,
    input  logic signed [23:0] play_right,
    output wire                tx_sample_valid,
    output wire                tx_metadata_valid,
    output wire                tx_req_id_valid,
    output wire [31:0]         tx_frame_id,
    output wire [31:0]         tx_req_id,
    output wire [1:0]          tx_clip_mask,
    output wire                tx_clip_any,
    output wire                tx_hold,
    output wire                tx_startup_zero,
    output wire signed [23:0]  tx_left,
    output wire signed [23:0]  tx_right,
    output wire                metadata_error,
    output wire                frame_id_overflow
);
    // pcm_result_hold stores only clip-any. Preserve both clip bits before
    // that OR, with the identical result/commit/frame priority. bit0=left,
    // bit1=right. A later result bus value must never label an earlier commit.
    logic result_hold_tag_valid;
    logic [31:0] result_hold_id;
    logic [1:0] result_hold_clip_mask;

    // Storage-valid is distinct from identity-valid. Missing identity after
    // an error is not startup silence and cannot manufacture a null HOLD.
    logic pending_storage_valid, pending_id_valid;
    logic [31:0] pending_id;
    logic [1:0] pending_clip_mask;
    logic signed [23:0] pending_left, pending_right;
    logic held_storage_valid, held_id_valid;
    logic [31:0] held_id;
    logic [1:0] held_clip_mask;
    logic signed [23:0] held_left, held_right;
    logic [FRAME_ID_WIDTH-1:0] next_tx_frame_id;
    logic frame_id_overflow_sticky, metadata_error_sticky;

    wire return_accept = result_valid && result_ready;
    wire selected_id_valid = buffer_pending_valid ?
                             pending_id_valid : held_id_valid;
    wire selected_storage_valid = buffer_pending_valid ?
                                  pending_storage_valid : held_storage_valid;
    wire selected_startup = !buffer_pending_valid && !held_storage_valid;

    // These checks diagnose disagreement without changing PCM, ready, valid,
    // cancellation, clock, reset, or any other production control signal.
    wire metadata_error_now =
        (buffer_pending_valid != pending_storage_valid) ||
        (buffer_pending_valid &&
            ((play_left != pending_left) || (play_right != pending_right))) ||
        (!buffer_pending_valid && held_storage_valid &&
            ((play_left != held_left) || (play_right != held_right))) ||
        (selected_startup && ((play_left != 24'sd0) ||
                              (play_right != 24'sd0))) ||
        (frame_tick && (commit_pulse || return_accept)) ||
        (!frame_tick && commit_pulse &&
            (!result_hold_tag_valid || (commit_id != result_hold_id))) ||
        (!frame_tick && return_accept &&
            (result_hold_tag_valid || commit_pulse));

    // This is the actual hardware adoption predicate even if metadata is bad.
    // Never suppress an observed TX sample because its label is unusable.
    assign tx_sample_valid = rst_n && frame_tick && tx_valid;
    assign frame_id_overflow = frame_id_overflow_sticky;
    assign metadata_error = rst_n &&
                            (metadata_error_sticky || metadata_error_now);
    assign tx_metadata_valid = tx_sample_valid && !metadata_error &&
                               !frame_id_overflow &&
                               (selected_startup ||
                                (selected_storage_valid && selected_id_valid));
    assign tx_req_id_valid = tx_metadata_valid && !selected_startup;
    assign tx_frame_id = {{(32-FRAME_ID_WIDTH){1'b0}}, next_tx_frame_id};
    assign tx_req_id = buffer_pending_valid ? pending_id : held_id;
    assign tx_clip_mask = buffer_pending_valid ? pending_clip_mask :
                                                held_clip_mask;
    assign tx_clip_any = |tx_clip_mask;
    assign tx_hold = tx_sample_valid && !buffer_pending_valid &&
                     held_storage_valid;
    assign tx_startup_zero = tx_sample_valid && selected_startup;
    // Exactly the signed PCM24 sampled by i2s_tx before its 24-to-16 quantizer.
    assign tx_left = play_left;
    assign tx_right = play_right;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result_hold_tag_valid <= 1'b0;
            result_hold_id <= '0;
            result_hold_clip_mask <= '0;
        end else if (frame_tick) begin
            result_hold_tag_valid <= 1'b0;
            result_hold_clip_mask <= '0;
        end else if (commit_pulse) begin
            result_hold_tag_valid <= 1'b0;
            result_hold_clip_mask <= '0;
        end else if (return_accept) begin
            result_hold_tag_valid <= 1'b1;
            result_hold_id <= result_id;
            result_hold_clip_mask <= result_clip_mask;
        end
    end

    // On FRAME, TX uses the old selection above while these NBA assignments
    // move the old pending tuple into held, exactly as pcm_frame_buffer does.
    // Commit is exclusively pcm_valid && pcm_ready; it is not result accept.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pending_storage_valid <= 1'b0;
            pending_id_valid <= 1'b0;
            pending_id <= '0;
            pending_clip_mask <= '0;
            pending_left <= '0;
            pending_right <= '0;
            held_storage_valid <= 1'b0;
            held_id_valid <= 1'b0;
            held_id <= '0;
            held_clip_mask <= '0;
            held_left <= '0;
            held_right <= '0;
        end else if (frame_tick) begin
            if (buffer_pending_valid) begin
                held_storage_valid <= 1'b1;
                held_id_valid <= pending_storage_valid && pending_id_valid;
                held_id <= pending_id;
                held_clip_mask <= pending_clip_mask;
                held_left <= pending_left;
                held_right <= pending_right;
            end
            pending_storage_valid <= 1'b0;
            pending_id_valid <= 1'b0;
        end else if (commit_pulse) begin
            pending_storage_valid <= 1'b1;
            pending_id_valid <= result_hold_tag_valid &&
                                (commit_id == result_hold_id);
            pending_id <= commit_id;
            pending_clip_mask <= result_hold_clip_mask;
            pending_left <= commit_left;
            pending_right <= commit_right;
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            next_tx_frame_id <= '0;
            frame_id_overflow_sticky <= 1'b0;
            metadata_error_sticky <= 1'b0;
        end else begin
            if (metadata_error_now)
                metadata_error_sticky <= 1'b1;
            if (tx_sample_valid && !frame_id_overflow_sticky) begin
                if (&next_tx_frame_id)
                    frame_id_overflow_sticky <= 1'b1;
                else
                    next_tx_frame_id <= next_tx_frame_id + 1'b1;
            end
        end
    end
`ifndef SYNTHESIS
    initial if (FRAME_ID_WIDTH < 1 || FRAME_ID_WIDTH > 32)
        $fatal(1, "FRAME_ID_WIDTH must be in 1..32");
`endif
endmodule
