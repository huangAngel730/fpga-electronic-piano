// -----------------------------------------------------------------------------
// pro_visual_score_tracker.sv
//
// Bounded falling-score timeline and hit/miss tracker.  Score timestamps are
// absolute frame numbers.  The module owns no pixel clock, raster timing, CDC,
// top-level integration, or board constraints.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module pro_visual_score_tracker #(
    parameter integer SLOT_COUNT         = 8,
    parameter integer FRAME_WIDTH        = 32,
    parameter integer Y_WIDTH            = 10,
    parameter integer PREVIEW_FRAMES     = 120,
    parameter integer TRAVEL_Y           = 400,
    parameter integer HIT_WINDOW_FRAMES  = 12,
    parameter bit BOTTOM_EXIT_GEOMETRY = 1'b0,
    parameter bit STRICT_CONTACT = 1'b0,
    parameter integer RASTER_HEIGHT = 480,
    parameter integer MIN_NOTE_HEIGHT = 12
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
    output logic [6:0]                            hit_note_number,
    output wire                                  duplicate_id_fault
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
    // Bottom-exit geometry needs only duration!=0 after accepting the full
    // timestamp tuple. Legacy retirement still stores the complete duration.
    localparam integer DURATION_STORE_WIDTH = BOTTOM_EXIT_GEOMETRY ? 1 : FRAME_WIDTH;
    logic [DURATION_STORE_WIDTH-1:0]   duration_frames_mem [0:SLOT_COUNT-1];
    // R04: invariant absolute stamps are computed once when a score is
    // accepted, instead of inserting a 33-bit saturating add into every pixel.
    logic [FRAME_WIDTH-1:0]            tail_frame_mem      [0:SLOT_COUNT-1];
    logic                              visual_trim_mem     [0:SLOT_COUNT-1];
    logic                              trim_one_pixel_mem [0:SLOT_COUNT-1];
    logic [FRAME_WIDTH-1:0]            retire_frame_mem    [0:SLOT_COUNT-1];
    logic [9:0]                        velocity_mem        [0:SLOT_COUNT-1];
    logic                              judged_mem          [0:SLOT_COUNT-1];
    logic                              hit_mem             [0:SLOT_COUNT-1];
    logic                              miss_mem            [0:SLOT_COUNT-1];

    logic [FRAME_WIDTH-1:0] effective_frame;

    // R04: keep the already-known next frame in a parallel register. The
    // invariant next_frame == current_frame+1 (modulo FRAME_WIDTH) starts at
    // reset and advances on every frame_start, including video_desync. This
    // removes the measured full-width increment before contact comparison;
    // no event, frame or output is delayed by a cycle.
    logic [FRAME_WIDTH-1:0] next_frame;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) next_frame <= FRAME_WIDTH'(1);
        else if (frame_start) next_frame <= next_frame + FRAME_WIDTH'(1);
    end

    logic                   score_accept;
    logic                   duplicate_score_id;
    assign duplicate_id_fault=score_valid && duplicate_score_id;
    logic                   match_commit;
    logic [(SLOT_COUNT <= 1 ? 1 : $clog2(SLOT_COUNT))-1:0] match_commit_index;
    logic [6:0]             match_commit_note;
    logic [FRAME_WIDTH-1:0] match_commit_frame;
    integer output_index;
    integer state_index;

    // R13: frame maintenance and geometry share one 32-cycle scanner.  The
    // former implementation updated every score slot in parallel at
    // frame_start, replicating full-width miss/retire comparisons 32 times.
    // A video frame provides hundreds of thousands of pixel clocks, so one
    // slot per clock completes during blanking without changing frame time.
    localparam integer GEO_INDEX_BITS = (SLOT_COUNT <= 1) ? 1 : $clog2(SLOT_COUNT);
    logic geo_scan_active;
    logic [GEO_INDEX_BITS-1:0] geo_scan_index;
    logic [FRAME_WIDTH-1:0] geo_scan_frame;

    // R13: score admission uses the same bounded-latency principle as match
    // and geometry processing.  The previous combinational ready path built a
    // 32-way free-slot priority tree plus 32 parallel 16-bit ID comparators.
    // A standard ready/valid source keeps its payload stable while ready is
    // low, so capture it once, inspect one slot per clock, then acknowledge.
    logic score_scan_active;
    logic score_decision_valid;
    logic score_scan_free_valid;
    logic score_scan_duplicate;
    logic [GEO_INDEX_BITS-1:0] score_scan_index;
    logic [GEO_INDEX_BITS-1:0] score_selected_index;
    logic [15:0] score_latched_note_id;
    logic [6:0] score_latched_note_number;
    logic [FRAME_WIDTH-1:0] score_latched_hit_frame;
    logic score_latched_duration_valid;
    logic [FRAME_WIDTH-1:0] score_latched_duration_frames;
    logic [9:0] score_latched_velocity;
    // The production raster moves by four pixels per score frame. With an
    // integral pixels/frame and minimum height, a one-frame tail cap gives
    // a visible gap without moving either hit time. Keep legacy geometries.
    localparam bit REPEAT_GAP = BOTTOM_EXIT_GEOMETRY &&
        (RASTER_HEIGHT % PREVIEW_FRAMES == 0) &&
        ((MIN_NOTE_HEIGHT * PREVIEW_FRAMES) % RASTER_HEIGHT == 0);
    logic [FRAME_WIDTH-1:0] score_gap_cutoff;
    logic [FRAME_WIDTH-1:0] score_natural_tail;
    logic [FRAME_WIDTH-1:0] score_min_tail, score_initial_tail;
    logic [SLOT_COUNT-1:0] score_trim_mask, score_one_pixel_mask;
    logic score_gap_sample_valid, score_gap_same_note;
    logic [GEO_INDEX_BITS-1:0] score_gap_slot;
    logic [FRAME_WIDTH-1:0] score_gap_prior_hit, score_gap_prior_tail;
    wire score_scan_slot_duplicate = slot_used_mem[score_scan_index] &&
        note_id_mem[score_scan_index] == score_latched_note_id;
    wire score_scan_slot_free = !slot_used_mem[score_scan_index] &&
        !score_scan_free_valid;

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
        input logic duration_valid,
        input logic [FRAME_WIDTH-1:0] tail_frame
    );
        logic [Y_WIDTH-1:0] tail,short_top;
        begin
            short_top=short_top_y(now_frame,arrival);
            tail=front_end_y(now_frame,tail_frame);
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
            effective_frame = next_frame;
        end
    end

    // The decision is held for exactly one cycle.  A duplicate is acknowledged
    // and discarded, matching the original consume-without-rearm behavior.
    always_comb begin
        duplicate_score_id = STRICT_CONTACT && score_decision_valid &&
            score_scan_duplicate;
        score_ready = score_decision_valid && !geo_scan_active && !frame_start &&
            !score_gap_sample_valid &&
            (score_scan_free_valid || duplicate_score_id);
        score_accept = score_valid && score_ready && !duplicate_score_id;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            score_scan_active <= 1'b0;
            score_decision_valid <= 1'b0;
            score_scan_free_valid <= 1'b0;
            score_scan_duplicate <= 1'b0;
            score_scan_index <= '0;
            score_selected_index <= '0;
            score_latched_note_id <= '0;
            score_latched_note_number <= '0;
            score_latched_hit_frame <= '0;
            score_latched_duration_valid <= 1'b0;
            score_latched_duration_frames <= '0;
            score_latched_velocity <= '0;
        end else if (video_desync) begin
            score_scan_active <= 1'b0;
            score_decision_valid <= 1'b0;
            score_scan_free_valid <= 1'b0;
            score_scan_duplicate <= 1'b0;
        end else begin
            if (score_decision_valid && (!score_valid || score_ready)) begin
                // Hold the decision across a geometry snapshot.  When ready is
                // high, the state process samples score_accept on this edge.
                score_decision_valid <= 1'b0;
            end else if (score_scan_active) begin
                if (score_scan_slot_free) begin
                    score_scan_free_valid <= 1'b1;
                    score_selected_index <= score_scan_index;
                end
                if (STRICT_CONTACT && score_scan_slot_duplicate) begin
                    score_scan_duplicate <= 1'b1;
                end
                if (score_scan_index == GEO_INDEX_BITS'(SLOT_COUNT-1)) begin
                    score_scan_active <= 1'b0;
                    if ((STRICT_CONTACT &&
                         (score_scan_duplicate || score_scan_slot_duplicate)) ||
                        score_scan_free_valid || score_scan_slot_free) begin
                        score_decision_valid <= 1'b1;
                    end
                end else begin
                    score_scan_index <= score_scan_index + GEO_INDEX_BITS'(1);
                end
            end else if (!score_decision_valid && score_valid && !geo_scan_active && !frame_start) begin
                score_scan_active <= 1'b1;
                score_scan_index <= '0;
                score_scan_free_valid <= 1'b0;
                score_scan_duplicate <= 1'b0;
                score_selected_index <= '0;
                score_latched_note_id <= score_note_id;
                score_latched_note_number <= score_note_number;
                score_latched_hit_frame <= score_hit_frame;
                score_latched_duration_valid <= score_duration_valid;
                score_latched_duration_frames <= score_duration_frames;
                score_latched_velocity <= score_velocity;
            end
        end
    end

    // Scan earlier notes in upload order. Register the shared slot read
    // before comparing timestamps. Commit the mask only on real admission,
    // so a duplicate or withdrawn transaction cannot shorten earlier notes.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            score_gap_sample_valid <= 0;
            score_gap_same_note <= 0;
            score_gap_slot <= '0;
            score_gap_prior_hit <= '0;
            score_gap_prior_tail <= '0;
            score_gap_cutoff <= '0;
            score_natural_tail <= '0;
            score_min_tail <= '0;
            score_initial_tail <= '0;
            score_trim_mask <= '0;
            score_one_pixel_mask <= '0;
        end else if (video_desync) begin
            score_gap_sample_valid <= 0;
            score_trim_mask <= '0;
            score_one_pixel_mask <= '0;
        end else if (REPEAT_GAP) begin
            score_gap_sample_valid <= score_scan_active;
            if (score_scan_active) begin
                if (score_scan_index == 0)
                    score_initial_tail <= score_natural_tail > score_min_tail ?
                        score_natural_tail : score_min_tail;
                score_gap_slot <= score_scan_index;
                score_gap_prior_hit <= hit_frame_mem[score_scan_index];
                score_gap_prior_tail <= tail_frame_mem[score_scan_index];
                score_gap_same_note <= slot_used_mem[score_scan_index] &&
                    note_number_mem[score_scan_index] == score_latched_note_number;
            end
            if (score_gap_sample_valid) begin
                score_trim_mask[score_gap_slot] <= score_gap_same_note &&
                    score_gap_prior_hit < score_latched_hit_frame &&
                    score_gap_prior_tail > score_gap_cutoff;
                score_one_pixel_mask[score_gap_slot] <= score_gap_prior_hit == score_gap_cutoff;
            end
            if (!score_scan_active && !score_decision_valid && score_valid &&
                !geo_scan_active && !frame_start) begin
                score_gap_cutoff <= score_hit_frame - FRAME_WIDTH'(1);
                score_natural_tail <= saturating_frame_add(
                    score_hit_frame, score_duration_valid ? score_duration_frames : '0);
                score_min_tail <= saturating_frame_add(
                    score_hit_frame, FRAME_WIDTH'(SHORT_EXIT_FRAMES));
                score_trim_mask <= '0;
                score_one_pixel_mask <= '0;
            end
        end
    end

    // R06: MIDI events are separated by thousands of pixel clocks, while the
    // old implementation instantiated 32 full-width subtractors plus a wide
    // nearest-match tree on every clock.  Latch one NoteOn and inspect one slot
    // per clock instead.  The bounded 32-cycle latency is below one microsecond
    // at the 40 MHz pixel clock and preserves lower-index tie breaking.
    localparam integer MATCH_INDEX_BITS = (SLOT_COUNT <= 1) ? 1 : $clog2(SLOT_COUNT);
    logic match_scan_active, match_best_valid;
    logic [MATCH_INDEX_BITS-1:0] match_scan_index, match_best_index;
    logic [FRAME_WIDTH-1:0] match_scan_frame, match_best_error;
    logic [6:0] match_scan_note;
    wire [FRAME_WIDTH-1:0] match_scan_error =
        absolute_frame_error(match_scan_frame, hit_frame_mem[match_scan_index]);
    wire match_scan_candidate = slot_used_mem[match_scan_index] &&
        !judged_mem[match_scan_index] &&
        note_number_mem[match_scan_index] == match_scan_note &&
        (!STRICT_CONTACT || match_scan_error <= FRAME_WIDTH'(HIT_WINDOW_FRAMES));
    wire match_scan_take = match_scan_candidate &&
        (!match_best_valid || match_scan_error < match_best_error);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            match_scan_active <= 1'b0;
            match_scan_index <= '0;
            match_scan_frame <= '0;
            match_scan_note <= '0;
            match_best_valid <= 1'b0;
            match_best_index <= '0;
            match_best_error <= '1;
            match_commit <= 1'b0;
            match_commit_index <= '0;
            match_commit_note <= '0;
            match_commit_frame <= '0;
        end else if (video_desync) begin
            match_scan_active <= 1'b0;
            match_best_valid <= 1'b0;
            match_commit <= 1'b0;
        end else begin
            match_commit <= 1'b0;
            if (!match_scan_active && performance_fire &&
                performance_data.event_type == EVENT_NOTE_ON &&
                performance_data.velocity != 0 &&
                (!STRICT_CONTACT || match_enabled)) begin
                match_scan_active <= 1'b1;
                match_scan_index <= '0;
                match_scan_frame <= effective_frame;
                match_scan_note <= performance_data.note_number;
                match_best_valid <= 1'b0;
                match_best_index <= '0;
                match_best_error <= '1;
            end else if (match_scan_active) begin
                if (match_scan_take) begin
                    match_best_valid <= 1'b1;
                    match_best_index <= match_scan_index;
                    match_best_error <= match_scan_error;
                end
                if (match_scan_index == MATCH_INDEX_BITS'(SLOT_COUNT-1)) begin
                    match_scan_active <= 1'b0;
                    if (match_scan_take || match_best_valid) begin
                        match_commit <= 1'b1;
                        match_commit_index <= match_scan_take ?
                            match_scan_index : match_best_index;
                        match_commit_note <= match_scan_note;
                        match_commit_frame <= match_scan_frame;
                    end
                end else begin
                    match_scan_index <= match_scan_index + MATCH_INDEX_BITS'(1);
                end
            end
        end
    end

    // V3 geometry: exact signed differences supply range and bounded distance.
    // Parameter-wide constant comparisons fold to low-bit tests/reductions;
    // no new state, latency, preservation attributes or scoring changes.
    // V3: one signed full difference per arrival feeds sign, constant-range
    // checks and low-bit geometry. Avoid separate dynamic lookahead/cutoff
    // comparisons competing with the independently narrowed subtractions.
    localparam logic [63:0] GEOMETRY_SHORT_EXIT =
        (64'(MIN_NOTE_HEIGHT)*64'(PREVIEW_FRAMES)+64'(RASTER_HEIGHT)-1)/64'(RASTER_HEIGHT);
    // Caller proves delta<PREVIEW_FRAMES. No wide subtract or saturating
    // comparison is hidden inside this per-slot conversion.
    function automatic logic [Y_WIDTH-1:0] bounded_raster_distance(
        input logic [REM_BITS-1:0] delta
    );
        logic [GEO_PRODUCT_BITS-1:0] product,quotient;
        begin
            if(RASTER_HEIGHT%PREVIEW_FRAMES==0)begin
                product=delta*GEO_PRODUCT_BITS'(RASTER_HEIGHT/PREVIEW_FRAMES);
                quotient=product;
            end else begin
                product=delta*GEO_PRODUCT_BITS'(RASTER_HEIGHT);
                quotient=GEO_DIV_BITS'(product)/GEO_DIV_BITS'(PREVIEW_FRAMES);
            end
            bounded_raster_distance=Y_WIDTH'(quotient);
        end
    endfunction
    function automatic logic [Y_WIDTH-1:0] bounded_travel_distance(
        input logic [REM_BITS-1:0] delta
    );
        logic [PRODUCT_BITS-1:0] product,quotient;
        begin
            product=delta*PRODUCT_BITS'(TRAVEL_Y);
            quotient=DIV_BITS'(product)/DIV_BITS'(PREVIEW_FRAMES);
            bounded_travel_distance=Y_WIDTH'(quotient);
        end
    endfunction
    // R06: one geometry datapath is shared by all score slots.  A complete
    // output snapshot is refreshed in 32 clocks immediately after frame_start,
    // instead of recomputing 32 copies during every pixel.  Output registers
    // remain parallel, so the existing renderer interface is unchanged.
    wire signed [FRAME_WIDTH:0] geo_hit_gap =
        $signed({1'b0,hit_frame_mem[geo_scan_index]})-
        $signed({1'b0,geo_scan_frame});
    wire signed [FRAME_WIDTH:0] geo_tail_gap =
        $signed({1'b0,tail_frame_mem[geo_scan_index]})-
        $signed({1'b0,geo_scan_frame});
    wire geo_arrived = geo_hit_gap[FRAME_WIDTH] ||
        !(|geo_hit_gap[FRAME_WIDTH-1:0]);
    wire geo_hit_far = !geo_hit_gap[FRAME_WIDTH] &&
        64'(geo_hit_gap[FRAME_WIDTH-1:0]) >= 64'(PREVIEW_FRAMES);
    wire geo_tail_arrived = geo_tail_gap[FRAME_WIDTH] ||
        !(|geo_tail_gap[FRAME_WIDTH-1:0]);
    wire geo_tail_far = !geo_tail_gap[FRAME_WIDTH] &&
        64'(geo_tail_gap[FRAME_WIDTH-1:0]) >= 64'(PREVIEW_FRAMES);
    wire [REM_BITS-1:0] geo_hit_delta = geo_hit_gap[REM_BITS-1:0];
    wire [REM_BITS-1:0] geo_tail_delta = geo_tail_gap[REM_BITS-1:0];
    wire [REM_BITS-1:0] geo_after_delta = -geo_hit_gap[REM_BITS-1:0];
    wire geo_visible = geo_hit_gap[FRAME_WIDTH] ||
        64'(geo_hit_gap[FRAME_WIDTH-1:0]) <= 64'(PREVIEW_FRAMES);
    wire [Y_WIDTH-1:0] geo_hit_distance =
        bounded_raster_distance(geo_hit_delta);
    wire [Y_WIDTH-1:0] geo_tail_distance =
        bounded_raster_distance(geo_tail_delta);
    wire [Y_WIDTH-1:0] geo_front = geo_arrived ? Y_WIDTH'(RASTER_HEIGHT) :
        geo_hit_far ? Y_WIDTH'(0) : Y_WIDTH'(RASTER_HEIGHT)-geo_hit_distance;
    wire [Y_WIDTH-1:0] geo_tail = geo_tail_arrived ? Y_WIDTH'(RASTER_HEIGHT) :
        geo_tail_far ? Y_WIDTH'(0) : Y_WIDTH'(RASTER_HEIGHT)-geo_tail_distance;
    localparam logic signed [FRAME_WIDTH:0] GEO_NEG_EXIT =
        -$signed((FRAME_WIDTH+1)'(GEOMETRY_SHORT_EXIT));
    wire geo_short_exited = (GEOMETRY_SHORT_EXIT > ((64'd1<<FRAME_WIDTH)-1)) ?
        1'b0 : (geo_hit_gap <= GEO_NEG_EXIT);
    wire [Y_WIDTH-1:0] geo_after_distance =
        bounded_raster_distance(geo_after_delta);
    wire [Y_WIDTH-1:0] geo_short_top = geo_arrived ?
        (geo_short_exited ? Y_WIDTH'(RASTER_HEIGHT) :
            Y_WIDTH'((RASTER_HEIGHT-MIN_NOTE_HEIGHT)+{1'b0,geo_after_distance})) :
        (geo_front<MIN_NOTE_HEIGHT ? Y_WIDTH'(0) :
            geo_front-Y_WIDTH'(MIN_NOTE_HEIGHT));
    wire [Y_WIDTH-1:0] geo_regular_top =
        (duration_valid_mem[geo_scan_index] &&
         duration_frames_mem[geo_scan_index]!=0 && geo_tail<geo_short_top) ?
        geo_tail : geo_short_top;
    // One-frame-separated onsets still show a one-pixel head. A pair
    // quantized to the same display frame is never artificially displaced.
    wire [Y_WIDTH-1:0] geo_one_pixel_top =
        geo_hit_gap[FRAME_WIDTH] ? Y_WIDTH'(RASTER_HEIGHT) :
        geo_hit_far ? Y_WIDTH'(0) : Y_WIDTH'(RASTER_HEIGHT-1)-geo_hit_distance;
    wire [Y_WIDTH-1:0] geo_top =
        (REPEAT_GAP && visual_trim_mem[geo_scan_index]) ?
            (trim_one_pixel_mem[geo_scan_index] ? geo_one_pixel_top : geo_tail) :
            geo_regular_top;
    wire [Y_WIDTH-1:0] geo_y = geo_arrived ? Y_WIDTH'(0) :
        geo_hit_far ? TRAVEL_Y_VALUE :
        ((TRAVEL_Y==RASTER_HEIGHT) ? geo_hit_distance :
            bounded_travel_distance(geo_hit_delta));

    // One shared maintenance datapath replaces SLOT_COUNT parallel copies.
    // These expressions deliberately preserve the original strict > tests and
    // unsaturated FRAME_WIDTH arithmetic used by the parallel implementation.
    wire scan_miss_due = slot_used_mem[geo_scan_index] &&
        !judged_mem[geo_scan_index] &&
        (geo_scan_frame >
         (hit_frame_mem[geo_scan_index] + FRAME_WIDTH'(HIT_WINDOW_FRAMES)));
    wire scan_retire_bottom = BOTTOM_EXIT_GEOMETRY &&
        slot_used_mem[geo_scan_index] &&
        (geo_scan_frame > retire_frame_mem[geo_scan_index]);
    wire scan_retire_duration = !BOTTOM_EXIT_GEOMETRY &&
        slot_used_mem[geo_scan_index] &&
        duration_valid_mem[geo_scan_index] &&
        (geo_scan_frame >
         (hit_frame_mem[geo_scan_index] +
          FRAME_WIDTH'(duration_frames_mem[geo_scan_index])));
    wire scan_retire_legacy = !BOTTOM_EXIT_GEOMETRY &&
        slot_used_mem[geo_scan_index] &&
        !duration_valid_mem[geo_scan_index] &&
        judged_mem[geo_scan_index] &&
        (geo_scan_frame >
         (hit_frame_mem[geo_scan_index] + FRAME_WIDTH'(HIT_WINDOW_FRAMES)));
    wire scan_retire_due = scan_retire_bottom || scan_retire_duration ||
        scan_retire_legacy;
    wire scan_used_next = slot_used_mem[geo_scan_index] && !scan_retire_due;
    wire scan_judged_next = judged_mem[geo_scan_index] || scan_miss_due;
    wire scan_hit_next = scan_miss_due ? 1'b0 : hit_mem[geo_scan_index];
    wire scan_miss_next = miss_mem[geo_scan_index] || scan_miss_due;
    logic scan_visible_valid;
    logic [GEO_INDEX_BITS-1:0] scan_visible_index;
    logic scan_visible_hit,scan_visible_miss,scan_visible_slot;
    logic [15:0] scan_visible_note_id;
    logic [6:0] scan_visible_note_number;
    logic [Y_WIDTH-1:0] scan_visible_y,scan_visible_top,scan_visible_end;
    logic [9:0] scan_visible_velocity;
    wire scan_hit_flash = STRICT_CONTACT && hit_mem[geo_scan_index] &&
        (geo_scan_frame == hit_frame_mem[geo_scan_index]);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            geo_scan_active <= 1'b0;
            geo_scan_index <= '0;
            geo_scan_frame <= '0;
            scan_visible_valid <= 1'b0; scan_visible_index <= '0;
            scan_visible_hit <= 1'b0; scan_visible_miss <= 1'b0;
            slot_valid <= '0;
            slot_note_id <= '0;
            slot_note_number <= '0;
            slot_y <= '0;
            slot_top_y <= '0;
            slot_end_y <= '0;
            slot_velocity <= '0;
            slot_hit <= '0;
            slot_miss <= '0;
        end else if (video_desync) begin
            geo_scan_active <= 1'b0;
            scan_visible_valid <= 1'b0;
            slot_valid <= '0;
            slot_note_id <= '0;
            slot_note_number <= '0;
            slot_y <= '0;
            slot_top_y <= '0;
            slot_end_y <= '0;
            slot_velocity <= '0;
            slot_hit <= '0;
            slot_miss <= '0;
        end else begin
            scan_visible_valid <= geo_scan_active && !frame_start;
            if (scan_visible_valid) begin
                slot_valid[scan_visible_index] <= scan_visible_slot;
                slot_note_id[scan_visible_index*16 +: 16] <= scan_visible_note_id;
                slot_note_number[scan_visible_index*7 +: 7] <= scan_visible_note_number;
                slot_y[scan_visible_index*Y_WIDTH +: Y_WIDTH] <= scan_visible_y;
                slot_top_y[scan_visible_index*Y_WIDTH +: Y_WIDTH] <= scan_visible_top;
                slot_end_y[scan_visible_index*Y_WIDTH +: Y_WIDTH] <= scan_visible_end;
                slot_velocity[scan_visible_index*10 +: 10] <= scan_visible_velocity;
                slot_hit[scan_visible_index] <= scan_visible_hit;
                slot_miss[scan_visible_index] <= scan_visible_miss;
            end
            if (frame_start) begin
                geo_scan_active <= 1'b1;
                geo_scan_index <= '0;
                geo_scan_frame <= effective_frame;
            end else if (geo_scan_active) begin
                scan_visible_index <= geo_scan_index;
                scan_visible_slot <= scan_used_next && geo_visible;
                scan_visible_note_id <= note_id_mem[geo_scan_index];
                scan_visible_note_number <= note_number_mem[geo_scan_index];
                scan_visible_y <= geo_y;
                scan_visible_top <= geo_top;
                scan_visible_end <= geo_front;
                scan_visible_velocity <= velocity_mem[geo_scan_index];
                scan_visible_hit <= scan_hit_next &&
                    (!STRICT_CONTACT || geo_scan_frame>=hit_frame_mem[geo_scan_index]);
                scan_visible_miss <= scan_miss_next;
                if (geo_scan_index == GEO_INDEX_BITS'(SLOT_COUNT-1)) begin
                    geo_scan_active <= 1'b0;
                end else begin
                    geo_scan_index <= geo_scan_index + GEO_INDEX_BITS'(1);
                end
            end
        end
    end

    // All timeline state is owned by this single sequential process.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
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
                tail_frame_mem[state_index]       <= '0;
                visual_trim_mem[state_index]       <= 1'b0;
                trim_one_pixel_mem[state_index]    <= 1'b0;
                retire_frame_mem[state_index]     <= '0;
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
                tail_frame_mem[state_index]       <= '0;
                visual_trim_mem[state_index]       <= 1'b0;
                trim_one_pixel_mem[state_index]    <= 1'b0;
                retire_frame_mem[state_index]     <= '0;
                velocity_mem[state_index]        <= 10'd0;
                judged_mem[state_index]          <= 1'b0;
                hit_mem[state_index]             <= 1'b0;
                miss_mem[state_index]            <= 1'b0;
            end
        end else begin
            hit_pulse<=0;
            if (frame_start) begin
                current_frame <= effective_frame;
            end

            if (geo_scan_active) begin
                slot_used_mem[geo_scan_index] <= scan_used_next;
                judged_mem[geo_scan_index] <= scan_judged_next;
                hit_mem[geo_scan_index] <= scan_hit_next;
                miss_mem[geo_scan_index] <= scan_miss_next;
                if (scan_hit_flash) begin
                    hit_pulse <= 1'b1;
                    hit_note_number <= note_number_mem[geo_scan_index];
                end
            end

            if (match_commit) begin
                if(!STRICT_CONTACT ||
                   match_commit_frame>=hit_frame_mem[match_commit_index])begin
                    hit_pulse<=1;hit_note_number<=match_commit_note;
                end
                judged_mem[match_commit_index] <= 1'b1;
                hit_mem[match_commit_index]    <= 1'b1;
                miss_mem[match_commit_index]   <= 1'b0;
            end

            if (REPEAT_GAP && score_accept) begin
                for (integer trim_slot=0; trim_slot<SLOT_COUNT; trim_slot++) begin
                    if (score_trim_mask[trim_slot]) begin
                        tail_frame_mem[trim_slot] <= score_gap_cutoff;
                        visual_trim_mem[trim_slot] <= 1'b1;
                        trim_one_pixel_mem[trim_slot] <= score_one_pixel_mask[trim_slot];
                    end
                end
            end

            if (score_accept) begin
                slot_used_mem[score_selected_index]       <= 1'b1;
                note_id_mem[score_selected_index]         <= score_latched_note_id;
                note_number_mem[score_selected_index]     <= score_latched_note_number;
                hit_frame_mem[score_selected_index]       <= score_latched_hit_frame;
                duration_valid_mem[score_selected_index]  <= score_latched_duration_valid;
                duration_frames_mem[score_selected_index] <= BOTTOM_EXIT_GEOMETRY ?
                    DURATION_STORE_WIDTH'(score_latched_duration_frames!=0) :
                    DURATION_STORE_WIDTH'(score_latched_duration_frames);
                tail_frame_mem[score_selected_index]       <= REPEAT_GAP ?
                    score_initial_tail :
                    saturating_frame_add(score_latched_hit_frame,score_latched_duration_frames);
                visual_trim_mem[score_selected_index]      <= 1'b0;
                trim_one_pixel_mem[score_selected_index]    <= 1'b0;
                retire_frame_mem[score_selected_index]     <= retirement_frame(
                    score_latched_hit_frame,score_latched_duration_frames,
                    score_latched_duration_valid);
                velocity_mem[score_selected_index]        <= score_latched_velocity;
                judged_mem[score_selected_index]          <= 1'b0;
                hit_mem[score_selected_index]             <= 1'b0;
                miss_mem[score_selected_index]            <= 1'b0;
            end
        end
    end

`ifndef SYNTHESIS
    initial begin
        if (SLOT_COUNT < 1) begin
            $fatal(1, "pro_visual_score_tracker SLOT_COUNT must be positive");
        end
        if (FRAME_WIDTH < 1 || FRAME_WIDTH > 32) begin
            $fatal(1, "pro_visual_score_tracker FRAME_WIDTH must be 1..32");
        end
        if (Y_WIDTH < 1 || Y_WIDTH > 32) begin
            $fatal(1, "pro_visual_score_tracker Y_WIDTH must be 1..32");
        end
        if (PREVIEW_FRAMES < 1) begin
            $fatal(1, "pro_visual_score_tracker PREVIEW_FRAMES must be positive");
        end
        if(RASTER_HEIGHT<MIN_NOTE_HEIGHT || MIN_NOTE_HEIGHT<1 || RASTER_HEIGHT>65535 ||
           RASTER_HEIGHT >= (64'd1<<Y_WIDTH))
            $fatal(1,"bottom geometry outside coordinate width");
        if (TRAVEL_Y < 0 || TRAVEL_Y_64 >= (64'd1 << Y_WIDTH)) begin
            $fatal(1, "pro_visual_score_tracker TRAVEL_Y does not fit Y_WIDTH");
        end
    end
`endif

endmodule
