// Two clock-synchronous performance-event inputs -> one 32-entry system FIFO.
// Reset is active low, synchronous. Source valid/data stay stable until ready.
`timescale 1ns/1ps
module fifo_no_full_bypass #(
    parameter integer DEPTH = 32
) (
    input  logic clk, rst_n,
    input  logic button_valid,
    output logic button_ready,
    input  audio_defs_pkg::performance_event_t button_data,
    input  logic midi_valid,
    output logic midi_ready,
    input  audio_defs_pkg::performance_event_t midi_data,
    output logic event_valid,
    input  logic event_ready,
    output audio_defs_pkg::performance_event_t event_data,
    output logic [15:0] event_fifo_level,
    output logic [15:0] event_fifo_high_watermark
);
    localparam integer PTR_W = (DEPTH <= 2) ? 1 : $clog2(DEPTH);
    localparam integer CNT_W = $clog2(DEPTH + 1);
    audio_defs_pkg::performance_event_t entries [0:DEPTH-1];
    logic [PTR_W-1:0] wr_ptr, rd_ptr;
    logic [CNT_W-1:0] count;
    logic prefer_midi, pop, push, space;
    logic [CNT_W-1:0] next_count;

    function automatic [PTR_W-1:0] advance(input [PTR_W-1:0] ptr);
        if (ptr == DEPTH-1) advance = '0;
        else advance = ptr + 1'b1;
    endfunction

    always_comb begin
        event_valid = rst_n && (count != 0);
        event_data = '0;
        if (event_valid) event_data = entries[rd_ptr];
        pop = event_valid && event_ready;
        // A simultaneous dequeue makes one slot available even at full depth.
        space = rst_n && (count < DEPTH);
        button_ready = space && (!midi_valid || !prefer_midi);
        midi_ready = space && (!button_valid || prefer_midi);
        push = (button_valid && button_ready) || (midi_valid && midi_ready);
        next_count = count + push - pop;
    end

    assign event_fifo_level = {{(16-CNT_W){1'b0}}, count};

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr <= '0;
            rd_ptr <= '0;
            count <= '0;
            prefer_midi <= 1'b0;
            event_fifo_high_watermark <= '0;
        end else begin
            if (push) begin
                entries[wr_ptr] <= midi_valid && midi_ready ? midi_data : button_data;
                wr_ptr <= advance(wr_ptr);
                prefer_midi <= ! (midi_valid && midi_ready);
            end
            if (pop) rd_ptr <= advance(rd_ptr);
            count <= next_count;
            if (next_count > event_fifo_high_watermark)
                event_fifo_high_watermark <= next_count;
        end
    end
endmodule
