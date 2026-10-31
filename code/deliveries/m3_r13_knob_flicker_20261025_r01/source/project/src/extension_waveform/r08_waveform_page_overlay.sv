// Reserved analysis side branch. Actual waveform/spectrum engines are deferred.
// Page/timbre state crosses atomically; display commits it only at frame_start.
// Scene and placeholder both have exactly five pixel captures. No sixth stage.
// Future engine return ports must already refer to that same five-capture pixel.
`timescale 1ns/1ps
module r08_waveform_page_overlay #(
    parameter bit WAVEFORM_ATTACHED=1'b0,
    parameter bit SPECTRUM_ATTACHED=1'b0
)(
    input wire core_clk,pixel_clk,core_rst_n,pixel_rst_n,
    input wire [1:0] page_select,
    input wire selected_timbre,
    input wire audio_frame_load,
    input wire signed [23:0] play_left,play_right,
    input wire [15:0] pixel_x,pixel_y,
    input wire data_enable,hsync,vsync,frame_start,desync_latched,
    input wire [7:0] scene_r,scene_g,scene_b,
    input wire scene_de,scene_hs,scene_vs,
    // Future pixel-domain algorithm returns, aligned by exactly five captures.
    // Attach parameters are static capabilities, never ready/backpressure.
    input wire waveform_mask_aligned,spectrum_mask_aligned,
    input wire [23:0] waveform_rgb_aligned,spectrum_rgb_aligned,
    // Public future analysis source: core-domain actual I2S-adopted PCM.
    output wire analysis_sample_valid,
    output wire [31:0] analysis_sample_seq,
    output wire signed [23:0] analysis_left,analysis_right,
    output wire analysis_selected_timbre,
    output wire [1:0] analysis_page_select,
    output wire analysis_view_selected,
    output wire [1:0] page_for_pixel,
    output wire [1:0] page_aligned,
    output logic [7:0] rgb_r,rgb_g,rgb_b,
    output wire out_de,out_hs,out_vs,
    output wire waveform_trace_valid,
    output wire [31:0] observation_drop_count,display_gap_count,window_drop_count
);
    function automatic [1:0] safe_page(input [1:0] value);
        case(value)2'd1:safe_page=1;2'd2:safe_page=2;2'd3:safe_page=3;default:safe_page=0;endcase
    endfunction
    wire [2:0] requested_state={selected_timbre,safe_page(page_select)};
    logic sent_valid;
    logic [2:0] sent_state;
    wire page_src_ready,page_dst_valid,page_src_up,page_dst_up;
    wire [2:0] page_dst_data;
    wire page_send=core_rst_n && (!sent_valid || requested_state!=sent_state);
    visual_mailbox_cdc #(.WIDTH(3)) u_page_mailbox(
        .src_clk(core_clk),.dst_clk(pixel_clk),.rst_n(core_rst_n && pixel_rst_n),
        .src_valid(page_send),.src_ready(page_src_ready),.src_data(requested_state),
        .dst_valid(page_dst_valid),.dst_ready(1'b1),.dst_data(page_dst_data),
        .src_reset_done(page_src_up),.dst_reset_done(page_dst_up));
    always_ff @(posedge core_clk or negedge page_src_up)begin
        if(!page_src_up)begin sent_valid<=0;sent_state<=0;end
        else if(page_send && page_src_ready)begin sent_valid<=1;sent_state<=requested_state;end
    end
    logic [2:0] pending_state,committed_state;
    wire [2:0] newest_state=page_dst_valid ? page_dst_data : pending_state;
    assign page_for_pixel=frame_start ? newest_state[1:0] : committed_state[1:0];
    wire timbre_for_pixel=frame_start ? newest_state[2] : committed_state[2];
    always_ff @(posedge pixel_clk or negedge pixel_rst_n)begin
        if(!pixel_rst_n)begin pending_state<=0;committed_state<=0;end
        else begin
            if(page_dst_valid)pending_state<=page_dst_data;
            if(frame_start)committed_state<=newest_state;
        end
    end
    pcm_frame_observer u_analysis_observer(
        .audio_clk(core_clk),.audio_rst_n(core_rst_n),
        .frame_load(audio_frame_load),.play_left(play_left),.play_right(play_right),
        .observed_valid(analysis_sample_valid),.observed_seq(analysis_sample_seq),
        .observed_left(analysis_left),.observed_right(analysis_right));
    assign analysis_selected_timbre=selected_timbre;
    assign analysis_page_select=page_select;
    assign analysis_view_selected=page_select[1];
    // No engine is attached: these compatibility counters are inactive, not
    // a claim that a waveform engine ran without loss.
    assign waveform_trace_valid=1'b0;
    assign observation_drop_count=32'd0;
    assign display_gap_count=32'd0;
    assign window_drop_count=32'd0;
    wire [7:0] pending_r,pending_g,pending_b;
    pro_reserved_analysis_page u_pending_page(
        .pixel_clk(pixel_clk),.rst_n(pixel_rst_n),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.data_enable(data_enable),
        .page_is_spectrum(page_for_pixel[0]),.selected_timbre(timbre_for_pixel),
        .rgb_r(pending_r),.rgb_g(pending_g),.rgb_b(pending_b));
    logic [1:0] page_pipe[0:4];
    logic [15:0] x_pipe[0:4],y_pipe[0:4];
    logic [4:0] fault_pipe;
    integer k;
    always_ff @(posedge pixel_clk or negedge pixel_rst_n)begin
        if(!pixel_rst_n)begin
            fault_pipe<=0;
            for(k=0;k<5;k=k+1)begin page_pipe[k]<=0;x_pipe[k]<=0;y_pipe[k]<=0;end
        end else begin
            page_pipe[0]<=page_for_pixel;x_pipe[0]<=pixel_x;y_pipe[0]<=pixel_y;
            fault_pipe<={fault_pipe[3:0],desync_latched};
            for(k=1;k<5;k=k+1)begin page_pipe[k]<=page_pipe[k-1];x_pipe[k]<=x_pipe[k-1];y_pipe[k]<=y_pipe[k-1];end
        end
    end
    assign page_aligned=page_pipe[4];
    assign out_de=scene_de;assign out_hs=scene_hs;assign out_vs=scene_vs;
    always_comb begin
        {rgb_r,rgb_g,rgb_b}={scene_r,scene_g,scene_b};
        if(page_pipe[4]==2)begin
            if(WAVEFORM_ATTACHED){rgb_r,rgb_g,rgb_b}=waveform_mask_aligned ? waveform_rgb_aligned : 24'd0;
            else {rgb_r,rgb_g,rgb_b}={pending_r,pending_g,pending_b};
        end else if(page_pipe[4]==3)begin
            if(SPECTRUM_ATTACHED){rgb_r,rgb_g,rgb_b}=spectrum_mask_aligned ? spectrum_rgb_aligned : 24'd0;
            else {rgb_r,rgb_g,rgb_b}={pending_r,pending_g,pending_b};
        end
        if(fault_pipe[4] && y_pipe[4]<18)
            {rgb_r,rgb_g,rgb_b}=x_pipe[4][4] ? 24'hff2828 : 24'h800808;
        if(!scene_de){rgb_r,rgb_g,rgb_b}=0;
    end
endmodule
