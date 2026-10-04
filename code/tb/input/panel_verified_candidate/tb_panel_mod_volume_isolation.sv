`timescale 1ns/1ps
module tb_panel_mod_volume_isolation;
import audio_defs_pkg::*;
logic clk=0;always #10 clk=~clk;logic rst_n=0,valid=0,ready=1;logic[7:0]b=0;
wire ev;performance_event_t data;wire[15:0]level,peak;wire[31:0]overflow,errors;
midi_event_parser #(.CLK_HZ(1000),.PANEL_CONTROL_ENABLE(1))dut(clk,rst_n,b,valid,1'b0,ready,ev,data,level,peak,overflow,errors);
integer checks=0,mods=0,vols=0;logic[11:0]last_mod=0;
task automatic ck(input logic ok,input string msg);checks++;if(ok!==1'b1)$fatal(1,"volume/mod isolation %s mods%0d vols%0d",msg,mods,vols);endtask
always @(posedge clk)if(rst_n&&ev&&ready)begin
 if(data.event_type==4&&data.control_id==1)begin mods++;last_mod=data.control_value;end
 if(data.event_type==4&&data.control_id==2)vols++;
end
task automatic octet(input logic[7:0]v);@(negedge clk);b=v;valid=1;@(negedge clk);valid=0;endtask
task automatic cc(input integer id,value);octet(8'hb0);octet(8'(id));octet(8'(value));endtask
initial begin
repeat(3)@(negedge clk);rst_n=1;cc(1,5);repeat(12)@(negedge clk);ck(mods==1&&dut.locked_index==1,"initialCC1 ack occupies odd old index");
ready=0;cc(7,70);repeat(8)@(negedge clk);ck(ev&&data.control_id==2,"volume held behind oldMod index");
cc(1,70);ck(dut.control_pending[1],"volume cannot cancel same-valued newMod before last ack");
ready=1;repeat(24)@(negedge clk);ck(vols==1&&mods==2&&last_mod==midi_cc_to_12bit(70),"distinctCC1 delivered not silently deduped");
cc(1,70);repeat(20)@(negedge clk);ck(mods==2,"real lastCC1 ack dedup still works");
ck(errors==0&&overflow==0,"no transport error");$display("PASS volume/CC1 isolation checks=%0d mods=%0d vols=%0d",checks,mods,vols);$finish;
end
initial begin #1000000;$fatal(1,"isolationtimeout");end
endmodule
