// M2 isolated experiment benchmark; no production source replacement.
`timescale 1ns/1ps
module tb_control_chain_counter_compare;
 import audio_defs_pkg::*;
 parameter integer DEPTH=3, LOCAL=2;
 logic clk=0; always #10 clk=~clk;
 logic rst_n=0, consumer_ready=0;
 logic [1:0] press=0,release_keys=0;
 wire [2:0] in_valid,in_ready,out_valid;
 performance_event_t in_data[0:2],out_data[0:2];
 wire [31:0] overflow[0:2];
 wire [15:0] level[0:2],peak[0:2];
 wire [2:0] unused_midi_ready;
 integer checks=0,cycles=0,base_transfers=0,conservative_transfers=0;
 logic [31:0] previous_overflow=0;
 logic [31:0] random_state=32'h683be921;
 logic observed_full_ready_difference=0;
 button_reference #(.BUTTON_COUNT(2),.LOCAL_FIFO_DEPTH(LOCAL)) b0(
  .clk(clk),.rst_n(rst_n),.button_press_pulse(press),.button_release_pulse(release_keys),
  .event_ready(in_ready[0]),.event_valid(in_valid[0]),.event_data(in_data[0]),.overflow_count(overflow[0]));
 button_reference #(.BUTTON_COUNT(2),.LOCAL_FIFO_DEPTH(LOCAL)) b1(
  .clk(clk),.rst_n(rst_n),.button_press_pulse(press),.button_release_pulse(release_keys),
  .event_ready(in_ready[1]),.event_valid(in_valid[1]),.event_data(in_data[1]),.overflow_count(overflow[1]));
 button_parallel_counter #(.BUTTON_COUNT(2),.LOCAL_FIFO_DEPTH(LOCAL)) b2(
  .clk(clk),.rst_n(rst_n),.button_press_pulse(press),.button_release_pulse(release_keys),
  .event_ready(in_ready[2]),.event_valid(in_valid[2]),.event_data(in_data[2]),.overflow_count(overflow[2]));
 for(genvar i=0;i<3;i++)begin:g_fifo
  if(i==1)begin
   fifo_no_full_bypass #(.DEPTH(DEPTH)) f(.clk(clk),.rst_n(rst_n),
    .button_valid(in_valid[i]),.button_ready(in_ready[i]),.button_data(in_data[i]),
    .midi_valid(1'b0),.midi_ready(unused_midi_ready[i]),.midi_data(performance_event_t'(64'd0)),
    .event_valid(out_valid[i]),.event_ready(consumer_ready),.event_data(out_data[i]),
    .event_fifo_level(level[i]),.event_fifo_high_watermark(peak[i]));
  end else begin
   fifo_reference #(.DEPTH(DEPTH)) f(.clk(clk),.rst_n(rst_n),
    .button_valid(in_valid[i]),.button_ready(in_ready[i]),.button_data(in_data[i]),
    .midi_valid(1'b0),.midi_ready(unused_midi_ready[i]),.midi_data(performance_event_t'(64'd0)),
    .event_valid(out_valid[i]),.event_ready(consumer_ready),.event_data(out_data[i]),
    .event_fifo_level(level[i]),.event_fifo_high_watermark(peak[i]));
  end
 end
 task automatic check(input logic condition,input string label);
  checks=checks+1;if(condition!==1'b1)$fatal(1,"%s at cycle%0d",label,cycles);
 endtask
 task automatic cycle(input logic reset,input logic ready,
                      input logic[1:0] ps,input logic[1:0] rs);
  @(negedge clk);rst_n=reset;consumer_ready=ready;press=ps;release_keys=rs;
  #1;
  check(in_ready[0]===in_ready[2],"counter candidate same ready");
  check(in_valid[0]===in_valid[2] && in_data[0]===in_data[2],"same source event");
  check(out_valid[0]===out_valid[2] && out_data[0]===out_data[2],"same output event");
  if(level[0]==DEPTH && ready && in_ready[0] && !in_ready[1])observed_full_ready_difference=1;
  @(posedge clk);
  if(rst_n && out_valid[0] && consumer_ready)base_transfers++;
  if(rst_n && out_valid[1] && consumer_ready)conservative_transfers++;
  #1;cycles++;
  check(level[0]===level[2] && peak[0]===peak[2],"same watermarks");
  if(!reset)begin check(overflow[2]===0,"reset clears delayed count");previous_overflow=0;end
  else begin check(overflow[2]===overflow[0],"counter exactly same cycle");previous_overflow=overflow[0];end
 endtask
 task automatic reset_all;
  cycle(0,0,0,0);cycle(0,0,0,0);cycle(1,0,0,0);
  base_transfers=0;conservative_transfers=0;
 endtask
 initial begin
  reset_all();
  // Fill public FIFO and local FIFO using genuine one-cycle external pulses.
  for(integer n=0;n<DEPTH+LOCAL;n++)begin
   cycle(1,0,2'b01,0);repeat(3)cycle(1,0,0,0);
  end
  check(level[0]==DEPTH && level[1]==DEPTH,"public queues full");
  check(b0.fifo_count==LOCAL && b1.fifo_count==LOCAL,"local queues full");
  check(overflow[0]==0 && overflow[1]==0,"no prior loss");
  cycle(1,1,2'b10,0);
  check(overflow[0]==0 && overflow[1]==1,"no-full-bypass introduces exactly one drop");
  check(observed_full_ready_difference,"ready chain distinction observed");
  repeat(DEPTH+LOCAL+5)cycle(1,1,0,0);
  check(base_transfers==DEPTH+LOCAL+1,"baseline delivered all directed events");
  check(conservative_transfers==DEPTH+LOCAL,"conservative lost directed event");
  $display("DIRECTED depth=%0d baseline_drop=%0d conservative_drop=%0d baseline_delivered=%0d conservative_delivered=%0d",DEPTH,overflow[0],overflow[1],base_transfers,conservative_transfers);
  reset_all();
  for(integer n=0;n<20000;n++)begin
   random_state=random_state^(random_state<<13);
   random_state=random_state^(random_state>>17);
   random_state=random_state^(random_state<<5);
   cycle(n%997!=0,random_state[8],random_state[1:0],random_state[3:2]);
  end
  repeat(DEPTH+LOCAL+5)cycle(1,1,0,0);
  check(overflow[0]==overflow[2],"counter same-cycle after drain");
  // Saturation test starts from a near-max known state in the bench only.
  reset_all();
  @(negedge clk);b0.overflow_count=32'hfffffffe;b2.overflow_count=32'hfffffffe;
  previous_overflow=32'hfffffffe;
  for(integer n=0;n<DEPTH+LOCAL;n++)begin cycle(1,0,2'b01,0);repeat(3)cycle(1,0,0,0);end
  cycle(1,0,2'b11,2'b11);cycle(1,0,2'b11,2'b11);cycle(1,0,0,0);
  check(overflow[0]==32'hffffffff && overflow[2]==32'hffffffff,"exact U32 saturation");
  // Exercise every legal per-cycle drop increment across carry/saturation edges.
  for(integer seed_index=0;seed_index<8;seed_index++)begin
   logic[31:0] seed;
   case(seed_index)
    0:seed=32'h00000000;1:seed=32'h000000fe;
    2:seed=32'h0000fffe;3:seed=32'h00fffffe;
    4:seed=32'h7ffffffe;5:seed=32'hfffffffc;
    6:seed=32'hfffffffe;default:seed=32'hffffffff;
   endcase
   for(integer increment=0;increment<=4;increment++)begin
    @(negedge clk);press=0;release_keys=0;consumer_ready=0;
    b0.overflow_count=seed;b2.overflow_count=seed;
    cycle(1,0,increment>=2 ? 2'b11 : (increment==1 ? 2'b01 : 2'b00),
                   increment==4 ? 2'b11 : (increment==3 ? 2'b01 : 2'b00));
    check(overflow[0]===overflow[2],"parallel same-cycle carry and saturation");
   end
  end
  cycle(0,0,0,0);check(overflow[2]==0,"reset kills pending count");
  if(checks<100000)$fatal(1,"empty or truncated run");
  $display("PASS control_chain_candidates depth=%0d checks=%0d cycles=%0d: no-bypass rejected; parallel counter fully cycle-equivalent",DEPTH,checks,cycles);$finish;
 end
 initial begin #5000000;$fatal(1,"candidate test timeout");end
endmodule
