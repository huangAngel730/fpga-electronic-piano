`timescale 1ns/1ps
module tb_polyphonic_event_router;
    import audio_defs_pkg::*;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,sample_owner_ready=1,event_valid=0;
    logic [63:0] event_data=0;logic [3:0] release_done=0;
    wire event_ready,dispatch_busy;wire [3:0] slot_note_on,slot_note_off,slot_occupied,slot_releasing;
    wire [39:0] slot_velocity;wire [127:0] slot_fcw;wire [31:0] slot_notes,active_voice_count;
    wire [3:0] slot_timbre;
    polyphonic_event_router dut(.*);
    integer checks=0,on_count=0,off_count=0;
    task automatic check(input logic ok,input string label);
        checks++;if(ok!==1'b1)$fatal(1,"Router %s occupied=%b",label,slot_occupied);
    endtask
    always @(negedge clk) begin
        for(integer i=0;i<4;i++)begin
            if(slot_note_on[i])on_count++;
            if(slot_note_off[i])off_count++;
        end
    end
    task automatic send(input logic [2:0] kind,input logic [3:0] src,ch,input logic [6:0] note,input logic [9:0] vel);
        performance_event_t e;
        e='0;e.event_type=kind;e.source_id=src;e.channel=ch;e.note_number=note;e.velocity=vel;
        wait(event_ready);@(negedge clk);event_data=e;event_valid=1;
        @(negedge clk);event_valid=0;
        wait(event_ready);repeat(2)@(negedge clk);
    endtask
    initial begin
        repeat(3)@(negedge clk);check(active_voice_count==0,"reset clears");rst_n=1;
        for(integer i=0;i<4;i++)send(EVENT_NOTE_ON,0,0,60+i,1000-i);
        check(active_voice_count==4,"four identities allocated");check(on_count==4,"one pulse per accepted note");
        check(slot_notes==32'h3f3e3d3c,"each note preserved");
        check(slot_velocity[9:0]==1000 && slot_velocity[39:30]==997,"velocity goes to allocated slot");
        check(slot_fcw[31:0]!=0 && slot_fcw[127:96]>slot_fcw[31:0],"FCW goes to each slot");
        send(EVENT_NOTE_ON,0,0,60,5);check(active_voice_count==4 && slot_velocity[9:0]==5,"same identity retriggers original slot");
        send(EVENT_NOTE_OFF,1,0,60,0);check(off_count==0,"different source cannot release note");
        send(EVENT_NOTE_OFF,0,0,60,0);check(off_count==1 && active_voice_count==4,"release tail still occupied");
        send(EVENT_NOTE_ON,0,0,60,500);check(slot_velocity[9:0]==500 && active_voice_count==4,"release retrigger original slot");
        send(EVENT_NOTE_ON,1,0,60,700);check(slot_notes[15:8]==60 && slot_velocity[19:10]==700,"fifth identity steals oldest not newest");
        sample_owner_ready=0;repeat(3)@(negedge clk);check(!event_ready,"PCM owner can backpressure events");sample_owner_ready=1;
        send(EVENT_NOTE_ON,1,0,60,0);check(off_count==2,"zero velocity means off");
        send(EVENT_NOTE_ON,1,0,60,700);
        send(EVENT_ALL_NOTES_OFF,0,0,0,0);check(off_count==6,"global panic releases all sources");
        @(negedge clk);release_done=4'b1101;@(negedge clk);release_done=0;repeat(20)@(negedge clk);wait(event_ready);
        check(active_voice_count==1 && slot_occupied==4'b0010,"release complete is per slot");

        @(negedge clk);release_done=4'b0010;@(negedge clk);release_done=0;repeat(20)@(negedge clk);wait(event_ready);
        check(active_voice_count==0,"all release tails reclaimed");
        send(EVENT_NOTE_ON,0,0,69,900);
        @(negedge clk);release_done=4'b0001;@(negedge clk);release_done=0;
        check(active_voice_count==1,"done cannot clear held non-release note");
        send(EVENT_NOTE_OFF,0,1,69,0);check(active_voice_count==1 && off_count==6,"different channel cannot release");
        send(EVENT_PITCH_BEND,0,0,0,0);check(active_voice_count==1,"unimplemented control cannot corrupt allocation");
        @(negedge clk);sample_owner_ready=0;event_valid=1;
        repeat(5)@(negedge clk);check(!event_ready && !dispatch_busy && on_count==9,"held valid backpressured without consuming event");
        sample_owner_ready=1;@(negedge clk);event_valid=0;
        check(dispatch_busy && !event_ready,"accepted event dispatch blocks another handshake");
        wait(event_ready);repeat(2)@(negedge clk);
        check(on_count==9,"held control accepted once without spurious Note On");
        rst_n=0;repeat(3)@(negedge clk);check(!event_ready && slot_fcw==0,"reset discards routing state");
        $display("PASS polyphonic_event_router checks=%0d on=%0d off=%0d",checks,on_count,off_count);$finish;
    end
    initial begin #100000;$fatal(1,"Router timeout");end
endmodule