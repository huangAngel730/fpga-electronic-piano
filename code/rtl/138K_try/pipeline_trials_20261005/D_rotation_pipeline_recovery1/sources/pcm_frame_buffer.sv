// T055: one pending stereo sample per I2S frame, sys_clk domain only.
// rst_n: active-low asynchronous assertion, synchronous release upstream.
// frame_tick denotes completion of one whole left+right frame, not an LRCLK edge.
`timescale 1ns/1ps
module pcm_frame_buffer #(
    parameter int unsigned PCM_WIDTH = 24,
    parameter int unsigned ID_WIDTH = 32
) (
    input  logic                        clk,
    input  logic                        rst_n,
    input  logic                        frame_tick,
    input  logic                        calc_ready,
    output logic                        sample_req,
    output logic [ID_WIDTH-1:0]         sample_req_id,
    input  logic                        pcm_valid,
    output logic                        pcm_ready,
    input  logic [ID_WIDTH-1:0]         pcm_req_id,
    input  logic signed [PCM_WIDTH-1:0] pcm_left,
    input  logic signed [PCM_WIDTH-1:0] pcm_right,
    output logic signed [PCM_WIDTH-1:0] play_left,
    output logic signed [PCM_WIDTH-1:0] play_right,
    output logic                        pending_valid,
    output logic [31:0]                 audio_frame_count,
    output logic [31:0]                 pcm_request_count,
    output logic [31:0]                 pcm_commit_count,
    output logic [31:0]                 audio_underrun
);
    logic signed [PCM_WIDTH-1:0] pending_left, pending_right;
    logic signed [PCM_WIDTH-1:0] held_left, held_right;
    logic ever_committed, request_active;
    assign play_left = pending_valid ? pending_left : held_left;
    assign play_right = pending_valid ? pending_right : held_right;

    // An old frame must be cancelled by the producer when the ID changes.
    // A handshake is exclusively a successful buffer commit, never a discard.
    assign pcm_ready = rst_n && request_active && !frame_tick && !pending_valid &&
                       (pcm_req_id == sample_req_id);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_req        <= 1'b0;
            sample_req_id     <= '0;
            pending_valid     <= 1'b0;
            pending_left      <= '0;
            pending_right     <= '0;
            held_left         <= '0;
            held_right        <= '0;
            request_active    <= 1'b0;
            ever_committed    <= 1'b0;
            audio_frame_count <= '0;
            pcm_request_count <= '0;
            pcm_commit_count  <= '0;
            audio_underrun    <= '0;
        end else begin
            sample_req <= 1'b0;
            if (frame_tick) begin
                if (audio_frame_count != 32'hffff_ffff)
                    audio_frame_count <= audio_frame_count + 1'b1;
                sample_req_id <= sample_req_id + 1'b1;
                request_active <= calc_ready;
                if (calc_ready) begin
                    sample_req <= 1'b1;
                    if (pcm_request_count != 32'hffff_ffff)
                        pcm_request_count <= pcm_request_count + 1'b1;
                end
                if (pending_valid) begin
                    held_left      <= pending_left;
                    held_right     <= pending_right;
                    pending_valid  <= 1'b0;
                    ever_committed <= 1'b1;
                end else if (ever_committed && audio_underrun != 32'hffff_ffff) begin
                    audio_underrun <= audio_underrun + 1'b1;
                end
            end else if (pcm_valid && pcm_ready) begin
                pending_left  <= pcm_left;
                pending_right <= pcm_right;
                pending_valid <= 1'b1;
                request_active <= 1'b0;
                if (pcm_commit_count != 32'hffff_ffff)
                    pcm_commit_count <= pcm_commit_count + 1'b1;
            end
        end
    end
endmodule
