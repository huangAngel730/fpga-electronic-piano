// Isolated E4 composition; frozen backend/router/ROM remain unchanged.
module e4_n32_candidate #(parameter integer N=8, RESPONSE=1, SW=$clog2(N), TW=72+SW) (
    input wire clk, rst_n, cancel,
    input wire event_valid, output wire event_ready, input wire [63:0] event_data,
    input wire sample_valid, output wire sample_ready, input wire [31:0] sample_id,
    output wire result_valid, input wire result_ready,
    output wire [31:0] result_id, output wire signed [23:0] left, right,
    output wire late, clipped, output wire aborted, output wire [1:0] abort_reason,
    output wire idle, output wire fault,
    // Verification input is a real result-port injection, disabled by caller
    // for ordinary operation. It never replaces a simultaneous real result.
    input wire inject_valid, input wire [TW-1:0] inject_tag, input wire [73:0] inject_context,
    output wire inject_ready,
    input wire read_valid, input wire [SW-1:0] read_slot,
    output wire read_ready, read_out_valid, output wire [73:0] read_context,
    output wire [N-1:0] ons, offs, occupied, releasing,
    output wire [N*10-1:0] velocities, output wire [N*32-1:0] bases, generations,
    output wire [N*8-1:0] notes, output wire [N*4-1:0] sources, channels,
    output wire issue_valid, output wire [TW-1:0] issue_tag, output wire [73:0] issue_context,
    output wire [1:0] issue_flags, output wire [28:0] issue_control,
    output wire issue_pedal,
    output wire write_valid, write_accepted, write_injected,
    output wire [TW-1:0] write_tag, output wire [73:0] write_context,
    output wire publish,
    output wire be_launch, advance, lane_valid,
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
    // Observation-only N32-C contract.  All signals mirror existing public
    // transactions or state; none feeds back into the audio business path.
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
    wire [31:0] raw_id;
    wire signed [23:0] raw_left;
    wire raw_valid, raw_event_ready, raw_clipped;
    wire actual_cancel;
`ifdef E4_BAD_CANCEL
    assign actual_cancel=1'b0;
`else
    assign actual_cancel=cancel;
`endif
    wire drop_event;
    reg [31:0] accepted_ons;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) accepted_ons<=0;
        else if(event_valid && event_ready && event_data[63:61]==0)
            accepted_ons<=accepted_ons+1;
`ifdef E4_DROP_STEAL
    assign drop_event=event_data[63:61]==0 && accepted_ons==N;
`elsif E4_DROP_RETRIGGER
    assign drop_event=event_data[63:61]==0 && accepted_ons==N+1;
`elsif E4_DROP_CC64
    assign drop_event=event_data[63:61]==4 && event_data[25:18]==6;
`else
    assign drop_event=1'b0;
`endif
    assign event_ready=raw_event_ready;
`ifdef E4_BAD_ID
    assign result_id=raw_id ^ 32'd1;
`else
    assign result_id=raw_id;
`endif
`ifdef E4_BAD_HOLD
    assign left=raw_left ^ ((raw_valid && !result_ready) ? 24'd1 : 24'd0);
`else
    assign left=raw_left;
`endif
    assign result_valid=raw_valid;
`ifdef E4_BAD_CLIP
    assign clipped=raw_clipped ^ raw_valid;
`else
    assign clipped=raw_clipped;
`endif
`ifdef E4_BAD_RESET
    reg reset_seen=0;
    always @(posedge clk) if(rst_n) reset_seen<=1;
    wire source_rst_n=rst_n || reset_seen;
`else
    wire source_rst_n=rst_n;
`endif
    b_n32_event_audio_prom #(.N(N),.RESPONSE(RESPONSE)) source (
        .result_id(raw_id),.left(raw_left),.result_valid(raw_valid),.clipped(raw_clipped),
        .event_valid(event_valid && !drop_event),.event_ready(raw_event_ready),
        .cancel(actual_cancel),.rst_n(source_rst_n),.*
    );
endmodule
