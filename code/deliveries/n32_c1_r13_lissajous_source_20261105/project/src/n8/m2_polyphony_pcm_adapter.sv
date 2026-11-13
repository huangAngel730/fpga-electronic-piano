// One unchanged frozen M1 stereo postprocessor, after the complete N-voice mix.
// Candidate interface: clip_bits[7:0]={feedbackR,feedbackL,effectR,effectL,
// upstreamR,upstreamL,clipR,clipL}. Flags qualify exactly the held result ID.
// cancel/frame_tick kills eligibility, not already accepted effect-history work.
module m2_polyphony_pcm_adapter (
    input wire clk,rst_n,cancel,frame_tick,
    input wire [31:0] current_req_id,
    input wire input_valid,
    output wire input_ready,
    input wire [31:0] input_id,
    input wire signed [23:0] input_left,input_right,
    input wire input_clip_left,input_clip_right,
    input wire config_valid,
    output wire config_ready,
    input wire config_enable,
    input wire [15:0] config_delay_samples,
    input wire [14:0] config_dry_gain,config_wet_gain,config_feedback,
    output wire result_valid,
    input wire result_ready,
    output wire [31:0] result_id,
    output wire signed [23:0] left,right,
    output wire [7:0] clip_bits,
    output wire busy
);
    wire clip_l,clip_r,up_l,up_r,fx_l,fx_r,fb_l,fb_r;
    m1td_stereo_delay post(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick || cancel),
        .current_req_id(current_req_id),
        .input_valid(input_valid && !cancel),.input_ready(input_ready),
        .input_id(input_id),.input_left(input_left),.input_right(input_right),
        .input_clipped_left(input_clip_left),.input_clipped_right(input_clip_right),
        .config_valid(config_valid && !cancel),.config_ready(config_ready),
        .config_enable(config_enable),.config_delay_samples(config_delay_samples),
        .config_dry_gain(config_dry_gain),.config_wet_gain(config_wet_gain),
        .config_feedback(config_feedback),.output_valid(result_valid),
        .output_ready(result_ready),.output_id(result_id),
        .output_left(left),.output_right(right),
        .upstream_clipped_left(up_l),.upstream_clipped_right(up_r),
        .effect_clipped_left(fx_l),.effect_clipped_right(fx_r),
        .feedback_clipped_left(fb_l),.feedback_clipped_right(fb_r),
        .clipped_left(clip_l),.clipped_right(clip_r),.busy(busy));
    assign clip_bits={fb_r,fb_l,fx_r,fx_l,up_r,up_l,clip_r,clip_l};
endmodule
