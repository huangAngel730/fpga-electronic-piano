// Self-authored 8-note C-major verification exercise, NOT an official song.
// Absolute hit frames relative to a restarted score epoch. 25MHz/800x525
// gives about59.5238Hz; no hard-coded assumption that a frame is1/60 second.
module panel_demo_score #(parameter integer PREVIEW_FRAMES=120,STEP_FRAMES=30,DURATION_FRAMES=12)(
 input logic clk,rst_n,restart,output wire score_valid,input logic score_ready,
 output wire[15:0]score_note_id,output logic[6:0]score_note_number,
 output wire[31:0]score_hit_frame,score_duration_frames,
 output wire score_duration_valid,output wire[9:0]score_velocity,
 output wire loaded,output wire[31:0]last_hit_frame);
 logic[3:0]index;
 assign score_valid=rst_n&&index<8;
 assign loaded=index==8;
 assign score_note_id={12'd0,index};
 assign score_hit_frame=32'(PREVIEW_FRAMES)+32'(index)*32'(STEP_FRAMES);
 assign score_duration_frames=32'(DURATION_FRAMES);assign score_duration_valid=1;
 assign score_velocity=700;assign last_hit_frame=32'(PREVIEW_FRAMES+7*STEP_FRAMES);
 always_comb case(index)
 0:score_note_number=60;1:score_note_number=62;2:score_note_number=64;3:score_note_number=65;
 4:score_note_number=67;5:score_note_number=69;6:score_note_number=71;7:score_note_number=72;
 default:score_note_number=0;
 endcase
 always_ff @(posedge clk or negedge rst_n)begin
 if(!rst_n)index<=0;else if(restart)index<=0;else if(score_valid&&score_ready)index<=index+1'b1;
 end
endmodule
