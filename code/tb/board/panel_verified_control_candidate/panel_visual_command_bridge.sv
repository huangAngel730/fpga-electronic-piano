// Isolated accepted-event tap. NEVER has an audio-ready output.
// Bounded source FIFO+original reliable CDC mailbox; every queued command kept.
// Overflow is explicit/fail-closed, not silently treated as successful action.
// video_fault is an explicit display-transaction abort: held valid may cancel
// only with this fault. The consumer must pause/clear judgement until shared reset.
module panel_visual_command_bridge #(parameter integer DEPTH=16)(
 input logic sys_clk,pixel_clk,rst_n,accepted_valid,input logic[63:0]accepted_data,
 output wire video_valid,input logic video_ready,output wire[7:0]video_id,
 output logic[31:0]command_drop_count,output wire sys_reset_done,video_reset_done,output wire video_fault);
 import audio_defs_pkg::*;
 wire performance_event_t ev=accepted_data;
 localparam integer CW=$clog2(DEPTH+1),AW=$clog2(DEPTH);
 logic[7:0]queue[0:DEPTH-1];logic[AW-1:0]rd,wr;logic[CW-1:0]count;
 wire mailbox_ready,mailbox_video_valid;
 wire[7:0]mailbox_video_id;
 (* async_reg="true" *)logic fault_meta,fault_sync;
 assign video_fault=fault_sync;
 assign video_valid=mailbox_video_valid&&!fault_sync;
 assign video_id=mailbox_video_id;
 always_ff @(posedge pixel_clk or negedge rst_n)begin
  if(!rst_n)begin fault_meta<=0;fault_sync<=0;end
  else begin fault_meta<=command_drop_count!=0;fault_sync<=fault_meta;end
 end
 wire pop=count!=0&&mailbox_ready;
 wire wants=accepted_valid&&ev.event_type==EVENT_CONTROL_CHANGE&&ev.control_value==1&&(ev.control_id==8||ev.control_id==9);
 wire push=wants&&command_drop_count==0&&(count<DEPTH||pop);
 visual_mailbox_cdc #(.WIDTH(8))u_command(
  .src_clk(sys_clk),.dst_clk(pixel_clk),.rst_n(rst_n),.src_valid(count!=0),.src_ready(mailbox_ready),
  .src_data(queue[rd]),.dst_valid(mailbox_video_valid),.dst_ready(fault_sync||video_ready),.dst_data(mailbox_video_id),
  .src_reset_done(sys_reset_done),.dst_reset_done(video_reset_done));
 always_ff @(posedge sys_clk or negedge rst_n)begin
 if(!rst_n)begin rd<=0;wr<=0;count<=0;command_drop_count<=0;end
 else begin
  if(push)begin queue[wr]<=ev.control_id;wr<=wr==DEPTH-1?0:wr+1'b1;end
  else if(wants&&command_drop_count!=32'hffffffff)command_drop_count<=command_drop_count+1'b1;
  if(pop)rd<=rd==DEPTH-1?0:rd+1'b1;
  case({push,pop})2'b10:count<=count+1'b1;2'b01:count<=count-1'b1;default:begin end endcase
 end
 end
endmodule
