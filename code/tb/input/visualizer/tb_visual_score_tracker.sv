// -----------------------------------------------------------------------------
// tb_visual_score_tracker.sv
// Self-checking tests for the M1 falling-score frame examples and tracker edges.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module tb_visual_score_tracker;

    import audio_defs_pkg::*;

    localparam integer SLOT_COUNT        = 8;
    localparam integer FRAME_WIDTH       = 32;
    localparam integer Y_WIDTH           = 10;
    localparam integer PREVIEW_FRAMES    = 120;
    localparam integer TRAVEL_Y          = 400;
    localparam integer HIT_WINDOW_FRAMES = 6;
    localparam integer CLK_PERIOD_NS     = 10;

    logic                               clk;
    logic                               rst_n;
    logic                               frame_start;
    logic                               score_valid;
    logic                               score_ready;
    logic [15:0]                        score_note_id;
    logic [6:0]                         score_note_number;
    logic [FRAME_WIDTH-1:0]             score_hit_frame;
    logic                               score_duration_valid;
    logic [FRAME_WIDTH-1:0]             score_duration_frames;
    logic [9:0]                         score_velocity;
    logic                               performance_fire;
    performance_event_t                 performance_data;
    logic                               video_desync;
    logic [FRAME_WIDTH-1:0]             current_frame;
    logic [SLOT_COUNT-1:0]              slot_valid;
    logic [SLOT_COUNT*16-1:0]           slot_note_id;
    logic [SLOT_COUNT*7-1:0]            slot_note_number;
    logic [SLOT_COUNT*Y_WIDTH-1:0]      slot_y;
    logic [SLOT_COUNT*10-1:0]           slot_velocity;
    logic [SLOT_COUNT-1:0]              slot_hit;
    logic [SLOT_COUNT-1:0]              slot_miss;

    integer check_count;
    integer error_count;

    visual_score_tracker #(
        .SLOT_COUNT        (SLOT_COUNT),
        .FRAME_WIDTH       (FRAME_WIDTH),
        .Y_WIDTH           (Y_WIDTH),
        .PREVIEW_FRAMES    (PREVIEW_FRAMES),
        .TRAVEL_Y          (TRAVEL_Y),
        .HIT_WINDOW_FRAMES (HIT_WINDOW_FRAMES)
    ) dut (
        .clk                   (clk),
        .rst_n                 (rst_n),
        .frame_start           (frame_start),
        .score_valid           (score_valid),
        .score_ready           (score_ready),
        .score_note_id         (score_note_id),
        .score_note_number     (score_note_number),
        .score_hit_frame       (score_hit_frame),
        .score_duration_valid  (score_duration_valid),
        .score_duration_frames (score_duration_frames),
        .score_velocity        (score_velocity),
        .performance_fire      (performance_fire),
        .performance_data      (performance_data),
        .video_desync          (video_desync),
        .current_frame         (current_frame),
        .slot_valid            (slot_valid),
        .slot_note_id          (slot_note_id),
        .slot_note_number      (slot_note_number),
        .slot_y                (slot_y),
        .slot_velocity         (slot_velocity),
        .slot_hit              (slot_hit),
        .slot_miss             (slot_miss)
    );

    initial begin
        clk = 1'b0;
        forever #(CLK_PERIOD_NS / 2) clk = ~clk;
    end

    task automatic check_value(
        input logic condition,
        input string description
    );
        begin
            check_count = check_count + 1;
            if (!condition) begin
                error_count = error_count + 1;
                $display("ERROR: %s, frame=%0d time=%0t",
                         description, current_frame, $time);
            end
        end
    endtask

    task automatic apply_reset;
        begin
            @(negedge clk);
            rst_n           = 1'b0;
            frame_start     = 1'b0;
            score_valid     = 1'b0;
            performance_fire = 1'b0;
            video_desync    = 1'b0;
            repeat (3) @(negedge clk);
            check_value(current_frame == 0, "reset must clear current_frame");
            check_value(slot_valid == '0, "reset must clear visible slots");
            check_value(slot_hit == '0, "reset must clear hit state");
            check_value(slot_miss == '0, "reset must clear miss state");
            rst_n = 1'b1;
            repeat (2) @(negedge clk);
        end
    endtask

    task automatic pulse_frame;
        begin
            @(negedge clk);
            frame_start = 1'b1;
            @(negedge clk);
            frame_start = 1'b0;
        end
    endtask

    task automatic advance_to(input integer target_frame);
        begin
            while (current_frame < target_frame) begin
                pulse_frame();
            end
            check_value(current_frame == target_frame,
                        "advance_to reached an unexpected frame");
        end
    endtask

    task automatic enqueue_score(
        input logic [15:0] note_id_value,
        input logic [6:0]  note_number_value,
        input integer      hit_frame_value,
        input logic        duration_valid_value,
        input integer      duration_frames_value,
        input logic [9:0]  velocity_value
    );
        begin
            while (!score_ready) @(negedge clk);
            @(negedge clk);
            score_note_id         = note_id_value;
            score_note_number     = note_number_value;
            score_hit_frame       = hit_frame_value;
            score_duration_valid  = duration_valid_value;
            score_duration_frames = duration_frames_value;
            score_velocity        = velocity_value;
            score_valid           = 1'b1;
            @(negedge clk);
            score_valid           = 1'b0;
        end
    endtask

    task automatic send_note_on(
        input logic [6:0] note_number_value,
        input logic [9:0] velocity_value
    );
        begin
            @(negedge clk);
            performance_data = make_note_event(
                1'b1, 4'd0, 4'd0, note_number_value, velocity_value
            );
            performance_fire = 1'b1;
            @(negedge clk);
            performance_fire = 1'b0;
            performance_data = '0;
        end
    endtask

    function automatic logic [15:0] note_id_at(input integer slot_index);
        note_id_at = slot_note_id[slot_index*16 +: 16];
    endfunction

    function automatic logic [6:0] note_number_at(input integer slot_index);
        note_number_at = slot_note_number[slot_index*7 +: 7];
    endfunction

    function automatic logic [Y_WIDTH-1:0] y_at(input integer slot_index);
        y_at = slot_y[slot_index*Y_WIDTH +: Y_WIDTH];
    endfunction

    initial begin
        integer slot_index;
        integer frame_before_desync;

        rst_n                 = 1'b0;
        frame_start           = 1'b0;
        score_valid           = 1'b0;
        score_note_id         = 16'd0;
        score_note_number     = 7'd0;
        score_hit_frame       = 32'd0;
        score_duration_valid  = 1'b0;
        score_duration_frames = 32'd0;
        score_velocity        = 10'd0;
        performance_fire      = 1'b0;
        performance_data      = '0;
        video_desync          = 1'b0;
        check_count           = 0;
        error_count           = 0;

        // [1] M1 single-note example converted to 60 fps.
        apply_reset();
        enqueue_score(16'd1, 7'd72, 300, 1'b0, 0, 10'd512);
        advance_to(179);
        check_value(slot_valid[0] == 1'b0,
                    "single note became visible before preview frame");
        advance_to(180);
        check_value(slot_valid[0] && note_id_at(0) == 16'd1,
                    "single note must appear at frame 180");
        check_value(note_number_at(0) == 7'd72 && y_at(0) == 400,
                    "single note frame 180 must be note 72 at y=400");
        check_value(slot_velocity[0 +: 10] == 10'd512,
                    "single note velocity was not retained");
        advance_to(240);
        check_value(y_at(0) == 200,
                    "single note frame 240 must be y=200");
        advance_to(300);
        check_value(y_at(0) == 0,
                    "single note frame 300 must reach y=0");

        // [2] Repeated pitch must retain distinct note IDs and schedules.
        apply_reset();
        enqueue_score(16'd11, 7'd60, 180, 1'b0, 0, 10'd300);
        enqueue_score(16'd12, 7'd60, 240, 1'b0, 0, 10'd600);
        advance_to(60);
        check_value(slot_valid[0] && !slot_valid[1],
                    "first repeated note preview boundary is wrong");
        advance_to(120);
        check_value(slot_valid[0] && slot_valid[1],
                    "second repeated note did not appear");
        check_value(note_id_at(0) == 16'd11 && note_id_at(1) == 16'd12,
                    "repeated pitch note IDs were not kept distinct");
        check_value(note_number_at(0) == 7'd60 &&
                    note_number_at(1) == 7'd60,
                    "repeated pitch note numbers changed");
        advance_to(180);
        check_value(y_at(0) == 0 && y_at(1) == 200,
                    "repeated pitch positions are incorrect at frame 180");
        send_note_on(7'd60, 10'd300);
        check_value(slot_hit[0] && !slot_hit[1],
                    "repeated pitch match did not select the nearest slot");

        // [3] Three-note chord occupies independent simultaneous slots.
        apply_reset();
        enqueue_score(16'd21, 7'd60, 180, 1'b0, 0, 10'd500);
        enqueue_score(16'd22, 7'd64, 180, 1'b0, 0, 10'd501);
        enqueue_score(16'd23, 7'd67, 180, 1'b0, 0, 10'd502);
        advance_to(60);
        check_value(slot_valid[2:0] == 3'b111,
                    "all chord notes must appear together");
        check_value(y_at(0) == 400 && y_at(1) == 400 && y_at(2) == 400,
                    "chord preview positions are incorrect");
        advance_to(180);
        check_value(y_at(0) == 0 && y_at(1) == 0 && y_at(2) == 0,
                    "all chord notes must arrive together");

        // [4] A duration slot remains through hit+duration, then releases.
        apply_reset();
        enqueue_score(16'd31, 7'd65, 130, 1'b1, 20, 10'd700);
        advance_to(130);
        send_note_on(7'd65, 10'd700);
        check_value(slot_hit[0] && !slot_miss[0],
                    "duration note was not marked hit");
        advance_to(150);
        check_value(slot_valid[0] && slot_hit[0] && y_at(0) == 0,
                    "duration note must remain through its end frame");
        advance_to(151);
        check_value(!slot_valid[0] && score_ready,
                    "duration note was not released after its end frame");

        // [5] Inclusive early and late hit-window boundaries.
        apply_reset();
        enqueue_score(16'd41, 7'd60, 100, 1'b0, 0, 10'd400);
        enqueue_score(16'd42, 7'd62, 100, 1'b0, 0, 10'd500);
        advance_to(94);
        send_note_on(7'd60, 10'd400);
        check_value(slot_hit[0] && !slot_miss[0],
                    "-HIT_WINDOW_FRAMES boundary must hit");
        advance_to(106);
        send_note_on(7'd62, 10'd500);
        check_value(slot_hit[1] && !slot_miss[1],
                    "+HIT_WINDOW_FRAMES boundary must hit");

        // [6] The first frame beyond the window reports Miss, then releases.
        apply_reset();
        enqueue_score(16'd51, 7'd69, 100, 1'b0, 0, 10'd512);
        advance_to(106);
        check_value(!slot_miss[0],
                    "inclusive deadline must not be marked miss");
        advance_to(107);
        send_note_on(7'd69, 10'd512);
        check_value(slot_valid[0] && slot_miss[0] && !slot_hit[0],
                    "out-of-window Note On must remain a miss");
        advance_to(108);
        check_value(!slot_valid[0],
                    "undurationed miss slot must release after reporting");

        // [7] Runtime reset clears a populated, judged tracker.
        apply_reset();
        enqueue_score(16'd61, 7'd72, 20, 1'b1, 20, 10'd900);
        advance_to(20);
        send_note_on(7'd72, 10'd900);
        check_value(slot_valid[0] && slot_hit[0],
                    "reset precondition did not create a hit slot");
        @(negedge clk);
        rst_n = 1'b0;
        repeat (2) @(negedge clk);
        check_value(current_frame == 0 && slot_valid == '0,
                    "runtime reset did not clear timeline and slots");
        check_value(slot_hit == '0 && slot_miss == '0,
                    "runtime reset did not clear judgement state");
        rst_n = 1'b1;
        repeat (2) @(negedge clk);

        // [8] video_desync flushes slots without rewinding absolute time.
        enqueue_score(16'd71, 7'd60, 30, 1'b1, 20, 10'd600);
        advance_to(10);
        frame_before_desync = current_frame;
        @(negedge clk);
        video_desync = 1'b1;
        @(negedge clk);
        video_desync = 1'b0;
        check_value(current_frame == frame_before_desync,
                    "video_desync must not rewind current_frame");
        check_value(slot_valid == '0 && slot_hit == '0 && slot_miss == '0,
                    "video_desync did not clear all slot state");
        check_value(score_ready,
                    "video_desync did not free score capacity");

        // [9] All eight stored future notes deassert score_ready.
        apply_reset();
        for (slot_index = 0; slot_index < SLOT_COUNT;
             slot_index = slot_index + 1) begin
            enqueue_score(16'd100 + slot_index,
                          7'd40 + slot_index,
                          500,
                          1'b1,
                          50,
                          10'd200 + slot_index);
        end
        check_value(!score_ready,
                    "score_ready must deassert when every slot is occupied");
        advance_to(380);
        check_value(slot_valid == {SLOT_COUNT{1'b1}},
                    "all full-queue notes must become visible at preview frame");
        check_value(!score_ready,
                    "visibility must not create extra score capacity");

        if (error_count == 0) begin
            $display("PASS: tb_visual_score_tracker completed %0d checks",
                     check_count);
        end else begin
            $display("FAIL: tb_visual_score_tracker found %0d error(s)",
                     error_count);
            $fatal(1);
        end
        $finish;
    end

    initial begin
        #(CLK_PERIOD_NS * 20000);
        $display("FAIL: tb_visual_score_tracker timeout");
        $fatal(1);
    end

endmodule
