`timescale 1ns/1ps
module tb_panel_visual_command_bridge;
import audio_defs_pkg::*;
logic sys_clk=0,pixel_clk=0;always #10 sys_clk=~sys_clk;always #23 pixel_clk=~pixel_clk;
logic rst_n=0,accepted=0,ready=0;performance_event_t ev='0;
wire vv,fault;wire[7:0]id;wire[31:0]drops;wire sd,vd;
panel_visual_command_bridge #(.DEPTH(8))dut(sys_clk,pixel_clk,rst_n,accepted,ev,vv,ready,id,drops,sd,vd,fault);
integer checks=0,outputs=0;logic[7:0]expected[0:63];integer queued=0;logic held=0;logic[7:0]heldid;
task automatic ck(input logic ok,input string msg);checks++;if(ok!==1'b1)$fatal(1,"panel CDC %s gotid%0d count%0d",msg,id,outputs);endtask
always @(posedge pixel_clk)begin
 if(!vd || fault)held=0;
 else begin
 if(held)ck(vv&&id==heldid,"video stalled payload stable");held=vv&&!ready;heldid=id;
 if(vv&&ready)begin ck(outputs<queued&&id==expected[outputs],"video commands exactly ordered");outputs++;end
 end
end
task automatic tap(input integer ctrl);@(negedge sys_clk);ev='0;ev.event_type=EVENT_CONTROL_CHANGE;ev.control_id=ctrl;ev.control_value=1;accepted=1;
 if(ctrl==8||ctrl==9)begin expected[queued]=ctrl;queued++;end
 @(negedge sys_clk);accepted=0;endtask
initial begin
repeat(5)@(negedge sys_clk);rst_n=1;wait(sd&&vd);
// Both clocks running, screen backpressured; audio tap has no ready wire.
tap(8);tap(9);tap(8);tap(9);tap(7);tap(2);repeat(15)@(negedge sys_clk);
ck(drops==0&&queued==4,"normal finite queue no merge/drop");ready=1;repeat(120)@(negedge sys_clk);ck(outputs==4,"CDC four ordered commands");
ready=0;repeat(3)@(negedge sys_clk);for(integer k=0;k<14;k++)tap(k%2?8:9);
repeat(20)@(negedge sys_clk);ck(drops>0&&fault&&!vv,"unbounded video backpressure reports finite overflow");
// Flush source and sink together after intentional loss; never replay old action.
rst_n=0;outputs=0;queued=0;repeat(5)@(negedge sys_clk);rst_n=1;ready=1;wait(sd&&vd);tap(9);repeat(100)@(negedge sys_clk);
ck(drops==0&&outputs==1,"reset flushes old queued commands and overflow");ck(checks>8,"nonempty CDC proof");
$display("PASS panel CDC checks=%0d",checks);$finish;
end
initial begin #2000000;$fatal(1,"CDC timeout");end
endmodule
