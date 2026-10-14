`timescale 1ns/1ps
module tb_m2_score_playback_candidate;
    reg clk=0,rst_n=0,frame_tick=0,committed_valid=0,commit_pulse=0;
    reg [9:0] committed_count=0;
    reg [31:0] committed_score_id=0;
    wire rd_req;wire [8:0] rd_index;
    reg rd_valid=0;
    reg [63:0] rd_event=0;
    reg base_valid=0,event_ready=1;
    wire base_ready,event_valid;
    reg [63:0] base_data=0;
    wire [63:0] event_data;
    wire [9:0] consumed_events;
    wire [31:0] late_events,active_score_id;
    wire fault;
    reg bank=0;
    reg [63:0] bank0[0:2],bank1[0:1];
    always #12.5 clk=~clk; // 40 MHz, input frame_tick is a clock enable.
    function automatic [63:0] record(input [31:0] tick,input [7:0] kind,ch,note,vel);
        record={vel,note,ch,kind,tick};
    endfunction
    m2_score_playback_candidate dut(.*);
    // A synchronous one-cycle public read port, matching T062 port-A timing.
    always @(posedge clk)begin
        rd_valid<=rd_req;
        if(rd_req)begin
`ifdef MUTANT_STALE_BANK
            rd_event<=bank0[rd_index];
`else
            rd_event<=bank ? bank1[rd_index] : bank0[rd_index];
`endif
        end
    end
    audio_defs_pkg::performance_event_t decoded;
    assign decoded=event_data;
    integer accepted=0,base_count=0,panic_count=0,notes=0,offs=0,old_after_switch=0;
    integer release_cycle=0;
    reg switched=0;
    always @(posedge clk)if(rst_n && event_valid && event_ready)begin
        accepted=accepted+1;
        if(decoded.source_id==0)base_count=base_count+1;
        if(decoded.source_id==2)begin
            if(decoded.event_type==audio_defs_pkg::EVENT_ALL_NOTES_OFF)panic_count=panic_count+1;
            if(decoded.event_type==audio_defs_pkg::EVENT_NOTE_ON)begin
                notes=notes+1;
                if(switched && decoded.note_number!=7'd67)$fatal(1,"SCORE_STALE_BANK_OR_ID");
            end
            if(decoded.event_type==audio_defs_pkg::EVENT_NOTE_OFF)begin
                offs=offs+1;
                if(switched && decoded.note_number!=7'd67)$fatal(1,"SCORE_OLD_GENERATION_DELIVERED");
            end
        end
    end
    task automatic pulse_frame;
        begin @(negedge clk);frame_tick=1;@(negedge clk);frame_tick=0;end
    endtask
    initial begin
        bank0[0]=record(0,0,0,60,100);
        bank0[1]=record(0,0,0,64,90);
        bank0[2]=record(2,1,0,60,0);
        bank1[0]=record(0,0,0,67,80);
        bank1[1]=record(2,1,0,67,0);
        base_data=audio_defs_pkg::make_note_event(1'b1,4'd0,4'd1,7'd69,10'd500);
        repeat(4)@(negedge clk);rst_n=1;
        // First COMMIT starts private score playback; real MIDI wins immediately.
        @(negedge clk);committed_count=3;committed_score_id=32'd1;
        committed_valid=1;commit_pulse=1;
        @(negedge clk);commit_pulse=0;base_valid=1;
        @(negedge clk);base_valid=0;
        if(base_count!=1 || panic_count!=0 || consumed_events!=0)
            $fatal(1,"BASE_PRIORITY_OVER_SCORE_PANIC");
        wait(panic_count==1);
        wait(event_valid && decoded.event_type==audio_defs_pkg::EVENT_NOTE_ON && decoded.note_number==7'd60);
        @(negedge clk);event_ready=0;
        repeat(3)begin @(negedge clk);
            if(!event_valid || decoded.note_number!=7'd60 || consumed_events!=0)
                $fatal(1,"SCORE_HELD_EVENT_NOT_STABLE");
        end
        event_ready=1;
        wait(consumed_events==2);
        // The old bank's final tick=2 NoteOff is in flight but not due.
        wait(rd_req);@(posedge clk);@(negedge clk);
        if(!rd_valid)$fatal(1,"OLD_READ_NOT_IN_FLIGHT");
        bank=1;committed_count=2;committed_score_id=32'd2;
        commit_pulse=1;switched=1;
        @(negedge clk);commit_pulse=0;
        wait(panic_count==2);
        wait(consumed_events==1);
        pulse_frame();repeat(2)@(negedge clk);
        if(offs!=0)$fatal(1,"SCORE_TICK2_EARLY_AFTER_ONE_FRAME");
        pulse_frame();wait(consumed_events==2);
        repeat(2)@(negedge clk);
        if(fault || active_score_id!=2 || base_count!=1 || panic_count!=2 || notes!=3 || offs!=1 ||
           accepted!=7 || late_events!=0 || rd_req)
            $fatal(1,"SCORE_PLAYBACK_COUNTS_OR_RESET");
        bank0[0]=record(0,2,0,60,70); // Invalid kind: fail closed if RAM bytes drift.
        @(negedge clk);bank=0;committed_count=1;committed_score_id=32'd3;commit_pulse=1;
        @(negedge clk);commit_pulse=0;
        wait(fault);wait(panic_count==4);
        if(consumed_events!=0 || active_score_id!=3 || notes!=3 || offs!=1)
            $fatal(1,"SCORE_BAD_RAM_RECORD_WAS_PLAYED");
        rst_n=0;committed_valid=0;
        repeat(2)@(negedge clk);
        if(fault || consumed_events || event_valid || rd_req)
            $fatal(1,"SCORE_RESET_NOT_CLEAN");
        $display("END base=%0d panic=%0d notes=%0d off=%0d good_score2=2 bad_score3=0",
                 base_count,panic_count,notes,offs);
        $display("PASS M2_SCORE_RAM_EVENT_PRIORITY_ISOLATED");$finish;
    end
    initial begin #200us;$fatal(1,"SCORE_PLAYBACK_TB_TIMEOUT");end
endmodule