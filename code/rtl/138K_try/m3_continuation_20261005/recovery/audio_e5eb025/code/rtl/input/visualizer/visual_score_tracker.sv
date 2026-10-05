// -----------------------------------------------------------------------------
// visual_score_tracker.sv
//
// Bounded falling-score timeline and hit/miss tracker.  Score timestamps are
// absolute frame numbers.  The module owns no pixel clock, raster timing, CDC,
// top-level integration, or board constraints.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module visual_score_tracker #(
    parameter integer SLOT_COUNT         = 8,
    parameter integer FRAME_WIDTH        = 32,
    parameter integer Y_WIDTH            = 10,
    parameter integer PREVIEW_FRAMES     = 120,
    parameter integer TRAVEL_Y           = 400,
    parameter integer HIT_WINDOW_FRAMES  = 6
) (
    input  logic                                  clk,
    input  logic                                  rst_n,
    input  logic                                  frame_start,

    input  logic                                  score_valid,
    output logic                                  score_ready,
    input  logic [15:0]                           score_note_id,
    input  logic [6:0]                            score_note_number,
    input  logic [FRAME_WIDTH-1:0]                score_hit_frame,
    input  logic                                  score_duration_valid,
    input  logic [FRAME_WIDTH-1:0]                score_duration_frames,
    input  logic [9:0]                            score_velocity,

    input  logic                                  performance_fire,
    input  audio_defs_pkg::performance_event_t    performance_data,
    input  logic                                  video_desync,

    output logic [FRAME_WIDTH-1:0]                current_frame,
    output logic [SLOT_COUNT-1:0]                 slot_valid,
    output logic [SLOT_COUNT*16-1:0]              slot_note_id,
    output logic [SLOT_COUNT*7-1:0]               slot_note_number,
    output logic [SLOT_COUNT*Y_WIDTH-1:0]         slot_y,
    output logic [SLOT_COUNT*10-1:0]              slot_velocity,
    output logic [SLOT_COUNT-1:0]                 slot_hit,
    output logic [SLOT_COUNT-1:0]                 slot_miss
);

    import audio_defs_pkg::*;

    localparam logic [Y_WIDTH-1:0] TRAVEL_Y_VALUE =
        TRAVEL_Y[Y_WIDTH-1:0];
    localparam logic [63:0] PREVIEW_FRAMES_64 =
        {32'd0, PREVIEW_FRAMES[31:0]};
    localparam logic [63:0] TRAVEL_Y_64 =
        {32'd0, TRAVEL_Y[31:0]};

    logic                              slot_used_mem       [0:SLOT_COUNT-1];
    logic [15:0]                       note_id_mem         [0:SLOT_COUNT-1];
    logic [6:0]                        note_number_mem     [0:SLOT_COUNT-1];
    logic [FRAME_WIDTH-1:0]            hit_frame_mem       [0:SLOT_COUNT-1];
    logic                              duration_valid_mem  [0:SLOT_COUNT-1];
    logic [FRAME_WIDTH-1:0]            duration_frames_mem [0:SLOT_COUNT-1];
    logic [9:0]                        velocity_mem        [0:SLOT_COUNT-1];
    logic                              judged_mem          [0:SLOT_COUNT-1];
    logic                              hit_mem             [0:SLOT_COUNT-1];
    logic                              miss_mem            [0:SLOT_COUNT-1];

    logic [FRAME_WIDTH-1:0] effective_frame;
    logic                   score_accept;
    logic                   match_valid;
    integer                 free_slot_index;
    integer                 match_slot_index;
    logic [FRAME_WIDTH-1:0] match_error;

    integer output_index;
    integer free_search_index;
    integer match_search_index;
    integer state_index;

    function automatic logic [FRAME_WIDTH-1:0] absolute_frame_error(
        input logic [FRAME_WIDTH-1:0] first_frame,
        input logic [FRAME_WIDTH-1:0] second_frame
    );
        begin
            if (first_frame >= second_frame) begin
                absolute_frame_error = first_frame - second_frame;
            end else begin
                absolute_frame_error = second_frame - first_frame;
            end
        end
    endfunction

    function automatic logic [FRAME_WIDTH-1:0] preview_start_frame(
        input logic [FRAME_WIDTH-1:0] hit_frame_value
    );
        begin
            if (hit_frame_value >= PREVIEW_FRAMES) begin
                preview_start_frame = hit_frame_value - PREVIEW_FRAMES;
            end else begin
                preview_start_frame = {FRAME_WIDTH{1'b0}};
            end
        end
    endfunction

    function automatic logic [Y_WIDTH-1:0] calculate_y(
        input logic [FRAME_WIDTH-1:0] frame_value,
        input logic [FRAME_WIDTH-1:0] hit_frame_value
    );
        logic [FRAME_WIDTH-1:0] remaining_frames;
        logic [63:0]            scaled_distance;
        logic [63:0]            scaled_quotient;
        begin
            remaining_frames = {FRAME_WIDTH{1'b0}};
            scaled_distance  = 64'd0;
            scaled_quotient  = 64'd0;

            if (frame_value >= hit_frame_value) begin
                calculate_y = {Y_WIDTH{1'b0}};
            end else begin
                remaining_frames = hit_frame_value - frame_value;
                if (remaining_frames >= PREVIEW_FRAMES) begin
                    calculate_y = TRAVEL_Y_VALUE;
                end else begin
                    scaled_distance = remaining_frames * TRAVEL_Y;
                    scaled_quotient = scaled_distance / PREVIEW_FRAMES_64;
                    calculate_y = scaled_quotient[Y_WIDTH-1:0];
                end
            end
        end
    endfunction

    always_comb begin
        effective_frame = current_frame;
        if (frame_start) begin
            effective_frame = current_frame + {{(FRAME_WIDTH-1){1'b0}}, 1'b1};
        end
    end

    // Locate the first free score slot.  A slot expiring on this same clock is
    // deliberately not advertised until the following clock, keeping ready
    // independent of the frame-update path.
    always_comb begin
        score_ready     = 1'b0;
        free_slot_index = 0;
        for (free_search_index = 0; free_search_index < SLOT_COUNT;
             free_search_index = free_search_index + 1) begin
            if (!score_ready && !slot_used_mem[free_search_index]) begin
                score_ready     = 1'b1;
                free_slot_index = free_search_index;
            end
        end
        score_accept = score_valid && score_ready;
    end

    // A live Note On selects the nearest unjudged score note of the same pitch.
    // Strictly smaller comparison gives deterministic low-slot tie breaking.
    always_comb begin
        match_valid      = 1'b0;
        match_slot_index = 0;
        match_error      = {FRAME_WIDTH{1'b1}};

        if (performance_fire &&
            (performance_data.event_type == EVENT_NOTE_ON)) begin
            for (match_search_index = 0; match_search_index < SLOT_COUNT;
                 match_search_index = match_search_index + 1) begin
                if (slot_used_mem[match_search_index] &&
                    !judged_mem[match_search_index] &&
                    (note_number_mem[match_search_index] ==
                     performance_data.note_number) &&
                    (!match_valid ||
                     (absolute_frame_error(effective_frame,
                                           hit_frame_mem[match_search_index]) <
                      match_error))) begin
                    match_valid      = 1'b1;
                    match_slot_index = match_search_index;
                    match_error      = absolute_frame_error(
                        effective_frame, hit_frame_mem[match_search_index]
                    );
                end
            end
        end
    end

    // Flatten only visible slots.  Stored future notes remain private until
    // their preview frame, so slot_valid is a drawing-valid qualifier.
    always_comb begin
        slot_valid       = '0;
        slot_note_id     = '0;
        slot_note_number = '0;
        slot_y           = '0;
        slot_velocity    = '0;
        slot_hit         = '0;
        slot_miss        = '0;

        for (output_index = 0; output_index < SLOT_COUNT;
             output_index = output_index + 1) begin
            if (slot_used_mem[output_index] &&
                (current_frame >= preview_start_frame(
                    hit_frame_mem[output_index]))) begin
                slot_valid[output_index] = 1'b1;
                slot_note_id[output_index*16 +: 16] =
                    note_id_mem[output_index];
                slot_note_number[output_index*7 +: 7] =
                    note_number_mem[output_index];
                slot_y[output_index*Y_WIDTH +: Y_WIDTH] =
                    calculate_y(current_frame, hit_frame_mem[output_index]);
                slot_velocity[output_index*10 +: 10] =
                    velocity_mem[output_index];
                slot_hit[output_index]  = hit_mem[output_index];
                slot_miss[output_index] = miss_mem[output_index];
            end
        end
    end

    // All timeline state is owned by this single sequential process.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_frame <= {FRAME_WIDTH{1'b0}};
            for (state_index = 0; state_index < SLOT_COUNT;
                 state_index = state_index + 1) begin
                slot_used_mem[state_index]       <= 1'b0;
                note_id_mem[state_index]         <= 16'd0;
                note_number_mem[state_index]     <= 7'd0;
                hit_frame_mem[state_index]       <= {FRAME_WIDTH{1'b0}};
                duration_valid_mem[state_index]  <= 1'b0;
                duration_frames_mem[state_index] <= {FRAME_WIDTH{1'b0}};
                velocity_mem[state_index]        <= 10'd0;
                judged_mem[state_index]          <= 1'b0;
                hit_mem[state_index]             <= 1'b0;
                miss_mem[state_index]            <= 1'b0;
            end
        end else if (video_desync) begin
            // Keep the absolute frame counter running, but discard all score
            // and judgement state.  Lost live events are never replayed.
            if (frame_start) begin
                current_frame <= effective_frame;
            end
            for (state_index = 0; state_index < SLOT_COUNT;
                 state_index = state_index + 1) begin
                slot_used_mem[state_index]       <= 1'b0;
                note_id_mem[state_index]         <= 16'd0;
                note_number_mem[state_index]     <= 7'd0;
                hit_frame_mem[state_index]       <= {FRAME_WIDTH{1'b0}};
                duration_valid_mem[state_index]  <= 1'b0;
                duration_frames_mem[state_index] <= {FRAME_WIDTH{1'b0}};
                velocity_mem[state_index]        <= 10'd0;
                judged_mem[state_index]          <= 1'b0;
                hit_mem[state_index]             <= 1'b0;
                miss_mem[state_index]            <= 1'b0;
            end
        end else begin
            if (frame_start) begin
                current_frame <= effective_frame;

                for (state_index = 0; state_index < SLOT_COUNT;
                     state_index = state_index + 1) begin
                    if (slot_used_mem[state_index]) begin
                        // A miss becomes visible on the first frame strictly
                        // beyond the inclusive hit window.
                        if (!judged_mem[state_index] &&
                            (effective_frame >
                             (hit_frame_mem[state_index] +
                              HIT_WINDOW_FRAMES))) begin
                            judged_mem[state_index] <= 1'b1;
                            hit_mem[state_index]    <= 1'b0;
                            miss_mem[state_index]   <= 1'b1;
                        end

                        if (duration_valid_mem[state_index]) begin
                            if (effective_frame >
                                (hit_frame_mem[state_index] +
                                 duration_frames_mem[state_index])) begin
                                slot_used_mem[state_index] <= 1'b0;
                            end
                        end else if (judged_mem[state_index] &&
                                     (effective_frame >
                                      (hit_frame_mem[state_index] +
                                       HIT_WINDOW_FRAMES))) begin
                            slot_used_mem[state_index] <= 1'b0;
                        end
                    end
                end
            end

            if (match_valid && (match_error <= HIT_WINDOW_FRAMES)) begin
                judged_mem[match_slot_index] <= 1'b1;
                hit_mem[match_slot_index]    <= 1'b1;
                miss_mem[match_slot_index]   <= 1'b0;
            end

            if (score_accept) begin
                slot_used_mem[free_slot_index]       <= 1'b1;
                note_id_mem[free_slot_index]         <= score_note_id;
                note_number_mem[free_slot_index]     <= score_note_number;
                hit_frame_mem[free_slot_index]       <= score_hit_frame;
                duration_valid_mem[free_slot_index]  <= score_duration_valid;
                duration_frames_mem[free_slot_index] <= score_duration_frames;
                velocity_mem[free_slot_index]        <= score_velocity;
                judged_mem[free_slot_index]          <= 1'b0;
                hit_mem[free_slot_index]             <= 1'b0;
                miss_mem[free_slot_index]            <= 1'b0;
            end
        end
    end

`ifndef SYNTHESIS
    initial begin
        if (SLOT_COUNT < 1) begin
            $fatal(1, "visual_score_tracker SLOT_COUNT must be positive");
        end
        if (FRAME_WIDTH < 1 || FRAME_WIDTH > 32) begin
            $fatal(1, "visual_score_tracker FRAME_WIDTH must be 1..32");
        end
        if (Y_WIDTH < 1 || Y_WIDTH > 32) begin
            $fatal(1, "visual_score_tracker Y_WIDTH must be 1..32");
        end
        if (PREVIEW_FRAMES < 1) begin
            $fatal(1, "visual_score_tracker PREVIEW_FRAMES must be positive");
        end
        if (TRAVEL_Y < 0 || TRAVEL_Y_64 >= (64'd1 << Y_WIDTH)) begin
            $fatal(1, "visual_score_tracker TRAVEL_Y does not fit Y_WIDTH");
        end
    end
`endif

endmodule
