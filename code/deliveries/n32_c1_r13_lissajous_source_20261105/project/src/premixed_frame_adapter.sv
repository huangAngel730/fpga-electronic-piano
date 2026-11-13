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
    // Hold-only identity path for the frame-buffer request identifier.  The
    // queued request is still captured on the same edge with the same value.
    (* syn_keep=1, syn_dont_touch=1 *) wire [31:0] queued_id_input_hold;
    for(genvar queued_id_bit=0;queued_id_bit<32;queued_id_bit=queued_id_bit+1)begin:g_queued_id_hold
        (* syn_keep=1, syn_dont_touch=1 *)wire[2:0]chain;
        assign chain[0]=current_id[queued_id_bit];
        for(genvar queued_id_stage=0;queued_id_stage<2;queued_id_stage=queued_id_stage+1)begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *)LUT1 #(.INIT(2'h2))u_identity(
                .I0(chain[queued_id_stage]),.F(chain[queued_id_stage+1]));
        end
        assign queued_id_input_hold[queued_id_bit]=chain[2];
    end
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
            else if(frame_sample_req) begin queued_request<=1;queued_id<=queued_id_input_hold;end
        end
    end
    wire pcm_valid,pcm_ready,pcm_clip,hold_ready;
    wire [31:0] pcm_id;
    wire signed [23:0] pcm_left,pcm_right;
    (* syn_keep=1, syn_dont_touch=1 *) wire signed [23:0] pcm_left_hold,pcm_right_hold;
    for(genvar pcm_hold_bit=0;pcm_hold_bit<24;pcm_hold_bit=pcm_hold_bit+1)begin:g_pcm_commit_hold
        (* syn_keep=1, syn_dont_touch=1 *)wire[2:0]left_chain,right_chain;
        assign left_chain[0]=pcm_left[pcm_hold_bit];
        assign right_chain[0]=pcm_right[pcm_hold_bit];
        for(genvar pcm_hold_stage=0;pcm_hold_stage<2;pcm_hold_stage=pcm_hold_stage+1)begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *)LUT1 #(.INIT(2'h2))u_left_identity(
                .I0(left_chain[pcm_hold_stage]),.F(left_chain[pcm_hold_stage+1]));
            (* syn_keep=1, syn_dont_touch=1 *)LUT1 #(.INIT(2'h2))u_right_identity(
                .I0(right_chain[pcm_hold_stage]),.F(right_chain[pcm_hold_stage+1]));
        end
        assign pcm_left_hold[pcm_hold_bit]=left_chain[2];
        assign pcm_right_hold[pcm_hold_bit]=right_chain[2];
    end
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
        .pcm_left(pcm_left_hold),.pcm_right(pcm_right_hold),.play_left(play_left),.play_right(play_right),
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
