// Display-domain live performance state for the M3 visualizer.
//
// Events are consumed after visual_event_bridge has crossed them into clk.
// Working state may change at any time, while public outputs change only at
// frame_start so one raster frame always observes a coherent snapshot.
`timescale 1ns/1ps

module visual_live_state #(
    parameter integer SLOT_COUNT = 8,
    parameter integer Y_WIDTH    = 10,
    parameter integer JUDGE_Y    = 400,
    parameter integer RISE_STEP  = 4
) (
    input  logic clk,
    input  logic rst_n,
    input  logic frame_start,
    input  logic performance_fire,
    input  audio_defs_pkg::performance_event_t performance_data,
    input  logic video_desync,

    output logic [127:0]                    key_down,
    output logic [SLOT_COUNT-1:0]           live_valid,
    output logic [SLOT_COUNT*7-1:0]         live_note_number,
    output logic [SLOT_COUNT*Y_WIDTH-1:0]   live_y,
    output logic [SLOT_COUNT*10-1:0]        live_velocity,
    output logic                            desync_latched
);

    logic [127:0] work_key_down_q;
    logic [127:0] work_key_down_d;
    logic [SLOT_COUNT-1:0] work_valid_q;
    logic [SLOT_COUNT-1:0] work_valid_d;
    logic [6:0] work_note_q [0:SLOT_COUNT-1];
    logic [6:0] work_note_d [0:SLOT_COUNT-1];
    logic [Y_WIDTH-1:0] work_y_q [0:SLOT_COUNT-1];
    logic [Y_WIDTH-1:0] work_y_d [0:SLOT_COUNT-1];
    logic [9:0] work_velocity_q [0:SLOT_COUNT-1];
    logic [9:0] work_velocity_d [0:SLOT_COUNT-1];

    logic desync_pending_q;
    logic desync_pending_d;
    logic desync_latched_d;

    logic [127:0] key_down_d;
    logic [SLOT_COUNT-1:0] live_valid_d;
    logic [SLOT_COUNT*7-1:0] live_note_number_d;
    logic [SLOT_COUNT*Y_WIDTH-1:0] live_y_d;
    logic [SLOT_COUNT*10-1:0] live_velocity_d;

    logic slot_allocated;
    integer comb_i;
    integer seq_i;
    localparam logic [Y_WIDTH-1:0] JUDGE_Y_VALUE = JUDGE_Y[Y_WIDTH-1:0];
    localparam logic [Y_WIDTH-1:0] RISE_STEP_VALUE = RISE_STEP[Y_WIDTH-1:0];

    always_comb begin
        work_key_down_d = work_key_down_q;
        work_valid_d = work_valid_q;
        desync_pending_d = desync_pending_q;
        desync_latched_d = desync_latched;

        key_down_d = key_down;
        live_valid_d = live_valid;
        live_note_number_d = live_note_number;
        live_y_d = live_y;
        live_velocity_d = live_velocity;
        slot_allocated = 1'b0;

        for (comb_i = 0; comb_i < SLOT_COUNT; comb_i = comb_i + 1) begin
            work_note_d[comb_i] = work_note_q[comb_i];
            work_y_d[comb_i] = work_y_q[comb_i];
            work_velocity_d[comb_i] = work_velocity_q[comb_i];
        end

        if (video_desync)
            desync_pending_d = 1'b1;

        if (frame_start) begin
            if (video_desync || desync_pending_q || desync_latched) begin
                work_key_down_d = '0;
                work_valid_d = '0;
                key_down_d = '0;
                live_valid_d = '0;
                live_note_number_d = '0;
                live_y_d = '0;
                live_velocity_d = '0;
                desync_pending_d = 1'b0;
                desync_latched_d = 1'b1;
                for (comb_i = 0; comb_i < SLOT_COUNT;
                     comb_i = comb_i + 1) begin
                    work_note_d[comb_i] = '0;
                    work_y_d[comb_i] = '0;
                    work_velocity_d[comb_i] = '0;
                end
            end else begin
                // Publish the complete pre-boundary working state atomically.
                key_down_d = work_key_down_q;
                live_valid_d = work_valid_q;
                for (comb_i = 0; comb_i < SLOT_COUNT;
                     comb_i = comb_i + 1) begin
                    live_note_number_d[comb_i*7 +: 7] =
                        work_note_q[comb_i];
                    live_y_d[comb_i*Y_WIDTH +: Y_WIDTH] =
                        work_y_q[comb_i];
                    live_velocity_d[comb_i*10 +: 10] =
                        work_velocity_q[comb_i];

                    // Prepare the following frame. A slot remains visible at
                    // its current coordinate for this frame, then advances.
                    if (work_valid_q[comb_i]) begin
                        if (work_y_q[comb_i] <= RISE_STEP_VALUE) begin
                            work_valid_d[comb_i] = 1'b0;
                            work_note_d[comb_i] = '0;
                            work_y_d[comb_i] = '0;
                            work_velocity_d[comb_i] = '0;
                        end else begin
                            work_y_d[comb_i] =
                                work_y_q[comb_i] - RISE_STEP_VALUE;
                        end
                    end
                end
            end
        end

        // An event coincident with frame_start belongs to the following frame.
        // Once desynchronization is seen, no further performance state is used.
        if (performance_fire && !video_desync && !desync_pending_q &&
            !desync_latched) begin
            if ((performance_data.event_type == audio_defs_pkg::EVENT_NOTE_ON) &&
                (performance_data.velocity != 10'd0)) begin
                work_key_down_d[performance_data.note_number] = 1'b1;
                for (comb_i = 0; comb_i < SLOT_COUNT;
                     comb_i = comb_i + 1) begin
                    if (!slot_allocated && !work_valid_d[comb_i]) begin
                        work_valid_d[comb_i] = 1'b1;
                        work_note_d[comb_i] =
                            performance_data.note_number;
                        work_y_d[comb_i] = JUDGE_Y_VALUE;
                        work_velocity_d[comb_i] =
                            performance_data.velocity;
                        slot_allocated = 1'b1;
                    end
                end
            end else if ((performance_data.event_type ==
                          audio_defs_pkg::EVENT_NOTE_OFF) ||
                         ((performance_data.event_type ==
                           audio_defs_pkg::EVENT_NOTE_ON) &&
                          (performance_data.velocity == 10'd0))) begin
                work_key_down_d[performance_data.note_number] = 1'b0;
            end else if (performance_data.event_type ==
                         audio_defs_pkg::EVENT_ALL_NOTES_OFF) begin
                work_key_down_d = '0;
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            work_key_down_q <= '0;
            work_valid_q <= '0;
            desync_pending_q <= 1'b0;
            desync_latched <= 1'b0;
            key_down <= '0;
            live_valid <= '0;
            live_note_number <= '0;
            live_y <= '0;
            live_velocity <= '0;
            for (seq_i = 0; seq_i < SLOT_COUNT; seq_i = seq_i + 1) begin
                work_note_q[seq_i] <= '0;
                work_y_q[seq_i] <= '0;
                work_velocity_q[seq_i] <= '0;
            end
        end else begin
            work_key_down_q <= work_key_down_d;
            work_valid_q <= work_valid_d;
            desync_pending_q <= desync_pending_d;
            desync_latched <= desync_latched_d;
            key_down <= key_down_d;
            live_valid <= live_valid_d;
            live_note_number <= live_note_number_d;
            live_y <= live_y_d;
            live_velocity <= live_velocity_d;
            for (seq_i = 0; seq_i < SLOT_COUNT; seq_i = seq_i + 1) begin
                work_note_q[seq_i] <= work_note_d[seq_i];
                work_y_q[seq_i] <= work_y_d[seq_i];
                work_velocity_q[seq_i] <= work_velocity_d[seq_i];
            end
        end
    end

`ifndef SYNTHESIS
    initial begin
        if (SLOT_COUNT < 1)
            $fatal(1, "SLOT_COUNT must be positive");
        if (Y_WIDTH < 1 || Y_WIDTH > 30)
            $fatal(1, "Y_WIDTH outside supported range 1..30");
        if (JUDGE_Y < 0 || JUDGE_Y >= (1 << Y_WIDTH))
            $fatal(1, "JUDGE_Y does not fit Y_WIDTH");
        if (RISE_STEP < 1 || RISE_STEP >= (1 << Y_WIDTH))
            $fatal(1, "RISE_STEP outside supported range");
    end
`endif

endmodule
