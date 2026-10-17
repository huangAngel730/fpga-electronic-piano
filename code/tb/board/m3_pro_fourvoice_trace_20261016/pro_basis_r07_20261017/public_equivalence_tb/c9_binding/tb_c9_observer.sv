`timescale 1ns/1ps
// C9 paired-lane static successor. Compile each lane in an isolated universe.
// External pins only; public C9 wire connections. No private hierarchy.
module tb_c9_observer;
    reg sys_clk_50m=0,reference_40m=0;
    always #10 sys_clk_50m=~sys_clk_50m;
    always #12.5 reference_40m=~reference_40m;
    wire rst_n,midi_rx,unused_ready;
    wire [12:0] pins;
    integer fd,event_fd=0,companion_fd=0,cycle=0;
    integer start_compare=1200,stop_cycle=12000000;
    real event_time_ps,finish_time_ps;
    string trace_path,event_path,companions_path;
    wire c9_obs_core_clk;
    wire c9_obs_polyphonic_valid;
    wire c9_obs_rst_n;
    wire c9_obs_frame_tick;
    wire c9_obs_event_valid;
    wire c9_obs_event_ready;
    wire [63:0] c9_obs_event_data;
    wire c9_obs_req_valid;
    wire c9_obs_req_ready;
    wire c9_obs_result_valid;
    wire c9_obs_result_ready;
    wire [31:0] c9_obs_result_id;
    wire signed [23:0] c9_obs_result_left;
    wire signed [23:0] c9_obs_result_right;
    wire [1:0] c9_obs_result_clip_mask;
    wire [31:0] c9_obs_req_id;
    wire c9_obs_commit;
    wire [31:0] c9_obs_commit_id;
    wire signed [23:0] c9_obs_commit_left;
    wire signed [23:0] c9_obs_commit_right;
    wire c9_obs_commit_clip;
    wire c9_obs_cancel;
    wire c9_obs_config_valid;
    wire c9_obs_config_ready;
    wire signed [23:0] c9_obs_tx_left;
    wire signed [23:0] c9_obs_tx_right;
    wire c9_obs_pll_locked;
    wire c9_obs_tx_sample_valid;
    wire c9_obs_tx_metadata_valid;
    wire c9_obs_tx_req_id_valid;
    wire [31:0] c9_obs_tx_frame_id;
    wire [31:0] c9_obs_tx_req_id;
    wire [1:0] c9_obs_tx_clip_mask;
    wire c9_obs_tx_clip_any;
    wire c9_obs_tx_hold;
    wire c9_obs_tx_startup_zero;
    wire c9_obs_metadata_error;
    wire c9_obs_frame_id_overflow;
    wire [1:0] c9_obs_raw_cancel_reason;
    wire c9_obs_apply_valid;
    wire [63:0] c9_obs_apply_data;
    wire [3:0] c9_obs_occupied_mask;
    wire [3:0] c9_obs_releasing_mask;
    wire [3:0] c9_obs_note_on_mask;
    wire [3:0] c9_obs_note_off_mask;
    wire [3:0] c9_obs_retire_mask;
    wire [15:0] c9_obs_slot_sources;
    wire [15:0] c9_obs_slot_channels;
    wire [31:0] c9_obs_slot_notes;
    wire [127:0] c9_obs_slot_generations;
    wire [3:0] c9_obs_advance_mask;
    wire [31:0] c9_obs_advance_frame_req_id;
    wire c9_obs_effect_input_valid;
    wire c9_obs_effect_input_ready;
    wire [31:0] c9_obs_effect_input_id;
    wire signed [23:0] c9_obs_effect_input_left;
    wire signed [23:0] c9_obs_effect_input_right;
    wire [1:0] c9_obs_effect_input_clip_mask;
    wire [3:0] c9_obs_apply_kind;
    wire [3:0] c9_obs_apply_mask;
    wire [31:0] c9_obs_router_apply_seq;
    wire c9_obs_router_apply_seq_valid;
    wire c9_obs_config_take;
    wire [61:0] c9_obs_config_payload;
    wire [1:0] c9_obs_upstream_clip_mask;
    wire [1:0] c9_obs_effect_clip_mask;
    wire [1:0] c9_obs_feedback_clip_mask;
    midi_public_port_driver #(.EVENT_LOG("driver_events.log")) driver(
        .clk(reference_40m),.sys_rst_n(rst_n),.midi_rx(midi_rx),
        .event_ready(unused_ready),.event_valid(1'b0),.event_data(64'b0));
    m2_138k_pro_fourvoice_observer_top_r06c9 dut(
        .sys_clk_50m(sys_clk_50m),
        .sys_rst_n(rst_n),
        .key_n(2'b11),
        .midi_rx(midi_rx),
        .i2s_bclk(pins[0]),
        .i2s_lrck(pins[1]),
        .i2s_din(pins[2]),
        .pa_en(pins[3]),
        .uart_tx(pins[4]),
        .tmds_clk_p(pins[5]),
        .tmds_clk_n(pins[6]),
        .tmds_data_p(pins[9:7]),
        .tmds_data_n(pins[12:10]),
        .obs_core_clk(c9_obs_core_clk),
        .obs_polyphonic_valid(c9_obs_polyphonic_valid),
        .obs_rst_n(c9_obs_rst_n),
        .obs_frame_tick(c9_obs_frame_tick),
        .obs_event_valid(c9_obs_event_valid),
        .obs_event_ready(c9_obs_event_ready),
        .obs_event_data(c9_obs_event_data),
        .obs_req_valid(c9_obs_req_valid),
        .obs_req_ready(c9_obs_req_ready),
        .obs_result_valid(c9_obs_result_valid),
        .obs_result_ready(c9_obs_result_ready),
        .obs_result_id(c9_obs_result_id),
        .obs_result_left(c9_obs_result_left),
        .obs_result_right(c9_obs_result_right),
        .obs_result_clip_mask(c9_obs_result_clip_mask),
        .obs_req_id(c9_obs_req_id),
        .obs_commit(c9_obs_commit),
        .obs_commit_id(c9_obs_commit_id),
        .obs_commit_left(c9_obs_commit_left),
        .obs_commit_right(c9_obs_commit_right),
        .obs_commit_clip(c9_obs_commit_clip),
        .obs_cancel(c9_obs_cancel),
        .obs_config_valid(c9_obs_config_valid),
        .obs_config_ready(c9_obs_config_ready),
        .obs_tx_left(c9_obs_tx_left),
        .obs_tx_right(c9_obs_tx_right),
        .obs_pll_locked(c9_obs_pll_locked),
        .obs_tx_sample_valid(c9_obs_tx_sample_valid),
        .obs_tx_metadata_valid(c9_obs_tx_metadata_valid),
        .obs_tx_req_id_valid(c9_obs_tx_req_id_valid),
        .obs_tx_frame_id(c9_obs_tx_frame_id),
        .obs_tx_req_id(c9_obs_tx_req_id),
        .obs_tx_clip_mask(c9_obs_tx_clip_mask),
        .obs_tx_clip_any(c9_obs_tx_clip_any),
        .obs_tx_hold(c9_obs_tx_hold),
        .obs_tx_startup_zero(c9_obs_tx_startup_zero),
        .obs_metadata_error(c9_obs_metadata_error),
        .obs_frame_id_overflow(c9_obs_frame_id_overflow),
        .obs_raw_cancel_reason(c9_obs_raw_cancel_reason),
        .obs_apply_valid(c9_obs_apply_valid),
        .obs_apply_data(c9_obs_apply_data),
        .obs_occupied_mask(c9_obs_occupied_mask),
        .obs_releasing_mask(c9_obs_releasing_mask),
        .obs_note_on_mask(c9_obs_note_on_mask),
        .obs_note_off_mask(c9_obs_note_off_mask),
        .obs_retire_mask(c9_obs_retire_mask),
        .obs_slot_sources(c9_obs_slot_sources),
        .obs_slot_channels(c9_obs_slot_channels),
        .obs_slot_notes(c9_obs_slot_notes),
        .obs_slot_generations(c9_obs_slot_generations),
        .obs_advance_mask(c9_obs_advance_mask),
        .obs_advance_frame_req_id(c9_obs_advance_frame_req_id),
        .obs_effect_input_valid(c9_obs_effect_input_valid),
        .obs_effect_input_ready(c9_obs_effect_input_ready),
        .obs_effect_input_id(c9_obs_effect_input_id),
        .obs_effect_input_left(c9_obs_effect_input_left),
        .obs_effect_input_right(c9_obs_effect_input_right),
        .obs_effect_input_clip_mask(c9_obs_effect_input_clip_mask),
        .obs_apply_kind(c9_obs_apply_kind),
        .obs_apply_mask(c9_obs_apply_mask),
        .obs_router_apply_seq(c9_obs_router_apply_seq),
        .obs_router_apply_seq_valid(c9_obs_router_apply_seq_valid),
        .obs_config_take(c9_obs_config_take),
        .obs_config_payload(c9_obs_config_payload),
        .obs_upstream_clip_mask(c9_obs_upstream_clip_mask),
        .obs_effect_clip_mask(c9_obs_effect_clip_mask),
        .obs_feedback_clip_mask(c9_obs_feedback_clip_mask)
    );
    initial begin
        if(!$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"TRACE_REQUIRED");
        if(!$value$plusargs("EVENTS=%s",event_path)) $fatal(1,"EVENTS_REQUIRED");
        fd=$fopen(trace_path,"w");event_fd=$fopen(event_path,"w");
        if(!fd || !event_fd) $fatal(1,"CAPTURE_OPEN");
        $fwrite(fd,"cycle,time_ps,rst_n,midi_rx,key_n,pins\n");
        $fwrite(event_fd,"time_ps,pins\n");
        if(!$value$plusargs("COMPANIONS=%s",companions_path)) $fatal(1,"COMPANIONS_REQUIRED");
        companion_fd=$fopen(companions_path,"w");
        if(!companion_fd) $fatal(1,"COMPANION_OPEN");
        $fwrite(companion_fd,"cycle,time_ps,rst_n,polyphonic_valid,apply_valid,apply_kind,apply_mask,router_apply_seq_valid,router_apply_seq,apply_data,advance_mask,advance_frame_req_id,config_valid,config_ready,config_take,config_payload,result_clip_mask,effect_input_clip_mask,upstream_clip_mask,effect_clip_mask,feedback_clip_mask\n");
    end
    always @(pins) begin
        event_time_ps=$realtime*1000.0;
        if(event_fd) $fstrobe(event_fd,"%0.0f,%013b",event_time_ps,pins);
    end
    always @(posedge c9_obs_core_clk) begin
        cycle=cycle+1;
        if(cycle==start_compare) begin
            event_time_ps=$realtime*1000.0;
            $fstrobe(event_fd,"%0.0f,%013b",event_time_ps,pins);
        end
        $fwrite(fd,"%0d,%0.0f,%b,%b,11,%013b\n",cycle,$realtime*1000.0,rst_n,midi_rx,pins);
        $fwrite(companion_fd,"%0d,%0.0f,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b\n",cycle,$realtime*1000.0,c9_obs_rst_n,c9_obs_polyphonic_valid,c9_obs_apply_valid,c9_obs_apply_kind,c9_obs_apply_mask,c9_obs_router_apply_seq_valid,c9_obs_router_apply_seq,c9_obs_apply_data,c9_obs_advance_mask,c9_obs_advance_frame_req_id,c9_obs_config_valid,c9_obs_config_ready,c9_obs_config_take,c9_obs_config_payload,c9_obs_result_clip_mask,c9_obs_effect_input_clip_mask,c9_obs_upstream_clip_mask,c9_obs_effect_clip_mask,c9_obs_feedback_clip_mask);
        if(cycle==stop_cycle) begin
            finish_time_ps=$realtime*1000.0;
            #0.001;
            $fflush(fd);$fclose(fd);$fflush(event_fd);$fclose(event_fd);event_fd=0;
            $fflush(companion_fd);$fclose(companion_fd);
            $display("LANE_END lane=observer cycle=%0d time_ps=%0.0f",cycle,finish_time_ps);
            $finish;
        end
    end
endmodule
