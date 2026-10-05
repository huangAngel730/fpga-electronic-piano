`define CHECK_LOOKAHEAD
`timescale 1ns/1ps
module tb_m2_parser_miter;
import audio_defs_pkg::*;
logic clk=0,rst_n=0,valid=0,err=0,ready=0;logic[7:0]byte_data=0;
always #10 clk=~clk;
integer cycles=0;
integer accepts[0:3],controls[0:3],stalls[0:3];
for(genvar i=0;i<4;i++)begin:g_pair
 localparam integer DEPTH=i==0?1:i==1?8:i==2?16:3;
 localparam integer BURST=i==0?1:i==3?3:8;
 localparam integer HZ=i==2?50000000:i==3?1:64000;
 wire nv,ov;performance_event_t nd,od;
 wire[15:0]nl,ol,np,op;wire[31:0]no,oo,ne,oe;
 midi_event_parser #(.LOCAL_FIFO_DEPTH(DEPTH),.SOURCE_ID(4'(i+4)),.CLK_HZ(HZ),.MAX_DISCRETE_BURST(BURST))dut(
 .clk(clk),.rst_n(rst_n),.midi_byte(byte_data),.midi_byte_valid(valid),.midi_byte_error(err),.event_ready(ready),
 .event_valid(nv),.event_data(nd),.event_fifo_level(nl),.event_fifo_high_watermark(np),.event_fifo_overflow_count(no),.parser_error_count(ne));
 midi_event_parser_frozen #(.LOCAL_FIFO_DEPTH(DEPTH),.SOURCE_ID(4'(i+4)),.CLK_HZ(HZ),.MAX_DISCRETE_BURST(BURST))ref_dut(
 .clk(clk),.rst_n(rst_n),.midi_byte(byte_data),.midi_byte_valid(valid),.midi_byte_error(err),.event_ready(ready),
 .event_valid(ov),.event_data(od),.event_fifo_level(ol),.event_fifo_high_watermark(op),.event_fifo_overflow_count(oo),.parser_error_count(oe));
 logic was_stalled=0;logic[63:0]held;
 always @(posedge clk)begin
  if(!rst_n)was_stalled=0;
  else begin
   if(was_stalled && (!nv || nd!==held))$fatal(1,"backpressure mismatch lane%0d",i);
   was_stalled=nv&&!ready;held=nd;
   if(was_stalled)stalls[i]++;
   if(nv&&ready)begin
    accepts[i]++;
    if(nd.event_type==EVENT_PITCH_BEND || (nd.event_type==EVENT_CONTROL_CHANGE && nd.control_id==CTRL_MODULATION))controls[i]++;
   end
  end
  #1;
  if(rst_n)begin
   if(dut.first_prepared_valid && dut.old_first_value!==dut.pending_value[dut.old_first_index])
    $fatal(1,"full parser buffer first payload stale lane=%0d cycle=%0d",i,cycles);
   if(dut.second_prepared_valid && dut.old_second_value!==dut.pending_value[dut.old_second_index])
    $fatal(1,"full parser buffer second payload stale lane=%0d cycle=%0d",i,cycles);
`ifdef CHECK_LOOKAHEAD
   if(dut.lookahead_rr_pending!==32'({dut.control_pending,dut.control_pending}>>dut.round_robin_index))
    $fatal(1,"lookahead rotation state mismatch lane=%0d cycle=%0d",i,cycles);
`endif
  end
  if({nv,nd,nl,np,no,ne}!=={ov,od,ol,op,oo,oe})$fatal(1,"full parser port equivalence mismatch lane=%0d cycle=%0d",i,cycles);
  if({dut.control_pending,dut.control_locked,dut.locked_event,dut.round_robin_index,dut.control_cooldown,dut.discrete_burst_count,dut.mod_sent_valid}!==
      {ref_dut.control_pending,ref_dut.control_locked,ref_dut.locked_event,ref_dut.round_robin_index,ref_dut.control_cooldown,ref_dut.discrete_burst_count,ref_dut.mod_sent_valid})
    $fatal(1,"full parser registered state mismatch lane=%0d cycle=%0d",i,cycles);
  if({dut.running_status,dut.first_data_byte,dut.channel_data_pending,dut.system_data_remaining,dut.sysex_active,dut.fifo_count}!==
     {ref_dut.running_status,ref_dut.first_data_byte,ref_dut.channel_data_pending,ref_dut.system_data_remaining,ref_dut.sysex_active,ref_dut.fifo_count})
    $fatal(1,"full parser decode/fifo state mismatch lane=%0d cycle=%0d",i,cycles);
  for(integer k=0;k<32;k++)if(dut.pending_value[k]!==ref_dut.pending_value[k])
    $fatal(1,"full parser pending payload state mismatch lane=%0d cycle=%0d",i,cycles);
  for(integer k=0;k<16;k++)if(dut.mod_sent_value[k]!==ref_dut.mod_sent_value[k])
    $fatal(1,"full parser last accepted payload state mismatch lane=%0d cycle=%0d",i,cycles);
  for(integer k=0;k<DEPTH;k++)if(dut.fifo_mem[k]!==ref_dut.fifo_mem[k])
    $fatal(1,"full parser FIFO contents mismatch lane=%0d cycle=%0d",i,cycles);
 end
end
logic[31:0]rng=32'h53acd188;
task automatic next_rng; rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);endtask
task automatic drive(input logic[7:0]b,input logic v,e,r);
 @(negedge clk);byte_data=b;valid=v;err=e;ready=r;cycles++;
endtask
task automatic msg(input logic[7:0]s,input logic[6:0]a,b);
 drive(s,1,0,ready);drive({1'b0,a},1,0,ready);if(s[7:4]!=4'hC&&s[7:4]!=4'hD)drive({1'b0,b},1,0,ready);
endtask
initial begin
 for(integer i=0;i<4;i++)begin accepts[i]=0;controls[i]=0;stalls[i]=0;end
 repeat(5)drive(0,0,0,0);rst_n=1;
 for(integer n=0;n<128;n++)begin
  msg(8'hE0|8'(n%16),7'(n),7'(127-n));msg(8'hB0|8'(n%16),7'd1,7'(n));
  msg(8'hC0|8'(n%16),7'(n),0);msg(8'h90|8'(n%16),7'(48+n%24),7'd100);
 end
 for(integer n=0;n<150000;n++)begin
  next_rng();
  if(n==80000)begin rst_n=0;repeat(3)drive(0,0,0,0);rst_n=1;end
  if(n%50000==0)msg(8'hE0,7'd0,7'd64);
  if(n%97==0)msg(8'hB0|8'(n%16),7'd64,7'(rng[6:0]));
  else if(n%17==0)msg(8'hE0|8'(n%16),7'(rng[6:0]),7'(rng[13:7]));
  else if(n%13==0)msg(8'hC0|8'(n%16),7'(rng[6:0]),0);
  else if(n%11==0)msg(8'h90|8'(n%16),7'(rng[6:0]),7'(rng[13:7]));
  else drive(rng[7:0],rng[10],rng[19:16]==0,rng[14]);
 end
 repeat(50010)drive(0,0,0,1);
 #3;
 for(integer i=0;i<4;i++)begin
  if(accepts[i]<100 || controls[i]<2 || stalls[i]<20)$fatal(1,"vacuous lane=%0d events%0d controls%0d stall%0d",i,accepts[i],controls[i],stalls[i]);
  $display("PASS M2 full original parser miter lane=%0d cycles=%0d events=%0d controls=%0d stalls=%0d",i,cycles,accepts[i],controls[i],stalls[i]);
 end
 $finish;
end
initial begin #30000000;$fatal(1,"miter timeout");end
endmodule
