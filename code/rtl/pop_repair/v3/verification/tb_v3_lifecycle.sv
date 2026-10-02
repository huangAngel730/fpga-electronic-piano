`timescale 1ns/1ps
// Independent public-core lifecycle tests. 50 MHz clock, accelerated frames;
// each real request/commit deadline is measured in system-clock cycles.
module tb_v3_lifecycle #(parameter integer HAS_CC64=0);
    import audio_defs_pkg::*;
    logic clk=0; always #10 clk=~clk;
    logic rst_n=0,event_valid=0,frame_tick=0;
    logic [63:0] event_data=0;
    wire event_ready,pending_valid;
    wire signed [23:0] play_left,play_right;
    wire [31:0] active_voice_count,clip_count,audio_underrun,audio_frame_count;
    wire [31:0] pcm_request_count,pcm_commit_count,max_processing_cycles;
    polyphonic_audio_core #(.PIANO_TIMBRE_ENABLE(1)) dut(.*);
    integer checks=0,frames=0,elapsed=0,trace=0;
    string trace_path;
    task automatic check(input logic pass,input string name);
        checks++;
        if(pass!==1'b1) $fatal(1,"FAIL V3 lifecycle: %s frame=%0d",name,frames);
    endtask
    task automatic reset_core;
        @(negedge clk);rst_n=0;event_valid=0;frame_tick=0;
        if(trace) $fdisplay(trace,"R");
        repeat(5) @(negedge clk);
        check(play_left==0 && active_voice_count==0,"reset silence");
        frames=0;rst_n=1;repeat(5) @(negedge clk);
    endtask
    task automatic message(input logic [2:0] kind,input integer number,velocity,
                           input logic [3:0] source,channel,
                           input logic [11:0] value);
        performance_event_t event_word;
        wait(event_ready);@(negedge clk);
        event_word='0;event_word.event_type=kind;event_word.note_number=number;
        event_word.velocity=velocity;event_word.source_id=source;event_word.channel=channel;
        if(kind==EVENT_CONTROL_CHANGE) event_word.control_id=CTRL_SUSTAIN;
        event_word.control_value=value;event_data=event_word;event_valid=1;
        @(negedge clk);event_valid=0;wait(event_ready);repeat(8)@(negedge clk);
    endtask
    task automatic note_on(input integer number,velocity);
        message(EVENT_NOTE_ON,number,velocity,0,0,0);
    endtask
    task automatic note_off(input integer number);
        message(EVENT_NOTE_OFF,number,0,0,0,0);
    endtask
    task automatic frame;
        @(negedge clk);frame_tick=1;@(negedge clk);frame_tick=0;
        frames++;elapsed=0;
        while(pcm_commit_count!=frames && elapsed<256) begin
            @(negedge clk);elapsed++;
        end
        check(pcm_commit_count==frames && elapsed<256,"commit within 256 cycles (<1041 real deadline)");
        repeat(3)@(negedge clk);
        check(pending_valid && play_left===play_right,"stereo and pending");
        check(clip_count==0 && audio_underrun==0,"no clip/underrun");
        check(!$isunknown({play_left,dut.bank_envelopes,dut.bank_waves}),"no unknown ROM/sample");
        if(trace) $fdisplay(trace,"D %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
             dut.bank_envelopes[15:0],dut.bank_envelopes[31:16],
             dut.bank_envelopes[47:32],dut.bank_envelopes[63:48],
             $signed(dut.bank_waves[15:0]),$signed(dut.bank_waves[31:16]),
             $signed(dut.bank_waves[47:32]),$signed(dut.bank_waves[63:48]),
             dut.bank_fcw[31:0],dut.bank_fcw[63:32],
             dut.bank_fcw[95:64],dut.bank_fcw[127:96],play_left,dut.bank_occupied);
    endtask
    task automatic pair_case(input integer low,high);
        reset_core();note_on(low,850);note_on(high,850);
        check(active_voice_count==2,"both adjacent notes accepted");
        repeat(1200) frame();
        check(active_voice_count==2 && (|dut.bank_envelopes),"held identities/envelopes preserved");
        note_off(low);repeat(4802)frame();
        check(active_voice_count==1,"one release does not retire held neighbour");
        note_off(high);repeat(4802)frame();
        check(active_voice_count==0 && play_left==0,"pair releases to exact silence");
    endtask
    always @(negedge clk) if(rst_n && trace) begin
        for(integer i=0;i<4;i++) begin
            if(dut.u_bank.slot_note_on[i]) $fdisplay(trace,"N %0d %0d %0d",i,
                 dut.u_bank.slot_velocity[10*i+:10],dut.u_bank.slot_fcw[32*i+:32]);
            if(dut.u_bank.slot_note_off[i]) $fdisplay(trace,"F %0d",i);
        end
    end
    integer peak,previous_peak;
    integer velocities[0:4]='{1,256,512,768,1023};
    initial begin
        if($value$plusargs("TRACE=%s",trace_path)) begin
            trace=$fopen(trace_path,"w");if(!trace)$fatal(1,"Cannot open independent trace");
        end
        pair_case(36,37);pair_case(48,49);pair_case(60,61);pair_case(84,85);
        previous_peak=-1;
        for(integer j=0;j<5;j++)begin
            reset_core();note_on(69,velocities[j]);peak=0;
            repeat(500)begin frame();if(play_left>peak)peak=play_left;end
            check(peak>previous_peak,"velocity positive peak strictly increases");
            previous_peak=peak;
        end
        reset_core();
        note_on(36,850);note_on(37,850);note_on(40,850);note_on(43,850);
        repeat(1200)frame();check(active_voice_count==4,"low four-note chord");
        note_on(45,850);repeat(8)frame();check(active_voice_count==4,"fifth key retains four voices");
        note_off(36);repeat(8)frame();check(active_voice_count==4,"stolen stale NoteOff ignored");
        note_on(37,512);repeat(8)frame();check(active_voice_count==4,"same-note retrigger not fifth voice");
        message(EVENT_ALL_NOTES_OFF,0,0,0,0,0);repeat(4802)frame();
        check(active_voice_count==0 && play_left==0,"global clear tail");
        if(HAS_CC64)begin
            reset_core();note_on(48,850);note_on(49,850);repeat(300)frame();
            message(EVENT_CONTROL_CHANGE,0,0,0,0,4095);note_off(48);
            repeat(4802)frame();check(active_voice_count==2,"pedal retains released identity");
            message(EVENT_CONTROL_CHANGE,0,0,0,0,0);repeat(4802)frame();
            check(active_voice_count==1,"pedal up leaves held neighbour");
        end
        reset_core();if(trace)$fclose(trace);
        $display("PASS independent V3 lifecycle checks=%0d HAS_CC64=%0d",checks,HAS_CC64);
        $finish;
    end
    initial begin #500000000; $fatal(1,"V3 independent lifecycle timeout"); end
endmodule
