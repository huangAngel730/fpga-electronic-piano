// M2 internal resource/STA probe. NEVER PROGRAM generated bitstream.
// Serial stimulus avoids exposing hundreds of ports; all result/tag bits have
// a readback path. This is an observability wrapper, not production encoding.
module pitch_mod_pipeline_timing_probe(
 input logic sys_clk,sys_rst_n,scan_load,
 input logic[15:0]scan_data,
 input logic drive_event,drive_request,drive_ready,cancel,
 input logic[4:0]observe_index,
 output logic[15:0]observed,
 output wire event_ready,request_ready,snapshot_valid,result_valid,
 output wire invalid_range
);
 wire rst_n;
 reset_sync u_reset(.clk(sys_clk),.rst_n(sys_rst_n),.rst_sync_n(rst_n));
 logic[391:0]stimulus;
 always_ff @(posedge sys_clk or negedge rst_n)
  if(!rst_n)stimulus<=0;else if(scan_load)stimulus<={stimulus[375:0],scan_data};
 wire[63:0]event_data=stimulus[63:0];
 wire[31:0]request_id=stimulus[95:64];wire[3:0]occupied=stimulus[99:96];
 wire[15:0]sources=stimulus[115:100],channels=stimulus[131:116];
 wire[127:0]generations=stimulus[259:132],base_fcw=stimulus[387:260];
 wire[3:0]note_on_mask=stimulus[391:388];
 wire snapshot_ready,control_applied;
 wire[31:0]sid,rid;wire[3:0]soccupied,roccupied;
 wire[15:0]ssources,schannels,rsources,rchannels;
 wire[127:0]sgenerations,rgenerations,fcw;
 wire[47:0]pitch,mod;wire[19:0]range_value;
 performance_control_snapshot u_controls(
  .clk(sys_clk),.rst_n(rst_n),.event_valid(drive_event),.event_ready(event_ready),.event_data(event_data),
  .request_valid(drive_request),.request_ready(request_ready),.request_id(request_id),
  .slot_occupied(occupied),.slot_source_ids(sources),.slot_channels(channels),.slot_generations(generations),
  .snapshot_valid(snapshot_valid),.snapshot_ready(snapshot_ready),.snapshot_id(sid),.snapshot_occupied(soccupied),
  .snapshot_sources(ssources),.snapshot_channels(schannels),.snapshot_generations(sgenerations),
  .snapshot_pitch_bend(pitch),.snapshot_modulation(mod),.snapshot_pitch_range(range_value),
  .control_applied(control_applied),.invalid_range(invalid_range));
 pitch_mod_snapshot_pipeline u_fcw(
  .clk(sys_clk),.rst_n(rst_n),.cancel(cancel),.request_valid(snapshot_valid),.request_ready(snapshot_ready),
  .request_id(sid),.request_occupied(soccupied),.note_on_mask(note_on_mask),
  .request_sources(ssources),.request_channels(schannels),.request_generations(sgenerations),
  .request_base_fcw(base_fcw),.request_pitch_bend(pitch),.request_modulation(mod),.request_pitch_range(range_value),
  .result_valid(result_valid),.result_ready(drive_ready),.result_id(rid),.result_occupied(roccupied),
  .result_sources(rsources),.result_channels(rchannels),.result_generations(rgenerations),.result_fcw(fcw));
 wire[335:0]readback={11'd0,control_applied,rid,roccupied,rsources,rchannels,rgenerations,fcw};
 always_comb begin observed=0;if(observe_index<21)observed=readback[16*observe_index+:16];end
endmodule
