`timescale 1ns/1ps
module tb_panel_score_transport;
import audio_defs_pkg::*;
logic clk=0;always #20 clk=~clk;
logic rst_n=0,frame=0,cmd_valid=0,fault=0;logic[7:0]cmd_id=0;
wire ready,mode,restart,tick,match_enable;wire[1:0]state;
wire[31:0]current,hit_frame,duration,last_hit;wire valid,score_ready,duration_valid,loaded;
wire[15:0]id;wire[6:0]note;wire[9:0]velocity;
wire[7:0]slots;wire[127:0]ids;wire[55:0]notes;wire[79:0]ys,tops,ends,vel;
wire[7:0]hit,miss;wire hp;wire[6:0]hn;
wire complete=loaded && current>=last_hit+12 && slots==0;
performance_event_t performance='0;
panel_score_transport control(.clk(clk),.rst_n(rst_n),.frame_start(frame),.command_valid(cmd_valid),.command_id(cmd_id),.command_ready(ready),.score_complete(complete),.transport_fault(fault),.display_mode(mode),.transport_state(state),.restart_pulse(restart),.timeline_tick(tick),.match_enabled(match_enable));
panel_demo_score #(.PREVIEW_FRAMES(4),.STEP_FRAMES(3),.DURATION_FRAMES(2))demo(
 .clk(clk),.rst_n(rst_n),.restart(restart),.score_valid(valid),.score_ready(score_ready),.score_note_id(id),.score_note_number(note),.score_hit_frame(hit_frame),.score_duration_frames(duration),.score_duration_valid(duration_valid),.score_velocity(velocity),.loaded(loaded),.last_hit_frame(last_hit));
visual_score_tracker_transport #(.PREVIEW_FRAMES(4),.TRAVEL_Y(20),.STRICT_CONTACT(1),.BOTTOM_EXIT_GEOMETRY(1),.RASTER_HEIGHT(40))tracker(
 .clk(clk),.rst_n(rst_n),.frame_start(tick),.transport_clear(restart),
 .score_valid(valid&&!restart),.score_ready(score_ready),.score_note_id(id),.score_note_number(note),.score_hit_frame(hit_frame),.score_duration_valid(duration_valid),.score_duration_frames(duration),.score_velocity(velocity),
 .performance_fire(1'b0),.match_enabled(match_enable),.performance_data(performance),.video_desync(1'b0),
 .current_frame(current),.slot_valid(slots),.slot_note_id(ids),.slot_note_number(notes),.slot_y(ys),.slot_top_y(tops),.slot_end_y(ends),.slot_velocity(vel),.slot_hit(hit),.slot_miss(miss),.hit_pulse(hp),.hit_note_number(hn));
integer checks=0,restarts=0,scanframes=0,loaded_count=0;
logic[31:0]saved;
task automatic ck(input logic ok,input string msg);checks++;if(ok!==1'b1)$fatal(1,"score transport %s state=%0d mode=%0d time=%0d",msg,state,mode,current);endtask
always @(posedge clk)begin if(rst_n&&restart)restarts++;if(rst_n&&frame)begin
 if(mode&&state==1&&control.count!=0&&control.queue[control.rd]==9)ck(!tick&&!match_enable,"pause boundary cancels same-frame judgement");
 scanframes++;end
if(rst_n&&valid&&score_ready&&!restart)loaded_count++;end
task automatic command(input integer idv);@(negedge clk);wait(ready);cmd_id=idv;cmd_valid=1;@(negedge clk);cmd_valid=0;endtask
task automatic frames(input integer n);for(integer k=0;k<n;k++)begin @(negedge clk);frame=1;@(negedge clk);frame=0;repeat(16)@(negedge clk);end endtask
initial begin
repeat(4)@(negedge clk);rst_n=1;repeat(16)@(negedge clk);
ck(!mode&&state==0&&current==0&&loaded,"reset upper/ready exercise loaded");frames(5);ck(current==0,"scan does not advance paused score");
command(9);frames(1);ck(state==0&&current==0,"upper B3 ignores hidden start");
command(8);ck(!mode,"mode only changes frame boundary");frames(1);ck(mode&&state==0,"first falling mode ready");
command(9);frames(1);ck(state==1&&current==0&&restarts==1,"first start clears score and gives full preview");
frames(3);ck(current==3&&match_enable,"running timeline advances");
command(9);frames(1);saved=current;ck(state==2&&!match_enable,"pause stops judgement");frames(8);ck(current==saved,"pause scan continues position frozen");
command(9);frames(1);ck(state==1&&current==saved+1&&restarts==1,"resume original position not restart");
command(8);frames(1);saved=current;ck(!mode&&state==2,"leave falling auto pauses");frames(4);ck(current==saved,"upper preserves position");
command(9);frames(1);ck(state==2&&current==saved,"upper does not secretly resume");command(8);frames(1);ck(mode&&state==2&&current==saved,"return falling still paused");command(9);frames(1);ck(state==1&&current==saved+1,"explicit resume after return");
begin integer guard;guard=0;while(state!=3 && guard<200)begin frames(1);guard++;end ck(guard<200&&complete,"finite exercise reaches ended only after cues exit");end
saved=current;frames(6);ck(current==saved&&state==3,"ended scan stable");command(9);frames(1);ck(current==0&&state==1&&restarts==2,"ended restart clears epoch not old judgement");frames(2);ck(current==2,"restarted timeline");
command(8);command(8);frames(1);ck(!mode&&state==2,"two toggles first applies no merge");frames(1);ck(mode&&state==2,"two toggles second applies in order");
command(9);command(9);frames(1);ck(state==1,"two transports first resumes");frames(1);ck(state==2,"two transports second pauses");
fault=1;#1;ck(!tick&&!match_enable&&!ready,"explicit display fault blocks timeline/judgement/commands");@(negedge clk);ck(state==2,"fault forces paused state");
rst_n=0;#1;ck(!mode&&state==0&&current==0,"reset flush queued command and score");
repeat(4)@(negedge clk);rst_n=1;fault=0;frames(2);ck(state==0&&current==0,"no stale commands after reset");
ck(checks>=24&&scanframes>40&&loaded_count>=24,"nonempty episode coverage");$display("PASS score transport checks=%0d scans=%0d restarts=%0d cues=%0d",checks,scanframes,restarts,loaded_count);$finish;
end
initial begin #5000000;$fatal(1,"score transport timeout");end
endmodule
