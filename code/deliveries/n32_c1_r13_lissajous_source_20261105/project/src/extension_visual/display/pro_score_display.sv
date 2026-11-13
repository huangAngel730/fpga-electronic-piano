// Display-only CDC boundary. No output can backpressure human audio.
// Global reset asserts asynchronously and releases independently in each domain.
// Score flush resets BOTH score mailbox endpoints and score state only.
// Human bridge/live state run through score controls without clear or pause.
// Private matching tags cross in the same mailbox transaction as each human
// event; pre-flush and during-flush events cannot judge a new score epoch.
`timescale 1ns/1ps
module pro_score_display #(
    parameter integer LIVE_SLOT_COUNT=32, SCORE_SLOT_COUNT=32,
    parameter integer EVENT_FIFO_DEPTH=32,
    parameter integer H_RESET_OFFSET=50
) (
    input logic core_clk,pixel_clk,serial_clk,rst_n,
    input wire [2:0] page_select,
    input wire selected_timbre,
    input wire audio_frame_load,
    input wire signed [23:0] play_left,play_right,
    input logic accepted_valid,
    input audio_defs_pkg::performance_event_t accepted_data,
    input logic score_valid,
    output wire score_ready,
    input logic [97:0] score_payload,
    input logic flush_req, external_fault,
    output logic flush_ack,
    output wire tmds_clk_p,tmds_clk_n,
    output wire [2:0] tmds_data_p,tmds_data_n,
    output logic [31:0] visual_drop_count,
    output wire desync_latched,
    output logic [31:0] frame_snapshot,
    output logic frame_snapshot_valid,frame_snapshot_pulse
);
    import audio_defs_pkg::*;
    wire core_rst_n,pixel_rst_n;
    reset_sync u_core_reset(.clk(core_clk),.rst_n(rst_n),.rst_sync_n(core_rst_n));
    reset_sync u_pixel_reset(.clk(pixel_clk),.rst_n(rst_n),.rst_sync_n(pixel_rst_n));
    // R10: keep the dedicated DVI release stage distinct from the high-fanout
    // raster reset. Global reset asserts asynchronously. pixel_rst_n rises on
    // the second pixel rising edge; DVI releases on the following falling edge,
    // 20 ns later at 25 MHz (20 ns earlier than R06's third rising edge).
    // Infer the negative edge for this target; do not instantiate an old-family
    // DFFNCE or add any serial-clock fabric reset stage.
    (* syn_preserve=1, syn_keep=1 *) logic dvi_rst_n;
    // Consumer-only raw-reset delay. No new reset domain or release cycle.
    (* syn_keep=1, syn_dont_touch=1 *) wire dvi_clear_hold_l0;
    (* syn_keep=1, syn_dont_touch=1 *) wire dvi_async_rst_n;
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) dvi_clear_hold0(
        .I0(rst_n),.F(dvi_clear_hold_l0));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) dvi_clear_hold1(
        .I0(dvi_clear_hold_l0),.F(dvi_async_rst_n));
    always_ff @(negedge pixel_clk or negedge dvi_async_rst_n)begin
        if(!dvi_async_rst_n)dvi_rst_n<=1'b0;
        else dvi_rst_n<=pixel_rst_n;
    end
    logic [1:0] flush_state;
    logic flush_target;
    // R08: four identity cells on the flush_target data capture branch only.
    (* syn_keep=1, syn_dont_touch=1 *) wire flush_target_hold1;
    (* syn_keep=1, syn_dont_touch=1 *) wire flush_target_hold2;
    (* syn_keep=1, syn_dont_touch=1 *) wire flush_target_hold3;
    (* syn_keep=1, syn_dont_touch=1 *) wire flush_req_for_target;
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_flush_target_hold1(
        .I0(flush_req),.F(flush_target_hold1));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_flush_target_hold2(
        .I0(flush_target_hold1),.F(flush_target_hold2));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_flush_target_hold3(
        .I0(flush_target_hold2),.F(flush_target_hold3));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_flush_target_hold4(
        .I0(flush_target_hold3),.F(flush_req_for_target));
    logic [31:0] match_epoch_core,match_epoch_pixel;
    logic epoch_overflow;
    wire flush_assert=(flush_state==1);
    wire epoch_rst_n=rst_n && !flush_assert;
    (* async_reg="true" *) logic flush_meta,flush_pixel;
    logic pixel_clear_ack;
    (* async_reg="true" *) logic clear_meta,clear_sync;
    (* async_reg="true" *) logic ready_meta,ready_sync;
    wire event_src_done,event_dst_done,score_src_done,score_dst_done;
    wire ingress_enable=core_rst_n && flush_state==0 && flush_req==flush_ack &&
        score_src_done && ready_sync;
    wire human_ingress_enable=core_rst_n && event_src_done;
    always_ff @(posedge pixel_clk or negedge pixel_rst_n)begin
        if(!pixel_rst_n)begin flush_meta<=0;flush_pixel<=0;pixel_clear_ack<=0;match_epoch_pixel<=0;end
        else begin
            flush_meta<=flush_assert;flush_pixel<=flush_meta;
            // One additional pixel edge guarantees state has been cleared.
            pixel_clear_ack<=flush_pixel;
            // Bundled epoch is held from core flush launch until the next
            // flush; two pixel synchronizers precede this capture.
            if(flush_pixel && !pixel_clear_ack)match_epoch_pixel<=match_epoch_core;
        end
    end
    always_ff @(posedge core_clk or negedge core_rst_n)begin
        if(!core_rst_n)begin
            clear_meta<=0;clear_sync<=0;ready_meta<=0;ready_sync<=0;
            flush_state<=0;flush_target<=0;flush_ack<=0;
            match_epoch_core<=0;epoch_overflow<=0;
        end else begin
            clear_meta<=pixel_clear_ack;clear_sync<=clear_meta;
            ready_meta<=score_dst_done;ready_sync<=ready_meta;
            case(flush_state)
                0:if(flush_req!=flush_ack)begin
                    flush_target<=flush_req_for_target;flush_state<=1;
                    if(match_epoch_core==32'hffffffff)epoch_overflow<=1;
                    else match_epoch_core<=match_epoch_core+1'b1;
                end
                1:if(clear_sync)flush_state<=2;
                2:if(!clear_sync && ready_sync && score_src_done)begin
                    flush_ack<=flush_target;flush_state<=0;
                end
                default:flush_state<=1;
            endcase
        end
    end
    wire [15:0] queue_level,queue_high;
    wire [31:0] epoch_drops;
    wire drop_pulse,video_event_valid,video_desync;
    performance_event_t video_event;
    wire [32:0] video_match_tag;
    wire match_eligible=flush_state==0 && flush_req==flush_ack && !epoch_overflow;
    wire human_valid=accepted_valid && (accepted_data.source_id==0 || accepted_data.source_id==1);
    logic startup_drop_fault;
    visual_event_bridge #(.DEPTH(EVENT_FIFO_DEPTH)) u_events(
        .sys_clk(core_clk),.video_clk(pixel_clk),.rst_n(rst_n),
        .accepted_valid(human_valid && human_ingress_enable),.accepted_data(accepted_data),
        .accepted_tag({match_eligible,match_epoch_core}),
        .visual_queue_level(queue_level),.visual_queue_high_watermark(queue_high),
        .visual_drop_count(epoch_drops),.visual_drop_pulse(drop_pulse),
        .sys_reset_done(event_src_done),.video_reset_done(event_dst_done),
        .video_valid(video_event_valid),.video_desync(video_desync),
        .video_ready(1'b1),.video_data(video_event),.video_tag(video_match_tag));
    always_ff @(posedge core_clk or negedge core_rst_n)begin
        if(!core_rst_n)begin visual_drop_count<=0;startup_drop_fault<=0;end
        else begin
            if(human_valid && !human_ingress_enable)
                startup_drop_fault<=1;
            if((drop_pulse || (human_valid && !human_ingress_enable)) && visual_drop_count!=32'hffffffff)
                visual_drop_count<=visual_drop_count+1'b1;
        end
    end
    wire video_score_valid,mailbox_ready;
    wire [97:0] video_score;
    wire tracker_ready;
    assign score_ready=ingress_enable && mailbox_ready;
    // R07 private: score98 bundle delay only at mailbox capture consumer.
    // No FF, CE, valid/ready, reset, producer or public cycle change.
    wire [97:0] score_payload_mailbox_data;
    for(genvar score_bit=0;score_bit<98;score_bit=score_bit+1)begin:g_score_mailbox_hold
        (* syn_keep=1,syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=score_payload[score_bit];
        for(genvar stage=0;stage<2;stage=stage+1)begin:g_delay
            (* syn_keep=1,syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                .I0(chain[stage]),.F(chain[stage+1]));
        end
        assign score_payload_mailbox_data[score_bit]=chain[2];
    end
    visual_mailbox_cdc #(.WIDTH(98)) u_score_mailbox(
        .src_clk(core_clk),.dst_clk(pixel_clk),.rst_n(epoch_rst_n),
        .src_valid(score_valid && ingress_enable),.src_ready(mailbox_ready),.src_data(score_payload_mailbox_data),
        .dst_valid(video_score_valid),.dst_ready(tracker_ready && !flush_pixel),.dst_data(video_score),
        .src_reset_done(score_src_done),.dst_reset_done(score_dst_done));
    wire hs,vs,de,frame_start;
    wire [15:0] px,py;
    pro_visual_scan #(.H_RESET_OFFSET(H_RESET_OFFSET)) u_scan(
        .pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.pixel_x(px),.pixel_y(py),
        .data_enable(de),.hsync(hs),.vsync(vs),.frame_start(frame_start),.line_start());
    wire [31:0] current_frame;
    logic frame_toggle;
    logic [31:0] frame_hold;
    (* async_reg="true" *) logic frame_meta,frame_sync;
    logic frame_seen;
    always_ff @(posedge pixel_clk or negedge pixel_rst_n)begin
        if(!pixel_rst_n)begin frame_toggle<=0;frame_hold<=0;end
        else if(frame_start)begin frame_hold<=current_frame+1'b1;frame_toggle<=~frame_toggle;end
    end
    // Bundled frame_hold is stable for a full frame (672000 core clocks).
    // Non-metastable RTL path: pixel edge -> first core capture -> second
    // core synchronizer edge -> third core detection/capture (2..3 periods).
    // Constrain frame_hold to frame_snapshot before the third edge. Snapshot
    // is an observed frame boundary; it alone does NOT prove audio tick phase.
    always_ff @(posedge core_clk or negedge core_rst_n)begin
        if(!core_rst_n)begin
            frame_meta<=0;frame_sync<=0;frame_seen<=0;frame_snapshot<=0;
            frame_snapshot_valid<=0;frame_snapshot_pulse<=0;
        end else begin
            frame_meta<=frame_toggle;frame_sync<=frame_meta;frame_snapshot_pulse<=0;
            if(frame_sync!=frame_seen)begin
                frame_snapshot<=frame_hold;frame_snapshot_valid<=1;
                frame_snapshot_pulse<=1;frame_seen<=frame_sync;
            end
        end
    end
    wire [LIVE_SLOT_COUNT-1:0] live_valid,live_held;
    wire [SCORE_SLOT_COUNT-1:0] falling_valid;
    wire [LIVE_SLOT_COUNT*7-1:0] live_note;
    wire [SCORE_SLOT_COUNT*7-1:0] falling_note;
    wire [LIVE_SLOT_COUNT*10-1:0] live_top,live_end,live_velocity;
    wire [SCORE_SLOT_COUNT*10-1:0] falling_y,falling_top,falling_end,falling_velocity;
    wire [127:0] key_down;
    wire [SCORE_SLOT_COUNT*16-1:0] falling_ids;
    wire [SCORE_SLOT_COUNT-1:0] falling_hit,falling_miss;
    wire [31:0] live_drops;
    wire live_desync;
    wire duplicate_id_fault;
    logic fatal_pixel;
    logic fatal_live_pixel;
    (* async_reg="true" *) logic fault_meta,fault_sync;
    (* async_reg="true" *) logic human_fault_meta,human_fault_sync;
    (* async_reg="true" *) logic fatal_meta,fatal_sync;
    wire [31:0] pending_live_drops;
    wire live_overflow=(pending_live_drops!=0);
    wire range_fault=video_score_valid &&
        (video_score[81:75]<36 || video_score[81:75]>84 || video_score[9:0]==0 || !video_score[42] ||
         video_score[74:43]<current_frame);
    wire human_range_fault=video_event_valid && video_event.event_type==EVENT_NOTE_ON &&
        video_event.velocity!=0 && (video_event.note_number<36 || video_event.note_number>84);
    always_ff @(posedge pixel_clk or negedge pixel_rst_n)begin
        if(!pixel_rst_n)begin
            fault_meta<=0;fault_sync<=0;fatal_pixel<=0;
            human_fault_meta<=0;human_fault_sync<=0;fatal_live_pixel<=0;
        end
        else begin
            fault_meta<=external_fault || epoch_overflow;fault_sync<=fault_meta;
            human_fault_meta<=startup_drop_fault;human_fault_sync<=human_fault_meta;
            if(video_desync || human_fault_sync || live_overflow || human_range_fault)fatal_live_pixel<=1;
            if(flush_pixel)fatal_pixel<=0;
            // A full tracker may legally hold the mailbox's valid/data until
            // a slot retires. Backpressure alone is not a desync condition.
            else if(fault_sync || range_fault || duplicate_id_fault)fatal_pixel<=1;
        end
    end
    always_ff @(posedge core_clk or negedge core_rst_n)begin
        if(!core_rst_n)begin fatal_meta<=0;fatal_sync<=0;end
        else begin fatal_meta<=fatal_pixel || fatal_live_pixel || live_desync;fatal_sync<=fatal_meta;end
    end
    assign desync_latched=fatal_sync;
    pro_visual_live_state #(.SLOT_COUNT(LIVE_SLOT_COUNT),.JUDGE_Y(470),.RISE_STEP(4)) u_live(
        .clk(pixel_clk),.rst_n(pixel_rst_n),.frame_start(frame_start),.flush(1'b0),
        .performance_fire(video_event_valid),.performance_data(video_event),
        .video_desync(fatal_live_pixel),.key_down(key_down),.live_valid(live_valid),
        .live_note_number(live_note),.live_y(live_top),.live_end_y(live_end),.live_held(live_held),
        .live_velocity(live_velocity),.visual_slot_drop_count(live_drops),.desync_latched(live_desync),
        .pending_drop_count(pending_live_drops));
    pro_visual_score_tracker #(.SLOT_COUNT(SCORE_SLOT_COUNT),.PREVIEW_FRAMES(120),.TRAVEL_Y(480),
        .HIT_WINDOW_FRAMES(12),.BOTTOM_EXIT_GEOMETRY(1),.STRICT_CONTACT(1),.RASTER_HEIGHT(480)) u_score(
        .clk(pixel_clk),.rst_n(pixel_rst_n),.frame_start(frame_start),
        .score_valid(video_score_valid && !flush_pixel && !fatal_pixel && !range_fault),
        .score_ready(tracker_ready),.score_note_id(video_score[97:82]),.score_note_number(video_score[81:75]),
        .score_hit_frame(video_score[74:43]),.score_duration_valid(video_score[42]),
        .score_duration_frames(video_score[41:10]),.score_velocity(video_score[9:0]),
        .performance_fire(video_event_valid && video_match_tag[32] &&
            video_match_tag[31:0]==match_epoch_pixel && !flush_pixel && !fatal_live_pixel),
        .performance_data(video_event),.match_enabled(1'b1),
        .video_desync(flush_pixel || fatal_pixel),.current_frame(current_frame),
        .slot_valid(falling_valid),.slot_note_id(falling_ids),.slot_note_number(falling_note),
        .slot_y(falling_y),.slot_top_y(falling_top),.slot_end_y(falling_end),
        .slot_velocity(falling_velocity),.slot_hit(falling_hit),.slot_miss(falling_miss),
        .hit_pulse(),.hit_note_number(),.duplicate_id_fault(duplicate_id_fault));
    wire [7:0] red,green,blue;
    wire [2:0] page_for_pixel;
    // R04: one coherent raster snapshot cuts absolute-frame geometry from
    // lane/rectangle/color selection and the vendor TMDS encoder input cone.
    // Every piece of state used to draw the pixel is captured on the SAME edge
    // as its px/py/control/frame stamp. Never combine old geometry with a newer
    // current_frame. Framecounter, judgement and anchor CDC remain undelayed.
    logic [15:0] render_px,render_py;
    logic render_de,render_hs,render_vs,render_desync;
    logic [31:0] render_frame_stamp;
    logic [127:0] render_keys;
    logic [LIVE_SLOT_COUNT-1:0] render_live_valid;
    logic [SCORE_SLOT_COUNT-1:0] render_score_valid,render_score_hit,render_score_miss;
    logic [LIVE_SLOT_COUNT*7-1:0] render_live_note;
    logic [SCORE_SLOT_COUNT*7-1:0] render_score_note;
    logic [LIVE_SLOT_COUNT*10-1:0] render_live_top,render_live_end,render_live_velocity;
    logic [SCORE_SLOT_COUNT*10-1:0] render_score_y,render_score_top,render_score_end,render_score_velocity;
    // R07: the old R15/R16 builds added two kept identity LUTs to every
    // member of six payload classes in order to repair a handful of physical
    // Hold endpoints.  With N32 those transparent chains consumed more than
    // three thousand LUTs and materially increased congestion.  The coherent
    // S0 snapshot below already registers every payload, so connect it
    // directly and repair only actual post-route Hold endpoints if required.
    wire [LIVE_SLOT_COUNT*7-1:0] live_note_for_render = live_note;
    wire [SCORE_SLOT_COUNT*7-1:0] score_note_for_render = falling_note;
    wire [LIVE_SLOT_COUNT*10-1:0] live_velocity_for_render = live_velocity;
    wire [SCORE_SLOT_COUNT*10-1:0] score_velocity_for_render = falling_velocity;
    wire [LIVE_SLOT_COUNT*10-1:0] live_top_for_render = live_top;
    wire [LIVE_SLOT_COUNT*10-1:0] live_end_for_render = live_end;
    always_ff @(posedge pixel_clk or negedge pixel_rst_n)begin
        if(!pixel_rst_n)begin
            render_px<=0;render_py<=0;render_de<=0;render_hs<=1;render_vs<=1;
            render_desync<=0;render_frame_stamp<=0;render_keys<=0;
            render_live_valid<=0;render_score_valid<=0;render_score_hit<=0;render_score_miss<=0;
            render_live_note<=0;render_score_note<=0;
            render_live_top<=0;render_live_end<=0;render_live_velocity<=0;
            render_score_y<=0;render_score_top<=0;render_score_end<=0;render_score_velocity<=0;
        end else begin
            render_px<=px;render_py<=py;render_de<=de;render_hs<=hs;render_vs<=vs;
            render_frame_stamp<=current_frame;
            render_desync<=fatal_pixel || fatal_live_pixel || live_desync;
            render_keys<=page_for_pixel==0 ? key_down : '0;
            render_live_valid<=page_for_pixel==0 ? live_valid : '0;render_live_note<=live_note_for_render;
            render_live_top<=live_top_for_render;render_live_end<=live_end_for_render;render_live_velocity<=live_velocity_for_render;
            render_score_valid<=(flush_pixel || page_for_pixel!=1) ? '0 : falling_valid;
            render_score_note<=score_note_for_render;render_score_y<=falling_y;
            render_score_top<=falling_top;render_score_end<=falling_end;render_score_velocity<=score_velocity_for_render;
            render_score_hit<=falling_hit;render_score_miss<=falling_miss;
        end
    end
    // R05: four pixel-clock capture stages split lane/rectangle, local slot,
    // group winner and RGB composition. Sync/DE follow the exact same pixel.
    wire renderer_hs,renderer_vs,renderer_de;
    pro_visual_scene_renderer_pipe #(.LIVE_SLOT_COUNT(LIVE_SLOT_COUNT),.SCORE_SLOT_COUNT(SCORE_SLOT_COUNT),
        .JUDGE_Y(478),.KEYBOARD_TOP(479)) u_renderer(
        .pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.hsync(render_hs),.vsync(render_vs),
        .hsync_out(renderer_hs),.vsync_out(renderer_vs),.data_enable_out(renderer_de),
        .data_enable(render_de),.pixel_x(render_px),.pixel_y(render_py),.display_mode(1'b1),
        .desync_latched(render_desync),.key_down(render_keys),
        .flash_active(128'd0),.flash_level(256'd0),
        .live_valid(render_live_valid),.live_note_number(render_live_note),.live_y(render_live_top),.live_end_y(render_live_end),
        .live_velocity(render_live_velocity),.score_valid(render_score_valid),.score_note_number(render_score_note),
        .score_y(render_score_y),.score_top_y(render_score_top),.score_end_y(render_score_end),
        .score_velocity(render_score_velocity),.score_hit(render_score_hit),.score_miss(render_score_miss),
        .rgb_r(red),.rgb_g(green),.rgb_b(blue));
    // Shared PLL clocks are related 5:1. Global reset asserts asynchronously;
    // its existing two-pixel synchronizer plus one dedicated low-load stage
    // releases the DVI encoder/OSER10. No 125MHz fabric FF is needed. OSER10
    // recovery/removal paths remain timed; score epoch controls cannot reset it.
    // Page 0 live, 1 score, 2 waveform, 3 spectrum, 4 Lissajous.
    // Page selection gates rendering only; audio, trackers and score keep running.
    wire [7:0] display_red,display_green,display_blue;
    wire display_de,display_hs,display_vs;
    // Future engine attachment point: no external pin or audio feedback.
    // PCM tuple is core-clock; selected page/timbre are controls for new notes,
    // not per-sample claims about which held voices contribute to the mix.
    wire analysis_sample_valid,analysis_selected_timbre,analysis_view_selected;
    wire [31:0] analysis_sample_seq;
    wire signed [23:0] analysis_left,analysis_right;
    wire [2:0] analysis_page_select;
    r08_waveform_page_overlay #(.WAVEFORM_ATTACHED(1'b1),.SPECTRUM_ATTACHED(1'b1)) u_waveform_overlay(
        .core_clk(core_clk),.pixel_clk(pixel_clk),.core_rst_n(core_rst_n),.pixel_rst_n(pixel_rst_n),
        .page_select(page_select),.selected_timbre(selected_timbre),.audio_frame_load(audio_frame_load),.play_left(play_left),.play_right(play_right),
        .analysis_sample_valid(analysis_sample_valid),.analysis_sample_seq(analysis_sample_seq),
        .analysis_left(analysis_left),.analysis_right(analysis_right),
        .analysis_selected_timbre(analysis_selected_timbre),.analysis_page_select(analysis_page_select),
        .analysis_view_selected(analysis_view_selected),
        .pixel_x(px),.pixel_y(py),.data_enable(de),.hsync(hs),.vsync(vs),.frame_start(frame_start),
        .desync_latched(fatal_pixel || fatal_live_pixel || live_desync),
        .scene_r(red),.scene_g(green),.scene_b(blue),.scene_de(renderer_de),.scene_hs(renderer_hs),.scene_vs(renderer_vs),
        .page_for_pixel(page_for_pixel),.page_aligned(),.rgb_r(display_red),.rgb_g(display_green),.rgb_b(display_blue),
        .out_de(display_de),.out_hs(display_hs),.out_vs(display_vs),.waveform_trace_valid(),
        .observation_drop_count(),.display_gap_count(),.window_drop_count());
    Pro_DVI_TX_Top u_dvi(.I_rst_n(dvi_rst_n),.I_serial_clk(serial_clk),.I_rgb_clk(pixel_clk),
        .I_rgb_vs(display_vs),.I_rgb_hs(display_hs),.I_rgb_de(display_de),.I_rgb_r(display_red),.I_rgb_g(display_green),.I_rgb_b(display_blue),
        .O_tmds_clk_p(tmds_clk_p),.O_tmds_clk_n(tmds_clk_n),
        .O_tmds_data_p(tmds_data_p),.O_tmds_data_n(tmds_data_n));
endmodule
