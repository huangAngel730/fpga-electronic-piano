// Already-mixed stereo PCM postprocessor: usable after N32 without remixing.
// One accepted token at E, history write E+2, held output after E+3 NBA.
// frame_tick cancels result eligibility, never rolls back accepted history work.
// Bypass is a direct PCM register and DOES NOT clock delay history.
module m1td_stereo_delay (
    input logic clk,rst_n,frame_tick,
    input logic [31:0] current_req_id,
    input logic input_valid,
    output wire input_ready,
    input logic [31:0] input_id,
    input logic signed [23:0] input_left,input_right,
    input logic input_clipped_left,input_clipped_right,
    input logic config_valid,
    output wire config_ready,
    input logic config_enable,
    input logic [15:0] config_delay_samples,
    input logic [14:0] config_dry_gain,config_wet_gain,config_feedback,
    output wire output_valid,
    input logic output_ready,
    output logic [31:0] output_id,
    output logic signed [23:0] output_left,output_right,
    output logic upstream_clipped_left,upstream_clipped_right,
    output logic effect_clipped_left,effect_clipped_right,
    output logic feedback_clipped_left,feedback_clipped_right,
    output wire clipped_left,clipped_right,
    output wire busy
);
    logic enabled;
    logic [15:0] delay_samples;
    logic [14:0] dry_gain,wet_gain,feedback;
    logic processing,killed,token_enabled,seen_id,held_valid;
    assign output_valid=rst_n && !frame_tick && held_valid && output_id==current_req_id;
    logic [1:0] age;
    logic [31:0] token_id,last_id;
    logic signed [23:0] token_left,token_right;
    logic token_clip_left,token_clip_right;
    wire config_take=config_valid && config_ready;
    wire flush=config_take && (config_enable!=enabled || config_delay_samples!=delay_samples);
    wire take=input_valid && input_ready;
    wire launch=take && enabled;
    wire signed [23:0] fx_left,fx_right;
    wire fx_valid_left,fx_valid_right,fx_clip_left,fx_clip_right,fb_clip_left,fb_clip_right;
    assign busy=processing || held_valid;
    assign config_ready=rst_n && !frame_tick && !busy && config_delay_samples<16'd1024;
    assign input_ready=rst_n && !frame_tick && !config_valid && !busy &&
                       input_id==current_req_id && (!seen_id || input_id!=last_id);
    assign clipped_left=upstream_clipped_left || effect_clipped_left;
    assign clipped_right=upstream_clipped_right || effect_clipped_right;
    m1td_delay_effect #(.DEPTH(1024))u_left(.sys_clk(clk),.sys_rst_n(rst_n),.flush(flush),
        .sample_enable(launch),.pcm_in(input_left),.delay_samples(delay_samples),
        .dry_gain(dry_gain),.wet_gain(wet_gain),.feedback(feedback),
        .pcm_out(fx_left),.pcm_valid(fx_valid_left),.output_clipped(fx_clip_left),.feedback_clipped(fb_clip_left));
    m1td_delay_effect #(.DEPTH(1024))u_right(.sys_clk(clk),.sys_rst_n(rst_n),.flush(flush),
        .sample_enable(launch),.pcm_in(input_right),.delay_samples(delay_samples),
        .dry_gain(dry_gain),.wet_gain(wet_gain),.feedback(feedback),
        .pcm_out(fx_right),.pcm_valid(fx_valid_right),.output_clipped(fx_clip_right),.feedback_clipped(fb_clip_right));
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            enabled<=0;delay_samples<=1;dry_gain<=32767;wet_gain<=0;feedback<=0;
            processing<=0;killed<=0;age<=0;token_enabled<=0;seen_id<=0;last_id<=0;
            token_id<=0;token_left<=0;token_right<=0;token_clip_left<=0;token_clip_right<=0;
            held_valid<=0;output_id<=0;output_left<=0;output_right<=0;
            upstream_clipped_left<=0;upstream_clipped_right<=0;
            effect_clipped_left<=0;effect_clipped_right<=0;feedback_clipped_left<=0;feedback_clipped_right<=0;
        end else begin
            if(config_take)begin
                enabled<=config_enable;delay_samples<=config_delay_samples;
                dry_gain<=config_dry_gain;wet_gain<=config_wet_gain;feedback<=config_feedback;
            end
            if(frame_tick)begin held_valid<=0;if(processing)killed<=1;end
            else if(output_valid && output_ready)held_valid<=0;
            if(take)begin
                processing<=1;killed<=0;age<=0;token_enabled<=enabled;
                token_id<=input_id;token_left<=input_left;token_right<=input_right;
                token_clip_left<=input_clipped_left;token_clip_right<=input_clipped_right;
                seen_id<=1;last_id<=input_id;
            end else if(processing)begin
                if(age==2)begin
                    processing<=0;
                    if(!killed && !frame_tick && token_id==current_req_id)begin
                        held_valid<=1;output_id<=token_id;
                        output_left<=token_enabled ? fx_left : token_left;
                        output_right<=token_enabled ? fx_right : token_right;
                        upstream_clipped_left<=token_clip_left;upstream_clipped_right<=token_clip_right;
                        effect_clipped_left<=token_enabled && fx_clip_left;
                        effect_clipped_right<=token_enabled && fx_clip_right;
                        feedback_clipped_left<=token_enabled && fb_clip_left;
                        feedback_clipped_right<=token_enabled && fb_clip_right;
                    end
                end else age<=age+1'b1;
            end
        end
    end
    // synthesis translate_off
    always @(posedge clk)if(rst_n && processing && age==2 && token_enabled)
        if(!fx_valid_left || !fx_valid_right)$fatal(1,"M1TD_EFFECT_VALID_ALIGNMENT");
    // synthesis translate_on
endmodule
