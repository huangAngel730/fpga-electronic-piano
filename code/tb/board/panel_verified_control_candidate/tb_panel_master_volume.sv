`timescale 1ns/1ps
module tb_panel_master_volume;
import audio_defs_pkg::*;
logic clk=0;always #10 clk=~clk;logic rst_n=0,tick=0,accepted=0;
performance_event_t ev='0;wire[16:0]gain,target;
panel_master_volume_proposal dut(clk,rst_n,tick,accepted,ev,gain,target);
logic cancel=0,request=0,ready=0;wire request_ready,result_valid;
logic[31:0]qid=0;logic signed[23:0]ql=0,qr=0;logic[16:0]qg=0;
wire[31:0]id;wire signed[23:0]left,right;
panel_pcm_gain_stage stage(clk,rst_n,cancel,request,request_ready,qid,ql,qr,qg,result_valid,ready,id,left,right);
integer checks=0,results=0;logic[31:0]rng=32'h287dbabc;logic[16:0]oldg;logic signed[63:0]pl,pr;
task automatic ck(input logic cond,input string reason);checks++;if(cond!==1'b1)$fatal(1,"volume proposal %s gain%0d target%0d",reason,gain,target);endtask
task automatic cc(input integer value,source);@(negedge clk);ev='0;ev.event_type=EVENT_CONTROL_CHANGE;ev.source_id=source;ev.channel=0;ev.control_id=CTRL_VOLUME;ev.control_value=midi_cc_to_12bit(7'(value));accepted=1;@(negedge clk);accepted=0;endtask
task automatic samples(input integer count);for(integer n=0;n<count;n++)begin @(negedge clk);oldg=gain;tick=1;@(negedge clk);tick=0;ck(gain<=65536&& (gain>oldg?gain-oldg:oldg-gain)<=128,"bounded update once per logical sample");end endtask
initial begin
repeat(4)@(negedge clk);rst_n=1;repeat(4)@(negedge clk);ck(gain==65536&&target==65536,"default exact unity no MIDI");
cc(0,6);ck(target==65536,"unconfigured source cannot alter global gain");cc(0,0);samples(512);ck(gain==0&&target==0,"exact mute endpoint after bounded slew");
cc(127,0);samples(512);ck(gain==65536&&target==65536,"exact no-amplification max");
for(integer x=0;x<128;x++)begin cc(x,0);ck(target==(x*65536+63)/127,"raw7 exact target mapping");samples(1);end
// Stable old sample/id while CC gain changes; math stage independent of controller.
for(integer k=0;k<1000;k++)begin
 rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
 wait(request_ready);@(negedge clk);qid=k;ql=24'(rng);qr=-ql;qg=k==0?0:k==1?65536:17'(rng%65537);pl=$signed(ql)*$signed({1'b0,qg});pr=$signed(qr)*$signed({1'b0,qg});request=1;
 @(negedge clk);request=0;qg=0;ql=0;qr=0;wait(result_valid);@(negedge clk);
 ck(id==k&&left===24'(pl>>>16)&&right===24'(pr>>>16),"signed floor gain and request frozen");
 repeat(3)begin @(negedge clk);ck(result_valid&&id==k&&left===24'(pl>>>16),"held output immutable");end
 ready=1;@(negedge clk);ready=0;results++;
end
wait(request_ready);request=1;qg=65536;qid=32'hffffffff;ql=123;@(negedge clk);request=0;cancel=1;#1;ck(!result_valid&&!request_ready,"cancel suppresses both handshakes");@(negedge clk);cancel=0;repeat(4)@(negedge clk);ck(!result_valid,"cancel never republishes old result");
rst_n=0;#1;ck(gain==65536&&!result_valid,"reset restores default and clears token");
ck(checks>4000&&results==1000,"nonempty math sample count");$display("PASS volume proposal checks=%0d results=%0d",checks,results);$finish;
end
initial begin #5000000;$fatal(1,"volume timeout");end
endmodule
