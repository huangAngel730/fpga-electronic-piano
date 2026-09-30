// T024/T025/T055 M2 result-to-commit integration; no amplitude policy here.
// Inputs are four already-defined signed PCM24 lanes per stereo result.
// The producer holds lanes and request ID until result_ready. All in clk domain.
// rst_n asynchronously asserts; caller must synchronize reset release.
module polyphonic_pcm_commit (
    input logic clk, rst_n, frame_tick, calc_ready,
    output wire sample_req,
    output wire [31:0] sample_req_id,
    input logic result_valid,
    output wire result_ready,
    input logic [31:0] result_req_id,
    input logic [95:0] voices_left, voices_right,
    output wire signed [23:0] play_left, play_right,
    output wire pending_valid,
    output wire [31:0] audio_frame_count, pcm_request_count, pcm_commit_count,
    output wire [31:0] audio_underrun, clip_count
);
    wire signed [23:0] mixed_left,mixed_right,pcm_left,pcm_right;
    wire clip_left,clip_right,clip_any,pcm_clip_any,pcm_valid,pcm_ready;
    wire [31:0] pcm_req_id;
    pcm_mixer_4voice u_mixer (
        .voices_left(voices_left),.voices_right(voices_right),
        .mixed_left(mixed_left),.mixed_right(mixed_right),
        .clip_left(clip_left),.clip_right(clip_right),.clip_any(clip_any)
    );
    pcm_result_hold u_result_hold (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .current_req_id(sample_req_id),.result_valid(result_valid),.result_ready(result_ready),
        .result_req_id(result_req_id),.result_left(mixed_left),.result_right(mixed_right),
        .result_clip_any(clip_any),.pcm_valid(pcm_valid),.pcm_ready(pcm_ready),
        .pcm_req_id(pcm_req_id),.pcm_left(pcm_left),.pcm_right(pcm_right),.pcm_clip_any(pcm_clip_any)
    );
    pcm_frame_buffer u_frame_buffer (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .sample_req(sample_req),.sample_req_id(sample_req_id),
        .pcm_valid(pcm_valid),.pcm_ready(pcm_ready),.pcm_req_id(pcm_req_id),
        .pcm_left(pcm_left),.pcm_right(pcm_right),.play_left(play_left),.play_right(play_right),
        .pending_valid(pending_valid),.audio_frame_count(audio_frame_count),
        .pcm_request_count(pcm_request_count),.pcm_commit_count(pcm_commit_count),.audio_underrun(audio_underrun)
    );
    pcm_clip_counter u_clip_counter (
        .clk(clk),.rst_n(rst_n),.pcm_valid(pcm_valid),.pcm_ready(pcm_ready),
        .clip_any(pcm_clip_any),.clip_count(clip_count)
    );
endmodule