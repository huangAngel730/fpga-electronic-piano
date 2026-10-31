// Source-scoped score cleanup at the production audio boundary.
// The unchanged baseline ALL_NOTES_OFF is GLOBAL panic. Never forward the
// score controller's cleanup request as that event. Drain prior routing,
// release only source14 slots using ordinary NoteOff, then acknowledge.
`timescale 1ns/1ps
module pro_score_audio_adapter (
    input wire clk,rst_n,
    input wire in_valid,
    output wire in_ready,
    input audio_defs_pkg::performance_event_t in_data,
    output wire out_valid,
    input wire out_ready,consumer_idle,
    output audio_defs_pkg::performance_event_t out_data,
    input wire [3:0] occupied,releasing,
    input wire [15:0] sources,channels,
    input wire [31:0] notes
);
    import audio_defs_pkg::*;
    localparam [2:0] IDLE=0, WAIT_IDLE=1, SCAN=2, SEND=3, WAIT_AFTER=4, ACK=5, NORMAL=6;
    reg [2:0] state;
    reg [2:0] index;
    performance_event_t held;
    wire cleanup=in_valid && in_data.source_id==4'd14 &&
        in_data.event_type==EVENT_ALL_NOTES_OFF;
    // Register the score offer before decoding reaches the shared audio
    // ready chain. The producer is acknowledged only on final acceptance,
    // so STOP_DRAIN still covers every captured event. Human FIFO bypass
    // and latency are unchanged. Ordinary score events add one core cycle.
    assign out_valid=rst_n && (state==NORMAL || state==SEND);
    assign out_data=held;
    // An idle source can observe the real consumer ready for STOP_DRAIN.
    assign in_ready=rst_n && (state==ACK ? consumer_idle :
        state==NORMAL ? out_ready :
        state==IDLE && !in_valid ? consumer_idle : 1'b0);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin state<=IDLE;index<=0;held<='0;end
        else case(state)
            IDLE:if(in_valid)begin
                if(cleanup)state<=WAIT_IDLE;
                else begin held<=in_data;state<=NORMAL;end
            end
            NORMAL:if(out_valid && out_ready)state<=IDLE;
            WAIT_IDLE:if(consumer_idle)begin index<=0;state<=SCAN;end
            SCAN:begin
                if(index==4)state<=ACK;
                else if(occupied[index[1:0]] && !releasing[index[1:0]] &&
                    sources[4*index[1:0]+:4]==4'd14)begin
                    held<=make_note_event(1'b0,4'd14,
                        channels[4*index[1:0]+:4],notes[8*index[1:0]+:7],10'd0);
                    state<=SEND;
                end else index<=index+1'b1;
            end
            SEND:if(out_valid && out_ready)state<=WAIT_AFTER;
            WAIT_AFTER:if(consumer_idle)begin index<=index+1'b1;state<=SCAN;end
            ACK:if(in_valid && in_ready)state<=IDLE;
            default:state<=WAIT_IDLE;
        endcase
    end
endmodule
