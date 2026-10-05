// T024 actual PCM capability test. Normal event interface drives the real core.
// Faster frame requests shorten simulation; audio interpretation is Fs=48000.
// No waveform/ADSR bypass, forced PCM, production test-mode or UART changes.
`timescale 1ns/1ps
module tb_piano_pair_capture #(parameter integer PIANO_TIMBRE_ENABLE=0);
    import audio_defs_pkg::*;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,event_valid=0,frame_tick=0;
    logic [63:0] event_data=0;
    wire event_ready,pending_valid;
    wire signed [23:0] play_left,play_right;
    wire [31:0] active_voice_count,clip_count,audio_underrun;
    wire [31:0] audio_frame_count,pcm_request_count,pcm_commit_count,max_processing_cycles;
    polyphonic_audio_core #(.PIANO_TIMBRE_ENABLE(PIANO_TIMBRE_ENABLE)) dut(.*);
    integer samples=0,checks=0,fd,total=0;
    string capture;
    task automatic check(input logic ok,input string label_text);
        checks++;
        if(ok!==1'b1)$fatal(1,"Audio capability %s sample=%0d voices=%0d",label_text,samples,active_voice_count);
    endtask
    task automatic reset_core;
        @(negedge clk);rst_n=0;frame_tick=0;event_valid=0;
        repeat(5)@(negedge clk);
        check(play_left==0 && play_right==0 && active_voice_count==0,"reset silence");
        samples=0;rst_n=1;repeat(3)@(negedge clk);
    endtask
    task automatic send(input logic [2:0] kind,input logic [6:0] note,input logic [9:0] velocity);
        performance_event_t msg;
        msg='0;msg.event_type=kind;msg.note_number=note;msg.velocity=velocity;
        wait(event_ready);@(negedge clk);event_data=msg;event_valid=1;
        @(negedge clk);event_valid=0;wait(event_ready);repeat(5)@(negedge clk);
    endtask
    task automatic sample_once;
        @(negedge clk);frame_tick=1;@(negedge clk);frame_tick=0;
        samples++;total++;
        wait(pcm_commit_count==samples);repeat(3)@(negedge clk);
        check(pending_valid && audio_underrun==0,"one actual accepted PCM generation per frame");
        check(clip_count==0 && play_left===play_right,"bounded clean equal stereo");
    endtask
    task automatic record_block(input string label_text,input integer n,input integer voices);
        $fdisplay(fd,"BEGIN %s %0d %0d",label_text,n,voices);
        repeat(n)begin
            sample_once();check(active_voice_count==voices,"occupied voices match capture stage");
            $fdisplay(fd,"PCM %0d %0d %0d",play_left,play_right,active_voice_count);
        end
    endtask
    initial begin
        if(!$value$plusargs("CAPTURE=%s",capture))$fatal(1,"CAPTURE required");
        fd=$fopen(capture,"w");if(!fd)$fatal(1,"Cannot open capture");
        reset_core();send(EVENT_NOTE_ON,60,1023);send(EVENT_NOTE_ON,61,1023);
        record_block("pair_attack",1920,2);
        repeat(3360)sample_once();record_block("pair_steady",16384,2);
        send(EVENT_NOTE_OFF,60,0);repeat(4802)sample_once();
        record_block("one_after_release",8192,1);
        send(EVENT_NOTE_OFF,61,0);repeat(4802)sample_once();
        check(active_voice_count==0 && play_left==0,"pair reaches final silence");
        rst_n=0;repeat(4)@(negedge clk);
        check(play_left==0 && active_voice_count==0,"final reset silence");
        $fclose(fd);
        $display("PASS piano_pair_capture checks=%0d samples=%0d",checks,total);$finish;
    end
    initial begin #200000000;$fatal(1,"Audio capability timeout");end
endmodule