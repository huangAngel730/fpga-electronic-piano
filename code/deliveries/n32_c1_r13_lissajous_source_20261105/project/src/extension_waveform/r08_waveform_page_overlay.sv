// Shared actual-playback analysis branch: one observer, one waveform, one FFT.
// K3 changes the sound producer; neither analysis engine filters by UI timbre.
// Page/timbre state crosses atomically; display commits it only at frame_start.
// Scene and placeholder both have exactly five pixel captures. No sixth stage.
// Future engine return ports must already refer to that same five-capture pixel.
`timescale 1ns/1ps
module r08_waveform_page_overlay #(
    parameter bit WAVEFORM_ATTACHED=1'b0,
    parameter bit SPECTRUM_ATTACHED=1'b0
)(
    input wire core_clk,pixel_clk,core_rst_n,pixel_rst_n,
    input wire [2:0] page_select,
    input wire selected_timbre,
    input wire audio_frame_load,
    input wire signed [23:0] play_left,play_right,
    input wire [15:0] pixel_x,pixel_y,
    input wire data_enable,hsync,vsync,frame_start,desync_latched,
    input wire [7:0] scene_r,scene_g,scene_b,
    input wire scene_de,scene_hs,scene_vs,
    // Public future analysis source: core-domain actual I2S-adopted PCM.
    output wire analysis_sample_valid,
    output wire [31:0] analysis_sample_seq,
    output wire signed [23:0] analysis_left,analysis_right,
    output wire analysis_selected_timbre,
    output wire [2:0] analysis_page_select,
    output wire analysis_view_selected,
    output wire [2:0] page_for_pixel,
    output wire [2:0] page_aligned,
    output logic [7:0] rgb_r,rgb_g,rgb_b,
    output wire out_de,out_hs,out_vs,
    output wire waveform_trace_valid,
    output wire [31:0] observation_drop_count,display_gap_count,window_drop_count
);
    wire [2:0] safe_page=page_select<=3'd4 ? page_select : 3'd0;
    wire [3:0] requested_state={selected_timbre,safe_page};
    logic sent_valid;
    logic [3:0] sent_state;
    wire page_src_ready,page_dst_valid,page_src_up,page_dst_up;
    wire [3:0] page_dst_data;
    wire page_send=core_rst_n && (!sent_valid || requested_state!=sent_state);
    visual_mailbox_cdc #(.WIDTH(4)) u_page_mailbox(
        .src_clk(core_clk),.dst_clk(pixel_clk),.rst_n(core_rst_n && pixel_rst_n),
        .src_valid(page_send),.src_ready(page_src_ready),.src_data(requested_state),
        .dst_valid(page_dst_valid),.dst_ready(1'b1),.dst_data(page_dst_data),
        .src_reset_done(page_src_up),.dst_reset_done(page_dst_up));
    always_ff @(posedge core_clk or negedge page_src_up)begin
        if(!page_src_up)begin sent_valid<=0;sent_state<=0;end
        else if(page_send && page_src_ready)begin sent_valid<=1;sent_state<=requested_state;end
    end
    logic [3:0] pending_state,committed_state;
    wire [3:0] newest_state=page_dst_valid ? page_dst_data : pending_state;
    assign page_for_pixel=frame_start ? newest_state[2:0] : committed_state[2:0];
    wire timbre_for_pixel=frame_start ? newest_state[3] : committed_state[3];
    always_ff @(posedge pixel_clk or negedge pixel_rst_n)begin
        if(!pixel_rst_n)begin pending_state<=0;committed_state<=0;end
        else begin
            if(page_dst_valid)pending_state<=page_dst_data;
            if(frame_start)committed_state<=newest_state;
        end
    end
    // One M2 observer samples precisely the actual I2S-adopted pre-NBA mix.
    // Both engines observe continuously, even when another page is visible.
    wire waveform_mask_aligned,spectrum_mask_aligned;
    wire [23:0] waveform_rgb_aligned,spectrum_rgb_aligned;
    wire waveform_de_aligned,spectrum_de_aligned;
    wire spectrum_available,spectrum_render_available,spectrum_busy;
    wire [31:0] spectrum_complete_count,spectrum_drop_count;
    wire lissajous_reset_n,lissajous_stream_restart,lissajous_sample_valid;
    wire [31:0] lissajous_sample_seq;
    wire signed [23:0] lissajous_sample_left,lissajous_sample_right;
    k4_waveform_engine u_shared_waveform(
        .core_clk(core_clk),.pixel_clk(pixel_clk),
        .core_rst_n(core_rst_n),.pixel_rst_n(pixel_rst_n),
        .audio_frame_load(audio_frame_load),.play_left(play_left),.play_right(play_right),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.data_enable(data_enable),
        .frame_start(frame_start),.view_enable(page_for_pixel==3'd2),
        .waveform_mask(waveform_mask_aligned),.waveform_rgb(waveform_rgb_aligned),
        .data_enable_out(waveform_de_aligned),
        .observed_valid(analysis_sample_valid),.observed_seq(analysis_sample_seq),
        .observed_left(analysis_left),.observed_right(analysis_right),
        .pixel_reset_done(lissajous_reset_n),.stream_restart(lissajous_stream_restart),
        .pixel_sample_valid(lissajous_sample_valid),.pixel_sample_seq(lissajous_sample_seq),
        .pixel_sample_left(lissajous_sample_left),.pixel_sample_right(lissajous_sample_right),
        .trace_valid(waveform_trace_valid),.display_gap_count(display_gap_count),
        .window_drop_count(window_drop_count),.observation_drop_count(observation_drop_count));
    k4_spectrum_engine u_shared_spectrum(
        .core_clk(core_clk),.core_rst_n(core_rst_n),
        .pixel_clk(pixel_clk),.pixel_rst_n(pixel_rst_n),
        .sample_valid(analysis_sample_valid),.sample_seq(analysis_sample_seq),
        .pcm_mono(analysis_left),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.data_enable(data_enable),
        .frame_start(frame_start),.view_enable(page_for_pixel==3'd3),
        .spectrum_mask(spectrum_mask_aligned),.spectrum_rgb(spectrum_rgb_aligned),
        .data_enable_out(spectrum_de_aligned),
        .snapshot_available(spectrum_available),.render_available(spectrum_render_available),
        .complete_spectrum_count(spectrum_complete_count),.snapshot_drop_count(spectrum_drop_count),
        .candidate_busy(spectrum_busy));
    assign analysis_selected_timbre=selected_timbre;
    assign analysis_page_select=page_select;
    assign analysis_view_selected=page_select>=3'd2 && page_select<=3'd4;
    // PCM already crossed into pixel_clk through u_shared_waveform.u_bridge.
    // Hold activity across silent samples within the note's decay or echo.
    wire lissajous_enable=page_for_pixel==3'd4;
    logic lissajous_active;
    logic [10:0] lissajous_silent_samples;
    always_ff @(posedge pixel_clk) begin
        if(!lissajous_reset_n || !lissajous_enable || lissajous_stream_restart) begin
            lissajous_active<=0;
            lissajous_silent_samples<=0;
        end else if(lissajous_sample_valid) begin
            if((|lissajous_sample_left) || (|lissajous_sample_right)) begin
                lissajous_active<=1;
                lissajous_silent_samples<=0;
            end else if(&lissajous_silent_samples) begin
                lissajous_active<=0;
            end else begin
                lissajous_silent_samples<=lissajous_silent_samples+1'b1;
            end
        end
    end
    wire [23:0] lissajous_rgb;
    wire lissajous_mask,lissajous_trace;
    wire [31:0] lissajous_published_frames;
    piano_lissajous_candidate u_lissajous(
        .pixel_clk(pixel_clk),.pixel_rst_n(lissajous_reset_n),
        .enable(lissajous_enable),.activity(lissajous_active),
        .stream_restart(lissajous_stream_restart),
        .sample_valid(lissajous_sample_valid),.sample_seq(lissajous_sample_seq),
        .pcm_left(lissajous_sample_left),.pcm_right(lissajous_sample_right),
        .stereo_mode(1'b0),.delay_samples(8'd27),.gain_shift(3'd1),
        .timbre_id({1'b0,timbre_for_pixel}),
        .pixel_x(pixel_x[11:0]),.pixel_y(pixel_y[11:0]),
        .pixel_de(data_enable && !(|pixel_x[15:12]) && !(|pixel_y[15:12])),
        .frame_start(frame_start),.hsync_in(hsync),.vsync_in(vsync),
        .rgb(lissajous_rgb),.mask(lissajous_mask),.trace_valid(lissajous_trace),
        .gap_count(),.point_drop_count(),.published_frames(lissajous_published_frames),
        .hsync_out(),.vsync_out(),.data_enable_out());
    // The plotter emits after three captures. Two registers align it to the
    // same five-capture token used by the existing HDMI page selector.
    wire lissajous_title_aligned;
    r13_lissajous_title u_lissajous_title(
        .clk(pixel_clk),.rst_n(pixel_rst_n),
        .enable(lissajous_enable && data_enable),
        .x(pixel_x),.y(pixel_y),.dot(lissajous_title_aligned));
    logic [25:0] lissajous_four,lissajous_five;
    always_ff @(posedge pixel_clk) begin
        if(!lissajous_reset_n) begin lissajous_four<=0;lissajous_five<=0;end
        else begin
            lissajous_four<={lissajous_trace,lissajous_mask,lissajous_rgb};
            lissajous_five<=lissajous_four;
        end
    end
    wire lissajous_trace_aligned,lissajous_mask_aligned;
    wire [23:0] lissajous_rgb_aligned;
    assign {lissajous_trace_aligned,lissajous_mask_aligned,lissajous_rgb_aligned}=lissajous_five;
    // R17: decoration runs alongside the analysis engines, with the same
    // five-capture pixel token. Grid sits behind the transparent trace mask.
    // This private pixel branch never modifies or backpressures audio.
    wire graph_mask_aligned, grid_mask_aligned;
    wire [23:0] graph_rgb_aligned, grid_rgb_aligned;
    analysis_graph_overlay u_analysis_graph(
        .pixel_clk(pixel_clk), .rst_n(pixel_rst_n),
        .pixel_x(pixel_x), .pixel_y(pixel_y),
        .data_enable(data_enable), .page(page_for_pixel[1:0]),
        .graph_mask(graph_mask_aligned), .graph_rgb(graph_rgb_aligned),
        .grid_mask(grid_mask_aligned), .grid_rgb(grid_rgb_aligned));
    wire [7:0] pending_r,pending_g,pending_b;
    pro_reserved_analysis_page u_pending_page(
        .pixel_clk(pixel_clk),.rst_n(pixel_rst_n),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.data_enable(data_enable),
        .page_is_spectrum(page_for_pixel[0]),.selected_timbre(timbre_for_pixel),
        .rgb_r(pending_r),.rgb_g(pending_g),.rgb_b(pending_b));
    logic [2:0] page_pipe[0:4];
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
            if(WAVEFORM_ATTACHED)begin
                {rgb_r,rgb_g,rgb_b}=24'h081020;
                if(grid_mask_aligned){rgb_r,rgb_g,rgb_b}=grid_rgb_aligned;
                if(waveform_mask_aligned){rgb_r,rgb_g,rgb_b}=waveform_rgb_aligned;
                if(graph_mask_aligned){rgb_r,rgb_g,rgb_b}=graph_rgb_aligned;
            end
            else {rgb_r,rgb_g,rgb_b}={pending_r,pending_g,pending_b};
        end else if(page_pipe[4]==3)begin
            if(SPECTRUM_ATTACHED)begin
                {rgb_r,rgb_g,rgb_b}=24'h081020;
                if(grid_mask_aligned){rgb_r,rgb_g,rgb_b}=grid_rgb_aligned;
                if(spectrum_mask_aligned){rgb_r,rgb_g,rgb_b}=spectrum_rgb_aligned;
                if(graph_mask_aligned){rgb_r,rgb_g,rgb_b}=graph_rgb_aligned;
            end
            else {rgb_r,rgb_g,rgb_b}={pending_r,pending_g,pending_b};
        end else if(page_pipe[4]==4)begin
            {rgb_r,rgb_g,rgb_b}=lissajous_mask_aligned ? lissajous_rgb_aligned : 24'h081020;
            if(lissajous_title_aligned){rgb_r,rgb_g,rgb_b}=24'hd6f7ff;
        end
        if(fault_pipe[4] && y_pipe[4]<18)
            {rgb_r,rgb_g,rgb_b}=x_pipe[4][4] ? 24'hff2828 : 24'h800808;
        if(!scene_de){rgb_r,rgb_g,rgb_b}=0;
    end
endmodule

// Static 5x7 title at 2x scale. Register position, character, glyph row,
// bit selection and output to align with the existing five pixel captures.
module r13_lissajous_title (
    input wire clk,rst_n,enable,
    input wire [15:0] x,y,
    output logic dot
);
    function automatic [7:0] character(input [3:0] slot);
        case(slot)
            4'd0: character=8'h4c;
            4'd1: character=8'h69;
            4'd2: character=8'h73;
            4'd3: character=8'h73;
            4'd4: character=8'h61;
            4'd5: character=8'h6a;
            4'd6: character=8'h6f;
            4'd7: character=8'h75;
            4'd8: character=8'h73;
            4'd10: character=8'h46;
            4'd11: character=8'h69;
            4'd12: character=8'h67;
            4'd13: character=8'h75;
            4'd14: character=8'h72;
            4'd15: character=8'h65;
            default: character=0;
        endcase
    endfunction
    function automatic [4:0] glyph_row(input [7:0] code,input [2:0] row);
        case({code,row})
            11'h260: glyph_row=5'b10000;
            11'h261: glyph_row=5'b10000;
            11'h262: glyph_row=5'b10000;
            11'h263: glyph_row=5'b10000;
            11'h264: glyph_row=5'b10000;
            11'h265: glyph_row=5'b10000;
            11'h266: glyph_row=5'b11111;
            11'h348: glyph_row=5'b00100;
            11'h34a: glyph_row=5'b01100;
            11'h34b: glyph_row=5'b00100;
            11'h34c: glyph_row=5'b00100;
            11'h34d: glyph_row=5'b00100;
            11'h34e: glyph_row=5'b01110;
            11'h39a: glyph_row=5'b01111;
            11'h39b: glyph_row=5'b10000;
            11'h39c: glyph_row=5'b01110;
            11'h39d: glyph_row=5'b00001;
            11'h39e: glyph_row=5'b11110;
            11'h30a: glyph_row=5'b01110;
            11'h30b: glyph_row=5'b00001;
            11'h30c: glyph_row=5'b01111;
            11'h30d: glyph_row=5'b10001;
            11'h30e: glyph_row=5'b01111;
            11'h350: glyph_row=5'b00010;
            11'h352: glyph_row=5'b00110;
            11'h353: glyph_row=5'b00010;
            11'h354: glyph_row=5'b00010;
            11'h355: glyph_row=5'b10010;
            11'h356: glyph_row=5'b01100;
            11'h37a: glyph_row=5'b01110;
            11'h37b: glyph_row=5'b10001;
            11'h37c: glyph_row=5'b10001;
            11'h37d: glyph_row=5'b10001;
            11'h37e: glyph_row=5'b01110;
            11'h3aa: glyph_row=5'b10001;
            11'h3ab: glyph_row=5'b10001;
            11'h3ac: glyph_row=5'b10001;
            11'h3ad: glyph_row=5'b10011;
            11'h3ae: glyph_row=5'b01101;
            11'h230: glyph_row=5'b11111;
            11'h231: glyph_row=5'b10000;
            11'h232: glyph_row=5'b10000;
            11'h233: glyph_row=5'b11110;
            11'h234: glyph_row=5'b10000;
            11'h235: glyph_row=5'b10000;
            11'h236: glyph_row=5'b10000;
            11'h33a: glyph_row=5'b01111;
            11'h33b: glyph_row=5'b10001;
            11'h33c: glyph_row=5'b01111;
            11'h33d: glyph_row=5'b00001;
            11'h33e: glyph_row=5'b01110;
            11'h392: glyph_row=5'b10110;
            11'h393: glyph_row=5'b11001;
            11'h394: glyph_row=5'b10000;
            11'h395: glyph_row=5'b10000;
            11'h396: glyph_row=5'b10000;
            11'h32a: glyph_row=5'b01110;
            11'h32b: glyph_row=5'b10001;
            11'h32c: glyph_row=5'b11111;
            11'h32d: glyph_row=5'b10000;
            11'h32e: glyph_row=5'b01110;
            default: glyph_row=0;
        endcase
    endfunction
    logic [3:0] slot0;
    logic [2:0] row0,row1,col0,col1,col2;
    logic [7:0] char1;
    logic [4:0] bits2;
    logic active0,active1,active2,dot3;
    always_ff @(posedge clk) begin
        if(!rst_n) begin
            active0<=0;active1<=0;active2<=0;dot3<=0;dot<=0;
        end else begin
            active0<=enable && x>=16'd16 && x<16'd272 && y>=16'd24 && y<16'd38;
            slot0<=x[7:4]-4'd1;
            row0<=y[3:1]-3'd4;
            col0<=x[3:1];
            active1<=active0;
            char1<=character(slot0);
            row1<=row0;
            col1<=col0;
            active2<=active1;
            bits2<=glyph_row(char1,row1);
            col2<=col1;
            dot3<=active2 && col2<3'd5 && bits2[3'd4-col2];
            dot<=dot3;
        end
    end
endmodule
