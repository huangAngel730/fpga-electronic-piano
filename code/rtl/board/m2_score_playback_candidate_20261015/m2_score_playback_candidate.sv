// Private M2 score RAM readout and event priority candidate, not production.
// clk is the 40MHz core clock; frame_tick is the existing 48kHz I2S frame pulse.
// rst_n asserts asynchronously and is synchronously released by the board.
// COMMIT auto-starts only in this isolated prototype (no PLAY command in T057).
module m2_score_playback_candidate #(
    parameter logic [3:0] SCORE_SOURCE_ID = 4'd2
) (
    input logic clk,rst_n,frame_tick,
    input logic committed_valid,commit_pulse,
    input logic [9:0] committed_count,
    input logic [31:0] committed_score_id,
    output wire rd_req,
    output wire [8:0] rd_index,
    input logic rd_valid,
    input logic [63:0] rd_event,
    input logic base_valid,
    input logic [63:0] base_data,
    output wire base_ready,
    output wire event_valid,
    output wire [63:0] event_data,
    input logic event_ready,
    output logic [9:0] consumed_events,
    output logic [31:0] late_events,
    output logic [31:0] active_score_id,
    output logic fault
);
    localparam logic [2:0] IDLE=0, ISSUE=1, WAIT_READ=2, HOLD=3, FAULT=4;
    logic [2:0] state;
    logic panic_pending;
    logic [63:0] held_record;
    logic [31:0] elapsed_tick, previous_tick;
    logic [9:0] next_index;
    wire [31:0] held_tick=held_record[31:0];
    wire [7:0] kind=held_record[39:32];
    wire [7:0] channel=held_record[47:40];
    wire [7:0] note=held_record[55:48];
    wire [7:0] velocity=held_record[63:56];
    wire due=(state==HOLD) && held_tick<=elapsed_tick && !fault;
    wire score_valid=rst_n && !commit_pulse && committed_valid && (panic_pending || due);
    audio_defs_pkg::performance_event_t score_data;
    always_comb begin
        score_data='0;
        if(panic_pending)
            score_data=audio_defs_pkg::make_all_notes_off(SCORE_SOURCE_ID);
        else if(due)
            score_data=audio_defs_pkg::make_note_event(kind==0,SCORE_SOURCE_ID,
                channel[3:0],note[6:0],audio_defs_pkg::midi_velocity_to_10bit(velocity[6:0]));
    end
    // No backpressure can reach the I2S frame clock. Existing MIDI/button
    // FIFO wins on a simultaneous request and holds the score event in HOLD.
    assign event_valid=rst_n && (base_valid || score_valid);
    assign event_data=base_valid ? base_data : score_data;
    assign base_ready=rst_n && base_valid && event_ready;
    wire score_take=score_valid && !base_valid && event_ready;
    assign rd_req=rst_n && !commit_pulse && committed_valid && !fault &&
                  !panic_pending && state==ISSUE && next_index<committed_count;
    assign rd_index=next_index[8:0];
    wire invalid_record=rd_event[39:32]>8'd1 || rd_event[47:40]>8'd15 ||
                        rd_event[55:48]>8'd127 || rd_event[63:56]>8'd127 ||
                        (rd_event[39:32]==0 && rd_event[63:56]==0) ||
                        (next_index!=0 && rd_event[31:0]<previous_tick);
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            state<=IDLE;panic_pending<=0;held_record<=0;elapsed_tick<=0;
            previous_tick<=0;next_index<=0;consumed_events<=0;late_events<=0;
            active_score_id<=0;fault<=0;
        end else if(commit_pulse)begin
            // A read launched on the COMMIT edge sees the OLD bank by T062
            // contract. Drop it and start after the published bank switches.
            state<=IDLE;panic_pending<=1;held_record<=0;elapsed_tick<=0;
            previous_tick<=0;next_index<=0;consumed_events<=0;late_events<=0;
            active_score_id<=committed_score_id;fault<=0;
        end else begin
            if(panic_pending)begin
                if(score_take)begin panic_pending<=0;elapsed_tick<=0;end
            end else if(frame_tick && committed_valid && elapsed_tick!=32'hffffffff)
                elapsed_tick<=elapsed_tick+1'b1;
            if(!panic_pending)begin
                case(state)
                    IDLE: if(!fault && committed_valid && next_index<committed_count)
                        state<=ISSUE;
                    ISSUE: if(rd_req)state<=WAIT_READ;
                    WAIT_READ:begin
                        if(!rd_valid || invalid_record)begin
                            fault<=1;panic_pending<=1;state<=FAULT;
                        end else begin held_record<=rd_event;state<=HOLD;end
                    end
                    HOLD:if(score_take)begin
                        previous_tick<=held_tick;
                        next_index<=next_index+1'b1;
                        consumed_events<=consumed_events+1'b1;
                        if(held_tick<elapsed_tick && late_events!=32'hffffffff)
                            late_events<=late_events+1'b1;
                        state<=IDLE;
                    end
                    default:state<=FAULT;
                endcase
            end
        end
    end
endmodule