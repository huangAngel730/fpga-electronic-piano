`timescale 1ns/1ps
module tb_pitch_mod_bank_integration;
 import audio_defs_pkg::*;
 logic clk=0;always #10 clk=~clk;
 logic rst_n=0,event_valid=0,frame_tick=0,sample_req=0,result_ready=0;
 logic[63:0]event_data=0;logic[31:0]sample_req_id=0;
 wire event_ready,calc_ready,result_valid;
 wire[31:0]result_req_id,active_voice_count;
 wire[63:0]result_envelopes,result_waves;
 wire[127:0]result_fcw;wire[3:0]result_occupied;wire[11:0]result_states;
 polyphonic_envelope_bank #(.PIANO_TIMBRE_ENABLE(1),
    .WAVE_ROM_FILE("wave.mem"),.OCT_FILE("oct.mem"),.SUB_FILE("sub.mem"),.LFO_FILE("lfo.mem"))dut(.*);
 wire ref_event_ready,ref_calc_ready,ref_valid;wire[31:0]ref_id,ref_count;
 wire[63:0]ref_env,ref_wave;wire[127:0]ref_fcw;wire[3:0]ref_occupied;wire[11:0]ref_states;
 logic ref_req=0,ref_ready=0,compare_enabled=1;
 bank_reference #(.PIANO_TIMBRE_ENABLE(1),.WAVE_ROM_FILE("wave.mem")) reference_bank(
 .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(ref_event_ready),.event_data(event_data),
 .frame_tick(frame_tick),.sample_req(ref_req),.sample_req_id(sample_req_id),.calc_ready(ref_calc_ready),
 .result_valid(ref_valid),.result_ready(ref_ready),.result_req_id(ref_id),
 .result_envelopes(ref_env),.result_waves(ref_wave),.result_fcw(ref_fcw),.result_occupied(ref_occupied),
 .result_states(ref_states),.active_voice_count(ref_count));
 integer fd,cycle=0,checks=0,consumed=0,ticks=0,compare_samples=0,launches=0;
 logic[31:0]dds_phase[0:3],lfo_phase[0:3];
 wire[127:0]actual_dds,actual_lfo;
 for(genvar i=0;i<4;i++)begin:g_observe
  assign actual_dds[32*i+:32]=dut.g_lane[i].g_piano.u_dds.phase_acc;
  assign actual_lfo[32*i+:32]=dut.u_pitch_mod.g_lane[i].u_control.lfo_phase;
 end
 task automatic check(input logic ok,input string message);
  checks++;if(ok!==1'b1)$fatal(1,"bank integration %s cycle%0d id%0d",message,cycle,sample_req_id);
 endtask
 always @(posedge clk)begin
  cycle++;
  if(!rst_n)begin
   for(integer k=0;k<4;k++)begin dds_phase[k]=0;lfo_phase[k]=0;end
   $fdisplay(fd,"R %0d",cycle);
  end else begin
   if(event_valid && event_ready)$fdisplay(fd,"E %0d %016h",cycle,event_data);
   if(dut.slot_note_on)$fdisplay(fd,"N %0d %h",cycle,dut.slot_note_on);
   if(dut.control_request_valid && dut.control_request_ready)
    $fdisplay(fd,"Q %0d %0d %h %04h %04h %032h %032h",cycle,dut.pending_req_id,
        dut.slot_occupied,dut.slot_sources,dut.slot_channels,dut.slot_generations,dut.slot_fcw);
   if(dut.control_snapshot_valid && dut.control_snapshot_ready && dut.phase==4)
    $fdisplay(fd,"S %0d %0d %012h %012h %05h",cycle,dut.control_id,dut.control_bend,dut.control_mod,dut.control_range);
   if(dut.fcw_result_valid && dut.fcw_result_ready && dut.phase==4)
    $fdisplay(fd,"F %0d %0d %h %04h %04h %032h %032h",cycle,dut.fcw_id,dut.fcw_occupied,
        dut.fcw_sources,dut.fcw_channels,dut.fcw_generations,dut.fcw_values);
   if(frame_tick)$fdisplay(fd,"X %0d",cycle);
   for(integer k=0;k<4;k++)begin
    if(dut.slot_note_on[k])lfo_phase[k]=0;
    if(dut.u_pitch_mod.accepted && dut.control_occupied[k])lfo_phase[k]=lfo_phase[k]+32'd447392;
    if(dut.lane_tick)dds_phase[k]=dds_phase[k]+dut.dds_fcw[32*k+:32];
   end
   if(dut.lane_tick)begin
    for(integer k=0;k<4;k++)if(dut.frozen_occupied[k])
     check(dut.dds_fcw[32*k+:32]===dut.fcw_values[32*k+:32],"computed adjusted FCW is not bypassed before DDS");
    ticks++;$fdisplay(fd,"D %0d %0d %032h",cycle,dut.pending_req_id,dut.dds_fcw);
   end
   #1;
   for(integer k=0;k<4;k++)begin
    check(actual_dds[32*k+:32]===dds_phase[k],"DDS consumes the frozen adjusted FCW exactly once");
    check(actual_lfo[32*k+:32]===lfo_phase[k],"LFO advances only on occupied accepted calculation");
   end
  end
 end
 function automatic performance_event_t note(input logic on,input integer src,ch,num,velocity);
  performance_event_t e;e='0;e.event_type=on?EVENT_NOTE_ON:EVENT_NOTE_OFF;
  e.source_id=4'(src);e.channel=4'(ch);e.note_number=7'(num);e.velocity=10'(velocity);return e;
 endfunction
 function automatic performance_event_t control(input integer src,ch,ctrl,value);
  performance_event_t e;e='0;e.event_type=ctrl==0?EVENT_PITCH_BEND:EVENT_CONTROL_CHANGE;
  e.source_id=4'(src);e.channel=4'(ch);e.control_id=8'(ctrl);e.control_value=12'(value);return e;
 endfunction
 task automatic send(input performance_event_t e);
  integer guard;guard=0;
  while(!(event_ready && ref_event_ready) && guard<200)begin @(negedge clk);guard++;end
  check(guard<200,"event acceptance bounded");
  @(negedge clk);event_data=e;event_valid=1;
  @(negedge clk);event_valid=0;
  guard=0;while(!(event_ready && ref_event_ready)&&guard<200)begin @(negedge clk);guard++;end
  check(guard<200,"real router completed event");repeat(8)@(negedge clk);
 endtask
 task automatic launch;
  integer guard;guard=0;
  while(!(calc_ready && ref_calc_ready)&&guard<200)begin @(negedge clk);guard++;end
  check(guard<200,"bank ready bounded after cancel");
  @(negedge clk);sample_req_id++;launches++;sample_req=1;ref_req=1;
  @(negedge clk);sample_req=0;ref_req=0;
 endtask
 task automatic sample_once;
  integer guard;
  launch();guard=0;
  while(!(result_valid&&ref_valid)&&guard<160)begin @(negedge clk);guard++;end
  check(guard<160,"finite accepted sample produces both results");
  check(result_req_id==sample_req_id,"result request tag exact");
  if(compare_enabled)begin
   compare_samples++;
   check({result_envelopes,result_waves,result_fcw,result_occupied,result_states}===
      {ref_env,ref_wave,ref_fcw,ref_occupied,ref_states},"center/Mod0 exact V1 ADSR bank per-request comparison");
  end
  $fdisplay(fd,"B %0d %0d %h %032h %016h %016h",cycle,result_req_id,result_occupied,result_fcw,result_envelopes,result_waves);
  @(negedge clk);result_ready=1;ref_ready=1;
  @(negedge clk);result_ready=0;ref_ready=0;consumed++;
 endtask
 task automatic reset;
  @(negedge clk);rst_n=0;sample_req=0;ref_req=0;result_ready=0;ref_ready=0;event_valid=0;frame_tick=0;
  #1;check(!result_valid&&active_voice_count==0,"reset flush and voices silent");
  repeat(4)@(negedge clk);rst_n=1;repeat(4)@(negedge clk);
 endtask
 task automatic cancel_phase(input integer target);
  integer guard,saved;launch();guard=0;
  while(dut.phase!=target && guard<100)begin @(negedge clk);guard++;end
  check(guard<100,"cancel target phase reached");saved=ticks;
  @(negedge clk);frame_tick=1;@(negedge clk);frame_tick=0;
  repeat(20)@(negedge clk);check(!result_valid,"cancelled token never published");
  check(ticks==saved || target==5,"cancelled pre-advance work never advances DDS");
  sample_once();
 endtask
 initial begin
  fd=$fopen("bank.capture","w");if(!fd)$fatal(1,"cannot create capture");
  reset();
  send(note(1,1,1,60,1023));send(note(1,1,2,64,768));
  send(note(1,9,1,67,512));send(note(1,1,1,72,256));
  check(active_voice_count==4,"real allocator four occupied voices");
  for(integer n=0;n<512;n++)sample_once();
  send(control(1,1,0,0));send(control(1,1,1,0));send(control(1,1,CTRL_VOICE_SELECT,127));
  for(integer n=0;n<16;n++)sample_once();
  compare_enabled=0;
  // Real accepted source/channel routing, existing 12-bit signed bend pattern.
  send(control(1,1,0,2047));send(control(1,2,0,2048));send(control(9,1,1,4095));
  for(integer n=0;n<1024;n++)sample_once();
  // Pedal held keys, same-note retrigger, stealing and old NoteOff.
  send(control(1,1,6,4095));send(note(0,1,1,60,0));
  check(active_voice_count==4,"sustain retains released key");
  for(integer n=0;n<32;n++)sample_once();
  send(note(1,1,1,60,1));send(note(1,9,3,79,1023));send(note(0,1,1,60,0));
  check(active_voice_count==4,"fifth-note steal does not remove newer voice");
  for(integer n=0;n<32;n++)sample_once();
  send(control(1,1,6,0));
  // Backpressure must freeze complete PCM-facing snapshot.
  launch();wait(result_valid&&ref_valid);@(negedge clk);
  begin
   logic[303:0]held;held={result_req_id,result_envelopes,result_waves,result_fcw,result_occupied,result_states};
   repeat(20)begin @(negedge clk);check(result_valid && !event_ready &&
       {result_req_id,result_envelopes,result_waves,result_fcw,result_occupied,result_states}===held,"held bank snapshot stable");end
  end
  @(negedge clk);result_ready=1;ref_ready=1;@(negedge clk);result_ready=0;ref_ready=0;
  for(integer st=0;st<7;st++)begin
   cancel_phase(st==0?3:st==1?4:st==2?5:st==3?6:st==4?7:st==5?1:2);
  end
  // Async reset at each state, followed by a real NoteOn and new sample.
  for(integer st=1;st<=7;st++)begin
   launch();wait(dut.phase==st);reset();send(note(1,1,1,60,1023));sample_once();
  end
  reset();compare_enabled=1;send(note(1,1,1,69,1023));for(integer n=0;n<256;n++)sample_once();
  check(compare_samples>=784 && consumed>1800 && ticks<=launches,"nonempty functional coverage");
  $fdisplay(fd,"END %0d %0d %0d %0d",checks,consumed,ticks,compare_samples);$fclose(fd);
  $display("PASS actual bank PitchMod V1 CC64 checks=%0d consumed=%0d ticks=%0d compare=%0d",checks,consumed,ticks,compare_samples);
  $finish;
 end
 initial begin #30000000;$fatal(1,"real bank integration timeout");end
endmodule
