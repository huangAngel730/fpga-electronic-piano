// Default640x480 bottom geometry, independent 64bit integer oracle and
// actual wrapper judgement after graphics are no longer visible.
`timescale 1ns/1ps
module tb_bottom_exit_motion;
 import audio_defs_pkg::*;
 logic pixel_clk=0;always #5 pixel_clk=~pixel_clk;
 logic video_rst_n=0,data_enable=1,frame_start=0,event_valid=0,event_ready;
 logic [15:0] pixel_x=1,pixel_y=479;
 performance_event_t event_data='0;
 logic video_desync=0,mode_toggle_pulse=0;
 logic score_valid=0,score_ready;
 logic [15:0] score_note_id=0;
 logic [6:0] score_note_number=36;
 logic [31:0] score_hit_frame=0,score_duration_frames=0;
 logic score_duration_valid=0;
 logic [9:0] score_velocity=600;
 wire display_mode;
 wire [31:0] current_frame;
 wire [7:0] rgb_r,rgb_g,rgb_b;
 integer checks=0,oracle_checks=0,seed=32'h020480;
 logic [31:0] hit_stamp;
 m3_visualizer dut(.*);
 task check(input logic ok,input string label_text);
  checks++;if(ok!==1)$fatal(1,"bottom motion %s frame=%0d top/end=%0d/%0d used=%b",label_text,current_frame,dut.score_top_y[0+:10],dut.score_end_y[0+:10],dut.u_score_tracker.slot_used_mem[0]);
 endtask
 task frame;
  @(negedge pixel_clk);frame_start=1;@(negedge pixel_clk);frame_start=0;#1;
 endtask
 task reset_all;
  @(negedge pixel_clk);video_rst_n=0;frame_start=0;event_valid=0;score_valid=0;
  @(negedge pixel_clk);video_rst_n=1;#1;
 endtask
 task falling;
  @(negedge pixel_clk);mode_toggle_pulse=1;@(negedge pixel_clk);mode_toggle_pulse=0;
  frame();@(negedge pixel_clk);#1;check(display_mode,"falling mode enabled");
 endtask
 task score(input logic with_duration,input integer duration,input integer ahead);
  @(negedge pixel_clk);score_hit_frame=current_frame+ahead;hit_stamp=score_hit_frame;
  score_duration_valid=with_duration;score_duration_frames=duration;score_valid=1;score_note_id++;
  do @(posedge pixel_clk);while(!score_ready);
  @(negedge pixel_clk);score_valid=0;#1;
 endtask
 task note(input logic on);
  @(negedge pixel_clk);event_data=make_note_event(on,2,0,36,on ? 700 : 0);event_valid=1;
  @(negedge pixel_clk);event_valid=0;repeat(2)@(negedge pixel_clk);#1;
 endtask
 task pixel(input integer y,input logic [23:0] expected);
  pixel_y=y;#1;check({rgb_r,rgb_g,rgb_b}===expected,"actual raster bottom/clipping");
 endtask
 function automatic integer distance_ref(input logic [31:0] frames);
  longint unsigned value;
  begin value=frames;distance_ref=value>=120 ? 480 : value*480/120;end
 endfunction
 function automatic integer front_ref(input logic [31:0] now_frame,arrival);
  front_ref=now_frame>=arrival ? 480 : 480-distance_ref(arrival-now_frame);
 endfunction
 task oracle(input logic [31:0] now_frame,arrival,duration,input bit valid_duration);
  integer front,short_top,tail,expected_top;
  longint unsigned tail_stamp;
  begin
   front=front_ref(now_frame,arrival);
   if(now_frame<arrival)short_top=front<12 ? 0 : front-12;
   else begin short_top=468+distance_ref(now_frame-arrival);if(short_top>480)short_top=480;end
   tail_stamp={1'b0,arrival}+{1'b0,duration};if(tail_stamp>32'hffffffff)tail_stamp=32'hffffffff;
   tail=front_ref(now_frame,32'(tail_stamp));
   expected_top=(valid_duration && duration!=0 && tail<short_top) ? tail : short_top;
   if(dut.u_score_tracker.front_end_y(now_frame,arrival)!==10'(front) ||
      dut.u_score_tracker.bar_top_y(now_frame,arrival,duration,valid_duration)!==10'(expected_top))
    $fatal(1,"geometry oracle f=%h hit=%h duration=%h valid=%b expected=%d/%d",now_frame,arrival,duration,valid_duration,expected_top,front);
   oracle_checks++;
  end
 endtask
 initial begin
  reset_all();note(1);frame();
  check(dut.live_y[0+:10]==470 && dut.live_end_y[0+:10]==480,"upward origin is actual screen bottom");
  pixel(479,24'h87c7cb);pixel(469,24'h081020);
  frame();check(dut.live_y[0+:10]==466 && dut.live_end_y[0+:10]==480,"held head rises tail anchored480");
  note(0);frame();frame();check(dut.live_end_y[0+:10]==476,"released tail leaves bottom");
  repeat(125)frame();check(dut.live_valid==0,"upward bar entirely off screen");
  reset_all();falling();score(0,0,3);
  frame();check(dut.score_top_y[0+:10]==460 && dut.score_end_y[0+:10]==472,"prehit descends to bottom");
  frame();check(dut.score_top_y[0+:10]==464 && dut.score_end_y[0+:10]==476,"motion continuous before hit");
  frame();check(current_frame==hit_stamp && dut.score_top_y[0+:10]==468 && dut.score_end_y[0+:10]==480,"leading edge at480 on exact target time");
  pixel(479,24'hbb6dd5);pixel(400,24'h081020);
  frame();check(dut.score_top_y[0+:10]==472 && dut.score_end_y[0+:10]==480,"no clamp pause after hit");
  frame();check(dut.score_top_y[0+:10]==476,"tail continues after hit");
  frame();check(dut.score_top_y[0+:10]==480 && dut.score_end_y[0+:10]==480,"short visual exits at3 frames");
  check(dut.u_score_tracker.slot_used_mem[0] && !dut.u_score_tracker.judged_mem[0],"judge identity retained after invisible");
  frame();frame();frame();check(current_frame==hit_stamp+6,"inclusive late window boundary");
  note(1);check(dut.hit_note_number==36 && dut.u_score_tracker.hit_mem[0],"invisible short note still accepts late correct key");
  frame();check(!dut.u_score_tracker.slot_used_mem[0],"slot reclaimed only after window");
  check(dut.flash_active[36],"late invisible hit still triggers bottom feedback");
  reset_all();falling();score(1,30,1);frame();
  check(dut.score_top_y[0+:10]==360 && dut.score_end_y[0+:10]==480,"30frame duration gives120px long bar");
  repeat(10)frame();check(dut.score_top_y[0+:10]==400 && dut.score_end_y[0+:10]==480,"long tail advances rather than fixed rectangle");
  repeat(20)frame();check(dut.score_top_y[0+:10]==480 && dut.score_end_y[0+:10]==480,"long tail exits on hit plus duration");
  check(dut.u_score_tracker.slot_used_mem[0],"end timestamp state held until next frame");
  frame();check(!dut.u_score_tracker.slot_used_mem[0],"long slot reclaimed");
  reset_all();falling();score(1,1,1);frame();repeat(3)frame();
  check(dut.u_score_tracker.slot_used_mem[0] && dut.score_top_y[0+:10]==480,"short duration does not truncate late window");
  repeat(3)frame();note(1);check(dut.u_score_tracker.hit_mem[0],"late hit valid for1frame duration");
  reset_all();falling();score(1,200,1);frame();
  check(dut.score_top_y[0+:10]==0 && dut.score_end_y[0+:10]==480,"very long bar clipped without shortening duration");
  repeat(125)frame();check(dut.u_score_tracker.slot_used_mem[0] && dut.score_top_y[0+:10]==180,"long hold tail remains past a full preview span");
  video_desync=1;@(negedge pixel_clk);#1;check(dut.score_slot_valid==0,"desync clears geometry");
  reset_all();check(dut.score_slot_valid==0,"reset clears geometry");
  // Independent arithmetic oracle: all surrounding arrival and release frames
  // plus random full32bit and overflow timestamps; not framebuffer snapshots.
  for(integer duration=0;duration<160;duration++)
   for(integer offset=0;offset<300;offset++)oracle(offset,120,duration,1);
  for(integer sample=0;sample<20000;sample++)begin
   oracle($random(seed),$random(seed),$random(seed),1'(sample));
   oracle(32'hfffffff0+32'(sample%16),32'hfffffff8,32'(sample%20),1);
  end
  $display("PASS bottom motion: %0d checks %0d integer geometry comparisons",checks,oracle_checks);$finish;
 end
 initial begin #10000000;$fatal(1,"bottom motion timeout");end
endmodule
