`timescale 1ns/1ps
module tb_pitch_mod_audio_commit;
 import audio_defs_pkg::*;
 logic clk=0;always #10 clk=~clk;
 logic rst_n=0,event_valid=0,frame_tick=0;
 logic[63:0]event_data=0;wire event_ready;
 wire signed[23:0]play_left,play_right;wire pending_valid;
 wire[31:0]active_voice_count,clip_count,audio_underrun,audio_frame_count,pcm_request_count,pcm_commit_count,max_processing_cycles;
 polyphonic_audio_core #(.PIANO_TIMBRE_ENABLE(1),.WAVE_ROM_FILE("wave.mem"))dut(.*);
 integer checks=0,frames=0,interval=1041,cycle=0,request_cycle=0,maximum_cycles=0,nonzero=0,ticks=0;
 task automatic check(input logic ok,input string label);
  checks++;if(ok!==1'b1)$fatal(1,"actual PCM PitchMod %s frame=%0d cycle=%0d",label,frames,cycle);
 endtask
 function automatic performance_event_t note(input logic on,input integer source,channel,num,vel);
  performance_event_t e;e='0;e.event_type=on?EVENT_NOTE_ON:EVENT_NOTE_OFF;
  e.source_id=4'(source);e.channel=4'(channel);e.note_number=7'(num);e.velocity=10'(vel);return e;
 endfunction
 function automatic performance_event_t control(input integer source,channel,ctrl,val);
  performance_event_t e;e='0;e.event_type=ctrl==0?EVENT_PITCH_BEND:EVENT_CONTROL_CHANGE;
  e.source_id=4'(source);e.channel=4'(channel);e.control_id=8'(ctrl);e.control_value=12'(val);return e;
 endfunction
 task automatic send(input performance_event_t e);
  integer guard;guard=0;
  while(!event_ready&&guard<200)begin @(negedge clk);guard++;end
  check(guard<200,"event ready bounded");
  @(negedge clk);event_data=e;event_valid=1;@(negedge clk);event_valid=0;
  guard=0;while(!event_ready&&guard<200)begin @(negedge clk);guard++;end
  check(guard<200,"dispatch bounded");repeat(8)@(negedge clk);
 endtask
 always @(posedge clk)begin
  cycle++;
  if(rst_n)begin
   if(dut.sample_req)request_cycle=cycle;
   if(dut.u_bank.lane_tick)ticks++;
   if(dut.actual_commit)begin
    if(cycle-request_cycle>maximum_cycles)maximum_cycles=cycle-request_cycle;
    check(cycle-request_cycle<100,"request and actual stereo commit bounded below100clk");
   end
  end
 end
 task automatic frame;
  integer guard;longint signed product,contrib,sum;
  @(negedge clk);frame_tick=1;@(negedge clk);frame_tick=0;frames++;guard=0;
  while(pcm_commit_count!=frames&&guard<200)begin @(negedge clk);guard++;end
  check(guard<200,"new frame request accepted after cancellation drain");
  check(audio_frame_count==frames&&pcm_request_count==frames,"one request per actual frame");
  check(pending_valid && audio_underrun==0,"valid PCM and no accidental underflow");
  sum=0;
  for(integer i=0;i<4;i++)begin
   product=$signed(dut.bank_waves[16*i+:16])*longint'({1'b0,dut.bank_envelopes[16*i+:16]});
   contrib=(product>>>15)*256;
   if(dut.bank_occupied[i])sum+=contrib;
  end
  if(sum>8388607)sum=8388607;if(sum< -8388608)sum=-8388608;
  check(play_left===24'(sum)&&play_right===24'(sum),"Q15 floor mixing is unchanged exactly");
  check(clip_count==0,"approved four-voice amplitudes remain unclipped");
  if(sum!=0)nonzero++;
  repeat(interval-guard-2)@(negedge clk);interval=interval==1041?1042:1041;
 endtask
 task automatic reset;
  @(negedge clk);rst_n=0;frame_tick=0;event_valid=0;
  #1;check(play_left==0&&play_right==0&&!pending_valid,"asynchronous PCM reset silence");
  repeat(4)@(negedge clk);rst_n=1;frames=0;repeat(4)@(negedge clk);
 endtask
 initial begin
  reset();send(note(1,1,1,60,1023));send(note(1,1,2,64,768));send(note(1,9,1,67,512));send(note(1,1,1,72,256));
  for(integer n=0;n<256;n++)frame();
  send(control(1,1,0,2047));send(control(1,2,0,2048));send(control(9,1,1,4095));
  for(integer n=0;n<256;n++)frame();
  send(control(1,1,6,4095));send(note(0,1,1,60,0));check(active_voice_count==4,"pedal holds real bank");
  for(integer n=0;n<16;n++)frame();
  send(note(1,1,1,60,1));send(note(1,9,3,79,1023));send(note(0,1,1,60,0));
  check(active_voice_count==4,"stolen old note off never stops newer slot");
  send(control(1,1,6,0));for(integer n=0;n<16;n++)frame();
  check(max_processing_cycles==maximum_cycles&&maximum_cycles>0,"real processing counter includes control pipeline");
  reset();send(note(1,1,1,69,1023));for(integer n=0;n<16;n++)frame();
  check(nonzero>500&&ticks>=560,"actual nonempty audio coverage");
  $display("PASS actual V1 CC64 PitchMod PCM frames=%0d nonzero=%0d checks=%0d max_cycles=%0d",ticks,nonzero,checks,maximum_cycles);$finish;
 end
 initial begin #30000000;$fatal(1,"audio commit timeout");end
endmodule
