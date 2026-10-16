// M2 isolated transport candidate, NOT in the production project.
// Single clk, async low reset assert/synchronized release upstream.
// Already mixed signed PCM24. clipped must accompany result_id; frozen b2d
// does not currently export that metadata. No second mixer or algorithm here.
module premixed_frame_adapter (
    input logic clk,rst_n,frame_tick,
    output wire candidate_cancel,candidate_sample_valid,
    input logic candidate_sample_ready,
    output wire [31:0] candidate_sample_id,
    input logic candidate_result_valid,
    output wire candidate_result_ready,
    input logic [31:0] candidate_result_id,
    input logic signed [23:0] candidate_left,candidate_right,
    input logic candidate_clipped,
    output wire signed [23:0] play_left,play_right,
    output wire pending_valid,commit_pulse,
    output wire [31:0] frame_count,frame_request_count,commit_count,underrun_count,clip_count,
    output wire [31:0] current_id,committed_id,
    output wire signed [23:0] committed_left,committed_right,
    output wire committed_clip,dispatched_this_frame
);
    wire frame_sample_req;
    logic queued_request,dispatched;
    logic [31:0] queued_id;
    wire request_present=queued_request || frame_sample_req;
    assign candidate_cancel=frame_tick;
    assign candidate_sample_id=queued_request ? queued_id : current_id;
`ifdef M2_FRAME_MUTANT_ACCEPT_FRAME
    assign candidate_sample_valid=rst_n && request_present;
`else
    assign candidate_sample_valid=rst_n && !frame_tick && request_present;
`endif
    wire request_accept=candidate_sample_valid && candidate_sample_ready;
    assign dispatched_this_frame=dispatched;
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin queued_request<=0;queued_id<=0;dispatched<=0;end
        else if(frame_tick) begin queued_request<=0;dispatched<=0;end
        else begin
            if(request_accept) begin queued_request<=0;dispatched<=1;end
            else if(frame_sample_req) begin queued_request<=1;queued_id<=current_id;end
        end
    end
    wire pcm_valid,pcm_ready,pcm_clip,hold_ready;
    wire [31:0] pcm_id;
    wire signed [23:0] pcm_left,pcm_right;
    wire valid_current_result=candidate_result_valid && dispatched;
    assign candidate_result_ready=hold_ready && dispatched;
    pcm_result_hold result_hold (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(1'b1),
        .current_req_id(current_id),.result_valid(valid_current_result),
        .result_ready(hold_ready),.result_req_id(candidate_result_id),
        .result_left(candidate_left),.result_right(candidate_right),
        .result_clip_any(candidate_clipped),.pcm_valid(pcm_valid),.pcm_ready(pcm_ready),
        .pcm_req_id(pcm_id),.pcm_left(pcm_left),.pcm_right(pcm_right),.pcm_clip_any(pcm_clip)
    );
    pcm_frame_buffer frame_buffer (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(1'b1),
        .sample_req(frame_sample_req),.sample_req_id(current_id),
        .pcm_valid(pcm_valid),.pcm_ready(pcm_ready),.pcm_req_id(pcm_id),
        .pcm_left(pcm_left),.pcm_right(pcm_right),.play_left(play_left),.play_right(play_right),
        .pending_valid(pending_valid),.audio_frame_count(frame_count),
        .pcm_request_count(frame_request_count),.pcm_commit_count(commit_count),
        .audio_underrun(underrun_count)
    );
    assign commit_pulse=pcm_valid && pcm_ready;
    assign committed_id=pcm_id;
    assign committed_left=pcm_left;
    assign committed_right=pcm_right;
    assign committed_clip=pcm_clip;
`ifdef M2_FRAME_MUTANT_CLIP_EVERY_VALID
    pcm_clip_counter clip_counter(.clk(clk),.rst_n(rst_n),
        .pcm_valid(candidate_result_valid),.pcm_ready(1'b1),
        .clip_any(candidate_clipped),.clip_count(clip_count));
`else
    pcm_clip_counter clip_counter(.clk(clk),.rst_n(rst_n),
        .pcm_valid(pcm_valid),.pcm_ready(pcm_ready),.clip_any(pcm_clip),.clip_count(clip_count));
`endif
endmodule
