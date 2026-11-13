`timescale 1ns/1ps
module tb_r12_falling_repeat_gap;
    import audio_defs_pkg::*;
    localparam integer SLOTS = 8;
    logic clk = 0;
    always #5 clk = !clk;
    logic rst_n = 0, frame_start = 0, score_valid = 0, video_desync = 0;
    logic [15:0] note_id;
    logic [6:0] note_number;
    logic [31:0] hit_frame, duration;
    wire score_ready;
    wire [31:0] current_frame;
    wire [SLOTS-1:0] valid;
    wire [SLOTS*16-1:0] ids;
    wire [SLOTS*10-1:0] top_y, end_y;
    performance_event_t no_performance = '0;

    pro_visual_score_tracker #(.SLOT_COUNT(SLOTS), .PREVIEW_FRAMES(120),
        .TRAVEL_Y(480), .BOTTOM_EXIT_GEOMETRY(1), .STRICT_CONTACT(1)) dut (
        .clk(clk), .rst_n(rst_n), .frame_start(frame_start),
        .score_valid(score_valid), .score_ready(score_ready),
        .score_note_id(note_id), .score_note_number(note_number),
        .score_hit_frame(hit_frame), .score_duration_valid(1'b1),
        .score_duration_frames(duration), .score_velocity(10'd400),
        .performance_fire(1'b0), .match_enabled(1'b0),
        .performance_data(no_performance), .video_desync(video_desync),
        .current_frame(current_frame), .slot_valid(valid), .slot_note_id(ids),
        .slot_note_number(), .slot_y(), .slot_top_y(top_y), .slot_end_y(end_y),
        .slot_velocity(), .slot_hit(), .slot_miss(), .hit_pulse(),
        .hit_note_number(), .duplicate_id_fault()
    );

    task automatic push(input logic [15:0] id, input logic [6:0] note,
                        input logic [31:0] onset, length);
        @(negedge clk);
        note_id = id; note_number = note; hit_frame = onset; duration = length;
        score_valid = 1;
        do @(posedge clk); while (!score_ready);
        @(negedge clk);
        score_valid = 0;
    endtask

    task automatic check_bar(input logic [15:0] id, input integer top_expected, front_expected);
        for (integer slot=0; slot<SLOTS; slot++) begin
            if (valid[slot] && ids[16*slot+:16] == id) begin
                if (top_y[10*slot+:10] !== 10'(top_expected) ||
                    end_y[10*slot+:10] !== 10'(front_expected))
                    $fatal(1, "id=%0d top/front=%0d/%0d expected=%0d/%0d", id,
                        top_y[10*slot+:10], end_y[10*slot+:10], top_expected, front_expected);
                return;
            end
        end
        $fatal(1, "missing note id=%0d", id);
    endtask

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        push(1, 60, 100, 30); // touches the next start at frame 130
        push(2, 60, 100, 60); // simultaneous other track, overlaps next start
        push(3, 62, 100, 30); // different pitch stays full length
        push(4, 64, 100, 10); // a natural gap is already available
        push(5, 67, 110,  1); // shortest representable distinct onset gap
        push(6, 67, 111,  3);
        push(7, 60, 130, 30);
        push(8, 64, 130, 15);
        repeat (20) begin
            @(negedge clk); frame_start = 1;
            @(negedge clk); frame_start = 0;
            repeat (SLOTS+2) @(negedge clk);
        end
        if (current_frame !== 32'd20) $fatal(1, "frame anchor");
        check_bar(1,  44, 160);
        check_bar(2,  44, 160);
        check_bar(3,  40, 160);
        check_bar(4, 120, 160);
        check_bar(5, 119, 120);
        check_bar(6, 104, 116);
        check_bar(7,   0,  40);
        check_bar(8,   0,  40);
        $display("PASS R12_FALLING_REPEAT_GAP touching overlap natural short same_frame");
        $finish;
    end

    initial begin #10000; $fatal(1, "timeout"); end
endmodule
