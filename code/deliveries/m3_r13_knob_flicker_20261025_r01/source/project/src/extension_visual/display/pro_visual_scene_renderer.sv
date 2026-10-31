// Pixel renderer; M2 constant-geometry timing optimization of M3 74cae4c.
// Contains no clock, CDC, HDMI or TMDS logic; RGB remains combinational.
`timescale 1ns/1ps
module pro_visual_scene_renderer #(
    parameter integer LIVE_SLOT_COUNT = 8,
    parameter integer SCORE_SLOT_COUNT = 8,
    parameter integer Y_WIDTH = 10,
    parameter integer SCREEN_WIDTH = 640,
    parameter integer SCREEN_HEIGHT = 480,
    parameter integer JUDGE_Y = 400,
    parameter integer KEYBOARD_TOP = 410,
    parameter integer BASE_NOTE = 36,
    parameter integer NOTE_COUNT = 49
) (
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
    output logic [7:0] rgb_r,
    output logic [7:0] rgb_g,
    output logic [7:0] rgb_b
);
    logic [7:0] live_selected_velocity, score_selected_velocity;
    logic score_selected_hit, score_selected_miss;
    wire [LIVE_SLOT_COUNT-1:0] live_winner;
    wire [SCORE_SLOT_COUNT-1:0] score_winner;
    integer selected_index;
    integer px;
    integer py;
    integer i;
    logic [LIVE_SLOT_COUNT-1:0] live_pixel_match;
    logic [SCORE_SLOT_COUNT-1:0] score_pixel_match;
    wire [NOTE_COUNT-1:0] lane_match, lane_body, lane_left, lane_right;
    wire [NOTE_COUNT-1:0] flash_core,flash_glow;
    wire [NOTE_COUNT-1:0] core_level[0:3],glow_level[0:3];
    wire [6:0] lane_note_term [0:NOTE_COUNT-1];
    logic [6:0] pixel_note;
    integer lane_index;

    // All divisions/products below are elaboration constants. A pixel belongs
    // to [ceil(k*W/N), ceil((k+1)*W/N)); borders retain the old floor(W*k/N)
    // convention, including its fractional-boundary pixel. Narrow lanes may
    // have no interior. Empty intervals do not match, even when N exceeds W.
    for (genvar k = 0; k < NOTE_COUNT; k = k + 1) begin : g_lane
        localparam integer START_X = (k*SCREEN_WIDTH + NOTE_COUNT-1)/NOTE_COUNT;
        localparam integer END_X = ((k+1)*SCREEN_WIDTH + NOTE_COUNT-1)/NOTE_COUNT;
        localparam integer LEFT_X = k*SCREEN_WIDTH/NOTE_COUNT;
        localparam integer RIGHT_X = (k+1)*SCREEN_WIDTH/NOTE_COUNT;
        localparam integer NOTE = BASE_NOTE + k;
        localparam integer CENTER_X=((2*k+1)*SCREEN_WIDTH)/(2*NOTE_COUNT);
        localparam integer CORE_LEFT=(CENTER_X<2) ? 0 : CENTER_X-2;
        localparam integer CORE_RIGHT=(CENTER_X+2>=SCREEN_WIDTH) ? SCREEN_WIDTH-1 : CENTER_X+2;
        localparam integer GLOW_LEFT=(CENTER_X<4) ? 0 : CENTER_X-4;
        localparam integer GLOW_RIGHT=(CENTER_X+4>=SCREEN_WIDTH) ? SCREEN_WIDTH-1 : CENTER_X+4;
        assign flash_core[k]=flash_active[NOTE] && pixel_x>=CORE_LEFT && pixel_x<=CORE_RIGHT;
        assign flash_glow[k]=flash_active[NOTE] && pixel_x>=GLOW_LEFT && pixel_x<=GLOW_RIGHT;
        for(genvar level=0;level<4;level=level+1)begin:g_flash_level
            assign core_level[level][k]=flash_core[k] && flash_level[2*NOTE+:2]==2'(level);
            assign glow_level[level][k]=flash_glow[k] && flash_level[2*NOTE+:2]==2'(level);
        end
        assign lane_match[k] = pixel_x >= START_X && pixel_x < END_X;
        if (RIGHT_X >= LEFT_X + 3) begin : g_body
            assign lane_body[k] = lane_match[k] &&
                pixel_x >= LEFT_X + 1 && pixel_x <= RIGHT_X - 2;
        end else begin : g_empty_body
            assign lane_body[k] = 1'b0;
        end
        assign lane_left[k] = lane_match[k] && pixel_x == LEFT_X;
        if (RIGHT_X > 0) begin : g_right
            assign lane_right[k] = lane_match[k] && pixel_x == RIGHT_X - 1;
        end else begin : g_empty_right
            assign lane_right[k] = 1'b0;
        end
        assign lane_note_term[k] = {7{lane_match[k]}} & 7'(NOTE);

    end
    // Parallel one-hot decode; no variable multiplication or 128:1 key mux.
    always_comb begin
        pixel_note = 7'd0;
        for (lane_index = 0; lane_index < NOTE_COUNT; lane_index = lane_index + 1)
            pixel_note = pixel_note | lane_note_term[lane_index];
    end
    wire pixel_note_body = |lane_body;
    wire lane_left_edge = |lane_left;
    wire lane_right_edge = |lane_right;

    // Grouped priority: eight local candidates per group, then eight groups.
    // The highest matching slot still wins. OR/AND structure preserves X
    // propagation; no mux, new register, clock, geometry or color change.
    localparam integer GROUP_SIZE=8;
    localparam integer LIVE_GROUPS=(LIVE_SLOT_COUNT+GROUP_SIZE-1)/GROUP_SIZE;
    localparam integer SCORE_GROUPS=(SCORE_SLOT_COUNT+GROUP_SIZE-1)/GROUP_SIZE;
    wire [LIVE_GROUPS-1:0] live_group_match;
    wire [SCORE_GROUPS-1:0] score_group_match;
    for(genvar g=0;g<LIVE_GROUPS;g=g+1)begin:g_live_group
        localparam integer FIRST=g*GROUP_SIZE;
        localparam integer LAST=((FIRST+GROUP_SIZE)>LIVE_SLOT_COUNT) ? LIVE_SLOT_COUNT-1 : FIRST+GROUP_SIZE-1;
        assign live_group_match[g]=|live_pixel_match[LAST:FIRST];
        wire no_higher_group;
        if(g==LIVE_GROUPS-1)assign no_higher_group=1'b1;
        else assign no_higher_group=!(|live_group_match[LIVE_GROUPS-1:g+1]);
        for(genvar k=FIRST;k<=LAST;k=k+1)begin:g_slot
            if(k==LAST)assign live_winner[k]=live_pixel_match[k] && no_higher_group;
            else assign live_winner[k]=live_pixel_match[k] &&
                !(|live_pixel_match[LAST:k+1]) && no_higher_group;
        end
    end
    for(genvar g=0;g<SCORE_GROUPS;g=g+1)begin:g_score_group
        localparam integer FIRST=g*GROUP_SIZE;
        localparam integer LAST=((FIRST+GROUP_SIZE)>SCORE_SLOT_COUNT) ? SCORE_SLOT_COUNT-1 : FIRST+GROUP_SIZE-1;
        assign score_group_match[g]=|score_pixel_match[LAST:FIRST];
        wire no_higher_group;
        if(g==SCORE_GROUPS-1)assign no_higher_group=1'b1;
        else assign no_higher_group=!(|score_group_match[SCORE_GROUPS-1:g+1]);
        for(genvar k=FIRST;k<=LAST;k=k+1)begin:g_slot
            if(k==LAST)assign score_winner[k]=score_pixel_match[k] && no_higher_group;
            else assign score_winner[k]=score_pixel_match[k] &&
                !(|score_pixel_match[LAST:k+1]) && no_higher_group;
        end
    end

    // Exactly one matching slot wins: later slots overwrite earlier slots.
    // Fixed part-selects avoid index*10 arithmetic and variable barrel muxes.
    always_comb begin
        live_selected_velocity = 8'd0;
        score_selected_velocity = 8'd0;
        score_selected_hit = 1'b0;
        score_selected_miss = 1'b0;
        for (selected_index = 0; selected_index < LIVE_SLOT_COUNT; selected_index = selected_index + 1)
            live_selected_velocity = live_selected_velocity |
                ({8{live_winner[selected_index]}} & live_velocity[selected_index*10+2 +: 8]);
        for (selected_index = 0; selected_index < SCORE_SLOT_COUNT; selected_index = selected_index + 1) begin
            score_selected_velocity = score_selected_velocity |
                ({8{score_winner[selected_index]}} & score_velocity[selected_index*10+2 +: 8]);
            score_selected_hit = score_selected_hit | (score_winner[selected_index] && score_hit[selected_index]);
            score_selected_miss = score_selected_miss | (score_winner[selected_index] && score_miss[selected_index]);
        end
    end

    // Match terms never depend on RGB or selected data; avoid a combinational
    // feedback through the winner stage by keeping them in a separate process.
    always_comb begin
        live_pixel_match = '0;
        score_pixel_match = '0;
        for (i = 0; i < LIVE_SLOT_COUNT; i = i + 1)
            live_pixel_match[i] = live_valid[i] && pixel_note_body &&
                live_note_number[i*7 +: 7] == pixel_note &&
                int'(pixel_y) >= int'(live_y[i*Y_WIDTH +: Y_WIDTH]) &&
                int'(pixel_y) < int'(live_end_y[i*Y_WIDTH +: Y_WIDTH]);
        for (i = 0; i < SCORE_SLOT_COUNT; i = i + 1)
            score_pixel_match[i] = score_valid[i] && pixel_note_body &&
                score_note_number[i*7 +: 7] == pixel_note &&
                int'(pixel_y) >= int'(score_top_y[i*Y_WIDTH+:Y_WIDTH]) &&
                int'(pixel_y) < int'(score_end_y[i*Y_WIDTH+:Y_WIDTH]);
    end

    always_comb begin
        rgb_r = 8'h00;
        rgb_g = 8'h00;
        rgb_b = 8'h00;
        px = int'(pixel_x);
        py = int'(pixel_y);

        if (data_enable && px < SCREEN_WIDTH && py < SCREEN_HEIGHT) begin
            rgb_r = 8'h08;
            rgb_g = 8'h10;
            rgb_b = 8'h20;
            if (lane_left_edge) begin
                rgb_r = 8'h18;
                rgb_g = 8'h28;
                rgb_b = 8'h3c;
            end

            if (display_mode && py == SCREEN_HEIGHT-1) begin
                rgb_r = 8'hf0;
                rgb_g = 8'hb0;
                rgb_b = 8'h30;
            end

            // Both layers: score first, then immediate live bars on top.
            if (|score_pixel_match) begin
                if(score_selected_hit)begin rgb_r=8'h30;rgb_g=8'he8;rgb_b=8'h70;end
                else if(score_selected_miss)begin rgb_r=8'he8;rgb_g=8'h38;rgb_b=8'h38;end
                else begin
                    rgb_r=112+(score_selected_velocity>>1);
                    rgb_g=72+(score_selected_velocity>>2);
                    rgb_b=176+(score_selected_velocity>>2);
                end
            end
            if (|live_pixel_match) begin
                rgb_r=48+(live_selected_velocity>>1);
                rgb_g=112+(live_selected_velocity>>1);
                rgb_b=160+(live_selected_velocity>>2);
            end

            // Bottom-border spark independent of removed keyboard graphics.
            // Constant boxes are clipped by active-area/data_enable above.
            if(display_mode && !desync_latched)begin
                if(py>=((SCREEN_HEIGHT>8) ? SCREEN_HEIGHT-8 : 0) && (|flash_glow))begin
                    if(|glow_level[3])begin rgb_r=8'h80;rgb_g=8'he8;rgb_b=8'hff;end
                    else if(|glow_level[2])begin rgb_r=8'h40;rgb_g=8'h80;rgb_b=8'hb0;end
                    else if(|glow_level[1])begin rgb_r=8'h20;rgb_g=8'h40;rgb_b=8'h60;end
                    else begin rgb_r=8'h10;rgb_g=8'h20;rgb_b=8'h30;end
                end
                if(py>=((SCREEN_HEIGHT>4) ? SCREEN_HEIGHT-4 : 0) && (|flash_core))begin
                    if(|core_level[3])begin rgb_r=8'hff;rgb_g=8'hff;rgb_b=8'he0;end
                    else if(|core_level[2])begin rgb_r=8'hff;rgb_g=8'hd0;rgb_b=8'h60;end
                    else if(|core_level[1])begin rgb_r=8'hb0;rgb_g=8'h68;rgb_b=8'h20;end
                    else begin rgb_r=8'h50;rgb_g=8'h30;rgb_b=8'h10;end
                end
            end

            if (desync_latched && py < 18) begin
                if (pixel_x[4]) begin
                    rgb_r = 8'hff;
                    rgb_g = 8'h28;
                    rgb_b = 8'h28;
                end else begin
                    rgb_r = 8'h80;
                    rgb_g = 8'h08;
                    rgb_b = 8'h08;
                end
            end
        end
    end

`ifndef SYNTHESIS
    initial begin
        if (LIVE_SLOT_COUNT < 1 || LIVE_SLOT_COUNT > 64 ||
            SCORE_SLOT_COUNT < 1 || SCORE_SLOT_COUNT > 64 || Y_WIDTH < 1 ||
            SCREEN_WIDTH < 1 || SCREEN_HEIGHT < 1 || NOTE_COUNT < 1 ||
            SCREEN_WIDTH > 65535 || SCREEN_HEIGHT > 65535 ||
            BASE_NOTE < 0 || BASE_NOTE + NOTE_COUNT > 128 ||
            JUDGE_Y < 1 || JUDGE_Y >= SCREEN_HEIGHT ||
            KEYBOARD_TOP <= JUDGE_Y || KEYBOARD_TOP >= SCREEN_HEIGHT)
            $fatal(1, "invalid pro_visual_scene_renderer parameters");
    end
`endif
endmodule
