`timescale 1ns/1ps
module tb_polyphonic_audio_core #(parameter integer PIANO_TIMBRE_ENABLE=0);
    import audio_defs_pkg::*;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,event_valid=0,frame_tick=0;
    logic [63:0] event_data=0;
    wire event_ready,pending_valid;
    wire signed [23:0] play_left,play_right;
    wire [31:0] active_voice_count,clip_count,audio_underrun,audio_frame_count,pcm_request_count,pcm_commit_count,max_processing_cycles;
    polyphonic_audio_core #(.PIANO_TIMBRE_ENABLE(PIANO_TIMBRE_ENABLE)) dut(.*);
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
    initial begin
        if($value$plusargs("TRACE=%s",trace_path))begin trace=$fopen(trace_path,"w");if(!trace)$fatal(1,"Cannot open trace");end
        repeat(4)@(negedge clk);check(play_left==0 && active_voice_count==0,"reset");rst_n=1;
        for(integer i=0;i<4;i++)send(EVENT_NOTE_ON,60+i,1023-i*180);
        check(active_voice_count==4,"four notes");
        for(integer n=0;n<300;n++)frame();
        send(EVENT_NOTE_OFF,60,0);for(integer n=0;n<4800;n++)frame();
        check(active_voice_count==3,"first release retires");
        send(EVENT_NOTE_ON,61,1);for(integer n=0;n<240;n++)frame();
        check(dut.bank_envelopes[31:16]==6553,"light retrigger exact target");
        send(EVENT_ALL_NOTES_OFF,0,0);for(integer n=0;n<4800;n++)frame();
        check(active_voice_count==0 && play_left==0 && play_right==0,"global release silence");
        check(max_processing_cycles>0 && max_processing_cycles<64,"actual request commit latency bounded");
        check(max_processing_cycles==observed_peak && observed_peak>=11,"reported peak equals independently timestamped request/commit cycles");
        rst_n=0;repeat(3)@(negedge clk);check(pcm_commit_count==0 && clip_count==0,"reset counters");
        if(trace)$fclose(trace);
        $display("PASS polyphonic_audio_core checks=%0d frames=%0d",checks,frames);$finish;
    end
    initial begin #100000000;$fatal(1,"Audio timeout");end
endmodule