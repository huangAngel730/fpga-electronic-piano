// Diagnostic generator + original bridges + actual tracker/renderer.
// Small display geometry keeps multi-minute-equivalent frame count practical;
// both25MHz pixel and50MHz system clock rates are unchanged.
`timescale 1ns/1ps
module tb_diagnostic_score_progress;
 logic sys_clk=0;always #10 sys_clk=~sys_clk;
 logic sys_rst_n=0,accepted_valid=0;
 audio_defs_pkg::performance_event_t accepted_data='0;
 wire tmds_clk_p,tmds_clk_n,visual_pll_locked;
 wire [2:0] tmds_data_p,tmds_data_n;
 audio_visual_display_probe #(.MODE_PERIOD_CYCLES(20000000),
  .VIDEO_FRAME_SYS_CYCLES(2048),.DIAG_SCORE_SPACING_FRAMES(30)) dut(.*);
 defparam dut.u_scan.H_ACTIVE=16;
 defparam dut.u_scan.H_FRONT=4;
 defparam dut.u_scan.H_SYNC=8;
 defparam dut.u_scan.H_BACK=4;
 defparam dut.u_scan.V_ACTIVE=12;
 defparam dut.u_scan.V_FRONT=4;
 defparam dut.u_scan.V_SYNC=2;
 defparam dut.u_scan.V_BACK=14;
 integer received=0,frames=0,retired=0,moves=0,checks=0;
 logic held_request=0;
 logic [97:0] held_packet;
 logic [7:0] prev_valid=0;
 logic [79:0] prev_y=0;
 logic [127:0] prev_id=0;
 wire [97:0] src_packet={dut.score_seq,7'd60+{4'd0,dut.score_seq[2:0]},
  dut.diag_hit_frame,dut.score_seq[0],32'd30,10'd600};
 always @(posedge sys_clk)begin
  if(!sys_rst_n)held_request=0;
  else begin
   if(held_request && src_packet!==held_packet)$fatal(1,"source score changed under backpressure");
   held_request=dut.score_pending && !dut.src_score_ready;
   held_packet=src_packet;
  end
 end
 always @(posedge dut.pixel_clk)begin
  if(dut.video_reset_done && dut.control_video_done)begin
   if(dut.video_score_valid && dut.score_ready)begin
    if(dut.video_score_hit_frame<dut.current_frame+100)
     $fatal(1,"diagnostic note already stale hit=%0d now=%0d",dut.video_score_hit_frame,dut.current_frame);
    received++;
   end
   if(dut.frame_start)begin
    frames++;
    for(integer slot=0;slot<8;slot++)begin
     if(dut.u_scene.u_score_tracker.slot_used_mem[slot] &&
        dut.current_frame > dut.u_scene.u_score_tracker.hit_frame_mem[slot] +
          (dut.u_scene.u_score_tracker.duration_valid_mem[slot] ? 40 : 16))
       $fatal(1,"expired diagnostic slot stuck beyond window/duration slot=%0d",slot);
    end
    for(integer slot=0;slot<8;slot++)begin
     if(prev_valid[slot] && !dut.u_scene.score_slot_valid[slot])retired++;
     if(prev_valid[slot] && dut.u_scene.score_slot_valid[slot] &&
      prev_id[slot*16+:16]==dut.u_scene.score_slot_note_id[slot*16+:16] &&
      dut.u_scene.score_end_y[slot*10+:10]>prev_y[slot*10+:10])moves++;
    end
    prev_valid=dut.u_scene.score_slot_valid;
    prev_y=dut.u_scene.score_end_y;prev_id=dut.u_scene.score_slot_note_id;
   end
  end
 end
 initial begin
  #400;sys_rst_n=1;
  wait(dut.current_frame>=360);#100;
  if(received<11 || retired<3 || moves<500)$fatal(1,"nonvacuous timeline recv=%d retired=%d moves=%d",received,retired,moves);
  if(dut.diag_hit_frame<dut.current_frame+50)$fatal(1,"late running generator stopped following time");
  checks++;
  // Legacy sequence+120 is stale by this point; reproduce that arithmetic
  // against current frame without claiming unseen live video root cause.
  if(({16'd0,dut.score_seq}+120)>=dut.current_frame)$fatal(1,"legacy stale-note scenario not reached");
  checks++;
  dut.u_video_pll.lock=0;#200;
  if(dut.current_frame!=0 || dut.score_seq!=0 || dut.score_pending)$fatal(1,"diagnostic reset epoch not cleared");
  dut.u_video_pll.lock=1;wait(dut.current_frame>=5);
  if(dut.video_score_hit_frame<100)$fatal(1,"diagnostic fresh epoch not rearmed");
  checks++;
  $display("PASS diagnostic score: checks=%0d frames=%0d received=%0d retired=%0d y_moves=%0d stale-legacy-reproduced",checks,frames,received,retired,moves);$finish;
 end
 initial begin #25000000;$fatal(1,"diagnostic score timeout");end
endmodule
