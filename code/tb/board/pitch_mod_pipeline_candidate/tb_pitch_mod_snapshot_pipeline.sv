// Actual control_snapshot held-valid -> FCW consumer -> result backpressure.
`timescale 1ns/1ps
module tb_pitch_mod_snapshot_pipeline;
 import audio_defs_pkg::*;
 logic clk=0;always #10 clk=~clk;
 logic rst_n=0,event_valid=0,request_valid=0;
 logic[63:0]event_data=0;logic[31:0]request_id=0;
 logic[3:0]slot_occupied=0,note_on_mask=0;
 logic[15:0]slot_source_ids=0,slot_channels=0;
 logic[127:0]slot_generations=0,base_fcw=0;
 wire event_ready,request_ready,snapshot_valid,snapshot_ready;
 wire[31:0]snapshot_id;wire[3:0]snapshot_occupied;
 wire[15:0]snapshot_sources,snapshot_channels;
 wire[127:0]snapshot_generations;wire[47:0]snapshot_pitch_bend,snapshot_modulation;
 wire[19:0]snapshot_pitch_range;wire control_applied,invalid_range;
 performance_control_snapshot control(.*);
 logic cancel=0,result_ready=0;wire result_valid;
 wire[31:0]result_id;wire[3:0]result_occupied;wire[15:0]result_sources,result_channels;
 wire[127:0]result_generations,result_fcw;
 pitch_mod_snapshot_pipeline #(.LFO_INC(32'h40000000))dut(
  .clk(clk),.rst_n(rst_n),.cancel(cancel),.request_valid(snapshot_valid),.request_ready(snapshot_ready),
  .request_id(snapshot_id),.request_occupied(snapshot_occupied),.note_on_mask(note_on_mask),
  .request_sources(snapshot_sources),.request_channels(snapshot_channels),.request_generations(snapshot_generations),
  .request_base_fcw(base_fcw),.request_pitch_bend(snapshot_pitch_bend),.request_modulation(snapshot_modulation),.request_pitch_range(snapshot_pitch_range),
  .result_valid(result_valid),.result_ready(result_ready),.result_id(result_id),.result_occupied(result_occupied),
  .result_sources(result_sources),.result_channels(result_channels),.result_generations(result_generations),.result_fcw(result_fcw));
 wire accept=snapshot_valid&&snapshot_ready;
 wire[127:0]reference_fcw;wire[3:0]reference_valid;
 wire[127:0]candidate_phases,reference_phases;
 for(genvar i=0;i<4;i++)begin:g_ref
  assign candidate_phases[32*i+:32]=dut.g_lane[i].u_control.lfo_phase;
  assign reference_phases[32*i+:32]=reference.lfo_phase;
  pitch_mod_fcw #(.LFO_INC(32'h40000000))reference(
   .sys_clk(clk),.sys_rst_n(rst_n),.sample_enable(accept&&snapshot_occupied[i]),.note_on(note_on_mask[i]),
   .bend($signed(snapshot_pitch_bend[12*i+:12])),.modulation(snapshot_modulation[12*i+:12]),
   .pitch_range(snapshot_pitch_range[5*i+:5]),.base_fcw(base_fcw[32*i+:32]),
   .fcw_out(reference_fcw[32*i+:32]),.fcw_valid(reference_valid[i]));
 end
 integer checks=0,launches=0,outputs=0,consumes=0,cancelled=0,cycle_index=0,due=0;
 logic expected_busy=0;
 logic[31:0]expected_id;logic[3:0]expected_occupied;
 logic[15:0]expected_sources,expected_channels;
 logic[127:0]expected_generations,expected_fcw;
 logic[31:0]previous_phase[0:3];logic observed_previous_valid=0;
 logic[327:0]held_result;
 logic[31:0]random_state=32'h85364729;
 task automatic check(input logic ok,input string label);
  checks++;if(ok!==1'b1)$fatal(1,"snapshot pipeline %s cycle%0d launches%0d id%0d",label,cycle_index,launches,result_id);
 endtask
 always @(posedge clk)begin
  logic fired;
  fired=accept;
  if(!rst_n)begin expected_busy=0;due=0;observed_previous_valid=0;cycle_index=0;end
  else begin
   cycle_index++;
   if(cancel && expected_busy)begin expected_busy=0;cancelled++;end
   if(result_valid&&result_ready)consumes++;
  end
  #2;
  if(rst_n)begin
   if(fired)begin
    launches++;expected_busy=1;due=cycle_index+7;expected_id=snapshot_id;
    expected_occupied=snapshot_occupied;expected_sources=snapshot_sources;
    expected_channels=snapshot_channels;expected_generations=snapshot_generations;
    for(integer i=0;i<4;i++)expected_fcw[32*i+:32]=snapshot_occupied[i]?reference_fcw[32*i+:32]:0;
   end
   for(integer i=0;i<4;i++)check(candidate_phases[32*i+:32]===reference_phases[32*i+:32],"independent lane LFO, held-valid not repeatedly ticked");
   if(expected_busy)begin
    if(cycle_index<due)check(!result_valid,"no early result");
    else if(cycle_index==due)begin
     check(result_valid && result_id===expected_id && result_occupied===expected_occupied,"E+7 result/id");
     check(result_sources===expected_sources&&result_channels===expected_channels&&result_generations===expected_generations,"all identity tags aligned");
     check(result_fcw===expected_fcw,"4exact results, inactivezero");outputs++;expected_busy=0;
    end
   end
   if(observed_previous_valid && !result_ready && !cancel)
    check(result_valid && {result_id,result_occupied,result_sources,result_channels,result_generations,result_fcw}===held_result,"backpressure result stable");
   held_result={result_id,result_occupied,result_sources,result_channels,result_generations,result_fcw};
   observed_previous_valid=result_valid;
  end else check(!result_valid&&result_fcw==0,"reset output cleared");
 end
 task automatic send_control(input logic[3:0]src,ch,input logic[2:0]kind,input logic[7:0]id,input logic[11:0]value);
  wait(event_ready);@(negedge clk);event_data='0;event_data[63:61]=kind;event_data[60:57]=src;event_data[56:53]=ch;event_data[25:18]=id;event_data[17:6]=value;event_valid=1;
  @(negedge clk);event_valid=0;
 endtask
 task automatic launch(input logic[31:0]id,input logic[3:0]occupied);
  wait(request_ready);@(negedge clk);request_id=id;slot_occupied=occupied;
  for(integer i=0;i<4;i++)begin slot_generations[32*i+:32]=id*4+i;end
  request_valid=1;@(negedge clk);request_valid=0;
 endtask
 task automatic consume;
  wait(result_valid);@(negedge clk);result_ready=1;@(negedge clk);result_ready=0;
 endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  slot_source_ids=16'h2100;slot_channels=16'h3200;
  base_fcw={32'd11746659,32'd1122405052,32'd39370534,32'd39370534};
  // lane0/1 share identity,2 and3 distinct; controls must isolate bysource/channel.
  send_control(0,0,EVENT_PITCH_BEND,CTRL_PITCH_BEND,12'h7ff);
  send_control(0,0,EVENT_CONTROL_CHANGE,CTRL_MODULATION,12'hfff);
  send_control(1,2,EVENT_PITCH_BEND,CTRL_PITCH_BEND,12'h800);
  send_control(1,2,EVENT_CONTROL_CHANGE,CTRL_PITCH_RANGE,12'd24);
  @(negedge clk);note_on_mask=4'b1111;@(negedge clk);note_on_mask=0;
  for(integer n=1;n<=200;n++)begin
   launch(n,4'(n%16));wait(result_valid);repeat(n%9)@(negedge clk);
   if(n%11==0)begin
    // Reset just LFO of a replaced slot; already-held result/metadata unchanged.
    @(negedge clk);note_on_mask=4'b0100;@(negedge clk);note_on_mask=0;
   end
   consume();
  end
  // Hold first result while control_snapshot already holds a second snapshot.
  launch(501,15);wait(result_valid);launch(502,5);wait(snapshot_valid);
  begin integer saved_launches;
   saved_launches=launches;repeat(20)@(negedge clk);
   check(launches==saved_launches,"held snapshot valid does not launch twice");
   send_control(0,0,EVENT_CONTROL_CHANGE,CTRL_MODULATION,0);
   consume();consume();
  end
  // cancel at each math stage, drain, next request fresh identity.
  for(integer k=0;k<7;k++)begin
   launch(600+k,15);wait(accept);@(posedge clk);@(negedge clk);
   repeat(k)@(negedge clk);cancel=1;@(negedge clk);cancel=0;
   repeat(10)@(negedge clk);check(!result_valid,"cancelled calculation has no leaked result");
   launch(700+k,10);consume();
  end
  // Reset a busy request flushes all pipeline valid and resets control defaults.
  launch(801,15);wait(accept);@(posedge clk);@(negedge clk);#3;rst_n=0;#1;
  check(!result_valid,"async reset flush");repeat(3)@(negedge clk);rst_n=1;
  launch(802,15);consume();
  check(outputs>200 && launches>210 && checks>14000,"not empty");
  $display("PASS actual control_snapshot to4lane FCW pipeline checks=%0d launches=%0d outputs=%0d cancelled=%0d consumed=%0d",checks,launches,outputs,cancelled,consumes);$finish;
 end
 initial begin #3000000;$fatal(1,"snapshot pipeline timeout");end
endmodule
