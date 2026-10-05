// M2 isolated seven-register-stage implementation of accepted M1 arithmetic.
// Input pulse at E -> fcw_valid after E+6 NBA; consume at E+7.
// No ready: every sample_enable pulse is accepted, including adjacent pulses.
// ROM/base/control are sampled at E; later input changes cannot alter the result.
// note_on resets LFO whether or not a sample is launched; in-flight results stay
// valid. Voice-generation cancellation must be done by the enclosing scheduler.
`timescale 1ns/1ps
module pitch_mod_fcw_pipeline #(
 parameter OCT_FILE="E:/FPGA/GAOYUNFPGA/138K_try/pipeline_trials_20261005/C_payload_buffer/rom/oct_ratio_q16.mem",
 parameter SUB_FILE="E:/FPGA/GAOYUNFPGA/138K_try/pipeline_trials_20261005/C_payload_buffer/rom/sub_ratio_q16.mem",
 parameter LFO_FILE="E:/FPGA/GAOYUNFPGA/138K_try/pipeline_trials_20261005/C_payload_buffer/rom/lfo_sine_q15.mem",
 parameter logic[31:0] LFO_INC=32'd447392,
 parameter logic[31:0] FCW_MAX=32'h80000000,
 parameter logic[9:0] MOD_DEPTH_MAX_Q10=10'd512
)(
 input logic sys_clk,sys_rst_n,sample_enable,note_on,
 input logic signed[11:0]bend,
 input logic[11:0]modulation,
 input logic[4:0]pitch_range,
 input logic[31:0]base_fcw,
 output logic[31:0]fcw_out,
 output logic fcw_valid
);
 logic[19:0]oct_lut[0:49],sub_lut[0:1023];
 logic[19:0]sub_source[0:1023];
 // Bijective fractional-ROM addressing. Each bit is a real three-input XOR
 // of registered fraction bits, avoiding bare register-to-BSRAM address wires.
 // Data permutation is constant initialization; numerical lookup is unchanged.
 function automatic logic[9:0]encode_fraction(input logic[9:0]value);
  encode_fraction=value ^ {value[8:0],value[9]} ^ {value[6:0],value[9:7]};
 endfunction
 logic signed[15:0]lfo_lut[0:1023];
 // synthesis translate_off
 string oct_path,sub_path,lfo_path;
 integer rom_check;
 // synthesis translate_on
 initial begin
  $readmemh(OCT_FILE,oct_lut);$readmemh(SUB_FILE,sub_source);$readmemh(LFO_FILE,lfo_lut);
  // synthesis translate_off
  if($value$plusargs("OCT_PATH=%s",oct_path))begin
   rom_check=$fopen(oct_path,"r");if(!rom_check)$fatal(1,"missing requested OCT_PATH");$fclose(rom_check);
   $readmemh(oct_path,oct_lut);
  end
  if($value$plusargs("SUB_PATH=%s",sub_path))begin
   rom_check=$fopen(sub_path,"r");if(!rom_check)$fatal(1,"missing requested SUB_PATH");$fclose(rom_check);
   $readmemh(sub_path,sub_source);
  end
  if($value$plusargs("LFO_PATH=%s",lfo_path))begin
   rom_check=$fopen(lfo_path,"r");if(!rom_check)$fatal(1,"missing requested LFO_PATH");$fclose(rom_check);
   $readmemh(lfo_path,lfo_lut);
  end
  // synthesis translate_on
  for(integer address=0;address<1024;address=address+1)
   sub_lut[encode_fraction(10'(address))]=sub_source[address];
  // synthesis translate_off
  for(integer i=0;i<50;i++)if(^oct_lut[i]===1'bx)$fatal(1,"pipeline missing oct[%0d]",i);
  for(integer i=0;i<1024;i++)begin
   if(^sub_lut[i]===1'bx || ^lfo_lut[i]===1'bx)$fatal(1,"pipeline missing sub/LFO[%0d]",i);
  end
  // synthesis translate_on
 end
 logic[31:0]lfo_phase;
 wire[31:0]phase_now=note_on ? 32'd0 : lfo_phase;
 always_ff @(posedge sys_clk or negedge sys_rst_n)begin
  if(!sys_rst_n)lfo_phase<=0;
  else if(sample_enable)lfo_phase<=phase_now+LFO_INC;
  else if(note_on)lfo_phase<=0;
 end
 // Explicit 17-bit /22-bit products reproduce accepted width and floor rules.
 wire signed[16:0]bend_product=$signed(bend)*$signed({1'b0,pitch_range});
 wire[21:0]mod_product=modulation*{12'd0,MOD_DEPTH_MAX_Q10};
 wire[21:0]rounded_depth=mod_product+22'd2048;
 logic signed[15:0]sine_s0;
 logic[9:0]depth_s0;
 logic signed[16:0]semi_s0,semi_s1;
 logic signed[25:0]sine_product_s1;
 logic signed[17:0]total_s2;
 logic[19:0]oct_s3,sub_s3;
 logic[39:0]ratio_s4;
 logic[56:0]fcw_product_s5;
 logic[31:0]base_s0,base_s1,base_s2,base_s3,base_s4;
 logic[5:0]valid_pipe;
 wire signed[16:0]vib_s1=sine_product_s1>>>15;
 wire signed[17:0]q_s2=total_s2>>>10;
 wire[5:0]oct_index=(q_s2>18'sd24) ? 6'd49 :
                      (q_s2< -18'sd25) ? 6'd0 : q_s2[5:0]+6'd25;
 wire[9:0]sub_index=total_s2[9:0];
 wire[24:0]factor_s4={1'b0,ratio_s4[39:16]};
 wire[56:0]round_fc_product=fcw_product_s5+57'd32768;
 // Same33-bit output intermediate as accepted M1 implementation. Legal MIDI
 // base/range/depth guarantees the shifted value fits; invalid arbitrary bases
 // are not an expanded arithmetic guarantee in this pipeline experiment.
 wire[32:0]raw_fcw=round_fc_product>>16;
 // Synchronous ROM captures have no reset, allowing ROM inference. Valid is
 // reset independently; stale ROM data never qualifies as an output result.
 always_ff @(posedge sys_clk)begin
  if(sample_enable)sine_s0<=lfo_lut[phase_now[31:22]];
  if(valid_pipe[2])begin oct_s3<=oct_lut[oct_index];sub_s3<=sub_lut[encode_fraction(sub_index)];end
 end
 always_ff @(posedge sys_clk or negedge sys_rst_n)begin
  if(!sys_rst_n)begin
   valid_pipe<=0;fcw_valid<=0;fcw_out<=0;
   depth_s0<=0;semi_s0<=0;semi_s1<=0;sine_product_s1<=0;total_s2<=0;
   ratio_s4<=0;fcw_product_s5<=0;
   base_s0<=0;base_s1<=0;base_s2<=0;base_s3<=0;base_s4<=0;
  end else begin
   valid_pipe<={valid_pipe[4:0],sample_enable};
   fcw_valid<=valid_pipe[5];
   if(sample_enable)begin depth_s0<=rounded_depth>>12;semi_s0<=bend_product>>>1;base_s0<=base_fcw;end
   if(valid_pipe[0])begin
    sine_product_s1<=sine_s0*$signed({1'b0,depth_s0});semi_s1<=semi_s0;base_s1<=base_s0;
   end
   if(valid_pipe[1])begin total_s2<=$signed(semi_s1)+$signed(vib_s1);base_s2<=base_s1;end
   if(valid_pipe[2])base_s3<=base_s2;
   if(valid_pipe[3])begin ratio_s4<=oct_s3*sub_s3;base_s4<=base_s3;end
   if(valid_pipe[4])fcw_product_s5<=base_s4*factor_s4;
   if(valid_pipe[5])fcw_out<=raw_fcw>FCW_MAX ? FCW_MAX : raw_fcw[31:0];
  end
 end
 // synthesis translate_off
 always @(posedge sys_clk)if(sys_rst_n && sample_enable && pitch_range>24)
  $fatal(1,"pitch_range outside accepted0..24 contract");
 // synthesis translate_on
endmodule
