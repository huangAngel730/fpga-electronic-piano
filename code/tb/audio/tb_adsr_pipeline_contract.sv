// M2 isolated pipeline-vs-original comparison at settled sample boundaries.
// No internal state-code reuse for sample-count checking.
`timescale 1ns/1ps
module tb_adsr_pipeline_contract;
 logic sys_clk=0;always #10 sys_clk=~sys_clk;
 logic sys_rst_n=0,sample_tick=0,note_on=0,note_off=0;
 logic[9:0]velocity=0;
 wire[15:0]envelope_level,ref_level;
 wire[2:0]state_out,ref_state;
 adsr_piano_envelope dut(.*);
 adsr_reference reference(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.sample_tick(sample_tick),
  .note_on(note_on),.note_off(note_off),.velocity(velocity),.envelope_level(ref_level),.state_out(ref_state));
 integer checks=0,samples=0,interrupts=0;
 logic[31:0]random_state=32'h29836bee;
 task automatic check(input logic ok,input string label);
  checks++;if(ok!==1'b1)$fatal(1,"ADSR pipeline %s samples=%0d got=%0d/%0d expected=%0d/%0d",label,samples,envelope_level,state_out,ref_level,ref_state);
 endtask
 task automatic settled;
  repeat(6)@(negedge sys_clk);#1;
  check(envelope_level===ref_level,"Q15 sample/event amplitude exact original");
  check(state_out===ref_state,"public state exact original");
  check(dut.level_q16===reference.level_q16,"internal accumulated Q16 exact original");
 endtask
 task automatic reset_all;
  @(negedge sys_clk);sys_rst_n=0;sample_tick=0;note_on=0;note_off=0;
  #1;check(envelope_level===0 && state_out===0,"asynchronous assert");
  repeat(2)@(negedge sys_clk);sys_rst_n=1;settled();
 endtask
 task automatic on_event(input logic[9:0]vel,input logic tick);
  @(negedge sys_clk);velocity=vel;note_on=1;sample_tick=tick;
  @(negedge sys_clk);note_on=0;sample_tick=0;if(tick)samples++;
  // Change live input while ROM pipeline is busy: only event velocity counts.
  velocity=~vel;settled();
 endtask
 task automatic off_event(input logic tick);
  @(negedge sys_clk);note_off=1;sample_tick=tick;
  @(negedge sys_clk);note_off=0;sample_tick=0;if(tick)samples++;settled();
 endtask
 task automatic sample_once;
  @(negedge sys_clk);sample_tick=1;
  @(negedge sys_clk);sample_tick=0;samples++;settled();
 endtask
 initial begin
  reset_all();
  // Every event velocity, including zero slope: 240 exact samples and state boundary.
  for(integer v=0;v<1024;v++)begin
   reset_all();on_event(10'(v),0);
   for(integer n=1;n<=240;n++)begin sample_once();check(state_out==(n==240 ? 2 : 1),"240-sample Attack regardless of slope");end
  end
  reset_all();on_event(1023,1);repeat(239)sample_once();
  check(envelope_level==32767 && state_out==2,"same-edge first sample not lost");
  repeat(4801)sample_once();check(state_out==3,"Decay reaches Sustain");
  repeat(25000)sample_once();
  off_event(1);repeat(4799)sample_once();check(envelope_level==0 && state_out==0,"same-edge Release4800 endpoint");
  // Consecutive events before an accepted sample: stale ROM/products cannot leak.
  for(integer wait_cycles=0;wait_cycles<5;wait_cycles++)begin
   reset_all();on_event(1023,0);repeat(40)sample_once();off_event(0);
   @(negedge sys_clk);velocity=1023;note_on=1;
   @(negedge sys_clk);note_on=0;
   repeat(wait_cycles)@(negedge sys_clk);
   @(negedge sys_clk);velocity=1;note_on=1;
   @(negedge sys_clk);note_on=0;interrupts++;settled();
   repeat(240)sample_once();
   check(envelope_level==6553 && state_out==2,"newest event owns peak after stale pipeline cancellation");
  end
  // Reset at each preparation stage, no stale positive output after reset.
  for(integer wait_cycles=0;wait_cycles<5;wait_cycles++)begin
   reset_all();@(negedge sys_clk);note_on=1;velocity=1023;sample_tick=1;
   @(negedge sys_clk);note_on=0;sample_tick=0;
   repeat(wait_cycles)@(negedge sys_clk);
   sys_rst_n=0;#1;check(envelope_level==0 && state_out==0,"reset aborts in-flight Attack");
   repeat(6)@(negedge sys_clk);sys_rst_n=1;settled();
   on_event(512,1);repeat(239)sample_once();check(envelope_level==13119,"recovered new velocity");
  end
  // Same-edge both events: NoteOn is deliberately first priority.
  reset_all();on_event(1023,0);repeat(500)sample_once();
  @(negedge sys_clk);note_on=1;note_off=1;sample_tick=1;velocity=1;
  @(negedge sys_clk);note_on=0;note_off=0;sample_tick=0;samples++;settled();
  check(state_out==1,"NoteOn priority over simultaneous NoteOff");
  repeat(239)sample_once();check(envelope_level==6553 && state_out==2,"priority still exact240 samples");
  // Random triggers at settled sample intervals, all current states incl IDLE.
  for(integer n=0;n<12000;n++)begin
   random_state=random_state^(random_state<<13);random_state=random_state^(random_state>>17);random_state=random_state^(random_state<<5);
   if(n%1501==0)reset_all();
   else if(random_state[5:0]==0)on_event(random_state[17:8],random_state[6]);
   else if(random_state[5:0]==1)off_event(random_state[6]);
   else sample_once();
  end
  if(checks<900000 || samples<280000 || interrupts!=5)$fatal(1,"empty or partial run");
  $display("PASS ADSR pipeline contract checks=%0d samples=%0d interrupted=%0d",checks,samples,interrupts);$finish;
 end
 initial begin #100000000;$fatal(1,"ADSR contract timeout");end
endmodule
