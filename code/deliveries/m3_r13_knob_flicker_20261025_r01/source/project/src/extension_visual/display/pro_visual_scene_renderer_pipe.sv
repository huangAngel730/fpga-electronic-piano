// Four-stage pixel pipeline. Input at rising edge k appears after edge k+3:
// S1 lane/Y decode, S2 local eight-slot selection, S3 group selection,
// S4 ordered color composition. RGB, DE, HS and VS all have four captures.
// rst_n asserts asynchronously; release must be synchronized in pixel domain.
`timescale 1ns/1ps
module pro_visual_scene_renderer_pipe #(
    parameter integer LIVE_SLOT_COUNT = 32,
    parameter integer SCORE_SLOT_COUNT = 32,
    parameter integer Y_WIDTH = 10,
    parameter integer SCREEN_WIDTH = 640,
    parameter integer SCREEN_HEIGHT = 480,
    parameter integer JUDGE_Y = 400,
    parameter integer KEYBOARD_TOP = 410,
    parameter integer BASE_NOTE = 36,
    parameter integer NOTE_COUNT = 49
) (
    input logic pixel_clk, rst_n,
    input logic hsync, vsync,
    input logic data_enable,
    input logic [15:0] pixel_x,
    input logic [15:0] pixel_y,
    input logic display_mode,
    input logic desync_latched,
    input logic [127:0] key_down,
    input logic [127:0] flash_active,
    input logic [255:0] flash_level,
    input logic [LIVE_SLOT_COUNT-1:0] live_valid,
    input logic [(LIVE_SLOT_COUNT*7)-1:0] live_note_number,
    input logic [(LIVE_SLOT_COUNT*Y_WIDTH)-1:0] live_y,
    input logic [(LIVE_SLOT_COUNT*Y_WIDTH)-1:0] live_end_y,
    input logic [(LIVE_SLOT_COUNT*10)-1:0] live_velocity,
    input logic [SCORE_SLOT_COUNT-1:0] score_valid,
    input logic [(SCORE_SLOT_COUNT*7)-1:0] score_note_number,
    input logic [(SCORE_SLOT_COUNT*Y_WIDTH)-1:0] score_y,
    input logic [(SCORE_SLOT_COUNT*Y_WIDTH)-1:0] score_top_y,score_end_y,
    input logic [(SCORE_SLOT_COUNT*10)-1:0] score_velocity,
    input logic [SCORE_SLOT_COUNT-1:0] score_hit,
    input logic [SCORE_SLOT_COUNT-1:0] score_miss,
    output logic hsync_out, vsync_out, data_enable_out,
    output logic [7:0] rgb_r,
    output logic [7:0] rgb_g,
    output logic [7:0] rgb_b
);
    wire [NOTE_COUNT-1:0] lane_match, lane_body, lane_left, lane_right;
    wire [NOTE_COUNT-1:0] flash_core,flash_glow;
    wire [NOTE_COUNT-1:0] core_level[0:3],glow_level[0:3];
    `include "physical_key_layout.svh"


    // Physical endpoint constants; overlapping notes stay independent.
    for (genvar k = 0; k < NOTE_COUNT; k = k + 1) begin : g_lane
        localparam integer NOTE = BASE_NOTE + k;
        localparam integer START_X = physical_key_left(7'(NOTE));
        localparam integer END_X = physical_key_right(7'(NOTE));
        localparam integer LEFT_X = START_X;
        localparam integer RIGHT_X = END_X;
        localparam integer VISIBLE = END_X > START_X;
        localparam integer CENTER_X=(START_X+END_X)/2;
        localparam integer CORE_LEFT=(CENTER_X<2) ? 0 : CENTER_X-2;
        localparam integer CORE_RIGHT=(CENTER_X+2>=SCREEN_WIDTH) ? SCREEN_WIDTH-1 : CENTER_X+2;
        localparam integer GLOW_LEFT=(CENTER_X<4) ? 0 : CENTER_X-4;
        localparam integer GLOW_RIGHT=(CENTER_X+4>=SCREEN_WIDTH) ? SCREEN_WIDTH-1 : CENTER_X+4;
        assign flash_core[k]=VISIBLE && flash_active[NOTE] && pixel_x>=CORE_LEFT && pixel_x<=CORE_RIGHT;
        assign flash_glow[k]=VISIBLE && flash_active[NOTE] && pixel_x>=GLOW_LEFT && pixel_x<=GLOW_RIGHT;
        for(genvar level=0;level<4;level=level+1)begin:g_flash_level
            assign core_level[level][k]=flash_core[k] && flash_level[2*NOTE+:2]==2'(level);
            assign glow_level[level][k]=flash_glow[k] && flash_level[2*NOTE+:2]==2'(level);
        end
        assign lane_match[k] = pixel_x >= START_X && pixel_x < END_X;
        assign lane_body[k] = lane_match[k]; // full physical width, no inset
        assign lane_left[k] = lane_match[k] && pixel_x == LEFT_X;
        if (RIGHT_X > 0) begin : g_right
            assign lane_right[k] = lane_match[k] && pixel_x == RIGHT_X - 1;
        end else begin : g_empty_right
            assign lane_right[k] = 1'b0;
        end

    end
    wire pixel_note_body = |lane_body;
    wire lane_left_edge = |lane_left;
    wire lane_right_edge = |lane_right;


    localparam integer GROUP_SIZE=8;
    localparam integer LIVE_GROUPS=(LIVE_SLOT_COUNT+GROUP_SIZE-1)/GROUP_SIZE;
    localparam integer SCORE_GROUPS=(SCORE_SLOT_COUNT+GROUP_SIZE-1)/GROUP_SIZE;
    // Only per-pixel decisions cross stages; absolute geometry is consumed
    // in S1. Retain unknown-valued flags, using the reference's procedural
    // if priority only in S4, rather than X-optimistic mux selection.
    typedef struct packed {
        logic de, hs, vs, active_area, lane_left, mode_bottom;
        logic glow_on, core_on;
        logic [2:0] glow_levels, core_levels;
        logic desync_top, stripe;
    } pixel_control_t;
    pixel_control_t c1,c2,c3;
    wire active_area=data_enable && int'(pixel_x)<SCREEN_WIDTH && int'(pixel_y)<SCREEN_HEIGHT;
    wire glow_on=display_mode && !desync_latched &&
        int'(pixel_y)>=((SCREEN_HEIGHT>8)?SCREEN_HEIGHT-8:0) && (|flash_glow);
    wire core_on=display_mode && !desync_latched &&
        int'(pixel_y)>=((SCREEN_HEIGHT>4)?SCREEN_HEIGHT-4:0) && (|flash_core);
    logic [NOTE_COUNT-1:0] s1_geometry;
    logic [LIVE_SLOT_COUNT-1:0] s1_live_rectangle;
    logic [SCORE_SLOT_COUNT-1:0] s1_score_rectangle;
    logic [LIVE_SLOT_COUNT*7-1:0] s1_live_note;
    logic [SCORE_SLOT_COUNT*7-1:0] s1_score_note;
    logic [LIVE_SLOT_COUNT*8-1:0] s1_live_velocity;
    logic [SCORE_SLOT_COUNT*8-1:0] s1_score_velocity;
    logic [SCORE_SLOT_COUNT-1:0] s1_score_hit,s1_score_miss;
    // R03: class-wide consumer-only hold refinement after placement moved
    // short paths twice. Exactly two LUT1s per S1-consumed bit, including
    // previous targets; no extra register, CE, reset or producer modification.
    wire [LIVE_SLOT_COUNT*7-1:0] live_note_s1_input;
    wire [SCORE_SLOT_COUNT*7-1:0] score_note_s1_input;
    wire [LIVE_SLOT_COUNT*10-1:0] live_velocity_s1_input;
    for(genvar bit_index=0;bit_index<LIVE_SLOT_COUNT*7;bit_index=bit_index+1)begin:g_live_note_hold
        (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=live_note_number[bit_index];
        for(genvar stage=0;stage<2;stage=stage+1)begin:g_delay
            (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(.I0(chain[stage]),.F(chain[stage+1]));
        end
        assign live_note_s1_input[bit_index]=chain[2];
    end
    for(genvar bit_index=0;bit_index<SCORE_SLOT_COUNT*7;bit_index=bit_index+1)begin:g_score_note_hold
        (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=score_note_number[bit_index];
        for(genvar stage=0;stage<2;stage=stage+1)begin:g_delay
            (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(.I0(chain[stage]),.F(chain[stage+1]));
        end
        assign score_note_s1_input[bit_index]=chain[2];
    end
    for(genvar bit_index=0;bit_index<LIVE_SLOT_COUNT*10;bit_index=bit_index+1)begin:g_live_velocity_hold
        // Input bits0/1 are never consumed: S1 takes slot*10+2 +:8.
        if(bit_index%10>=2)begin:g_consumed
        (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=live_velocity[bit_index];
        for(genvar stage=0;stage<2;stage=stage+1)begin:g_delay
            (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(.I0(chain[stage]),.F(chain[stage+1]));
        end
        assign live_velocity_s1_input[bit_index]=chain[2];
        end else assign live_velocity_s1_input[bit_index]=live_velocity[bit_index];
    end
    integer capture_index;
    // S1: all lane, rectangle, payload and overlay terms are from this pixel.
    always_ff @(posedge pixel_clk or negedge rst_n)begin
        if(!rst_n)begin
            c1<='0;c1.hs<=1'b1;c1.vs<=1'b1;
            s1_geometry<=0;s1_live_rectangle<=0;s1_score_rectangle<=0;
            s1_live_note<=0;s1_score_note<=0;s1_live_velocity<=0;s1_score_velocity<=0;
            s1_score_hit<=0;s1_score_miss<=0;
        end else begin
            c1.de<=data_enable;c1.hs<=hsync;c1.vs<=vsync;c1.active_area<=active_area;
            c1.lane_left<=lane_left_edge;
            c1.mode_bottom<=display_mode && int'(pixel_y)==SCREEN_HEIGHT-1;
            c1.glow_on<=glow_on;c1.core_on<=core_on;
            c1.glow_levels<={|glow_level[3],|glow_level[2],|glow_level[1]};
            c1.core_levels<={|core_level[3],|core_level[2],|core_level[1]};
            c1.desync_top<=desync_latched && int'(pixel_y)<18;c1.stripe<=pixel_x[4];
            s1_geometry<=lane_body;
            s1_live_note<=live_note_s1_input;s1_score_note<=score_note_s1_input;
            s1_score_hit<=score_hit;s1_score_miss<=score_miss;
            for(capture_index=0;capture_index<LIVE_SLOT_COUNT;capture_index=capture_index+1)begin
                s1_live_rectangle[capture_index]<=live_valid[capture_index] &&
                    int'(pixel_y)>=int'(live_y[capture_index*Y_WIDTH+:Y_WIDTH]) &&
                    int'(pixel_y)<int'(live_end_y[capture_index*Y_WIDTH+:Y_WIDTH]);
                s1_live_velocity[capture_index*8+:8]<=live_velocity_s1_input[capture_index*10+2+:8];
            end
            for(capture_index=0;capture_index<SCORE_SLOT_COUNT;capture_index=capture_index+1)begin
                s1_score_rectangle[capture_index]<=score_valid[capture_index] &&
                    int'(pixel_y)>=int'(score_top_y[capture_index*Y_WIDTH+:Y_WIDTH]) &&
                    int'(pixel_y)<int'(score_end_y[capture_index*Y_WIDTH+:Y_WIDTH]);
                s1_score_velocity[capture_index*8+:8]<=score_velocity[capture_index*10+2+:8];
            end
        end
    end
    wire [LIVE_SLOT_COUNT-1:0] live_match;
    wire [SCORE_SLOT_COUNT-1:0] score_match;
    // Fixed note terms retain overlapping rectangles and slot priority.
    for(genvar slot=0;slot<LIVE_SLOT_COUNT;slot=slot+1)begin:g_live_match
        wire [NOTE_COUNT-1:0] terms;
        for(genvar n=0;n<NOTE_COUNT;n=n+1)begin:g_note
            assign terms[n]=s1_geometry[n] && s1_live_note[slot*7+:7]==7'(BASE_NOTE+n);
        end
        assign live_match[slot]=s1_live_rectangle[slot] && (|terms);
    end
    for(genvar slot=0;slot<SCORE_SLOT_COUNT;slot=slot+1)begin:g_score_match
        wire [NOTE_COUNT-1:0] terms;
        for(genvar n=0;n<NOTE_COUNT;n=n+1)begin:g_note
            assign terms[n]=s1_geometry[n] && s1_score_note[slot*7+:7]==7'(BASE_NOTE+n);
        end
        assign score_match[slot]=s1_score_rectangle[slot] && (|terms);
    end
    logic [LIVE_GROUPS-1:0] s2_live_match;
    logic [SCORE_GROUPS-1:0] s2_score_match;
    logic [LIVE_GROUPS*8-1:0] s2_live_velocity;
    logic [SCORE_GROUPS*8-1:0] s2_score_velocity;
    logic [SCORE_GROUPS-1:0] s2_score_hit,s2_score_miss;
    // R11 overlap policy, known binary pixels: live color uses the maximum
    // visible velocity across every matching rectangle, independent of slot
    // order/history recycling. Keep live_any separate: zero is a valid level.
    function automatic [7:0] live_max(input [7:0] a,b);
        live_max=(a[7:1]>=b[7:1]) ? {a[7:1],1'b0} : {b[7:1],1'b0};
    endfunction
    // S2: balanced eight-leaf max (three comparisons deep), then the original
    // per-group registers. Nonmatching/padded leaves use neutral zero.
    for(genvar g=0;g<LIVE_GROUPS;g=g+1)begin:g_live_group
        localparam integer FIRST=g*GROUP_SIZE;
        localparam integer LAST=((FIRST+GROUP_SIZE)>LIVE_SLOT_COUNT)?LIVE_SLOT_COUNT-1:FIRST+GROUP_SIZE-1;
        wire [7:0] velocity_tree[1:2*GROUP_SIZE-1];
        for(genvar leaf=0;leaf<GROUP_SIZE;leaf=leaf+1)begin:g_velocity_leaf
            localparam integer SLOT=FIRST+leaf;
            if(SLOT<LIVE_SLOT_COUNT)begin:g_real
                assign velocity_tree[GROUP_SIZE+leaf]=
                    {8{live_match[SLOT]}} & s1_live_velocity[SLOT*8+:8];
            end else begin:g_pad
                assign velocity_tree[GROUP_SIZE+leaf]=8'd0;
            end
        end
        for(genvar node=1;node<GROUP_SIZE;node=node+1)begin:g_velocity_max
            assign velocity_tree[node]=live_max(velocity_tree[2*node],velocity_tree[2*node+1]);
        end
        always_ff @(posedge pixel_clk or negedge rst_n)begin
            if(!rst_n)begin s2_live_match[g]<=0;s2_live_velocity[g*8+:8]<=0;end
            else begin s2_live_match[g]<=|live_match[LAST:FIRST];s2_live_velocity[g*8+:8]<=velocity_tree[1];end
        end
    end
    for(genvar g=0;g<SCORE_GROUPS;g=g+1)begin:g_score_group
        localparam integer FIRST=g*GROUP_SIZE;
        localparam integer LAST=((FIRST+GROUP_SIZE)>SCORE_SLOT_COUNT)?SCORE_SLOT_COUNT-1:FIRST+GROUP_SIZE-1;
        wire [LAST:FIRST] winner;
        for(genvar k=FIRST;k<=LAST;k=k+1)begin:g_slot
            if(k==LAST)assign winner[k]=score_match[k];
            else assign winner[k]=score_match[k] && !(|score_match[LAST:k+1]);
        end
        logic [7:0] velocity;logic hit,miss;
        integer k;
        always_comb begin
            velocity=0;hit=0;miss=0;
            for(k=FIRST;k<=LAST;k=k+1)begin
                velocity=velocity | ({8{winner[k]}} & s1_score_velocity[k*8+:8]);
                hit=hit | (winner[k] && s1_score_hit[k]);
                miss=miss | (winner[k] && s1_score_miss[k]);
            end
        end
        always_ff @(posedge pixel_clk or negedge rst_n)begin
            if(!rst_n)begin s2_score_match[g]<=0;s2_score_velocity[g*8+:8]<=0;s2_score_hit[g]<=0;s2_score_miss[g]<=0;end
            else begin
                s2_score_match[g]<=|score_match[LAST:FIRST];s2_score_velocity[g*8+:8]<=velocity;
                s2_score_hit[g]<=hit;s2_score_miss[g]<=miss;
            end
        end
    end
    wire [SCORE_GROUPS-1:0] score_group_winner;
    for(genvar g=0;g<SCORE_GROUPS;g=g+1)begin:g_score_group_winner
        if(g==SCORE_GROUPS-1)assign score_group_winner[g]=1'b1;
        else assign score_group_winner[g]=!(|s2_score_match[SCORE_GROUPS-1:g+1]);
    end
    // S3: up to four group maxima, padded to a balanced tree; no new FF/cycle.
    localparam integer LIVE_MAX_LEAVES=1<<$clog2(LIVE_GROUPS);
    wire [7:0] live_max_tree[1:2*LIVE_MAX_LEAVES-1];
    for(genvar leaf=0;leaf<LIVE_MAX_LEAVES;leaf=leaf+1)begin:g_live_max_leaf
        if(leaf<LIVE_GROUPS)begin:g_real
            assign live_max_tree[LIVE_MAX_LEAVES+leaf]=s2_live_velocity[leaf*8+:8];
        end else begin:g_pad
            assign live_max_tree[LIVE_MAX_LEAVES+leaf]=8'd0;
        end
    end
    for(genvar node=1;node<LIVE_MAX_LEAVES;node=node+1)begin:g_live_max_branch
        assign live_max_tree[node]=live_max(live_max_tree[2*node],live_max_tree[2*node+1]);
    end
    wire [7:0] live_velocity_selected=live_max_tree[1];
    logic [7:0] score_velocity_selected;
    logic score_hit_selected,score_miss_selected;
    integer group_index;
    always_comb begin
        score_velocity_selected=0;score_hit_selected=0;score_miss_selected=0;
        for(group_index=0;group_index<SCORE_GROUPS;group_index=group_index+1)begin
            score_velocity_selected=score_velocity_selected |
                ({8{score_group_winner[group_index]}} & s2_score_velocity[group_index*8+:8]);
            score_hit_selected=score_hit_selected | (score_group_winner[group_index] && s2_score_hit[group_index]);
            score_miss_selected=score_miss_selected | (score_group_winner[group_index] && s2_score_miss[group_index]);
        end
    end
    logic s3_live_any,s3_score_any,s3_score_hit,s3_score_miss;
    logic [7:0] s3_live_velocity,s3_score_velocity;
    // S3: at production capacity this is four groups, not a 32-slot cascade.
    always_ff @(posedge pixel_clk or negedge rst_n)begin
        if(!rst_n)begin
            c2<='0;c2.hs<=1;c2.vs<=1;c3<='0;c3.hs<=1;c3.vs<=1;
            s3_live_any<=0;s3_score_any<=0;s3_live_velocity<=0;s3_score_velocity<=0;s3_score_hit<=0;s3_score_miss<=0;
        end else begin
            c2<=c1;c3<=c2;
            s3_live_any<=|s2_live_match;s3_score_any<=|s2_score_match;
            s3_live_velocity<=live_velocity_selected;s3_score_velocity<=score_velocity_selected;
            s3_score_hit<=score_hit_selected;s3_score_miss<=score_miss_selected;
        end
    end
    logic [7:0] color_r,color_g,color_b;
    // S4: exact reference overlay order, independent of live geometry wires.
    always_comb begin
        color_r=0;color_g=0;color_b=0;
        if(c3.active_area)begin
            color_r=8'h08;color_g=8'h10;color_b=8'h20;
            if(c3.lane_left)begin color_r=8'h18;color_g=8'h28;color_b=8'h3c;end
            if(c3.mode_bottom)begin color_r=8'hf0;color_g=8'hb0;color_b=8'h30;end
            if(s3_score_any)begin
                if(s3_score_hit)begin color_r=8'h30;color_g=8'he8;color_b=8'h70;end
                else if(s3_score_miss)begin color_r=8'he8;color_g=8'h38;color_b=8'h38;end
                else begin color_r=112+(s3_score_velocity>>1);color_g=72+(s3_score_velocity>>2);color_b=176+(s3_score_velocity>>2);end
            end
            if(s3_live_any)begin color_r=48+(s3_live_velocity>>1);color_g=112+(s3_live_velocity>>1);color_b=160+(s3_live_velocity>>2);end
            if(c3.glow_on)begin
                if(c3.glow_levels[2])begin color_r=8'h80;color_g=8'he8;color_b=8'hff;end
                else if(c3.glow_levels[1])begin color_r=8'h40;color_g=8'h80;color_b=8'hb0;end
                else if(c3.glow_levels[0])begin color_r=8'h20;color_g=8'h40;color_b=8'h60;end
                else begin color_r=8'h10;color_g=8'h20;color_b=8'h30;end
            end
            if(c3.core_on)begin
                if(c3.core_levels[2])begin color_r=8'hff;color_g=8'hff;color_b=8'he0;end
                else if(c3.core_levels[1])begin color_r=8'hff;color_g=8'hd0;color_b=8'h60;end
                else if(c3.core_levels[0])begin color_r=8'hb0;color_g=8'h68;color_b=8'h20;end
                else begin color_r=8'h50;color_g=8'h30;color_b=8'h10;end
            end
            if(c3.desync_top)begin
                if(c3.stripe)begin color_r=8'hff;color_g=8'h28;color_b=8'h28;end
                else begin color_r=8'h80;color_g=8'h08;color_b=8'h08;end
            end
        end
    end
    always_ff @(posedge pixel_clk or negedge rst_n)begin
        if(!rst_n)begin rgb_r<=0;rgb_g<=0;rgb_b<=0;hsync_out<=1;vsync_out<=1;data_enable_out<=0;end
        else begin rgb_r<=color_r;rgb_g<=color_g;rgb_b<=color_b;hsync_out<=c3.hs;vsync_out<=c3.vs;data_enable_out<=c3.de;end
    end
`ifndef SYNTHESIS
    initial begin
        if(LIVE_SLOT_COUNT<1 || LIVE_SLOT_COUNT>32 || SCORE_SLOT_COUNT<1 || SCORE_SLOT_COUNT>32 ||
           Y_WIDTH<1 || Y_WIDTH>16 || SCREEN_WIDTH!=640 ||
           SCREEN_HEIGHT<1 || SCREEN_HEIGHT>65535 || NOTE_COUNT<1 || BASE_NOTE<0 || BASE_NOTE+NOTE_COUNT>128 ||
           JUDGE_Y<1 || JUDGE_Y>=SCREEN_HEIGHT || KEYBOARD_TOP<=JUDGE_Y || KEYBOARD_TOP>=SCREEN_HEIGHT)
            $fatal(1,"invalid pro_visual_scene_renderer_pipe parameters");
    end
`endif
endmodule
