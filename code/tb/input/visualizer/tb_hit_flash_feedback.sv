// Real tracker judgement -> wrapper flash -> bottom RGB feedback.
`timescale 1ns/1ps
module tb_hit_flash_feedback;
 import audio_defs_pkg::*;
 logic pixel_clk=0;always #5 pixel_clk=~pixel_clk;
 logic video_rst_n=0,data_enable=1,frame_start=0,event_valid=0,event_ready;
 logic [15:0] pixel_x=1,pixel_y=47;
 performance_event_t event_data='0;
 logic video_desync=0,mode_toggle_pulse=0;
 logic score_valid=0,score_ready;
 logic [15:0] score_note_id=0;
 logic [6:0] score_note_number=60;
 logic [15:0] score_hit_frame=0,score_duration_frames=0;
 logic score_duration_valid=0;
 logic [9:0] score_velocity=600;
 wire display_mode;
 wire [15:0] current_frame;
 wire [7:0] rgb_r,rgb_g,rgb_b;
 integer checks=0,hits=0;
 m3_visualizer #(.FRAME_WIDTH(16),.Y_WIDTH(6),.SCREEN_WIDTH(64),.SCREEN_HEIGHT(48),
  .BASE_NOTE(60),.NOTE_COUNT(8),.JUDGE_Y(32),.KEYBOARD_TOP(36),
  .PREVIEW_FRAMES(4),.HIT_WINDOW_FRAMES(2),.HIT_FLASH_FRAMES(6)) dut(.*);
 always @(negedge pixel_clk)if(dut.hit_pulse)hits++;
 task check(input logic ok,input string label_text);
  checks++;if(ok!==1)$fatal(1,"hit flash %s mode=%d frame=%d hit=%d active=%h",label_text,display_mode,current_frame,hits,dut.flash_active);
 endtask
 task frame;
  @(negedge pixel_clk);frame_start=1;@(negedge pixel_clk);frame_start=0;#1;
 endtask
 task set_mode;
  @(negedge pixel_clk);mode_toggle_pulse=1;@(negedge pixel_clk);mode_toggle_pulse=0;
  frame();@(negedge pixel_clk);#1;
 endtask
 task score(input logic [6:0] note,input logic [15:0] hit_at);
  @(negedge pixel_clk);score_note_number=note;score_hit_frame=hit_at;
  score_note_id=score_note_id+1;score_valid=1;
  do @(posedge pixel_clk);while(!score_ready);
  @(negedge pixel_clk);score_valid=0;#1;
 endtask
 task note(input logic [6:0] pitch,input logic [2:0] typ,input logic [9:0] vel);
  @(negedge pixel_clk);event_data='0;event_data.event_type=typ;
  event_data.note_number=pitch;event_data.velocity=vel;event_valid=1;
  @(negedge pixel_clk);event_valid=0;repeat(2)@(negedge pixel_clk);#1;
 endtask
 task sample(input integer x,y,input logic de,input logic [23:0] expected);
  pixel_x=x;pixel_y=y;data_enable=de;#1;
  if({rgb_r,rgb_g,rgb_b}!==expected)$display("PIXEL x=%0d y=%0d actual=%h expected=%h",x,y,{rgb_r,rgb_g,rgb_b},expected);
  check({rgb_r,rgb_g,rgb_b}===expected,"bottom pixel/color/clip/blank");
 endtask
 initial begin
  repeat(2)@(negedge pixel_clk);video_rst_n=1;
  set_mode();check(display_mode,"enter falling mode");
  score(60,current_frame+2);
  note(61,EVENT_NOTE_ON,700);frame();check(hits==0 && dut.flash_active==0,"wrong key no flash");
  note(60,EVENT_NOTE_OFF,0);note(60,EVENT_CONTROL_CHANGE,700);
  check(hits==0,"off/control no trigger");
  note(60,EVENT_NOTE_ON,700);check(hits==1 && dut.flash_active==0,"true hit pending until boundary");
  frame();check(dut.flash_active[60],"correct hit flash");
  sample(4,47,1,24'hffffe0);sample(0,44,1,24'h30b0c8);
  sample(4,39,1,24'h30e870);sample(4,20,1,24'h081020);sample(4,48,1,24'h000000);
  sample(64,47,1,24'h000000);sample(4,47,0,24'h000000);
  data_enable=1;
  note(60,EVENT_NOTE_ON,700);check(hits==1,"judged note not repeated");
  repeat(5)begin frame();check(dut.flash_active[60],"six complete frames hold");end
  frame();check(!dut.flash_active[60],"flash automatically expires");
  score(62,current_frame+3);note(62,EVENT_NOTE_ON,700);check(hits==1,"window outside no flash");
  frame();note(62,EVENT_NOTE_ON,700);frame();check(hits==2 && dut.flash_active[62],"inclusive early boundary");
  score(63,current_frame);frame();frame();note(63,EVENT_NOTE_ON,700);frame();
  check(hits==3 && dut.flash_active[62] && dut.flash_active[63],"inclusive late boundary/multiple pitch feedback");
  // A second scored instance can refresh a still-lit pitch once judged.
  score(63,current_frame);note(63,EVENT_NOTE_ON,700);frame();
  check(hits==4 && dut.flash_active[63],"repeated successful instance refresh");
  repeat(5)frame();check(dut.flash_active[63],"refresh lifetime restarted");
  frame();check(!dut.flash_active[63],"refreshed feedback extinguishes");
  score(64,current_frame);note(64,EVENT_NOTE_ON,700);frame();check(dut.flash_active[64],"arm before clear");
  note(0,EVENT_ALL_NOTES_OFF,0);check(dut.flash_active==0,"all notes off clears pending/counts");
  score(65,current_frame);note(65,EVENT_NOTE_ON,700);frame();check(dut.flash_active[65],"arm before mode change");
  set_mode();check(!display_mode && dut.flash_active==0,"leave falling clears residual");
  score(66,current_frame);note(66,EVENT_NOTE_ON,700);frame();check(dut.flash_active==0,"live-mode hit never flashes");
  set_mode();score(67,current_frame);note(67,EVENT_NOTE_ON,700);frame();check(dut.flash_active[67],"last pitch");
  sample(63,47,1,24'h30b0c8); // last pitch core ends62, glow clips screen edge
  video_desync=1;@(negedge pixel_clk);#1;check(dut.flash_active==0,"desync clears");
  video_desync=0;frame();score(60,current_frame);note(60,EVENT_NOTE_ON,700);frame();check(dut.flash_active==0,"latched desync remains dark");
  video_rst_n=0;@(negedge pixel_clk);#1;check(dut.flash_active==0 && !dut.hit_pulse,"reset clears flash and notice");
  video_rst_n=1;set_mode();score(60,current_frame);
  begin : zero_velocity_case
   integer before_hits;
   before_hits=hits;note(60,EVENT_NOTE_ON,0);frame();
   check(hits==before_hits && dut.flash_active==0,"velocity-zero NoteOn does not flash");
  end
  $display("PASS hit flash feedback: %0d checks %0d true hits",checks,hits);$finish;
 end
 initial begin #300000;$fatal(1,"hit flash timeout");end
endmodule
