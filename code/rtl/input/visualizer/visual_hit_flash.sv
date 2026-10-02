// Local per-pitch hit feedback, bounded by display range. No clocks/CDC owned.
// True hit pulses are accumulated and published only at frame boundaries.
`timescale 1ns/1ps
module visual_hit_flash #(
 parameter integer BASE_NOTE=36,NOTE_COUNT=49,FLASH_FRAMES=6
)(
 input logic clk,rst_n,frame_start,enabled,clear,
 input logic hit_pulse,
 input logic [6:0] hit_note_number,
 output wire [127:0] flash_active
);
 localparam integer COUNT_BITS=(FLASH_FRAMES<2) ? 1 : $clog2(FLASH_FRAMES+1);
 logic [COUNT_BITS-1:0] count_q[0:NOTE_COUNT-1];
 logic [NOTE_COUNT-1:0] pending_q;
 for(genvar n=0;n<NOTE_COUNT;n=n+1)begin:g_pitch
  logic visible_q;
  assign flash_active[BASE_NOTE+n]=visible_q;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin count_q[n]<=0;pending_q[n]<=0;visible_q<=0;end
   else if(!enabled || clear)begin count_q[n]<=0;pending_q[n]<=0;visible_q<=0;end
   else begin
    if(frame_start)begin
     pending_q[n]<=0;
     if(pending_q[n])begin count_q[n]<=COUNT_BITS'(FLASH_FRAMES);visible_q<=1;end
     else begin
      count_q[n]<=count_q[n]==0 ? COUNT_BITS'(0) : count_q[n]-1'b1;
      visible_q<=count_q[n]>1;
     end
    end
    // A hit exactly on a boundary belongs to the following complete frame.
    if(hit_pulse && hit_note_number==7'(BASE_NOTE+n))pending_q[n]<=1;
   end
  end
 end
 for(genvar note=0;note<128;note=note+1)begin:g_unused
  if(note<BASE_NOTE || note>=BASE_NOTE+NOTE_COUNT)assign flash_active[note]=1'b0;
 end
`ifndef SYNTHESIS
 initial if(FLASH_FRAMES<1 || FLASH_FRAMES>255 || BASE_NOTE<0 || NOTE_COUNT<1 || BASE_NOTE+NOTE_COUNT>128)
  $fatal(1,"invalid hit flash parameters");
`endif
endmodule
