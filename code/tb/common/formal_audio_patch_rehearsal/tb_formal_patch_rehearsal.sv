`timescale 1ns/1ps
module tb_formal_patch_rehearsal;
import audio_defs_pkg::*;
logic sys_clk=0,sys_rst_n=0;always #10 sys_clk=~sys_clk;
logic[1:0]key_n=3;logic midi_rx=1;wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx;
electronic_piano_top dut(.*);
integer checks=0,bank_results=0,nonzero_pcm=0,pitch_changed=0,mod_changed=0;
logic[31:0]center_fcw;
task automatic ck(input logic ok,input string s);checks++;if(ok!==1'b1)$fatal(1,"formal patch %s",s);endtask
task automatic byte_in(input logic[7:0]b);
 @(negedge sys_clk);midi_rx=0;repeat(1600)@(negedge sys_clk);
 for(integer i=0;i<8;i++)begin midi_rx=b[i];repeat(1600)@(negedge sys_clk);end
 midi_rx=1;repeat(1600)@(negedge sys_clk);
endtask
task automatic msg(input logic[7:0]status,input logic[6:0]a,b);byte_in(status);byte_in({1'b0,a});byte_in({1'b0,b});endtask
task automatic frames(input integer n);
 integer before_count;before_count=dut.pcm_commit_count;
 wait(dut.pcm_commit_count>=before_count+n);@(negedge sys_clk);
 ck(dut.audio_underrun==0 && dut.status_clip_count==0,"no unintended audio underrun or clipping");
endtask
always @(posedge sys_clk)if(sys_rst_n)begin
 if(dut.g_polyphonic.u_audio_core.bank_valid && dut.g_polyphonic.u_audio_core.bank_ready)begin
  bank_results++;
  if(dut.g_polyphonic.u_audio_core.bank_occupied[0])begin
   if(dut.g_polyphonic.u_audio_core.bank_fcw[31:0]>center_fcw && center_fcw!=0)pitch_changed++;
  end
 end
 if(dut.buffered_left!=0)nonzero_pcm++;
end
initial begin
repeat(8)@(negedge sys_clk);ck(pa_en==1,"poweramp off reset");sys_rst_n=1;
msg(8'h90,7'd69,7'd127);wait(dut.status_active_voice_count==1);frames(16);
center_fcw=dut.g_polyphonic.u_audio_core.u_bank.slot_fcw[31:0];
ck(dut.g_polyphonic.u_audio_core.bank_fcw[31:0]==center_fcw,"center exact baseFCW");
msg(8'he0,7'd127,7'd127);frames(20);ck(dut.g_polyphonic.u_audio_core.bank_fcw[31:0]>center_fcw,"real UART bend modifies realDDS FCW");
msg(8'he0,7'd0,7'd64);msg(8'hb0,7'd1,7'd127);frames(64);
ck(dut.g_polyphonic.u_audio_core.u_bank.u_controls.initialized[0],"controltable accepted identity");
ck(dut.g_polyphonic.u_audio_core.u_bank.u_pitch_mod.g_lane[0].u_control.lfo_phase!=0,"real mod clock progression");
msg(8'hb0,7'd64,7'd127);msg(8'h80,7'd69,0);frames(8);
ck(dut.status_active_voice_count==1&&!dut.g_polyphonic.u_audio_core.u_bank.slot_releasing[0],"sustain keeps released actual voice");
msg(8'hb0,7'd64,0);frames(8);ck(dut.g_polyphonic.u_audio_core.u_bank.slot_releasing[0],"pedal off starts actual Release");
msg(8'h90,7'd69,7'd1);frames(8);ck(dut.status_active_voice_count==1,"real light retrigger");
@(negedge sys_clk);sys_rst_n=0;#1;ck(pa_en==1,"reset disables amplifier");repeat(8)@(negedge sys_clk);ck(dut.status_active_voice_count==0,"reset clears voices");
sys_rst_n=1;msg(8'h90,7'd72,7'd100);frames(8);
ck(nonzero_pcm>100 && bank_results>200 && pitch_changed>10,"not vacuous actual audio and controls");
$display("PASS production-path patch rehearsal checks=%0d results=%0d changed=%0d nonzeroPCMcycles=%0d",checks,bank_results,pitch_changed,nonzero_pcm);$finish;
end
initial begin #15000000;$fatal(1,"formal patch rehearsal timeout");end
endmodule
