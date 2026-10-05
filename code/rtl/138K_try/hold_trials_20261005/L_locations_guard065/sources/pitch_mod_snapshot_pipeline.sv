// M2 isolated four-lane FCW snapshot consumer, no formal audio-bank connection.
// Accept valid&ready once; parameters and identity metadata are frozen together.
// Each occupied lane owns its LFO. Result E+7, held until successful consumption.
// cancel removes a pending/held result but drains in-flight math before reuse;
// algorithm LFO progression is not rolled back (same generation policy as bank).
`timescale 1ns/1ps
module pitch_mod_snapshot_pipeline #(
 parameter OCT_FILE="E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/oct_ratio_q16.mem",
 parameter SUB_FILE="E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/sub_ratio_q16.mem",
 parameter LFO_FILE="E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/lfo_sine_q15.mem",
 parameter logic[31:0] LFO_INC=32'd447392,
 parameter logic[9:0] MOD_DEPTH_MAX_Q10=10'd512
)(
 input logic clk,rst_n,cancel,
 input logic request_valid,output wire request_ready,
 input logic[31:0]request_id,
 input logic[3:0]request_occupied,note_on_mask,
 input logic[15:0]request_sources,request_channels,
 input logic[127:0]request_generations,request_base_fcw,
 input logic[47:0]request_pitch_bend,request_modulation,
 input logic[19:0]request_pitch_range,
 output logic result_valid,input logic result_ready,
 output logic[31:0]result_id,
 output logic[3:0]result_occupied,
 output logic[15:0]result_sources,result_channels,
 output logic[127:0]result_generations,result_fcw
);
 logic busy,cancelled;logic[2:0]age;
 logic[31:0]held_id;
 logic[3:0]held_occupied;
 logic[15:0]held_sources,held_channels;
 logic[127:0]held_generations;
 wire accepted=request_valid&&request_ready;
 wire[127:0]lane_fcw;
 wire[3:0]lane_valid;
 assign request_ready=rst_n && !cancel && !busy && (!result_valid || result_ready);
 for(genvar lane=0;lane<4;lane++)begin:g_lane
  pitch_mod_fcw_pipeline #(.OCT_FILE(OCT_FILE),.SUB_FILE(SUB_FILE),.LFO_FILE(LFO_FILE),
       .LFO_INC(LFO_INC),.MOD_DEPTH_MAX_Q10(MOD_DEPTH_MAX_Q10))u_control(
   .sys_clk(clk),.sys_rst_n(rst_n),.sample_enable(accepted&&request_occupied[lane]),
   .note_on(note_on_mask[lane]),.bend($signed(request_pitch_bend[12*lane+:12])),
   .modulation(request_modulation[12*lane+:12]),.pitch_range(request_pitch_range[5*lane+:5]),
   .base_fcw(request_base_fcw[32*lane+:32]),.fcw_out(lane_fcw[32*lane+:32]),.fcw_valid(lane_valid[lane]));
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   busy<=0;cancelled<=0;age<=0;held_id<=0;held_occupied<=0;
   held_sources<=0;held_channels<=0;held_generations<=0;
   result_valid<=0;result_id<=0;result_occupied<=0;result_sources<=0;
   result_channels<=0;result_generations<=0;result_fcw<=0;
  end else begin
   if(result_valid && result_ready)result_valid<=0;
   if(cancel)begin result_valid<=0;if(busy)cancelled<=1;end
   if(accepted)begin
    busy<=1;cancelled<=0;age<=0;held_id<=request_id;held_occupied<=request_occupied;
    held_sources<=request_sources;held_channels<=request_channels;held_generations<=request_generations;
   end else if(busy)begin
    if(age==6)begin
     busy<=0;
     if(!cancelled && !cancel)begin
      result_valid<=1;result_id<=held_id;result_occupied<=held_occupied;
      result_sources<=held_sources;result_channels<=held_channels;result_generations<=held_generations;
      for(integer i=0;i<4;i++)result_fcw[32*i+:32]<=held_occupied[i] ? lane_fcw[32*i+:32] : 32'd0;
     end
    end else age<=age+1'b1;
   end
  end
 end
 // synthesis translate_off
 always @(posedge clk)if(rst_n && busy && age==6 && !cancelled && !cancel)
  for(integer i=0;i<4;i++)if(held_occupied[i] && !lane_valid[i])$fatal(1,"missing per-lane result token");
 // synthesis translate_on
endmodule
