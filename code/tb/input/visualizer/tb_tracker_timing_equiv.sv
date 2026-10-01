// Direct comparison against frozen M3 tracker source. Simulation only;
// hierarchy deposits exercise 32-bit rollover without billions of clocks.
`timescale 1ns/1ps
module tb_tracker_timing_equiv #(
    parameter integer SLOTS=8, FW=32, YW=10, PREVIEW=120, TRAVEL=400, WINDOW=6
);
    import audio_defs_pkg::*;
    logic clk=0; always #5 clk=~clk;
    logic rst_n=0, frame_start=0, score_valid=0;
    logic [15:0] score_note_id=0;
    logic [6:0] score_note_number=0;
    logic [FW-1:0] score_hit_frame=0, score_duration_frames=0;
    logic score_duration_valid=0;
    logic [9:0] score_velocity=0;
    logic performance_fire=0,video_desync=0;
    performance_event_t performance_data='0;
    wire score_ready,r_score_ready;
    wire [FW-1:0] current_frame,r_current_frame;
    wire [SLOTS-1:0] slot_valid,r_slot_valid,slot_hit,r_slot_hit,slot_miss,r_slot_miss;
    wire [SLOTS*16-1:0] slot_note_id,r_slot_note_id;
    wire [SLOTS*7-1:0] slot_note_number,r_slot_note_number;
    wire [SLOTS*YW-1:0] slot_y,r_slot_y;
    wire [SLOTS*10-1:0] slot_velocity,r_slot_velocity;
    integer checks=0, functions=0, searches=0;
    integer seed=32'h172034;
    visual_score_tracker #(.SLOT_COUNT(SLOTS),.FRAME_WIDTH(FW),.Y_WIDTH(YW),.PREVIEW_FRAMES(PREVIEW),.TRAVEL_Y(TRAVEL),.HIT_WINDOW_FRAMES(WINDOW)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .frame_start(frame_start),
        .score_valid(score_valid),
        .score_ready(score_ready),
        .score_note_id(score_note_id),
        .score_note_number(score_note_number),
        .score_hit_frame(score_hit_frame),
        .score_duration_valid(score_duration_valid),
        .score_duration_frames(score_duration_frames),
        .score_velocity(score_velocity),
        .performance_fire(performance_fire),
        .performance_data(performance_data),
        .video_desync(video_desync),
        .current_frame(current_frame),
        .slot_valid(slot_valid),
        .slot_note_id(slot_note_id),
        .slot_note_number(slot_note_number),
        .slot_y(slot_y),
        .slot_velocity(slot_velocity),
        .slot_hit(slot_hit),
        .slot_miss(slot_miss)
    );
    visual_score_tracker_reference #(.SLOT_COUNT(SLOTS),.FRAME_WIDTH(FW),.Y_WIDTH(YW),.PREVIEW_FRAMES(PREVIEW),.TRAVEL_Y(TRAVEL),.HIT_WINDOW_FRAMES(WINDOW)) ref_dut (
        .clk(clk),
        .rst_n(rst_n),
        .frame_start(frame_start),
        .score_valid(score_valid),
        .score_ready(r_score_ready),
        .score_note_id(score_note_id),
        .score_note_number(score_note_number),
        .score_hit_frame(score_hit_frame),
        .score_duration_valid(score_duration_valid),
        .score_duration_frames(score_duration_frames),
        .score_velocity(score_velocity),
        .performance_fire(performance_fire),
        .performance_data(performance_data),
        .video_desync(video_desync),
        .current_frame(r_current_frame),
        .slot_valid(r_slot_valid),
        .slot_note_id(r_slot_note_id),
        .slot_note_number(r_slot_note_number),
        .slot_y(r_slot_y),
        .slot_velocity(r_slot_velocity),
        .slot_hit(r_slot_hit),
        .slot_miss(r_slot_miss)
    );

    task automatic compare_all;
        begin
            #1;
            if ({score_ready,current_frame,slot_valid,slot_note_id,slot_note_number,
                 slot_y,slot_velocity,slot_hit,slot_miss} !==
                {r_score_ready,r_current_frame,r_slot_valid,r_slot_note_id,r_slot_note_number,
                 r_slot_y,r_slot_velocity,r_slot_hit,r_slot_miss})
                $fatal(1,"output mismatch frame=%h SLOTS=%0d FW=%0d",current_frame,SLOTS,FW);
            if ({dut.match_valid,dut.match_error,dut.match_slot_index} !==
                {ref_dut.match_valid,ref_dut.match_error,ref_dut.match_slot_index})
                $fatal(1,"nearest search differs index %0d/%0d error %h/%h",
                       dut.match_slot_index,ref_dut.match_slot_index,dut.match_error,ref_dut.match_error);
            for(integer slot=0;slot<SLOTS;slot=slot+1) begin
                if ({dut.slot_used_mem[slot],dut.hit_frame_mem[slot],dut.judged_mem[slot],
                     dut.hit_mem[slot],dut.miss_mem[slot],dut.duration_valid_mem[slot],
                     dut.duration_frames_mem[slot],dut.note_id_mem[slot],
                     dut.note_number_mem[slot],dut.velocity_mem[slot]} !==
                    {ref_dut.slot_used_mem[slot],ref_dut.hit_frame_mem[slot],ref_dut.judged_mem[slot],
                     ref_dut.hit_mem[slot],ref_dut.miss_mem[slot],ref_dut.duration_valid_mem[slot],
                     ref_dut.duration_frames_mem[slot],ref_dut.note_id_mem[slot],
                     ref_dut.note_number_mem[slot],ref_dut.velocity_mem[slot]})
                    $fatal(1,"stored state mismatch slot=%0d",slot);
            end
            checks=checks+1;
        end
    endtask
    task automatic compare_distance(input logic [FW-1:0] f,h);
        begin
            if(dut.calculate_y(f,h)!==ref_dut.calculate_y(f,h))
                $fatal(1,"distance mismatch f=%h h=%h preview=%0d travel=%0d",f,h,PREVIEW,TRAVEL);
            functions=functions+1;
        end
    endtask
    task automatic reset_all;
        begin
            @(negedge clk);rst_n=0;frame_start=0;score_valid=0;
            performance_fire=0;video_desync=0;compare_all();
            @(negedge clk);rst_n=1;compare_all();
        end
    endtask
    // Test-only deposits into both old/new memories. The clock still exercises
    // sequential next-state updates, including full frame wrap and reset.
    task automatic deposit_slot(input integer slot,input bit used,judged,
                                 input logic [6:0] note,input logic [FW-1:0] hit_frame);
        begin
            dut.slot_used_mem[slot]=used;ref_dut.slot_used_mem[slot]=used;
            dut.judged_mem[slot]=judged;ref_dut.judged_mem[slot]=judged;
            dut.note_number_mem[slot]=note;ref_dut.note_number_mem[slot]=note;
            dut.hit_frame_mem[slot]=hit_frame;ref_dut.hit_frame_mem[slot]=hit_frame;
        end
    endtask
    initial begin
        reset_all();
        // Every value near the default bounded arithmetic range, then random
        // full-width timestamps and saturated/boundary differences.
        for(integer r=0;r<512;r=r+1) begin
            compare_distance(FW'(0),FW'(r));
            compare_distance(FW'(32'hffff0000),FW'(32'hffff0000+r));
            compare_distance(FW'(r),FW'(0));
        end
        for(integer trial=0;trial<20000;trial=trial+1) begin
            compare_distance(FW'($random(seed)),FW'($random(seed)));
            compare_distance(FW'(0),FW'(PREVIEW+trial%3-1));
            compare_distance(FW'(trial),FW'(trial+PREVIEW-1));
        end
        // Complete occupancy masks, equal-distance ties and different pitches.
        for(integer mask=0;mask<(1<<SLOTS);mask=mask+1) begin
            @(negedge clk);frame_start=0;score_valid=0;performance_fire=1;
            performance_data.event_type=EVENT_NOTE_ON;performance_data.note_number=60;
            dut.current_frame=FW'(100);ref_dut.current_frame=FW'(100);
            for(integer slot=0;slot<SLOTS;slot=slot+1)
                deposit_slot(slot,1'(mask>>slot),0,60,FW'(slot%2 ? 102 : 98));
            compare_all();searches=searches+1;
            // nearest tie must select the lowest eligible slot
            for(integer slot=0;slot<SLOTS;slot=slot+1)
                deposit_slot(slot,1'(mask>>slot),slot%2==0,7'(60+slot%3),FW'(96+slot));
            compare_all();searches=searches+1;
            @(posedge clk);compare_all();
        end
        // A valid leaf at maximal error must win over invalid padded leaves.
        @(negedge clk);frame_start=0;performance_fire=1;
        dut.current_frame='0;ref_dut.current_frame='0;
        for(integer slot=0;slot<SLOTS;slot=slot+1)
            deposit_slot(slot,slot==SLOTS-1,0,60,{FW{1'b1}});
        compare_all();searches=searches+1;
        if(!dut.match_valid || dut.match_slot_index!=SLOTS-1 || dut.match_error!={FW{1'b1}})
            $fatal(1,"maximal-error eligible leaf lost");
        // Boundary window and same-clock frame_start: old/new see effective +1.
        for(integer offset=-WINDOW-1;offset<=WINDOW+1;offset=offset+1) begin
            @(negedge clk);dut.current_frame=FW'(100);ref_dut.current_frame=FW'(100);
            frame_start=1;
            for(integer slot=0;slot<SLOTS;slot=slot+1)
                deposit_slot(slot,slot==0,0,60,FW'(101+offset));
            compare_all();@(posedge clk);compare_all();
        end
        // Unsigned frame rollover and duration overflow must retain old rules.
        @(negedge clk);dut.current_frame='1;ref_dut.current_frame='1;frame_start=1;
        compare_all();@(posedge clk);compare_all();
        reset_all();
        // Real input-only sequential traffic compares both visible and hidden
        // state before/after every edge, stalls, resets and desync included.
        for(integer cycle=0;cycle<20000;cycle=cycle+1) begin
            @(negedge clk);
            rst_n=(cycle%503!=0);frame_start=(cycle%2==0);
            score_valid=($unsigned($random(seed))%5<2);
            score_note_id=16'($random(seed));score_note_number=7'(60+cycle%3);
            case(cycle%5)
                0:score_hit_frame=current_frame+FW'(PREVIEW+10);
                1:score_hit_frame=current_frame+FW'(WINDOW);
                2:score_hit_frame=current_frame-FW'(WINDOW+1);
                3:score_hit_frame={FW{1'b1}};
                default:score_hit_frame=current_frame;
            endcase
            score_duration_valid=1'($random(seed));
            score_duration_frames=FW'($unsigned($random(seed))%30);
            score_velocity=10'($random(seed));
            performance_fire=($unsigned($random(seed))%3==0);
            performance_data.event_type=(cycle%7==0) ? EVENT_NOTE_OFF : EVENT_NOTE_ON;
            performance_data.note_number=7'(60+cycle%3);
            video_desync=(cycle%211==0);
            compare_all();@(posedge clk);compare_all();
        end
        reset_all();
        $display("PASS tracker equivalence SLOTS=%0d FW=%0d PREVIEW/TRAVEL=%0d/%0d: %0d state checks, %0d distances, %0d searches",SLOTS,FW,PREVIEW,TRAVEL,checks,functions,searches);
        $finish;
    end
    initial begin #10_000_000; $fatal(1,"tracker equivalence timeout");end
endmodule
