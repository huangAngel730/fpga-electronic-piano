`timescale 1ns/1ps
// Testbench-only, public ports only; no production feedback or private DSP.
module r7a_c9_public_observer #(
    parameter string CAPTURE_ID = "",
    parameter string PLAN_STOP_ID = "",
    parameter string RAW_PATH = "RAW_CAPTURE.jsonl",
    parameter string RESET_PATH = "RESET_EDGES.jsonl",
    parameter string END_PATH = "END.json",
    parameter longint EXPECTED_FINISH_CORE_CYCLE = -1,
    parameter longint MAX_CORE_SAMPLES = 0
) (
    input wire sys_rst_n,
    input wire finish_requested,
    output logic capture_done = 1'b0,
    input wire obs_core_clk,
    input wire obs_polyphonic_valid,
    input wire obs_rst_n,
    input wire obs_frame_tick,
    input wire obs_event_valid,
    input wire obs_event_ready,
    input wire [63:0] obs_event_data,
    input wire obs_req_valid,
    input wire obs_req_ready,
    input wire obs_result_valid,
    input wire obs_result_ready,
    input wire [31:0] obs_result_id,
    input wire signed [23:0] obs_result_left,
    input wire signed [23:0] obs_result_right,
    input wire [1:0] obs_result_clip_mask,
    input wire [31:0] obs_req_id,
    input wire obs_commit,
    input wire [31:0] obs_commit_id,
    input wire signed [23:0] obs_commit_left,
    input wire signed [23:0] obs_commit_right,
    input wire obs_commit_clip,
    input wire obs_cancel,
    input wire obs_config_valid,
    input wire obs_config_ready,
    input wire signed [23:0] obs_tx_left,
    input wire signed [23:0] obs_tx_right,
    input wire obs_pll_locked,
    input wire obs_tx_sample_valid,
    input wire obs_tx_metadata_valid,
    input wire obs_tx_req_id_valid,
    input wire [31:0] obs_tx_frame_id,
    input wire [31:0] obs_tx_req_id,
    input wire [1:0] obs_tx_clip_mask,
    input wire obs_tx_clip_any,
    input wire obs_tx_hold,
    input wire obs_tx_startup_zero,
    input wire obs_metadata_error,
    input wire obs_frame_id_overflow,
    input wire [1:0] obs_raw_cancel_reason,
    input wire obs_apply_valid,
    input wire [63:0] obs_apply_data,
    input wire [3:0] obs_occupied_mask,
    input wire [3:0] obs_releasing_mask,
    input wire [3:0] obs_note_on_mask,
    input wire [3:0] obs_note_off_mask,
    input wire [3:0] obs_retire_mask,
    input wire [15:0] obs_slot_sources,
    input wire [15:0] obs_slot_channels,
    input wire [31:0] obs_slot_notes,
    input wire [127:0] obs_slot_generations,
    input wire [3:0] obs_advance_mask,
    input wire [31:0] obs_advance_frame_req_id,
    input wire obs_effect_input_valid,
    input wire obs_effect_input_ready,
    input wire [31:0] obs_effect_input_id,
    input wire signed [23:0] obs_effect_input_left,
    input wire signed [23:0] obs_effect_input_right,
    input wire [1:0] obs_effect_input_clip_mask,
    input wire [3:0] obs_apply_kind,
    input wire [3:0] obs_apply_mask,
    input wire [31:0] obs_router_apply_seq,
    input wire obs_router_apply_seq_valid,
    input wire obs_config_take,
    input wire [61:0] obs_config_payload,
    input wire [1:0] obs_upstream_clip_mask,
    input wire [1:0] obs_effect_clip_mask,
    input wire [1:0] obs_feedback_clip_mask,
    input wire i2s_bclk,
    input wire i2s_lrck,
    input wire i2s_din,
    input wire pa_en,
    input wire uart_tx
);
    integer raw_fd=0, reset_fd=0, end_fd=0, probe;
    longint sample_cycle=0, source_line=0, reset_seq=0;

    function automatic longint now_ps();
        now_ps = longint'($realtime * 1000.0);
    endfunction

    function automatic bit safe_token(input string value);
        integer i, c;
        begin
            safe_token = value.len()>0;
            for (i=0; i<value.len(); i=i+1) begin
                c=value.getc(i);
                if (!((c>=48 && c<=57) || (c>=65 && c<=90) ||
                      (c>=97 && c<=122) || c==45 || c==95)) safe_token=0;
            end
        end
    endfunction

    task automatic reset_snapshot(input string kind);
        begin
            reset_seq=reset_seq+1;
            $fwrite(reset_fd, "{\"schema\":\"M3_R7A_RESET_SNAPSHOT_V1\",\"capture_id\":\"%s\",\"edge_seq\":%0d,\"time_ps\":%0d,\"kind\":\"%s\",\"values\":{\"sys_rst_n\":\"%b\",\"obs_rst_n\":\"%b\",\"obs_pll_locked\":\"%b\"}}\n",
                    CAPTURE_ID, reset_seq, now_ps(), kind, sys_rst_n, obs_rst_n, obs_pll_locked);
        end
    endtask

    initial begin
        if (!safe_token(CAPTURE_ID) || !safe_token(PLAN_STOP_ID))
            $fatal(1,"CAPTURE_ID_AND_STOP_ID_REQUIRED_SAFE_ASCII");
        if (EXPECTED_FINISH_CORE_CYCLE<0 || MAX_CORE_SAMPLES<=EXPECTED_FINISH_CORE_CYCLE)
            $fatal(1,"FROZEN_CAPTURE_WINDOW_REQUIRED");
        probe=$fopen(RAW_PATH,"r"); if(probe) begin $fclose(probe); $fatal(1,"RAW_EXISTS"); end
        probe=$fopen(RESET_PATH,"r"); if(probe) begin $fclose(probe); $fatal(1,"RESET_EXISTS"); end
        probe=$fopen(END_PATH,"r"); if(probe) begin $fclose(probe); $fatal(1,"END_EXISTS"); end
        raw_fd=$fopen(RAW_PATH,"w"); reset_fd=$fopen(RESET_PATH,"w"); end_fd=$fopen(END_PATH,"w");
        if (!raw_fd || !reset_fd || !end_fd) $fatal(1,"CAPTURE_OPEN_FAILED");
        // Time-zero snapshot is actual initial signal state after initial
        // assignments; X is retained. It is not a fabricated reset edge.
        #0;
        reset_snapshot("INITIAL");
        forever begin
            @(sys_rst_n or obs_rst_n or obs_pll_locked);
            reset_snapshot("CHANGE");
        end
    end

    always @(posedge obs_core_clk) begin
        if (!capture_done) begin
            if (!raw_fd) $fatal(1,"CORE_EDGE_BEFORE_CAPTURE_OPEN");
            if (sample_cycle>=MAX_CORE_SAMPLES) $fatal(1,"CAPTURE_SAMPLE_LIMIT");
            if (obs_polyphonic_valid !== 1'b1) $fatal(1,"NOT_PUBLIC_POLYPHONIC_MODE");
            source_line=source_line+1;
            // No delay and no NBA await before any sampled public value.
            $fwrite(raw_fd, "{\"schema\":\"M3_R7A_C9_RAW_CORE_ROW_V1\",\"capture_id\":\"%s\",\"source_line\":%0d,\"cycle\":%0d,\"time_ps\":%0d,\"epoch\":null,\"epoch_reason\":\"BIND_FROM_INDEPENDENT_RESET_EDGES\",\"finish\":%0d,\"ports\":{\"obs_core_clk\":\"%b\",\"obs_polyphonic_valid\":\"%b\",\"obs_rst_n\":\"%b\",\"obs_frame_tick\":\"%b\",\"obs_event_valid\":\"%b\",\"obs_event_ready\":\"%b\",\"obs_event_data\":\"%b\",\"obs_req_valid\":\"%b\",\"obs_req_ready\":\"%b\",\"obs_result_valid\":\"%b\",\"obs_result_ready\":\"%b\",\"obs_result_id\":\"%b\",\"obs_result_left\":\"%b\",\"obs_result_right\":\"%b\",\"obs_result_clip_mask\":\"%b\",\"obs_req_id\":\"%b\",\"obs_commit\":\"%b\",\"obs_commit_id\":\"%b\",\"obs_commit_left\":\"%b\",\"obs_commit_right\":\"%b\",\"obs_commit_clip\":\"%b\",\"obs_cancel\":\"%b\",\"obs_config_valid\":\"%b\",\"obs_config_ready\":\"%b\",\"obs_tx_left\":\"%b\",\"obs_tx_right\":\"%b\",\"obs_pll_locked\":\"%b\",\"obs_tx_sample_valid\":\"%b\",\"obs_tx_metadata_valid\":\"%b\",\"obs_tx_req_id_valid\":\"%b\",\"obs_tx_frame_id\":\"%b\",\"obs_tx_req_id\":\"%b\",\"obs_tx_clip_mask\":\"%b\",\"obs_tx_clip_any\":\"%b\",\"obs_tx_hold\":\"%b\",\"obs_tx_startup_zero\":\"%b\",\"obs_metadata_error\":\"%b\",\"obs_frame_id_overflow\":\"%b\",\"obs_raw_cancel_reason\":\"%b\",\"obs_apply_valid\":\"%b\",\"obs_apply_data\":\"%b\",\"obs_occupied_mask\":\"%b\",\"obs_releasing_mask\":\"%b\",\"obs_note_on_mask\":\"%b\",\"obs_note_off_mask\":\"%b\",\"obs_retire_mask\":\"%b\",\"obs_slot_sources\":\"%b\",\"obs_slot_channels\":\"%b\",\"obs_slot_notes\":\"%b\",\"obs_slot_generations\":\"%b\",\"obs_advance_mask\":\"%b\",\"obs_advance_frame_req_id\":\"%b\",\"obs_effect_input_valid\":\"%b\",\"obs_effect_input_ready\":\"%b\",\"obs_effect_input_id\":\"%b\",\"obs_effect_input_left\":\"%b\",\"obs_effect_input_right\":\"%b\",\"obs_effect_input_clip_mask\":\"%b\",\"obs_apply_kind\":\"%b\",\"obs_apply_mask\":\"%b\",\"obs_router_apply_seq\":\"%b\",\"obs_router_apply_seq_valid\":\"%b\",\"obs_config_take\":\"%b\",\"obs_config_payload\":\"%b\",\"obs_upstream_clip_mask\":\"%b\",\"obs_effect_clip_mask\":\"%b\",\"obs_feedback_clip_mask\":\"%b\",\"i2s_bclk\":\"%b\",\"i2s_lrck\":\"%b\",\"i2s_din\":\"%b\",\"pa_en\":\"%b\",\"uart_tx\":\"%b\"}}\n",
                CAPTURE_ID, source_line, sample_cycle, now_ps(), finish_requested,
                obs_core_clk,
                obs_polyphonic_valid,
                obs_rst_n,
                obs_frame_tick,
                obs_event_valid,
                obs_event_ready,
                obs_event_data,
                obs_req_valid,
                obs_req_ready,
                obs_result_valid,
                obs_result_ready,
                obs_result_id,
                obs_result_left,
                obs_result_right,
                obs_result_clip_mask,
                obs_req_id,
                obs_commit,
                obs_commit_id,
                obs_commit_left,
                obs_commit_right,
                obs_commit_clip,
                obs_cancel,
                obs_config_valid,
                obs_config_ready,
                obs_tx_left,
                obs_tx_right,
                obs_pll_locked,
                obs_tx_sample_valid,
                obs_tx_metadata_valid,
                obs_tx_req_id_valid,
                obs_tx_frame_id,
                obs_tx_req_id,
                obs_tx_clip_mask,
                obs_tx_clip_any,
                obs_tx_hold,
                obs_tx_startup_zero,
                obs_metadata_error,
                obs_frame_id_overflow,
                obs_raw_cancel_reason,
                obs_apply_valid,
                obs_apply_data,
                obs_occupied_mask,
                obs_releasing_mask,
                obs_note_on_mask,
                obs_note_off_mask,
                obs_retire_mask,
                obs_slot_sources,
                obs_slot_channels,
                obs_slot_notes,
                obs_slot_generations,
                obs_advance_mask,
                obs_advance_frame_req_id,
                obs_effect_input_valid,
                obs_effect_input_ready,
                obs_effect_input_id,
                obs_effect_input_left,
                obs_effect_input_right,
                obs_effect_input_clip_mask,
                obs_apply_kind,
                obs_apply_mask,
                obs_router_apply_seq,
                obs_router_apply_seq_valid,
                obs_config_take,
                obs_config_payload,
                obs_upstream_clip_mask,
                obs_effect_clip_mask,
                obs_feedback_clip_mask,
                i2s_bclk,
                i2s_lrck,
                i2s_din,
                pa_en,
                uart_tx);
            if (finish_requested === 1'b1) begin
                if (sample_cycle != EXPECTED_FINISH_CORE_CYCLE)
                    $fatal(1,"FINISH_NOT_AT_FROZEN_CORE_CYCLE");
                $fwrite(end_fd, "{\"schema\":\"M3_R7A_END_V1\",\"capture_id\":\"%s\",\"plan_stop_id\":\"%s\",\"finish_cycle\":%0d,\"time_ps\":%0d,\"row_count\":%0d,\"reason\":\"PLANNED_WINDOW_END\",\"ledger_status\":\"NOT_CHECKED_R6_5_REQUIRED\",\"serial_tail_status\":\"UNKNOWN_R6_6_REQUIRED\"}\n",
                    CAPTURE_ID, PLAN_STOP_ID, sample_cycle, now_ps(), source_line);
                $display("MONITOR_END capture_id=%s cycle=%0d time_ps=%0d rows=%0d reason=PLANNED_WINDOW_END",
                    CAPTURE_ID, sample_cycle, now_ps(), source_line);
                $fclose(raw_fd); raw_fd=0; $fclose(end_fd); end_fd=0;
                capture_done=1'b1;
            end
            sample_cycle=sample_cycle+1;
        end
    end

    final begin
        if(raw_fd) $fclose(raw_fd);
        if(end_fd) $fclose(end_fd);
        if(reset_fd) $fclose(reset_fd);
    end
endmodule
