// Independent M2 resource probe: synthetic events keep full video logic live.
// Never substitutes for real audio, score CDC, or formal top integration.
`timescale 1ns/1ps
module visual_resource_probe (
    input logic sys_clk,sys_rst_n,
    output wire tmds_clk_p,tmds_clk_n,
    output wire [2:0] tmds_data_p,tmds_data_n,
    output wire pa_en
);
    import audio_defs_pkg::*;
    wire serial_clk,pixel_clk,pll_lock,serial_rst_n;
    wire visual_rst_n = sys_rst_n && pll_lock;
    wire sys_reset_done,video_reset_done;
    wire [15:0] pixel_x,pixel_y;
    wire hs,vs,de,frame_start,line_start;
    wire video_valid,video_desync,video_ready;
    wire [15:0] queue_level,queue_peak;
    wire [31:0] drop_count;
    wire drop_pulse,score_ready,display_mode;
    wire [31:0] current_frame;
    wire [7:0] rgb_r,rgb_g,rgb_b;
    performance_event_t video_data;
    performance_event_t synthetic_data;
    logic [23:0] sys_count;
    logic note_active;
    logic [2:0] note_idx;
    wire accepted_valid = (sys_count == 24'hffffff) && sys_reset_done;
    always_ff @(posedge sys_clk or negedge visual_rst_n) begin
        if(!visual_rst_n) begin sys_count<='0; note_active<=0;note_idx<='0; end
        else begin
            sys_count<=sys_count+1'b1;
            if(accepted_valid) begin
                note_active<=~note_active;
                if(note_active) note_idx<=note_idx+1'b1;
            end
        end
    end
    assign synthetic_data=make_note_event(!note_active,4'd2,4'd0,7'd60+{4'd0,note_idx},10'd700);
    TMDS_PLL u_video_pll(.clkin(sys_clk),.lock(pll_lock),.clkout0(serial_clk),.clkout1(pixel_clk));
    reset_sync u_serial_reset(.clk(serial_clk),.rst_n(visual_rst_n),.rst_sync_n(serial_rst_n));
    visual_event_bridge #(.DEPTH(32)) u_event_bridge(
        .sys_clk(sys_clk),.video_clk(pixel_clk),.rst_n(visual_rst_n),
        .accepted_valid(accepted_valid),.accepted_data(synthetic_data),
        .visual_queue_level(queue_level),.visual_queue_high_watermark(queue_peak),
        .visual_drop_count(drop_count),.visual_drop_pulse(drop_pulse),
        .sys_reset_done(sys_reset_done),.video_reset_done(video_reset_done),
        .video_valid(video_valid),.video_desync(video_desync),
        .video_ready(video_ready),.video_data(video_data));
    video_scan_timing u_scan(.pixel_clk(pixel_clk),.rst_n(video_reset_done),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.data_enable(de),
        .hsync(hs),.vsync(vs),.frame_start(frame_start),.line_start(line_start));
    m3_visualizer u_scene(
        .pixel_clk(pixel_clk),.video_rst_n(video_reset_done),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.data_enable(de),
        .frame_start(frame_start),.event_valid(video_valid),
        .event_data(video_data),.event_ready(video_ready),
        .video_desync(video_desync),
        .mode_toggle_pulse(frame_start && (current_frame[8:0]==9'd0)),
        .score_valid(frame_start && (current_frame[5:0]==6'd0)),
        .score_ready(score_ready),
        .score_note_id(current_frame[15:0]),
        .score_note_number(7'd60+{4'd0,current_frame[6:4]}),
        .score_hit_frame(current_frame+32'd120),
        .score_duration_valid(current_frame[0]),
        .score_duration_frames(32'd30),.score_velocity(10'd600),
        .display_mode(display_mode),.current_frame(current_frame),
        .rgb_r(rgb_r),.rgb_g(rgb_g),.rgb_b(rgb_b));
    logic dvi_hs,dvi_vs,dvi_de;
    logic [7:0] dvi_r,dvi_g,dvi_b;
    always_ff @(posedge pixel_clk or negedge video_reset_done) begin
        if(!video_reset_done) begin
            dvi_hs<=1'b1; dvi_vs<=1'b1; dvi_de<=1'b0;
            dvi_r<='0; dvi_g<='0; dvi_b<='0;
        end else begin
            dvi_hs<=hs; dvi_vs<=vs; dvi_de<=de;
            dvi_r<=rgb_r; dvi_g<=rgb_g; dvi_b<=rgb_b;
        end
    end
    DVI_TX_Top u_video_tx(.I_rst_n(serial_rst_n),.I_serial_clk(serial_clk),
        .I_rgb_clk(pixel_clk),.I_rgb_vs(dvi_vs),.I_rgb_hs(dvi_hs),.I_rgb_de(dvi_de),
        .I_rgb_r(dvi_r),.I_rgb_g(dvi_g),.I_rgb_b(dvi_b),
        .O_tmds_clk_p(tmds_clk_p),.O_tmds_clk_n(tmds_clk_n),
        .O_tmds_data_p(tmds_data_p),.O_tmds_data_n(tmds_data_n));
    assign pa_en=1'b1;
endmodule
