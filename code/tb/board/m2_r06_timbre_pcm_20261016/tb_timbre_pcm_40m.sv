`timescale 1ns/1ps
module tb_m2_timbre_pcm;
  import audio_defs_pkg::*;
  reg clk=0, rst_n=0, frame_tick=0, sample_req=0, ready=0;
  integer cycle_count=0;
  always @(posedge clk) cycle_count<=cycle_count+1;
  always #12.5 clk=~clk; // 40 MHz
  reg [31:0] req_id=0;
  reg ev_p=0,ev_t=0,ev_ref=0;
  reg [63:0] data_p=0,data_t=0,data_ref=0;
  wire event_ready_p,event_ready_t,event_ready_ref,calc_p,calc_t,calc_ref,valid_p,valid_t,valid_ref;
  wire [31:0] id_p,id_t,id_ref,voices_p,voices_t,voices_ref;
  wire signed [23:0] left_p,right_p,left_t,right_t,left_ref,right_ref;
  wire clip_lp,clip_rp,clip_lt,clip_rt,clip_lr,clip_rr;
  m1td_timbre_delay_chain piano(
    .clk(clk),.rst_n(rst_n),.event_valid(ev_p),.frame_tick(frame_tick),.sample_req(sample_req),
    .event_data(data_p),.sample_req_id(req_id),.event_ready(event_ready_p),.calc_ready(calc_p),
    .config_valid(1'b0),.config_ready(),.config_enable(1'b0),.config_delay_samples(16'd1),
    .config_dry_gain(15'd32767),.config_wet_gain(15'd0),.config_feedback(15'd0),
    .result_valid(valid_p),.result_ready(ready),.result_id(id_p),.result_left(left_p),.result_right(right_p),
    .clipped_left(clip_lp),.clipped_right(clip_rp),.upstream_clipped_left(),.upstream_clipped_right(),
    .effect_clipped_left(),.effect_clipped_right(),.feedback_clipped_left(),.feedback_clipped_right(),
    .active_voice_count(voices_p));
  m1td_timbre_delay_chain triangle(
    .clk(clk),.rst_n(rst_n),.event_valid(ev_t),.frame_tick(frame_tick),.sample_req(sample_req),
    .event_data(data_t),.sample_req_id(req_id),.event_ready(event_ready_t),.calc_ready(calc_t),
    .config_valid(1'b0),.config_ready(),.config_enable(1'b0),.config_delay_samples(16'd1),
    .config_dry_gain(15'd32767),.config_wet_gain(15'd0),.config_feedback(15'd0),
    .result_valid(valid_t),.result_ready(ready),.result_id(id_t),.result_left(left_t),.result_right(right_t),
    .clipped_left(clip_lt),.clipped_right(clip_rt),.upstream_clipped_left(),.upstream_clipped_right(),
    .effect_clipped_left(),.effect_clipped_right(),.feedback_clipped_left(),.feedback_clipped_right(),
    .active_voice_count(voices_t));
  m1td_timbre_delay_chain triangle_reference(
    .clk(clk),.rst_n(rst_n),.event_valid(ev_ref),.frame_tick(frame_tick),.sample_req(sample_req),
    .event_data(data_ref),.sample_req_id(req_id),.event_ready(event_ready_ref),.calc_ready(calc_ref),
    .config_valid(1'b0),.config_ready(),.config_enable(1'b0),.config_delay_samples(16'd1),
    .config_dry_gain(15'd32767),.config_wet_gain(15'd0),.config_feedback(15'd0),
    .result_valid(valid_ref),.result_ready(ready),.result_id(id_ref),.result_left(left_ref),.result_right(right_ref),
    .clipped_left(clip_lr),.clipped_right(clip_rr),.upstream_clipped_left(),.upstream_clipped_right(),
    .effect_clipped_left(),.effect_clipped_right(),.feedback_clipped_left(),.feedback_clipped_right(),
    .active_voice_count(voices_ref));
  task automatic push(input integer target,input performance_event_t e);
    integer left;
    begin
      @(negedge clk);
      case(target)
        0:begin ev_p=1;data_p=e;end
        1:begin ev_t=1;data_t=e;end
        2:begin ev_ref=1;data_ref=e;end
      endcase
      left=100;
      while(left>0 && !((target==0)?event_ready_p:(target==1)?event_ready_t:event_ready_ref))begin @(negedge clk);left=left-1;end
      if(left==0)$fatal(1,"EVENT_TIMEOUT");
      @(posedge clk);@(negedge clk);
      case(target)
        0:ev_p=0;1:ev_t=0;2:ev_ref=0;
      endcase
      repeat(20)@(negedge clk);
    end
  endtask
  performance_event_t e;
  integer n,waits,frame_start,frame_period,different=0,nonzero_p=0,nonzero_t=0;
  integer held_matches=0;
  bit skip_program1;
  initial begin
    skip_program1=$test$plusargs("skip_program1");
    repeat(8)@(negedge clk); rst_n=1;
    e='0;e.event_type=EVENT_CONTROL_CHANGE;e.source_id=0;e.channel=0;
    e.control_id=CTRL_VOICE_SELECT;e.control_value=1;
    if(!skip_program1)begin push(1,e);push(2,e);end
    e='0;e.event_type=EVENT_NOTE_ON;e.source_id=0;e.channel=0;
    e.note_number=7'd60;e.velocity=10'd1023;
    push(0,e);push(1,e);push(2,e);
    for(n=1;n<=128;n=n+1)begin
      frame_start=cycle_count;frame_period=(n%3==0)?834:833;
      req_id=n;frame_tick=1;
      @(negedge clk);frame_tick=0;sample_req=1;
      @(negedge clk);sample_req=0;
      waits=300;
      while(waits>0 && !(valid_p && valid_t && valid_ref))begin @(negedge clk);waits=waits-1;end
      if(waits==0)$fatal(1,"RESULT_TIMEOUT frame=%0d",n);
      if(id_p!==n || id_t!==n || id_ref!==n)$fatal(1,"ID_MISMATCH");
      if(left_p!==right_p || left_t!==right_t || left_ref!==right_ref)$fatal(1,"STEREO_BYPASS_MISMATCH");
      if(^left_p===1'bx || ^left_t===1'bx || ^left_ref===1'bx)$fatal(1,"UNKNOWN_PCM");
      if(left_p!=0)nonzero_p=nonzero_p+1;
      if(left_t!=0)nonzero_t=nonzero_t+1;
      if(left_p!=left_t)different=different+1;
      if(n>64 && left_t===left_ref)held_matches=held_matches+1;
      @(negedge clk);ready=1;
      @(negedge clk);ready=0;
      if(n==64)begin
        e='0;e.event_type=EVENT_CONTROL_CHANGE;e.source_id=0;e.channel=0;
        e.control_id=CTRL_VOICE_SELECT;e.control_value=0;
        push(1,e); // held triangle and untouched reference must stay bit identical
      end
      while(cycle_count-frame_start<frame_period)@(negedge clk);
      if(cycle_count-frame_start!=frame_period)$fatal(1,"FRAME_PERIOD_OVERFLOW");
    end
    if(voices_p!==1 || voices_t!==1 || voices_ref!==1)$fatal(1,"VOICE_COUNT");
    if(nonzero_p<80 || nonzero_t<80 || different<80 || held_matches!=64)$fatal(1,"TIMBRE_PCM_NOT_DISTINCT p=%0d t=%0d d=%0d",nonzero_p,nonzero_t,different);
    $display("PASS M2_R06_TIMBRE_PCM_ISOLATED frames=128 piano_nonzero=%0d triangle_nonzero=%0d different=%0d held_matches=%0d",nonzero_p,nonzero_t,different,held_matches);
    $finish;
  end
  initial begin #5000000;$fatal(1,"GLOBAL_TIMEOUT");end
endmodule
