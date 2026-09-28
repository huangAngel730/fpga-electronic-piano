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
    // Convert X to a lane with one fixed-point reciprocal multiply.  The
    // quotient is corrected once, which is sufficient because active X is
    // 16-bit and the reciprocal keeps 20 fractional bits.  This replaces the
    // per-pixel divider used by the original renderer.
    localparam integer LANE_RECIP_SHIFT = 20;
    localparam integer LANE_RECIP_SCALE = 1_048_576;
    localparam integer LANE_RECIP_MULT =
        (NOTE_COUNT * LANE_RECIP_SCALE) / SCREEN_WIDTH;

    integer lane;
    integer lane_scaled_left;
    integer lane_scaled_right;
    integer note_value;
    integer velocity_value;
    integer px;
    integer py;
    integer scaled_pixel;
    integer scaled_pixel_plus_one;
    integer scaled_pixel_plus_two;
    integer i;
    integer selected_live_slot;
    integer selected_score_slot;
    logic lane_left_edge;
    logic lane_right_edge;
    logic [7:0] live_pixel_match;
    logic [7:0] score_pixel_match;

    function automatic [15:0] lane_for_x(input logic [15:0] x_value);
        logic [47:0] reciprocal_product;
        logic [31:0] scaled_x;
        logic [31:0] candidate;
        begin
            reciprocal_product = $unsigned(x_value) * LANE_RECIP_MULT;
            candidate = reciprocal_product >> LANE_RECIP_SHIFT;
            scaled_x = $unsigned(x_value) * NOTE_COUNT;

            // floor(reciprocal) can underestimate the exact quotient by one.
            if (((candidate + 1) * SCREEN_WIDTH) <= scaled_x)
                candidate = candidate + 1;
            if (candidate >= NOTE_COUNT)
                candidate = NOTE_COUNT - 1;
            lane_for_x = candidate[15:0];
        end
    endfunction

    function automatic logic [127:0] make_black_note_mask;
        integer note_index;
        integer pitch_class;
        begin
            make_black_note_mask = 128'd0;
            for (note_index = 0; note_index < 128;
                 note_index = note_index + 1) begin
                pitch_class = note_index % 12;
                if (pitch_class == 1 || pitch_class == 3 ||
                    pitch_class == 6 || pitch_class == 8 ||
                    pitch_class == 10)
                    make_black_note_mask[note_index] = 1'b1;
            end
        end
    endfunction

    localparam logic [127:0] BLACK_NOTE_MASK = make_black_note_mask();

    // Preserve the original rule that a higher-numbered occupied slot draws
    // over a lower-numbered slot, but select it with one compact priority
    // encoder instead of cascading the RGB assignment through every slot.
    function automatic integer highest_set_bit8(input logic [7:0] value);
        begin
            casez (value)
                8'b1???????: highest_set_bit8 = 7;
                8'b01??????: highest_set_bit8 = 6;
                8'b001?????: highest_set_bit8 = 5;
                8'b0001????: highest_set_bit8 = 4;
                8'b00001???: highest_set_bit8 = 3;
                8'b000001??: highest_set_bit8 = 2;
                8'b0000001?: highest_set_bit8 = 1;
                8'b00000001: highest_set_bit8 = 0;
                default:     highest_set_bit8 = -1;
            endcase
        end
    endfunction

    always_comb begin
        rgb_r = 8'h00;
        rgb_g = 8'h00;
        rgb_b = 8'h00;
        lane = 0;
        lane_scaled_left = 0;
        lane_scaled_right = 0;
        note_value = 0;
        velocity_value = 0;
        px = int'(pixel_x);
        py = int'(pixel_y);
        scaled_pixel = px * NOTE_COUNT;
        scaled_pixel_plus_one = (px + 1) * NOTE_COUNT;
        scaled_pixel_plus_two = (px + 2) * NOTE_COUNT;
        lane_left_edge = 1'b0;
        lane_right_edge = 1'b0;
        live_pixel_match = 8'd0;
        score_pixel_match = 8'd0;
        selected_live_slot = -1;
        selected_score_slot = -1;

        if (data_enable && px < SCREEN_WIDTH && py < SCREEN_HEIGHT) begin
            rgb_r = 8'h08;
            rgb_g = 8'h10;
            rgb_b = 8'h20;
            lane = int'(lane_for_x(pixel_x));
            lane_scaled_left = lane * SCREEN_WIDTH;
            lane_scaled_right = (lane + 1) * SCREEN_WIDTH;
            // These comparisons are exactly equivalent to checking X against
            // floor(lane*width/count), without a run-time divider.
            lane_left_edge =
                (scaled_pixel <= lane_scaled_left) &&
                (lane_scaled_left < scaled_pixel_plus_one);
            lane_right_edge =
                (scaled_pixel_plus_one <= lane_scaled_right) &&
                (lane_scaled_right < scaled_pixel_plus_two);
            if (lane_left_edge) begin
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
                // The match terms are independent and synthesize in parallel.
                for (i = 0; i < LIVE_SLOT_COUNT; i = i + 1) begin
                    live_pixel_match[i] = live_valid[i] &&
                        int'(live_note_number[i*7 +: 7]) >= BASE_NOTE &&
                        int'(live_note_number[i*7 +: 7]) <
                            BASE_NOTE + NOTE_COUNT &&
                        scaled_pixel >
                            ((int'(live_note_number[i*7 +: 7]) - BASE_NOTE) *
                             SCREEN_WIDTH) &&
                        scaled_pixel_plus_two <=
                            ((int'(live_note_number[i*7 +: 7]) - BASE_NOTE + 1) *
                             SCREEN_WIDTH) &&
                        py >= int'(live_y[i*Y_WIDTH +: Y_WIDTH]) &&
                        py < int'(live_y[i*Y_WIDTH +: Y_WIDTH]) + 10;
                end
                selected_live_slot = highest_set_bit8(live_pixel_match);
                if (selected_live_slot >= 0) begin
                    velocity_value = int'(live_velocity[
                        selected_live_slot*10 +: 10]) >> 2;
                    // velocity_value is 0..255 after the existing
                    // quarter-scale conversion; all sums fit in U8.
                    rgb_r = 48 + (velocity_value >> 1);
                    rgb_g = 112 + (velocity_value >> 1);
                    rgb_b = 160 + (velocity_value >> 2);
                end
            end else begin
                // score_y is distance above the judgement line (positive is
                // upward); raster Y grows downward from the screen top.
                for (i = 0; i < SCORE_SLOT_COUNT; i = i + 1) begin
                    score_pixel_match[i] = score_valid[i] &&
                        int'(score_note_number[i*7 +: 7]) >= BASE_NOTE &&
                        int'(score_note_number[i*7 +: 7]) <
                            BASE_NOTE + NOTE_COUNT &&
                        scaled_pixel >
                            ((int'(score_note_number[i*7 +: 7]) - BASE_NOTE) *
                             SCREEN_WIDTH) &&
                        scaled_pixel_plus_two <=
                            ((int'(score_note_number[i*7 +: 7]) - BASE_NOTE + 1) *
                             SCREEN_WIDTH) &&
                        py >= ((int'(score_y[i*Y_WIDTH +: Y_WIDTH]) >= JUDGE_Y) ?
                               0 : JUDGE_Y -
                               int'(score_y[i*Y_WIDTH +: Y_WIDTH])) &&
                        py < ((int'(score_y[i*Y_WIDTH +: Y_WIDTH]) >= JUDGE_Y) ?
                              12 : JUDGE_Y -
                              int'(score_y[i*Y_WIDTH +: Y_WIDTH]) + 12);
                end
                selected_score_slot = highest_set_bit8(score_pixel_match);
                if (selected_score_slot >= 0) begin
                    velocity_value = int'(score_velocity[
                        selected_score_slot*10 +: 10]) >> 2;
                    if (score_hit[selected_score_slot]) begin
                        rgb_r = 8'h30;
                        rgb_g = 8'he8;
                        rgb_b = 8'h70;
                    end else if (score_miss[selected_score_slot]) begin
                        rgb_r = 8'he8;
                        rgb_g = 8'h38;
                        rgb_b = 8'h38;
                    end else begin
                        rgb_r = 112 + (velocity_value >> 1);
                        rgb_g = 72 + (velocity_value >> 2);
                        rgb_b = 176 + (velocity_value >> 2);
                    end
                end
            end

            if (py >= KEYBOARD_TOP) begin
                note_value = BASE_NOTE + lane;
                if (BLACK_NOTE_MASK[note_value]) begin
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
                if (lane_left_edge || lane_right_edge) begin
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
        if (LIVE_SLOT_COUNT < 1 || LIVE_SLOT_COUNT > 8 ||
            SCORE_SLOT_COUNT < 1 || SCORE_SLOT_COUNT > 8 || Y_WIDTH < 1 ||
            SCREEN_WIDTH < 1 || SCREEN_HEIGHT < 1 || NOTE_COUNT < 1 ||
            SCREEN_WIDTH > 65535 || SCREEN_HEIGHT > 65535 ||
            BASE_NOTE < 0 || BASE_NOTE + NOTE_COUNT > 128 ||
            JUDGE_Y < 1 || JUDGE_Y >= SCREEN_HEIGHT ||
            KEYBOARD_TOP <= JUDGE_Y || KEYBOARD_TOP >= SCREEN_HEIGHT)
            $fatal(1, "invalid visual_scene_renderer parameters");
    end
`endif
endmodule
