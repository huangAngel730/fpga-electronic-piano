`timescale 1ns/1ps
module tb_t027_dynamic_core;
    import audio_defs_pkg::*;
    logic clk=0;
    always #10 clk=~clk;
    logic rst_n=0,event_valid=0,frame_tick=0;
    logic [63:0] event_data=0;
    wire event_ready,pending_valid;
    wire signed [23:0] play_left,play_right;
    wire [31:0] active_voice_count,clip_count,audio_underrun;
    wire [31:0] audio_frame_count,pcm_request_count,pcm_commit_count,max_processing_cycles;
    integer frames=0,checks=0,nonzero=0;
    polyphonic_audio_core #(.DYNAMIC_TIMBRE_ENABLE(1'b1)) dut (.*);

    task automatic check(input logic ok,input string label);
        checks++;
        if(ok!==1'b1)$fatal(1,"T027 core %s frame=%0d",label,frames);
    endtask
    task automatic send(input logic [2:0] kind,input logic [3:0] src,ch,
                        input logic [6:0] note,input logic [9:0] velocity,
                        input logic [7:0] cid,input logic [11:0] value);
        performance_event_t e;
        e='0;e.event_type=kind;e.source_id=src;e.channel=ch;
        e.note_number=note;e.velocity=velocity;e.control_id=cid;e.control_value=value;
        wait(event_ready);@(negedge clk);event_valid=1;event_data=e;
        @(negedge clk);event_valid=0;wait(event_ready);repeat(3)@(negedge clk);
    endtask
    task automatic frame;
        integer sum,prod,scaled,w,e;
        @(negedge clk);frame_tick=1;@(negedge clk);frame_tick=0;
        frames++;wait(pcm_commit_count==frames);repeat(2)@(negedge clk);
        sum=0;
        for(integer i=0;i<4;i++)begin
            w=$signed(dut.bank_waves[16*i+:16]);e=dut.bank_envelopes[16*i+:16];
            prod=w*e;
            scaled=(prod>=0 ? prod/32768 : -((-prod+32767)/32768))*256;
            if(dut.bank_occupied[i])sum=sum+scaled;
        end
        if(sum>8388607)sum=8388607;
        if(sum< -8388608)sum=-8388608;
        check(play_left===sum && play_right===sum,"real waveform and ADSR to PCM");
        check(pending_valid && audio_underrun==0 && clip_count==0,
            "one committed sample, no underrun or clip");
        if(sum!=0)nonzero++;
    endtask
    initial begin
        repeat(4)@(negedge clk);check(play_left==0,"reset silence");rst_n=1;
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,1);
        send(EVENT_NOTE_ON,2,3,60,1023,0,0);
        send(EVENT_NOTE_ON,2,4,64,800,0,0);
        send(EVENT_NOTE_ON,3,3,67,600,0,0);
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,0);
        send(EVENT_NOTE_ON,2,3,72,700,0,0);
        check(active_voice_count==4,"four voice dispatch");
        check(dut.u_bank.slot_timbre==4'b0001,"per-source/channel new-note selection");
        for(integer n=0;n<256;n++)frame();
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,1);
        for(integer n=0;n<32;n++)frame();
        check(dut.u_bank.slot_timbre==4'b0001,"sounding notes keep their timbre");
        $display("TRACE dynamic core nonzero=%0d occupied=%b waves=%h envelopes=%h",
            nonzero,dut.bank_occupied,dut.bank_waves,dut.bank_envelopes);
        check(nonzero>100,"nonzero real PCM reached");
        rst_n=0;repeat(3)@(negedge clk);
        check(active_voice_count==0 && pcm_commit_count==0 && play_left==0,"reset clears lanes and PCM");
        $display("PASS T027 dynamic PCM checks=%0d frames=%0d nonzero=%0d",checks,frames,nonzero);
        $finish;
    end
    initial begin #100000000; $fatal(1,"T027 core timeout");end
endmodule
