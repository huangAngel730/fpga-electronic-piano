// Isolated B2/B3 contract. Pixel clock continues; commands execute in order
// at raster frame boundaries. No diagnostic automatic mode toggling.
module panel_score_transport #(parameter integer DEPTH=16)(
 input logic clk,rst_n,frame_start,command_valid,input logic[7:0]command_id,
 output wire command_ready,input logic score_complete,transport_fault,
 output logic display_mode,output logic[1:0]transport_state,
 output logic restart_pulse,output wire timeline_tick,match_enabled);
 localparam logic[1:0]READY=0,RUNNING=1,PAUSED=2,ENDED=3;
 localparam integer CW=$clog2(DEPTH+1),AW=DEPTH<=1?1:$clog2(DEPTH);
 logic[7:0]queue[0:DEPTH-1];logic[AW-1:0]rd,wr;logic[CW-1:0]count;
 logic next_mode;logic[1:0]next_state;logic restart_now;
 wire pop=!transport_fault && frame_start && count!=0;
 assign command_ready=rst_n && !transport_fault && (count<DEPTH || pop);
 wire push=command_valid&&command_ready;
 assign timeline_tick=rst_n && !transport_fault && frame_start && next_mode && next_state==RUNNING && !restart_now;
 assign match_enabled=rst_n && !transport_fault &&
     (frame_start ? (next_mode && next_state==RUNNING && !restart_now) :
                    (display_mode && transport_state==RUNNING));
 always_comb begin
  next_mode=display_mode;next_state=transport_state;restart_now=0;
  if(transport_fault)begin next_state=PAUSED;end
  else if(frame_start)begin
   if(display_mode && transport_state==RUNNING && score_complete)next_state=ENDED;
   if(pop)case(queue[rd])
    8:begin next_mode=~display_mode;if(!next_mode && next_state==RUNNING)next_state=PAUSED;end
    9:if(next_mode)case(next_state)
      READY,ENDED:begin next_state=RUNNING;restart_now=1;end
      RUNNING:next_state=PAUSED;
      PAUSED:next_state=RUNNING;
      default:next_state=READY;
     endcase
    default:begin end
   endcase
  end
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin display_mode<=0;transport_state<=READY;restart_pulse<=0;rd<=0;wr<=0;count<=0;end
  else begin
   restart_pulse<=0;
   if(frame_start || transport_fault)begin display_mode<=next_mode;transport_state<=next_state;restart_pulse<=restart_now;end
   if(push)begin queue[wr]<=command_id;wr<=wr==DEPTH-1?0:wr+1'b1;end
   if(pop)rd<=rd==DEPTH-1?0:rd+1'b1;
   case({push,pop})2'b10:count<=count+1'b1;2'b01:count<=count-1'b1;default:begin end endcase
  end
 end
 `ifndef SYNTHESIS
 initial if(DEPTH<2)$fatal(1,"command queue depth");
 `endif
endmodule
