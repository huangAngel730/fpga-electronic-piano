`timescale 1ns/1ps

module tb_visual_live_state;
    import audio_defs_pkg::*;

    localparam integer SLOT_COUNT = 3;
    localparam integer Y_WIDTH = 6;
    localparam integer JUDGE_Y = 20;
    localparam integer RISE_STEP = 4;

    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic frame_start = 1'b0;
    logic performance_fire = 1'b0;
    performance_event_t performance_data = '0;
    logic video_desync = 1'b0;

    logic [127:0] key_down;
    logic [SLOT_COUNT-1:0] live_valid;
    logic [SLOT_COUNT*7-1:0] live_note_number;
    logic [SLOT_COUNT*Y_WIDTH-1:0] live_y;
    logic [SLOT_COUNT*10-1:0] live_velocity;
    logic desync_latched;

    integer checks = 0;
    integer slot_index;

    visual_live_state #(
        .SLOT_COUNT(SLOT_COUNT),
        .Y_WIDTH(Y_WIDTH),
        .JUDGE_Y(JUDGE_Y),
        .RISE_STEP(RISE_STEP)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .frame_start(frame_start),
        .performance_fire(performance_fire),
        .performance_data(performance_data),
        .video_desync(video_desync),
        .key_down(key_down),
        .live_valid(live_valid),
        .live_note_number(live_note_number),
        .live_y(live_y),
        .live_velocity(live_velocity),
        .desync_latched(desync_latched)
    );

    always #5 clk = ~clk;

    function automatic [6:0] slot_note(input integer index);
        slot_note = live_note_number[index*7 +: 7];
    endfunction

    function automatic [Y_WIDTH-1:0] slot_y(input integer index);
        slot_y = live_y[index*Y_WIDTH +: Y_WIDTH];
    endfunction

    function automatic [9:0] slot_velocity(input integer index);
        slot_velocity = live_velocity[index*10 +: 10];
    endfunction

    function automatic integer live_count;
        integer count_index;
        begin
            live_count = 0;
            for (count_index = 0; count_index < SLOT_COUNT;
                 count_index = count_index + 1)
                live_count = live_count + live_valid[count_index];
        end
    endfunction

    function automatic logic slot_contains(input [6:0] note_number);
        integer find_index;
        begin
            slot_contains = 1'b0;
            for (find_index = 0; find_index < SLOT_COUNT;
                 find_index = find_index + 1)
                if (live_valid[find_index] &&
                    slot_note(find_index) == note_number)
                    slot_contains = 1'b1;
        end
    endfunction

    task automatic check(input logic condition, input string message);
        begin
            checks = checks + 1;
            if (condition !== 1'b1)
                $fatal(1, "FAIL check %0d: %s", checks, message);
        end
    endtask

    task automatic reset_dut;
        begin
            @(negedge clk);
            rst_n = 1'b0;
            frame_start = 1'b0;
            performance_fire = 1'b0;
            performance_data = '0;
            video_desync = 1'b0;
            repeat (2) @(negedge clk);
            rst_n = 1'b1;
            repeat (2) @(negedge clk);
            #1;
        end
    endtask

    task automatic send_event(
        input logic [2:0] event_type,
        input logic [6:0] note_number,
        input logic [9:0] velocity
    );
        begin
            @(negedge clk);
            performance_data = '0;
            performance_data.event_type = event_type;
            performance_data.note_number = note_number;
            performance_data.velocity = velocity;
            performance_fire = 1'b1;
            @(negedge clk);
            performance_fire = 1'b0;
            performance_data = '0;
            #1;
        end
    endtask

    task automatic pulse_frame;
        begin
            @(negedge clk);
            frame_start = 1'b1;
            @(negedge clk);
            frame_start = 1'b0;
            #1;
        end
    endtask

    task automatic send_event_with_frame(
        input logic [2:0] event_type,
        input logic [6:0] note_number,
        input logic [9:0] velocity
    );
        begin
            @(negedge clk);
            performance_data = '0;
            performance_data.event_type = event_type;
            performance_data.note_number = note_number;
            performance_data.velocity = velocity;
            performance_fire = 1'b1;
            frame_start = 1'b1;
            @(negedge clk);
            performance_fire = 1'b0;
            frame_start = 1'b0;
            performance_data = '0;
            #1;
        end
    endtask

    task automatic pulse_desync;
        begin
            @(negedge clk);
            video_desync = 1'b1;
            @(negedge clk);
            video_desync = 1'b0;
            #1;
        end
    endtask

    initial begin
        reset_dut();
        check(key_down == '0, "reset clears published key state");
        check(live_valid == '0, "reset clears published slots");
        check(!desync_latched, "reset clears desync latch");

        // Note On is collected immediately but published only at frame_start.
        send_event(EVENT_NOTE_ON, 7'd60, 10'd512);
        check(!key_down[60] && live_valid == '0,
              "Note On must not tear the current frame");
        pulse_frame();
        check(key_down[60], "Note On sets key on next frame");
        check(live_count() == 1, "Note On creates one live slot");
        check(slot_note(0) == 7'd60, "slot stores Note On number");
        check(slot_y(0) == JUDGE_Y, "new slot starts at judge line");
        check(slot_velocity(0) == 10'd512, "slot stores velocity");

        send_event(EVENT_NOTE_OFF, 7'd60, 10'd0);
        check(key_down[60], "Note Off remains private within current frame");
        pulse_frame();
        check(!key_down[60], "Note Off clears key on next frame");

        // A zero-velocity Note On is a Note Off.
        reset_dut();
        send_event(EVENT_NOTE_ON, 7'd61, 10'd333);
        pulse_frame();
        check(key_down[61], "nonzero Note On sets key");
        send_event(EVENT_NOTE_ON, 7'd61, 10'd0);
        check(key_down[61], "zero-velocity Note On is frame atomic");
        pulse_frame();
        check(!key_down[61], "zero-velocity Note On clears key");

        // All chord members received in one frame must survive.
        reset_dut();
        send_event(EVENT_NOTE_ON, 7'd60, 10'd400);
        send_event(EVENT_NOTE_ON, 7'd64, 10'd500);
        send_event(EVENT_NOTE_ON, 7'd67, 10'd600);
        check(key_down == '0 && live_valid == '0,
              "chord remains private before boundary");
        pulse_frame();
        check(key_down[60] && key_down[64] && key_down[67],
              "all chord keys are published");
        check(live_count() == 3, "all chord decorations are retained");

        // Repeated Note On events for one pitch create distinct decorations.
        reset_dut();
        send_event(EVENT_NOTE_ON, 7'd72, 10'd200);
        send_event(EVENT_NOTE_ON, 7'd72, 10'd800);
        pulse_frame();
        check(key_down[72], "repeated pitch remains down");
        check(live_count() == 2, "repeated pitch creates two slots");
        check(slot_note(0) == 7'd72 && slot_note(1) == 7'd72,
              "repeated slots preserve pitch");
        check(slot_velocity(0) == 10'd200 &&
              slot_velocity(1) == 10'd800,
              "repeated slots preserve independent velocities");

        // Slot exhaustion may discard decoration, never musical key state.
        reset_dut();
        send_event(EVENT_NOTE_ON, 7'd50, 10'd100);
        send_event(EVENT_NOTE_ON, 7'd51, 10'd200);
        send_event(EVENT_NOTE_ON, 7'd52, 10'd300);
        send_event(EVENT_NOTE_ON, 7'd99, 10'd900);
        pulse_frame();
        check(key_down[50] && key_down[51] && key_down[52] && key_down[99],
              "slot-full path still publishes every key");
        check(live_count() == SLOT_COUNT, "slot count remains bounded");
        check(!slot_contains(7'd99), "only full-slot decoration is dropped");

        send_event(EVENT_ALL_NOTES_OFF, 7'd0, 10'd0);
        check(key_down != '0, "All Notes Off waits for frame boundary");
        pulse_frame();
        check(key_down == '0, "All Notes Off clears every key");

        // Animation moves exactly once per frame and releases at the top.
        reset_dut();
        send_event(EVENT_NOTE_ON, 7'd40, 10'd700);
        pulse_frame();
        check(slot_y(0) == 20, "first visible frame uses JUDGE_Y");
        repeat (6) @(posedge clk);
        #1;
        check(slot_y(0) == 20, "ordinary clocks do not move animation");
        pulse_frame();
        check(slot_y(0) == 16, "second frame moves exactly one step");
        pulse_frame();
        check(slot_y(0) == 12, "third frame moves exactly one step");
        pulse_frame();
        check(slot_y(0) == 8, "fourth frame moves exactly one step");
        pulse_frame();
        check(slot_y(0) == 4, "last visible step reaches top region");
        pulse_frame();
        check(live_valid == '0, "slot is released after reaching top");

        // An event coincident with frame_start belongs to the next frame.
        reset_dut();
        send_event_with_frame(EVENT_NOTE_ON, 7'd80, 10'd444);
        check(!key_down[80] && live_valid == '0,
              "boundary event cannot alter the frame being opened");
        pulse_frame();
        check(key_down[80] && live_count() == 1,
              "boundary event appears on following frame");

        // Desync is applied atomically, sticky, and blocks future state.
        pulse_desync();
        check(!desync_latched && key_down[80],
              "desync waits for frame boundary");
        send_event(EVENT_NOTE_ON, 7'd81, 10'd555);
        pulse_frame();
        check(desync_latched, "desync latches at frame boundary");
        check(key_down == '0 && live_valid == '0,
              "desync clears keys and decorations");
        send_event(EVENT_NOTE_ON, 7'd82, 10'd666);
        pulse_frame();
        check(key_down == '0 && live_valid == '0,
              "latched desync ignores later performance events");

        reset_dut();
        check(!desync_latched && key_down == '0 && live_valid == '0,
              "reset is the only desync recovery");
        pulse_frame();
        check(key_down == '0 && live_valid == '0,
              "reset does not replay stale events");

        $display("PASS: tb_visual_live_state completed %0d checks", checks);
        $finish;
    end

    initial begin
        #200000;
        $fatal(1, "FAIL: tb_visual_live_state timeout");
    end

endmodule
