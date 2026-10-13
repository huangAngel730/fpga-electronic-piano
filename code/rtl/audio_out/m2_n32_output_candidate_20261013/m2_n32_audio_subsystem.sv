// Isolated fixed N32/R1 shell. Existing source/sender/observer/math readonly.
// This is not the production top and has no new event or STAT protocol.
module m2_n32_audio_subsystem (
    input wire clk,pixel_clk,rst_n,display_rst_n,
    input wire event_valid,input wire [63:0] event_data,output wire event_ready,
    input wire read_valid,input wire [4:0] read_slot,
    output wire read_ready,read_out_valid,output wire [73:0] read_context,
    output wire signed [23:0] play_left,play_right,
    output wire bclk,lrck,din,frame_tick,commit_pulse,
    output wire [31:0] frame_count,frame_request_count,commit_count,underrun_count,clip_count,
    output wire [31:0] active_voice_count,max_processing_cycles,
    output wire [31:0] occupied,
    output wire [255:0] notes,
    output wire result_valid,result_ready,
    output wire [31:0] result_id,
    output wire signed [23:0] result_left,result_right,
    output wire result_clip,
    output wire sample_request_valid,sample_request_ready,
    output wire [31:0] sample_request_id,
    output wire [31:0] committed_id,
    output wire signed [23:0] committed_left,committed_right,
    output wire committed_clip,
    output wire observed_valid,output wire [31:0] observed_seq,
    output wire signed [23:0] observed_left,observed_right,
    output wire waveform_rst_n,stream_restart,sample_valid,
    output wire [31:0] sample_seq,
    output wire signed [23:0] sample_left,sample_right,
    output wire [31:0] observation_drop_count,
    output wire late,aborted,idle,fault,output wire [1:0] abort_reason
);
    wire cancel;
    m2_b2d_event_audio_prom #(.N(32),.RESPONSE(1)) candidate (
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.event_valid(event_valid),.event_data(event_data),.event_ready(event_ready),
        .sample_valid(sample_request_valid),.sample_ready(sample_request_ready),.sample_id(sample_request_id),
        .result_valid(result_valid),.result_ready(result_ready),.result_id(result_id),
        .left(result_left),.right(result_right),.clipped(result_clip),.late(late),
        .aborted(aborted),.abort_reason(abort_reason),.idle(idle),.fault(fault),.occupied(occupied),.notes(notes),
        .read_valid(read_valid),.read_slot(read_slot),.read_ready(read_ready),.read_out_valid(read_out_valid),.read_context(read_context),
        .inject_valid(1'b0),.inject_tag(77'd0),.inject_context(74'd0)
    );
    m2_n32_output_transport output_path (
        .clk(clk),.pixel_clk(pixel_clk),.rst_n(rst_n),.display_rst_n(display_rst_n),
        .candidate_cancel(cancel),.candidate_sample_valid(sample_request_valid),.candidate_sample_ready(sample_request_ready),
        .candidate_sample_id(sample_request_id),.candidate_result_valid(result_valid),.candidate_result_ready(result_ready),
        .candidate_result_id(result_id),.candidate_left(result_left),.candidate_right(result_right),.candidate_clipped(result_clip),
        .play_left(play_left),.play_right(play_right),.bclk(bclk),.lrck(lrck),.din(din),.frame_tick(frame_tick),.commit_pulse(commit_pulse),
        .frame_count(frame_count),.frame_request_count(frame_request_count),.commit_count(commit_count),.underrun_count(underrun_count),.clip_count(clip_count),
        .committed_id(committed_id),.committed_left(committed_left),.committed_right(committed_right),.committed_clip(committed_clip),
        .observed_valid(observed_valid),.observed_seq(observed_seq),.observed_left(observed_left),.observed_right(observed_right),
        .waveform_rst_n(waveform_rst_n),.stream_restart(stream_restart),.sample_valid(sample_valid),.sample_seq(sample_seq),
        .sample_left(sample_left),.sample_right(sample_right),.observation_drop_count(observation_drop_count)
    );
    // Balanced population of occupied slots, including release tails, 0..32.
    wire [5:0] p1[0:15],p2[0:7],p3[0:3],p4[0:1];
    for(genvar i=0;i<16;i++)assign p1[i]={5'd0,occupied[2*i]}+{5'd0,occupied[2*i+1]};
    for(genvar i=0;i<8;i++)assign p2[i]=p1[2*i]+p1[2*i+1];
    for(genvar i=0;i<4;i++)assign p3[i]=p2[2*i]+p2[2*i+1];
    for(genvar i=0;i<2;i++)assign p4[i]=p3[2*i]+p3[2*i+1];
    wire [5:0] population=p4[0]+p4[1];
`ifdef M2_SUBSYSTEM_BAD_COUNT
    assign active_voice_count={27'd0,population[4:0]};
`else
    assign active_voice_count={26'd0,population};
`endif
    // Frame credit is produced on the frame edge and observed next edge,
    // exactly like the old frame_buffer sample_req. Includes READ/DRAIN wait.
    reg frame_credit;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)frame_credit<=1'b0;else frame_credit<=frame_tick;
    wire latency_request;
`ifdef M2_SUBSYSTEM_BAD_LATENCY
    assign latency_request=sample_request_valid && sample_request_ready;
`else
    assign latency_request=frame_credit;
`endif
    system_status_counters latency (
        .clk(clk),.rst_n(rst_n),.pcm_request(latency_request),.pcm_commit(commit_pulse),
        .button_overflow(32'd0),.midi_overflow(32'd0),.max_processing_cycles(max_processing_cycles)
    );
endmodule
