// R01 contract wrapper. Human audio is observed only after its final acceptance;
// neither display backpressure nor STOP can reach the independent human path.
module pro_score_visual (
    input wire core_clk, pixel_clk, serial_clk, rst_n, sample_tick,
    input wire [2:0] page_select,
    input wire audio_frame_load,
    input wire signed [23:0] play_left,play_right,
    input wire accepted_valid,
    input audio_defs_pkg::performance_event_t accepted_data,
    output wire event_valid,
    input wire event_ready,
    output audio_defs_pkg::performance_event_t event_data,
    input wire command_valid,
    input wire [1:0] command_kind,
    output wire command_ready, command_done,
    output wire [7:0] command_error,
    input wire committed_valid,
    input wire [9:0] committed_count,
    input wire [31:0] committed_score_id, committed_generation,
    input wire committed_bank, full_read_verified,
    output wire rd_req,
    output wire [8:0] rd_index,
    input wire rd_valid,
    input wire [63:0] rd_event,
    output wire lease_busy,
    output wire tmds_clk_p, tmds_clk_n,
    output wire [2:0] tmds_data_p, tmds_data_n,
    output wire [31:0] visual_drop_count,
    output wire desync_latched
);
    // Shared asynchronous assertion; release takes two local core edges.
    (* ASYNC_REG = "TRUE" *) reg [1:0] core_reset_sync;
    always @(posedge core_clk or negedge rst_n)
        if (!rst_n) core_reset_sync <= 0;
        else core_reset_sync <= {core_reset_sync[0],1'b1};
    wire core_rst_n = core_reset_sync[1];
    wire score_valid, score_ready, flush_req, flush_ack;
    wire [97:0] score_payload;
    wire [31:0] global_tick, frame_snapshot;
    wire frame_snapshot_valid, frame_snapshot_pulse;
    wire [31:0] anchor_frame, anchor_tick;
    wire [11:0] anchor_phase;
    // The anchor and scheduler are separate registered blocks in the same
    // core clock domain.  Preserve the exact phase value and capture cycle,
    // while adding physical delay to the otherwise zero-logic short path.
    (* syn_keep=1, syn_dont_touch=1 *) wire [11:0] scheduler_anchor_phase_hold;
    for(genvar anchor_phase_bit=0;anchor_phase_bit<12;anchor_phase_bit=anchor_phase_bit+1)begin:g_anchor_phase_hold
        (* syn_keep=1, syn_dont_touch=1 *)wire[2:0]chain;
        assign chain[0]=anchor_phase[anchor_phase_bit];
        for(genvar anchor_phase_stage=0;anchor_phase_stage<2;anchor_phase_stage=anchor_phase_stage+1)begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *)LUT1 #(.INIT(2'h2))u_identity(
                .I0(chain[anchor_phase_stage]),.F(chain[anchor_phase_stage+1]));
        end
        assign scheduler_anchor_phase_hold[anchor_phase_bit]=chain[2];
    end
    wire anchor_valid, scheduler_fault;
    wire human_accepted = accepted_valid &&
        (accepted_data.source_id == 4'd0 || accepted_data.source_id == 4'd1);

    // UI selection observes the same accepted voice-control event as audio.
    // It never feeds back into audio and does not relabel held voices/PCM.
    logic selected_timbre;
    always_ff @(posedge core_clk or negedge core_rst_n)begin
        if(!core_rst_n)selected_timbre<=1'b0;
        else if(human_accepted &&
                accepted_data.event_type==audio_defs_pkg::EVENT_CONTROL_CHANGE &&
                (accepted_data.control_id==8'd18 ||
                 (accepted_data.control_id==audio_defs_pkg::CTRL_VOICE_SELECT &&
                  accepted_data.control_value<=12'd1)))
            selected_timbre<=accepted_data.control_value==12'd1;
    end

    pro_visual_anchor u_anchor (
        .core_clk(core_clk), .rst_n(core_rst_n), .sample_tick(sample_tick),
        .global_tick(global_tick), .frame_snapshot(frame_snapshot),
        .frame_snapshot_valid(frame_snapshot_valid),
        .frame_snapshot_pulse(frame_snapshot_pulse),
        .anchor_frame(anchor_frame), .anchor_tick(anchor_tick),
        .anchor_phase(anchor_phase), .anchor_valid(anchor_valid)
    );
    pro_score_scheduler u_scheduler (
        .core_clk(core_clk), .rst_n(core_rst_n), .sample_tick(sample_tick),
        .event_valid(event_valid), .event_ready(event_ready), .event_data(event_data),
        .command_valid(command_valid), .command_kind(command_kind),
        .command_ready(command_ready), .command_done(command_done),
        .command_error(command_error), .committed_valid(committed_valid),
        .committed_count(committed_count), .committed_score_id(committed_score_id),
        .committed_generation(committed_generation), .committed_bank(committed_bank),
        .full_read_verified(full_read_verified), .rd_req(rd_req), .rd_index(rd_index),
        .rd_valid(rd_valid), .rd_event(rd_event), .lease_busy(lease_busy),
        .score_valid(score_valid), .score_ready(score_ready), .score_payload(score_payload),
        .flush_req(flush_req), .flush_ack(flush_ack),
        .anchor_frame(anchor_frame), .anchor_tick(anchor_tick),
        .anchor_phase(scheduler_anchor_phase_hold), .anchor_valid(anchor_valid),
        .global_tick(global_tick), .fault_latched(scheduler_fault)
    );
    pro_score_display u_display (
        .core_clk(core_clk), .pixel_clk(pixel_clk), .serial_clk(serial_clk),
        .rst_n(rst_n),.page_select(page_select),.selected_timbre(selected_timbre),.audio_frame_load(audio_frame_load),
        .play_left(play_left),.play_right(play_right), .accepted_valid(human_accepted && core_rst_n),
        .accepted_data(accepted_data), .score_valid(score_valid), .score_ready(score_ready),
        .score_payload(score_payload), .flush_req(flush_req), .flush_ack(flush_ack),
        .external_fault(scheduler_fault),
        .frame_snapshot(frame_snapshot), .frame_snapshot_valid(frame_snapshot_valid),
        .frame_snapshot_pulse(frame_snapshot_pulse),
        .tmds_clk_p(tmds_clk_p), .tmds_clk_n(tmds_clk_n),
        .tmds_data_p(tmds_data_p), .tmds_data_n(tmds_data_n),
        .visual_drop_count(visual_drop_count), .desync_latched(desync_latched)
    );
endmodule
