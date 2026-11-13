`timescale 1ns/1ps
// R15 adapter of USER-SUPPLIED K4/M2 component, not R14 tone1 RTL.
// One true final-mix sender-load observer is exported for FFT reuse.
module k4_waveform_engine #(
 parameter integer DEPTH=32,
 parameter [31:0] FIRST_SEQ=0
)(
 input wire core_clk,core_rst_n,pixel_clk,pixel_rst_n,
 input wire audio_frame_load,
 input wire signed [23:0] play_left,play_right,
 input wire [15:0] pixel_x,pixel_y,
 input wire data_enable,frame_start,view_enable,
 output wire waveform_mask,
 output wire [23:0] waveform_rgb,
 output wire data_enable_out,
 output wire observed_valid,
 output wire [31:0] observed_seq,
 output wire signed [23:0] observed_left,observed_right,
 output wire trace_valid,
 output wire [31:0] display_gap_count,window_drop_count,
 output wire pixel_sample_valid,
 output wire [31:0] pixel_sample_seq,
 output wire signed [23:0] pixel_sample_left,pixel_sample_right,
 output wire stream_restart,
 output wire observation_enqueued,observation_dropped,
 output wire [15:0] observation_queue_level,
 output wire [31:0] observation_drop_count,
 output wire source_reset_done,pixel_reset_done,observer_reset_done
);
 wire waveform_rst_n;
 k4_pcm_waveform_observer_bridge #(.DEPTH(DEPTH),.FIRST_SEQ(FIRST_SEQ)) u_bridge(
  .audio_clk(core_clk),.pixel_clk(pixel_clk),.audio_rst_n(core_rst_n),.display_rst_n(pixel_rst_n),
  .audio_frame_load(audio_frame_load),.audio_play_left(play_left),.audio_play_right(play_right),
  .waveform_rst_n(waveform_rst_n),.stream_restart(stream_restart),
  .sample_valid(pixel_sample_valid),.sample_seq(pixel_sample_seq),
  .sample_left(pixel_sample_left),.sample_right(pixel_sample_right),
  .observed_valid(observed_valid),.observed_seq(observed_seq),
  .observed_left(observed_left),.observed_right(observed_right),
  .observation_enqueued(observation_enqueued),.observation_dropped(observation_dropped),
  .observation_queue_level(observation_queue_level),.observation_drop_count(observation_drop_count),
  .source_reset_done(source_reset_done),.pixel_reset_done(pixel_reset_done),.observer_reset_done(observer_reset_done)
 );
 wire mask_three;
 wire [7:0] r_three,g_three,b_three;
 k4_pcm_waveform_candidate u_renderer(
  .pixel_clk(pixel_clk),.pixel_rst_n(waveform_rst_n),
  .sample_valid(pixel_sample_valid),.sample_seq(pixel_sample_seq),
  .sample_left(pixel_sample_left),.sample_right(pixel_sample_right),
  .stream_restart(stream_restart),.pixel_x(pixel_x),.pixel_y(pixel_y),
  .data_enable(data_enable),.frame_start(frame_start),.waveform_enable(view_enable),
  .waveform_mask(mask_three),.waveform_r(r_three),.waveform_g(g_three),.waveform_b(b_three),
  .trace_valid(trace_valid),.display_gap_count(display_gap_count),.window_drop_count(window_drop_count)
 );
 reg [24:0] align_four,align_five;
 reg [4:0] de_pipe;
 always @(posedge pixel_clk or negedge waveform_rst_n)begin
  if(!waveform_rst_n)begin align_four<=0;align_five<=0;de_pipe<=0;end
  else begin align_four<={mask_three,r_three,g_three,b_three};align_five<=align_four;de_pipe<={de_pipe[3:0],data_enable};end
 end
 assign {waveform_mask,waveform_rgb}=align_five;
 assign data_enable_out=de_pipe[4];
endmodule
