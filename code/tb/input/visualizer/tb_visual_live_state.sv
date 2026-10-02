`timescale 1ns/1ps
module tb_visual_live_state;
 import audio_defs_pkg::*;
 logic clk=0;always #5 clk=~clk;
 logic rst_n=0,frame_start=0,performance_fire=0,video_desync=0;
 performance_event_t performance_data='0;
 wire [127:0] key_down;
 wire [2:0] live_valid,live_held;
 wire [20:0] live_note_number;
 wire [17:0] live_y,live_end_y;
 wire [29:0] live_velocity;
 wire [31:0] visual_slot_drop_count;
 wire desync_latched;
 integer checks=0;
 visual_live_state #(.SLOT_COUNT(3),.Y_WIDTH(6),.JUDGE_Y(20),.RISE_STEP(4)) dut(.*);
 task check(input logic ok,input string label_text);
  checks++;if(ok!==1)$fatal(1,"duration bars %s valid=%b held=%b top/end=%h/%h",label_text,live_valid,live_held,live_y,live_end_y);
 endtask
 task tick_frame;
  @(negedge clk);frame_start=1;@(negedge clk);frame_start=0;#1;
 endtask
 task event_in(input bit on,input logic [3:0] src,ch,input logic [6:0] note,input logic [9:0] vel);
  @(negedge clk);performance_data=make_note_event(on,src,ch,note,vel);performance_fire=1;
  @(negedge clk);performance_fire=0;#1;
 endtask
 task reset_all;
  @(negedge clk);rst_n=0;performance_fire=0;video_desync=0;frame_start=0;
  @(negedge clk);rst_n=1;#1;
 endtask
 initial begin
  reset_all();check(live_valid==0 && visual_slot_drop_count==0,"reset");
  event_in(1,1,0,60,900);check(live_valid==0,"event waits for frame snapshot");
  tick_frame();check(live_valid==1 && live_held==1 && live_y[0+:6]==20 && live_end_y[0+:6]==30,"opens at original baseline");
  tick_frame();check(live_y[0+:6]==16 && live_end_y[0+:6]==30,"held grows");
  repeat(20)tick_frame();check(live_valid==1 && live_held==1 && live_y[0+:6]==0 && live_end_y[0+:6]==30,"long held crosses top but retains identity");
  event_in(0,2,0,60,0);tick_frame();check(live_held==1,"different source off ignored");
  event_in(0,1,1,60,0);tick_frame();check(live_held==1,"different channel off ignored");
  // CC64 does not release or lengthen physical key bars.
  @(negedge clk);performance_data='0;performance_data.event_type=EVENT_CONTROL_CHANGE;
  performance_data.control_id=64;performance_data.control_value=127;performance_fire=1;
  @(negedge clk);performance_fire=0;tick_frame();check(live_held==1,"CC64 ignored for physical hold");
  event_in(0,1,0,60,0);tick_frame();check(live_held==0 && live_end_y[0+:6]==30,"matching release freezes length");
  tick_frame();check(live_end_y[0+:6]==26 && live_y[0+:6]==0,"released both endpoints translate/clamp");
  repeat(8)tick_frame();check(live_valid==0,"released tail fully leaves screen");
  reset_all();event_in(1,1,0,60,100);event_in(1,2,0,60,200);event_in(1,1,1,60,300);
  tick_frame();check(live_valid==7 && live_held==7,"three isolated identities");
  event_in(0,2,0,60,0);tick_frame();check(live_held==5 && key_down[60],"off only own identity/key aggregate remains");
  event_in(1,3,0,61,400);tick_frame();check(visual_slot_drop_count==1 && live_valid==7,"full slot drops new without eviction");
  event_in(0,3,0,61,0);tick_frame();check(live_held==5,"dropped identity off cannot stop retained bars");
  event_in(1,1,0,60,500);tick_frame();check(live_held==5 && live_y[0+:6]==20 && live_velocity[0+:10]==500 && visual_slot_drop_count==2,"full retrigger reopens same slot/count overwrite");
  reset_all();event_in(1,1,0,60,100);tick_frame();tick_frame();
  event_in(1,1,0,60,600);tick_frame();check(live_valid==3 && live_held==2 && live_y[6+:6]==20,"retrigger ends old/open new free slot");
  event_in(1,1,0,60,0);tick_frame();check(live_held==0,"velocity zero is NoteOff");
  @(negedge clk);performance_data='0;performance_data.event_type=EVENT_ALL_NOTES_OFF;performance_fire=1;
  @(negedge clk);performance_fire=0;tick_frame();check(live_valid==0 && live_held==0,"all notes off clears bars");
  event_in(1,1,0,60,700);tick_frame();
  @(negedge clk);video_desync=1;@(negedge clk);video_desync=0;tick_frame();
  check(live_valid==0 && desync_latched,"desync clears and latches");
  event_in(1,1,0,60,900);tick_frame();check(live_valid==0,"desync refuses state until reset");
  reset_all();event_in(1,1,0,60,900);tick_frame();check(live_valid==1 && !desync_latched,"reset re-arms");
  // An event on a frame boundary is visible one frame later.
  reset_all();@(negedge clk);frame_start=1;performance_fire=1;performance_data=make_note_event(1,1,0,64,700);
  @(negedge clk);frame_start=0;performance_fire=0;#1;check(live_valid==0,"coincident event uses next snapshot");
  tick_frame();check(live_valid==1,"coincident event retained");
  reset_all();
  // Saturating local drop counter, not a wraparound indication.
  event_in(1,1,0,60,100);event_in(1,2,0,60,100);event_in(1,1,1,60,100);
  @(negedge clk);dut.drops_q=32'hfffffffe;
  event_in(1,3,0,61,100);tick_frame();check(visual_slot_drop_count==32'hffffffff,"drop counter reaches saturation");
  event_in(1,3,0,62,100);tick_frame();check(visual_slot_drop_count==32'hffffffff,"drop counter never wraps");
  // Released head and tail both move when neither has reached screen top.
  reset_all();event_in(1,1,0,60,100);tick_frame();event_in(0,1,0,60,0);tick_frame();
  check(live_y[0+:6]==16 && live_end_y[0+:6]==30,"release preserves complete accumulated length");
  tick_frame();check(live_y[0+:6]==12 && live_end_y[0+:6]==26,"release translates both ends");
  $display("PASS duration live state: %0d checks",checks);$finish;
 end
 initial begin #100000;$fatal(1,"live bars timeout");end
endmodule
