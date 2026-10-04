// -----------------------------------------------------------------------------
// visual_score_tracker.sv
//
// Bounded falling-score timeline and hit/miss tracker.  Score timestamps are
// absolute frame numbers.  The module owns no pixel clock, raster timing, CDC,
// top-level integration, or board constraints.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module visual_score_tracker_transport #(
    parameter integer SLOT_COUNT         = 8,
    parameter integer FRAME_WIDTH        = 32,
    parameter integer Y_WIDTH            = 10,
    parameter integer PREVIEW_FRAMES     = 120,
    parameter integer TRAVEL_Y           = 400,
    parameter integer HIT_WINDOW_FRAMES  = 6,
    parameter bit BOTTOM_EXIT_GEOMETRY = 1'b0,
    parameter bit STRICT_CONTACT = 1'b0,
    parameter integer RASTER_HEIGHT = 480,
    parameter integer MIN_NOTE_HEIGHT = 12
) (
    input  logic                                  clk,
    input  logic                                  rst_n,
    input  logic                                  frame_start,
    input logic transport_clear, // synchronous score-only restart

    input  logic                                  score_valid,
    output logic                                  score_ready,
    input  logic [15:0]                           score_note_id,
    input  logic [6:0]                            score_note_number,
    input  logic [FRAME_WIDTH-1:0]                score_hit_frame,
    input  logic                                  score_duration_valid,
    input  logic [FRAME_WIDTH-1:0]                score_duration_frames,
    input  logic [9:0]                            score_velocity,

    input  logic                                  performance_fire,
    input  logic                                  match_enabled,
    input  audio_defs_pkg::performance_event_t    performance_data,
    input  logic                                  video_desync,

    output logic [FRAME_WIDTH-1:0]                current_frame,
    output logic [SLOT_COUNT-1:0]                 slot_valid,
    output logic [SLOT_COUNT*16-1:0]              slot_note_id,
    output logic [SLOT_COUNT*7-1:0]               slot_note_number,
    output logic [SLOT_COUNT*Y_WIDTH-1:0]         slot_y,
    output logic [SLOT_COUNT*Y_WIDTH-1:0]         slot_top_y,
    output logic [SLOT_COUNT*Y_WIDTH-1:0]         slot_end_y,
    output logic [SLOT_COUNT*10-1:0]              slot_velocity,
    output logic [SLOT_COUNT-1:0]                 slot_hit,
    output logic [SLOT_COUNT-1:0]                 slot_miss,
    output logic                                  hit_pulse,
    output logic [6:0]                            hit_note_number
);

    import audio_defs_pkg::*;

    localparam logic [Y_WIDTH-1:0] TRAVEL_Y_VALUE =
        TRAVEL_Y[Y_WIDTH-1:0];
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
    logic                   duplicate_score_id;
    logic                   match_valid;
    integer                 free_slot_index;
    integer                 match_slot_index;
    logic [FRAME_WIDTH-1:0] match_error;

    integer output_index;
    integer free_search_index;
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

    // The unsaturated branch has remaining_frames < PREVIEW_FRAMES. Keep
    // full-width time comparisons, then narrow only this proven bounded value.
    localparam integer REM_BITS_RAW = (PREVIEW_FRAMES <= 1) ? 1 : $clog2(PREVIEW_FRAMES);
    localparam integer REM_BITS = (REM_BITS_RAW < FRAME_WIDTH) ? REM_BITS_RAW : FRAME_WIDTH;
    localparam integer TRAVEL_BITS = (TRAVEL_Y < 1) ? 1 : $clog2(TRAVEL_Y + 64'd1);
    localparam integer PRODUCT_BITS = REM_BITS + TRAVEL_BITS;
    localparam integer DIVISOR_BITS = $clog2(PREVIEW_FRAMES + 64'd1);
    localparam integer DIV_BITS = (PRODUCT_BITS > DIVISOR_BITS) ? PRODUCT_BITS : DIVISOR_BITS;

    function automatic logic [Y_WIDTH-1:0] calculate_y(
        input logic [FRAME_WIDTH-1:0] frame_value,
        input logic [FRAME_WIDTH-1:0] hit_frame_value
    );
        logic [FRAME_WIDTH-1:0] remaining_frames;
        logic [PRODUCT_BITS-1:0] scaled_distance;
        logic [PRODUCT_BITS-1:0] scaled_quotient;
        begin
            remaining_frames = '0;
            scaled_distance = '0;
            scaled_quotient = '0;
            if (frame_value >= hit_frame_value) begin
                calculate_y = '0;
            end else begin
                remaining_frames = hit_frame_value - frame_value;
                if (remaining_frames >= PREVIEW_FRAMES) begin
                    calculate_y = TRAVEL_Y_VALUE;
                end else begin
                    scaled_distance = remaining_frames[REM_BITS-1:0] * PRODUCT_BITS'(TRAVEL_Y);
                    scaled_quotient = DIV_BITS'(scaled_distance) / DIV_BITS'(PREVIEW_FRAMES);
                    calculate_y = Y_WIDTH'(scaled_quotient);
                end
            end
        end
    endfunction

    // Coordinate helpers only for the new raster geometry. Comparisons and
    // time differences remain full FRAME_WIDTH; narrow after saturation proof.
    localparam integer HEIGHT_BITS = $clog2(RASTER_HEIGHT+64'd1);
    localparam integer GEO_PRODUCT_BITS = REM_BITS + HEIGHT_BITS;
    localparam integer GEO_DIV_BITS = (GEO_PRODUCT_BITS > DIVISOR_BITS) ? GEO_PRODUCT_BITS : DIVISOR_BITS;
    localparam integer SHORT_EXIT_FRAMES = (MIN_NOTE_HEIGHT*PREVIEW_FRAMES + RASTER_HEIGHT-1)/RASTER_HEIGHT;

    function automatic logic [FRAME_WIDTH-1:0] saturating_frame_add(
        input logic [FRAME_WIDTH-1:0] stamp, offset
    );
        logic [FRAME_WIDTH:0] sum;
        begin
            sum={1'b0,stamp}+{1'b0,offset};
            saturating_frame_add=sum[FRAME_WIDTH] ? {FRAME_WIDTH{1'b1}} : sum[FRAME_WIDTH-1:0];
        end
    endfunction

    function automatic logic [Y_WIDTH-1:0] raster_distance(
        input logic [FRAME_WIDTH-1:0] frames
    );
        logic [GEO_PRODUCT_BITS-1:0] product;
        logic [GEO_PRODUCT_BITS-1:0] quotient;
        begin
            product='0;quotient='0;
            if(frames>=PREVIEW_FRAMES)raster_distance=Y_WIDTH'(RASTER_HEIGHT);
            else begin
                if(RASTER_HEIGHT%PREVIEW_FRAMES==0)begin
                    // Default480/120=4, a narrow shift/multiply, no divider.
                    product=frames[REM_BITS-1:0]*GEO_PRODUCT_BITS'(RASTER_HEIGHT/PREVIEW_FRAMES);
                    quotient=product;
                end else begin
                    product=frames[REM_BITS-1:0]*GEO_PRODUCT_BITS'(RASTER_HEIGHT);
                    quotient=GEO_DIV_BITS'(product)/GEO_DIV_BITS'(PREVIEW_FRAMES);
                end
                raster_distance=Y_WIDTH'(quotient);
            end
        end
    endfunction

    function automatic logic [Y_WIDTH-1:0] front_end_y(
        input logic [FRAME_WIDTH-1:0] now_frame, arrival
    );
        begin
            if(now_frame>=arrival)front_end_y=Y_WIDTH'(RASTER_HEIGHT);
            else front_end_y=Y_WIDTH'(RASTER_HEIGHT)-raster_distance(arrival-now_frame);
        end
    endfunction

    function automatic logic [Y_WIDTH-1:0] short_top_y(
        input logic [FRAME_WIDTH-1:0] now_frame, arrival
    );
        logic [Y_WIDTH-1:0] front,distance_after;
        logic [Y_WIDTH:0] top_after;
        begin
            front=front_end_y(now_frame,arrival);
            distance_after='0;top_after='0;
            if(now_frame<arrival)short_top_y=front<MIN_NOTE_HEIGHT ? Y_WIDTH'(0) : front-Y_WIDTH'(MIN_NOTE_HEIGHT);
            else begin
                distance_after=raster_distance(now_frame-arrival);
                top_after=(RASTER_HEIGHT-MIN_NOTE_HEIGHT)+{1'b0,distance_after};
                short_top_y=top_after>=RASTER_HEIGHT ? Y_WIDTH'(RASTER_HEIGHT) : top_after[Y_WIDTH-1:0];
            end
        end
    endfunction

    function automatic logic [Y_WIDTH-1:0] bar_top_y(
        input logic [FRAME_WIDTH-1:0] now_frame, arrival, duration,
        input logic duration_valid
    );
        logic [Y_WIDTH-1:0] tail,short_top;
        begin
            short_top=short_top_y(now_frame,arrival);
            tail=front_end_y(now_frame,saturating_frame_add(arrival,duration));
            bar_top_y=(duration_valid && duration!=0 && tail<short_top) ? tail : short_top;
        end
    endfunction

    function automatic logic [FRAME_WIDTH-1:0] retirement_frame(
        input logic [FRAME_WIDTH-1:0] arrival, duration,
        input logic duration_valid
    );
        logic [FRAME_WIDTH-1:0] retained;
        begin
            retained=FRAME_WIDTH'(HIT_WINDOW_FRAMES);
            if(duration_valid && duration>retained)retained=duration;
            if(SHORT_EXIT_FRAMES>retained)retained=FRAME_WIDTH'(SHORT_EXIT_FRAMES);
            retirement_frame=saturating_frame_add(arrival,retained);
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
        duplicate_score_id=1'b0;
        if(STRICT_CONTACT)begin
            for(integer id_slot=0;id_slot<SLOT_COUNT;id_slot=id_slot+1)
                if(slot_used_mem[id_slot] && note_id_mem[id_slot]==score_note_id)
                    duplicate_score_id=1'b1;
        end
        // Duplicate active instances are consumed but cannot rearm a hit.
        score_accept = score_valid && score_ready && !duplicate_score_id;
    end

    // Parallel absolute errors feed a balanced nearest-match tree. The left
    // child contains lower slot indices and wins equal errors, preserving the
    // original strictly-smaller scan including an eligible all-ones error.
    localparam integer MATCH_LEVELS = (SLOT_COUNT <= 1) ? 0 : $clog2(SLOT_COUNT);
    localparam integer MATCH_LEAVES = 1 << MATCH_LEVELS;
    localparam integer MATCH_INDEX_BITS = (SLOT_COUNT <= 1) ? 1 : $clog2(SLOT_COUNT);
    wire tree_valid [1:2*MATCH_LEAVES-1];
    wire [FRAME_WIDTH-1:0] tree_error [1:2*MATCH_LEAVES-1];
    wire [MATCH_INDEX_BITS-1:0] tree_index [1:2*MATCH_LEAVES-1];
    for (genvar slot = 0; slot < MATCH_LEAVES; slot = slot + 1) begin : g_match_leaf
        if (slot < SLOT_COUNT) begin : g_real
            assign tree_valid[MATCH_LEAVES+slot] = slot_used_mem[slot] &&
                !judged_mem[slot] && note_number_mem[slot] == performance_data.note_number &&
                (!STRICT_CONTACT || hit_frame_mem[slot]==effective_frame);
            if(STRICT_CONTACT)begin : g_contact_error
                assign tree_error[MATCH_LEAVES+slot] = '0;
            end else begin : g_legacy_error
                assign tree_error[MATCH_LEAVES+slot] = absolute_frame_error(effective_frame, hit_frame_mem[slot]);
            end
            assign tree_index[MATCH_LEAVES+slot] = MATCH_INDEX_BITS'(slot);
        end else begin : g_padding
            assign tree_valid[MATCH_LEAVES+slot] = 1'b0;
            assign tree_error[MATCH_LEAVES+slot] = '1;
            assign tree_index[MATCH_LEAVES+slot] = '0;
        end
    end
    for (genvar node = 1; node < MATCH_LEAVES; node = node + 1) begin : g_match_node
        wire choose_left = tree_valid[2*node] &&
            (!tree_valid[2*node+1] || tree_error[2*node] <= tree_error[2*node+1]);
        assign tree_valid[node] = tree_valid[2*node] || tree_valid[2*node+1];
        assign tree_error[node] = choose_left ? tree_error[2*node] : tree_error[2*node+1];
        assign tree_index[node] = choose_left ? tree_index[2*node] : tree_index[2*node+1];
    end
    always_comb begin
        match_valid = 1'b0;
        match_slot_index = 0;
        match_error = '1;
        // Strict eligibility is evaluated against the geometry becoming
        // visible after this edge, including frame_start's current_frame+1.
        if (performance_fire && performance_data.event_type == EVENT_NOTE_ON && tree_valid[1] &&
            (!STRICT_CONTACT || (match_enabled && performance_data.velocity!=0))) begin
            match_valid = 1'b1;
            match_slot_index = int'(tree_index[1]);
            match_error = tree_error[1];
        end
    end

    // Flatten only visible slots.  Stored future notes remain private until
    // their preview frame, so slot_valid is a drawing-valid qualifier.
    always_comb begin
        slot_valid       = '0;
        slot_note_id     = '0;
        slot_note_number = '0;
        slot_y           = '0;
        slot_top_y='0;slot_end_y='0;
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
                slot_end_y[output_index*Y_WIDTH+:Y_WIDTH]=front_end_y(current_frame,hit_frame_mem[output_index]);
                slot_top_y[output_index*Y_WIDTH+:Y_WIDTH]=bar_top_y(current_frame,hit_frame_mem[output_index],
                    duration_frames_mem[output_index],duration_valid_mem[output_index]);
                slot_velocity[output_index*10 +: 10] =
                    velocity_mem[output_index];
                slot_hit[output_index]  = hit_mem[output_index];
                slot_miss[output_index] = miss_mem[output_index];
            end
        end
    end

    // All timeline state is owned by this single sequential process.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n || transport_clear) begin
            current_frame <= {FRAME_WIDTH{1'b0}};
            hit_pulse<=0;hit_note_number<=0;
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
            hit_pulse<=0;hit_note_number<=0;
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
            hit_pulse<=0;
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
                              (STRICT_CONTACT ? 0 : HIT_WINDOW_FRAMES)))) begin
                            judged_mem[state_index] <= 1'b1;
                            hit_mem[state_index]    <= 1'b0;
                            miss_mem[state_index]   <= 1'b1;
                        end

                        if (BOTTOM_EXIT_GEOMETRY) begin
                            // Drawing can end before this gate; late hits still
                            // see the whole inclusive window. No extra motion hold.
                            if(effective_frame>retirement_frame(hit_frame_mem[state_index],
                                duration_frames_mem[state_index],duration_valid_mem[state_index]))
                                slot_used_mem[state_index]<=1'b0;
                        end else if (duration_valid_mem[state_index]) begin
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
                if(performance_data.velocity!=0)begin
                    hit_pulse<=1;hit_note_number<=performance_data.note_number;
                end
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
        if(RASTER_HEIGHT<MIN_NOTE_HEIGHT || MIN_NOTE_HEIGHT<1 || RASTER_HEIGHT>65535 ||
           RASTER_HEIGHT >= (64'd1<<Y_WIDTH))
            $fatal(1,"bottom geometry outside coordinate width");
        if (TRAVEL_Y < 0 || TRAVEL_Y_64 >= (64'd1 << Y_WIDTH)) begin
            $fatal(1, "visual_score_tracker TRAVEL_Y does not fit Y_WIDTH");
        end
    end
`endif

endmodule
