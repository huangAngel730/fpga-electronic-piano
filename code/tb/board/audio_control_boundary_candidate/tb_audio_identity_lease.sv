`timescale 1ns/1ps
module tb_audio_identity_lease;
import audio_defs_pkg::*;
logic clk=0;always #10 clk=~clk;
logic rst_n=0,event_valid=0,frame_tick=0,sample_req=0,result_ready=0;
logic[63:0]event_data=0;logic[31:0]sample_req_id=0;
wire event_ready,calc_ready,result_valid;
wire[31:0]result_req_id,active_voice_count;
wire[63:0]result_envelopes,result_waves;wire[127:0]result_fcw;
wire[3:0]result_occupied;wire[11:0]result_states;
polyphonic_envelope_bank #(.PIANO_TIMBRE_ENABLE(1),.WAVE_ROM_FILE("wave.mem"),
 .OCT_FILE("oct.mem"),.SUB_FILE("sub.mem"),.LFO_FILE("lfo.mem"))dut(.*);
integer checks=0,ticks=0,results=0,max_latency=0,cycles=0,start_cycle,completed_release=0;
logic[163:0]leased_id;logic have_lease=0;
task automatic check(input logic ok,input string msg);
 checks++;if(ok!==1'b1)$fatal(1,"lease boundary %s cycle=%0d phase=%0d",msg,cycles,dut.phase);
endtask
always @(posedge clk)begin
 cycles++;
 if(!rst_n || !dut.identity_hold)have_lease=0;
 if(rst_n && dut.identity_hold && dut.phase!=3)begin
  if(!have_lease)begin leased_id={dut.slot_occupied,dut.slot_sources,dut.slot_channels,dut.slot_generations};have_lease=1;end
  else check({dut.slot_occupied,dut.slot_sources,dut.slot_channels,dut.slot_generations}===leased_id,"held identity immutable");
 end
 if(rst_n && dut.lane_tick)begin
  check(dut.sample_authorized_q && dut.request_guard_q && (&dut.live_guard_q) && (&dut.math_guard_q),"tick only after registered authorization");
  check(dut.live_identity_matches && dut.math_identity_matches,"actual identity exact at tick");ticks++;
 end
 if(frame_tick)check(!dut.lane_tick && !dut.control_request_valid,"frame cancel blocks tick and capture");
end
task automatic send(input performance_event_t ev);
 integer guard;guard=0;while(!event_ready && guard<200)begin @(negedge clk);guard++;end
 check(guard<200,"event handshake finite");event_data=ev;event_valid=1;@(negedge clk);event_valid=0;
 guard=0;while(!event_ready && guard<200)begin @(negedge clk);guard++;end
 check(guard<200,"dispatch bounded");repeat(8)@(negedge clk);
endtask
task automatic request;
 integer guard;guard=0;while(!calc_ready && guard<200)begin @(negedge clk);guard++;end
 check(guard<200,"calc ready bounded");sample_req_id++;sample_req=1;start_cycle=cycles;@(negedge clk);sample_req=0;
 guard=0;while(!result_valid && guard<200)begin @(negedge clk);guard++;end
 check(guard<200,"request completes");check(result_req_id==sample_req_id,"request id exact");
 if(cycles-start_cycle>max_latency)max_latency=cycles-start_cycle;
endtask
task automatic consume;
 result_ready=1;@(negedge clk);result_ready=0;results++;repeat(16)@(negedge clk);
endtask
initial begin
 repeat(4)@(negedge clk);rst_n=1;repeat(4)@(negedge clk);
 send(make_note_event(1,1,0,69,32));
 for(integer n=0;n<260;n++)begin request();consume();end
 send(make_note_event(0,1,0,69,0));
 for(integer n=0;n<5000 && !completed_release;n++)begin
  request();
  if(result_states[2:0]==0)begin
   completed_release=1;
  end
  if(!completed_release)consume();
 end
 check(completed_release==1,"real release reaches zero");
 check(dut.slot_occupied[0] && active_voice_count==1,"retirement remains queued during leased result");
 // A new identity is offered while the zero-level old result is held.
 event_data=make_note_event(1,9,2,81,900);event_valid=1;
 repeat(12)begin @(negedge clk);check(!event_ready && dut.slot_occupied[0] && active_voice_count==1,"held identity immutable");end
 check(dut.u_events.retire_pending[0],"release retirement recorded, not dropped");
 result_ready=1;@(negedge clk);result_ready=0;results++;
 begin integer guard;guard=0;while(!event_ready && guard<200)begin @(negedge clk);guard++;end
 check(guard<200,"queued retirement eventually releases lease");@(negedge clk);event_valid=0;end
 repeat(30)@(negedge clk);check(active_voice_count==1,"new identity admitted after retirement");
 send(make_note_event(0,1,0,69,0));request();check(result_occupied!=0 && result_fcw[31:0]!=0,"old NoteOff does not stop replacement");consume();
 // Cancel before an authorized arithmetic tick, then reset dirty control state.
 sample_req_id++;sample_req=1;@(negedge clk);sample_req=0;wait(dut.phase==9);@(negedge clk);frame_tick=1;
 @(negedge clk);frame_tick=0;repeat(24)@(negedge clk);check(!result_valid,"VERIFY cancellation no stale result");
 request();consume();rst_n=0;#1;check(!result_valid && active_voice_count==0,"reset clears result and identities");
 repeat(4)@(negedge clk);rst_n=1;repeat(4)@(negedge clk);send(make_note_event(1,1,0,60,1023));request();consume();
 check(max_latency<80 && results>500 && ticks>=results,"nonempty coverage within frame budget");
 $display("PASS audio identity lease checks=%0d results=%0d ticks=%0d max_latency=%0d",checks,results,ticks,max_latency);$finish;
end
initial begin #40000000;$fatal(1,"lease TB timeout");end
endmodule
