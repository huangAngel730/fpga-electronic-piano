// T061 N32-B isolated adapter. This file does not change the frozen router,
// control, B1, pROM backend, or sound mathematics. It only exposes the
// N32/RESPONSE=1 composition and provides output-only checker mutations.
`timescale 1ns/1ps
module b_n32_r1_wrapper #(parameter integer N=32, RESPONSE=1,
    SW=$clog2(N), TW=72+SW) (
    input wire clk, rst_n, cancel,
    input wire event_valid, output wire event_ready, input wire [63:0] event_data,
    input wire sample_valid, output wire sample_ready, input wire [31:0] sample_id,
    output logic result_valid, input wire result_ready,
    output logic [31:0] result_id, output logic signed [23:0] left, right,
    output logic late, clipped, output wire aborted, output wire [1:0] abort_reason,
    output wire idle, output wire fault,
    input wire inject_valid, input wire [TW-1:0] inject_tag,
    input wire [73:0] inject_context, output wire inject_ready,
    input wire read_valid, input wire [SW-1:0] read_slot,
    output wire read_ready, read_out_valid, output wire [73:0] read_context,
    output wire [N-1:0] ons, offs, occupied, releasing,
    output wire [N*10-1:0] velocities,
    output wire [N*32-1:0] bases, generations,
    output wire [N*8-1:0] notes,
    output wire [N*4-1:0] sources, channels,
    output wire issue_valid, output wire [TW-1:0] issue_tag,
    output wire [73:0] issue_context, output wire [1:0] issue_flags,
    output wire [28:0] issue_control, output wire issue_pedal,
    output wire write_valid, write_accepted, write_injected,
    output wire [TW-1:0] write_tag, output wire [73:0] write_context,
    output wire publish, output wire be_launch, advance, lane_valid,
    output wire [SW-1:0] lane_slot, output wire [1:0] lane_table,
    output wire [31:0] lane_phase, lane_fcw,
    output wire signed [15:0] lane_wave, output wire [15:0] lane_env,
    output wire signed [23:0] lane_pcm,
    output wire [N*16-1:0] live_env, output wire [N*3-1:0] live_state,
    output wire [N*10-1:0] frame_velocity,
    output wire [N*32-1:0] frame_base, frame_gen,
    output wire [N*12-1:0] frame_bend, frame_mod,
    output wire [N*5-1:0] frame_range,
    output wire [N*4-1:0] frame_sources, frame_channels,
    output wire [N-1:0] frame_occupied,
    output wire [3:0] audio_state, router_state,
    output wire control_snapshot_valid, control_snapshot_ready,
    output wire [31:0] control_snapshot_id,
    output wire [N*29-1:0] control_snapshot_value,
    output wire [N-1:0] control_snapshot_occupied,
    output wire [N*4-1:0] control_snapshot_sources, control_snapshot_channels,
    output wire [N*32-1:0] control_snapshot_generations,
    output wire control_release_valid, control_release_ready,
    output wire [N-1:0] control_release_mask,
    output wire [N*32-1:0] control_release_generations,
    output wire backend_release_done_valid, backend_release_done_ready,
    output wire [SW-1:0] backend_release_done_slot,
    output wire [31:0] backend_release_done_generation,
    output wire [N-1:0] backend_release_done_mask
);
    wire raw_result_valid;
    wire [31:0] raw_result_id;
    wire signed [23:0] raw_left, raw_right;
    wire raw_late, raw_clipped;

    b_n32_event_audio_prom #(.N(N), .RESPONSE(RESPONSE)) u_event_audio (
        .result_valid(raw_result_valid), .result_id(raw_result_id),
        .left(raw_left), .right(raw_right), .late(raw_late),
        .clipped(raw_clipped), .*
    );

    always_comb begin
        result_valid = raw_result_valid;
        result_id = raw_result_id;
        left = raw_left;
        right = raw_right;
        late = raw_late;
        clipped = raw_clipped;
`ifdef B_N32_MUTANT_RESULT_ID
        if(raw_result_valid) result_id = raw_result_id ^ 32'd1;
`endif
`ifdef B_N32_MUTANT_PCM
        if(raw_result_valid) left[0] = ~raw_left[0];
`endif
`ifdef B_N32_MUTANT_CLIPPED
        if(raw_result_valid) clipped = ~raw_clipped;
`endif
    end

    initial begin
        if(N != 32 || RESPONSE != 1)
            $fatal(1, "N32_B_FIXED_CONFIGURATION_REQUIRED");
    end
endmodule

// Compatibility shell used only by the existing isolated B2C stimulus.
// The clipped signal remains visible to tb_b_n32_r1 through this instance.
module b2d_event_audio #(parameter integer N=32, RESPONSE=1,
    SW=$clog2(N), TW=72+SW) (
    input wire clk, rst_n, cancel,
    input wire event_valid, output wire event_ready, input wire [63:0] event_data,
    input wire sample_valid, output wire sample_ready, input wire [31:0] sample_id,
    output logic result_valid, input wire result_ready,
    output logic [31:0] result_id, output logic signed [23:0] left, right,
    output logic late, output wire aborted, output wire [1:0] abort_reason,
    output wire idle, output wire fault,
    input wire inject_valid, input wire [TW-1:0] inject_tag,
    input wire [73:0] inject_context, output wire inject_ready,
    input wire read_valid, input wire [SW-1:0] read_slot,
    output wire read_ready, read_out_valid, output wire [73:0] read_context,
    output wire [N-1:0] ons, offs, occupied, releasing,
    output wire [N*10-1:0] velocities,
    output wire [N*32-1:0] bases, generations,
    output wire [N*8-1:0] notes,
    output wire [N*4-1:0] sources, channels,
    output wire issue_valid, output wire [TW-1:0] issue_tag,
    output wire [73:0] issue_context, output wire [1:0] issue_flags,
    output wire [28:0] issue_control, output wire issue_pedal,
    output wire write_valid, write_accepted, write_injected,
    output wire [TW-1:0] write_tag, output wire [73:0] write_context,
    output wire publish, output wire be_launch, advance, lane_valid,
    output wire [SW-1:0] lane_slot, output wire [1:0] lane_table,
    output wire [31:0] lane_phase, lane_fcw,
    output wire signed [15:0] lane_wave, output wire [15:0] lane_env,
    output wire signed [23:0] lane_pcm,
    output wire [N*16-1:0] live_env, output wire [N*3-1:0] live_state,
    output logic [N*10-1:0] frame_velocity,
    output logic [N*32-1:0] frame_base, frame_gen,
    output logic [N*12-1:0] frame_bend, frame_mod,
    output logic [N*5-1:0] frame_range,
    output logic [N*4-1:0] frame_sources, frame_channels,
    output logic [N-1:0] frame_occupied
);
    logic clipped;
    wire [3:0] audio_state, router_state;
    wire control_snapshot_valid, control_snapshot_ready;
    wire [31:0] control_snapshot_id;
    wire [N*29-1:0] control_snapshot_value;
    wire [N-1:0] control_snapshot_occupied;
    wire [N*4-1:0] control_snapshot_sources, control_snapshot_channels;
    wire [N*32-1:0] control_snapshot_generations;
    wire control_release_valid, control_release_ready;
    wire [N-1:0] control_release_mask;
    wire [N*32-1:0] control_release_generations;
    wire backend_release_done_valid, backend_release_done_ready;
    wire [SW-1:0] backend_release_done_slot;
    wire [31:0] backend_release_done_generation;
    wire [N-1:0] backend_release_done_mask;
    b_n32_r1_wrapper #(.N(N), .RESPONSE(RESPONSE)) u_b_n32_r1 (.*);
endmodule
