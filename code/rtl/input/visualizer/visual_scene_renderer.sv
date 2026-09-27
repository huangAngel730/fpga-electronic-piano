// M3 pixel renderer. It contains no clock, CDC, HDMI or TMDS logic.
`timescale 1ns/1ps
module visual_scene_renderer #(
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
    input logic [LIVE_SLOT_COUNT-1:0] live_valid,
    input logic [(LIVE_SLOT_COUNT*7)-1:0] live_note_number,
    input logic [(LIVE_SLOT_COUNT*Y_WIDTH)-1:0] live_y,
    input logic [(LIVE_SLOT_COUNT*10)-1:0] live_velocity,
    input logic [SCORE_SLOT_COUNT-1:0] score_valid,
    input logic [(SCORE_SLOT_COUNT*7)-1:0] score_note_number,
    input logic [(SCORE_SLOT_COUNT*Y_WIDTH)-1:0] score_y,
    input logic [(SCORE_SLOT_COUNT*10)-1:0] score_velocity,
    input logic [SCORE_SLOT_COUNT-1:0] score_hit,
    input logic [SCORE_SLOT_COUNT-1:0] score_miss,
    output logic [7:0] rgb_r,
    output logic [7:0] rgb_g,
    output logic [7:0] rgb_b
);
    integer lane;
    integer lane_left;
    integer lane_right;
    integer note_value;
    integer note_lane;
    integer note_left;
    integer note_right;
    integer note_y;
    integer velocity_value;
    integer px;
    integer py;
    integer i;

    function automatic logic is_black_note(input integer note_number);
        integer pitch_class;
        begin
            pitch_class = note_number % 12;
            is_black_note = pitch_class == 1 || pitch_class == 3 ||
                            pitch_class == 6 || pitch_class == 8 ||
                            pitch_class == 10;
        end
    endfunction

    function automatic [7:0] clamp_u8(input integer value);
        begin
            if (value < 0) clamp_u8 = 8'd0;
            else if (value > 255) clamp_u8 = 8'd255;
            else clamp_u8 = value[7:0];
        end
    endfunction

    always_comb begin
        rgb_r = 8'h00;
        rgb_g = 8'h00;
        rgb_b = 8'h00;
        lane = 0;
        lane_left = 0;
        lane_right = 0;
        note_value = 0;
        note_lane = 0;
        note_left = 0;
        note_right = 0;
        note_y = 0;
        velocity_value = 0;
        px = int'(pixel_x);
        py = int'(pixel_y);

        if (data_enable && px < SCREEN_WIDTH && py < SCREEN_HEIGHT) begin
            rgb_r = 8'h08;
            rgb_g = 8'h10;
            rgb_b = 8'h20;
            lane = (px * NOTE_COUNT) / SCREEN_WIDTH;
            lane_left = (lane * SCREEN_WIDTH) / NOTE_COUNT;
            if (px == lane_left) begin
                rgb_r = 8'h18;
                rgb_g = 8'h28;
                rgb_b = 8'h3c;
            end

            if (py >= JUDGE_Y-1 && py <= JUDGE_Y+1) begin
                rgb_r = 8'hf0;
                rgb_g = 8'hb0;
                rgb_b = 8'h30;
            end

            if (!display_mode) begin
                for (i = 0; i < LIVE_SLOT_COUNT; i = i + 1) begin
                    note_value = int'(live_note_number[i*7 +: 7]);
                    note_y = int'(live_y[i*Y_WIDTH +: Y_WIDTH]);
                    velocity_value = int'(live_velocity[i*10 +: 10]) >> 2;
                    if (live_valid[i] && note_value >= BASE_NOTE &&
                        note_value < BASE_NOTE + NOTE_COUNT) begin
                        note_lane = note_value - BASE_NOTE;
                        note_left = (note_lane * SCREEN_WIDTH) / NOTE_COUNT;
                        note_right = ((note_lane + 1) * SCREEN_WIDTH) / NOTE_COUNT;
                        if (px >= note_left+1 && px < note_right-1 &&
                            py >= note_y && py < note_y+10) begin
                            rgb_r = clamp_u8(48 + (velocity_value >> 1));
                            rgb_g = clamp_u8(112 + (velocity_value >> 1));
                            rgb_b = clamp_u8(160 + (velocity_value >> 2));
                        end
                    end
                end
            end else begin
                for (i = 0; i < SCORE_SLOT_COUNT; i = i + 1) begin
                    note_value = int'(score_note_number[i*7 +: 7]);
                    // M1 uses distance above the judgement line (positive is
                    // upward); raster Y grows downward from the screen top.
                    if (int'(score_y[i*Y_WIDTH +: Y_WIDTH]) >= JUDGE_Y)
                        note_y = 0;
                    else
                        note_y = JUDGE_Y -
                            int'(score_y[i*Y_WIDTH +: Y_WIDTH]);
                    velocity_value = int'(score_velocity[i*10 +: 10]) >> 2;
                    if (score_valid[i] && note_value >= BASE_NOTE &&
                        note_value < BASE_NOTE + NOTE_COUNT) begin
                        note_lane = note_value - BASE_NOTE;
                        note_left = (note_lane * SCREEN_WIDTH) / NOTE_COUNT;
                        note_right = ((note_lane + 1) * SCREEN_WIDTH) / NOTE_COUNT;
                        if (px >= note_left+1 && px < note_right-1 &&
                            py >= note_y && py < note_y+12) begin
                            if (score_hit[i]) begin
                                rgb_r = 8'h30;
                                rgb_g = 8'he8;
                                rgb_b = 8'h70;
                            end else if (score_miss[i]) begin
                                rgb_r = 8'he8;
                                rgb_g = 8'h38;
                                rgb_b = 8'h38;
                            end else begin
                                rgb_r = clamp_u8(112 + (velocity_value >> 1));
                                rgb_g = clamp_u8(72 + (velocity_value >> 2));
                                rgb_b = clamp_u8(176 + (velocity_value >> 2));
                            end
                        end
                    end
                end
            end

            if (py >= KEYBOARD_TOP) begin
                lane = (px * NOTE_COUNT) / SCREEN_WIDTH;
                lane_left = (lane * SCREEN_WIDTH) / NOTE_COUNT;
                lane_right = ((lane + 1) * SCREEN_WIDTH) / NOTE_COUNT;
                note_value = BASE_NOTE + lane;
                if (is_black_note(note_value)) begin
                    rgb_r = 8'h18;
                    rgb_g = 8'h1c;
                    rgb_b = 8'h24;
                end else begin
                    rgb_r = 8'he8;
                    rgb_g = 8'he8;
                    rgb_b = 8'hdc;
                end
                if (key_down[note_value]) begin
                    rgb_r = 8'h20;
                    rgb_g = 8'hc8;
                    rgb_b = 8'he8;
                end
                if (px == lane_left || px+1 == lane_right) begin
                    rgb_r = 8'h04;
                    rgb_g = 8'h08;
                    rgb_b = 8'h10;
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
        if (LIVE_SLOT_COUNT < 1 || SCORE_SLOT_COUNT < 1 || Y_WIDTH < 1 ||
            SCREEN_WIDTH < 1 || SCREEN_HEIGHT < 1 || NOTE_COUNT < 1 ||
            BASE_NOTE < 0 || BASE_NOTE + NOTE_COUNT > 128 ||
            JUDGE_Y < 1 || JUDGE_Y >= SCREEN_HEIGHT ||
            KEYBOARD_TOP <= JUDGE_Y || KEYBOARD_TOP >= SCREEN_HEIGHT)
            $fatal(1, "invalid visual_scene_renderer parameters");
    end
`endif
endmodule
