`timescale 1ns/1ps
module tb_sustain_audio_integration;
    import audio_defs_pkg::*;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,event_valid=0,frame_tick=0;
    logic [63:0] event_data=0;
    wire event_ready,pending_valid;
    wire signed [23:0] play_left,play_right;
    wire [31:0] active_voice_count,clip_count,audio_underrun,audio_frame_count,pcm_request_count,pcm_commit_count,max_processing_cycles;
    polyphonic_audio_core dut(.*);
    integer checks=0,frames=0,expected,sum,prod,w,e,trace=0;
    string trace_path;
    task automatic check(input logic ok,input string label);
        checks++;if(ok!==1'b1)$fatal(1,"Audio core %s frame=%0d",label,frames);
    endtask
    task automatic send(input logic [2:0] kind,input logic [6:0] note,input logic [9:0] vel);
        performance_event_t msg;
        wait(event_ready);@(negedge clk);msg='0;msg.event_type=kind;msg.note_number=note;msg.velocity=vel;event_data=msg;event_valid=1;
        @(negedge clk);event_valid=0;wait(event_ready);repeat(5)@(negedge clk);
    endtask
    task automatic frame;
        @(negedge clk);frame_tick=1;@(negedge clk);frame_tick=0;
        frames++;wait(pcm_commit_count==frames);repeat(3)@(negedge clk);
        sum=0;
        for(integer i=0;i<4;i++)begin
            w=$signed(dut.bank_waves[16*i+:16]);e=dut.bank_envelopes[16*i+:16];prod=w*e;
            expected=(prod>=0 ? prod/32768 : -((-prod+32767)/32768))*256;
            if(dut.bank_occupied[i])sum=sum+expected;
        end
        if(sum>8388607)sum=8388607;if(sum< -8388608)sum=-8388608;
        check(play_left===sum && play_right===sum,"real waves/envelopes -> floor gain -> mix -> pending PCM exact");
        if(trace)$fdisplay(trace,"S %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
            dut.bank_envelopes[15:0],dut.bank_envelopes[31:16],dut.bank_envelopes[47:32],dut.bank_envelopes[63:48],
            $signed(dut.bank_waves[15:0]),$signed(dut.bank_waves[31:16]),$signed(dut.bank_waves[47:32]),$signed(dut.bank_waves[63:48]),play_left,play_right);
        check(pending_valid && clip_count==0 && audio_underrun==0,"normal approved amplitude no clipping or underrun");
    endtask
    always @(negedge clk) if(rst_n && trace)begin
        for(integer i=0;i<4;i++)begin
            if(dut.u_bank.slot_note_on[i])$fdisplay(trace,"N %0d %0d %0d",i,dut.u_bank.slot_velocity[10*i+:10],dut.u_bank.slot_fcw[32*i+:32]);
            if(dut.u_bank.slot_note_off[i])$fdisplay(trace,"F %0d",i);
        end
    end
    integer cycle_index=0,request_cycle=0,observed_peak=0;
    logic measuring=0;
    always @(posedge clk) begin
        if(!rst_n) begin cycle_index=0;request_cycle=0;observed_peak=0;measuring=0;end
        else begin
            cycle_index++;
            if(dut.sample_req)begin request_cycle=cycle_index;measuring=1;end
            if(dut.actual_commit && measuring)begin
                if(cycle_index-request_cycle>observed_peak)observed_peak=cycle_index-request_cycle;
                measuring=0;
            end
        end
    end
    task automatic message(input logic [2:0] kind,input logic [3:0] src,ch,
        input logic [6:0] note,input logic [9:0] vel,input logic [11:0] value);
        performance_event_t m;
        wait(event_ready);@(negedge clk);m='0;m.event_type=kind;m.source_id=src;
        m.channel=ch;m.note_number=note;m.velocity=vel;
        m.control_id=CTRL_SUSTAIN;m.control_value=value;event_data=m;event_valid=1;
        @(negedge clk);event_valid=0;wait(event_ready);repeat(5)@(negedge clk);
    endtask
    task automatic pedal(input logic [3:0] src,ch,input logic down);
        message(EVENT_CONTROL_CHANGE,src,ch,0,0,down ? 4095 : 0);
    endtask
    task automatic note(input logic on,input logic [3:0] src,ch,input logic [6:0] number);
        message(on ? EVENT_NOTE_ON : EVENT_NOTE_OFF,src,ch,number,on ? 900 : 0,0);
    endtask
    wire [3:0] deferred=dut.u_bank.u_events.controller_deferred;
    wire [3:0] releasing=dut.u_bank.slot_releasing;
    wire [3:0] occupied=dut.u_bank.slot_occupied;
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        note(1,0,0,60);note(1,0,0,64);repeat(300)frame();
        note(0,0,0,60);check(releasing==1 && active_voice_count==2,"normal NoteOff retains Release tail");
        repeat(4802)frame();check(occupied==2,"ordinary release retires one voice");
        pedal(0,0,1);note(0,0,0,64);
        check(deferred==2 && releasing==0 && occupied==2,"pedal NoteOff defers ADSR Release");
        repeat(5000)frame();check(occupied==2 && releasing==0 && deferred==2,"pedal does not freeze natural envelope or prematurely retire");
        pedal(0,0,0);check(releasing==2 && deferred==0,"pedal up triggers deferred release");
        repeat(4802)frame();check(active_voice_count==0,"deferred tail eventually retires");
        // Different source/channel identities, even when note number matches.
        note(1,0,0,69);note(1,1,0,69);note(1,0,1,69);
        pedal(0,0,1);note(0,0,0,69);note(0,1,0,69);note(0,0,1,69);
        check(deferred==1 && releasing==6,"pedal state isolated by source and channel");
        repeat(4802)frame();check(occupied==1,"unpedalled sources retire independently");
        // Release-deferred same-note retrigger cancels old hold without new slot.
        note(1,0,0,69);check(occupied==1 && deferred==0 && releasing==0,"same identity retrigger cancels deferred hold");
        pedal(0,0,0);check(releasing==0,"pedal up leaves physically held key sounding");
        // Fill all voices and defer first. Fifth identity steals its old slot.
        note(1,0,0,71);note(1,0,0,73);note(1,0,0,76);pedal(0,0,1);
        note(0,0,0,69);check(deferred==1,"oldest note deferred before steal");
        note(1,0,0,79);check(occupied==15 && deferred==0,"steal clears old deferred identity");
        pedal(0,0,0);check(releasing==0,"pedal release cannot release new stolen held note");
        note(0,0,0,69);check(releasing==0,"stale stolen NoteOff ignored");
        // Whole mask release must finish dispatch without stopping PCM requests.
        pedal(0,0,1);note(0,0,0,79);note(0,0,0,71);note(0,0,0,73);
        check(deferred==7 && releasing==0,"three deferred slots, fourth held");
        pedal(0,0,0);check(releasing==7 && occupied==15,"pedal group releases exactly three slots");
        repeat(4802)frame();check(occupied==8,"group release excludes held fourth slot");
        // Frozen global panic clears all pedal domains, keeps tail contract.
        pedal(0,0,1);note(0,0,0,76);check(deferred==8,"held last note becomes deferred");
        message(EVENT_ALL_NOTES_OFF,0,0,0,0,0);
        check(deferred==0 && releasing==8,"global panic overrides pedals");
        repeat(4802)frame();check(active_voice_count==0 && play_left==0,"panic reaches exact silence");
        note(1,0,0,60);note(0,0,0,60);check(releasing==1 && deferred==0,"panic cleared pedal state for new notes");
        note(1,0,0,60);check(releasing==0 && occupied==1,"retrigger during Release keeps original slot");
        pedal(0,0,1);note(0,0,0,60);rst_n=0;repeat(5)@(negedge clk);
        check(occupied==0 && deferred==0 && play_left==0,"reset clears sustain and PCM");
        frames=0;rst_n=1;note(1,0,0,65);note(0,0,0,65);
        check(releasing==1 && deferred==0,"reset cleared pedal bits");
        repeat(4802)frame();check(active_voice_count==0,"post-reset release retires");
        $display("PASS sustain_audio_integration checks=%0d frames=%0d",checks,frames);$finish;
    end
    initial begin #100000000;$fatal(1,"Sustain audio integration timeout");end
endmodule
