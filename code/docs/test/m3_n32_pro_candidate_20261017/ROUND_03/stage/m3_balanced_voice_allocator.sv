// Independent successor of b2c_voice_allocator SHA256 9fec9f83...39506061.
// Single sys_clk domain. Reset is asynchronously asserted low, as in original.
// Public ports, latency, packed state and pre-edge write priority are unchanged.
// Supported task configurations are N=4,8,16,32 with SW=$clog2(N).
`timescale 1ns/1ps

module m3_balanced_voice_allocator #(
    parameter integer N = 8,
    parameter integer SW = $clog2(N)
) (
    input  logic sys_clk,
    input  logic sys_rst_n,
    input  logic note_on,
    input  logic note_off,
    input  logic [3:0] source_id,
    input  logic [3:0] channel_id,
    input  logic [7:0] midi_note,
    input  logic [N-1:0] release_done,
    output logic [SW-1:0] allocated_slot,
    output logic slot_valid,
    output logic [SW-1:0] release_slot,
    output logic release_target_valid
);
    localparam integer WIDTH = 18 + SW;
    logic [WIDTH-1:0] slots [0:N-1];

    // Heap-indexed binary tree: leaves [N,2*N), root 1.
    // Class 0 is matching active/releasing identity, 1 is IDLE, 2 is LRU.
    wire [1:0] select_class [1:2*N-1];
    wire [SW-1:0] select_age [1:2*N-1];
    wire [SW-1:0] select_index [1:2*N-1];
    wire off_valid [1:2*N-1];
    wire [SW-1:0] off_index [1:2*N-1];

    genvar lane;
    generate
        for (lane = 0; lane < N; lane = lane + 1) begin : g_leaf
            wire identity_match =
                slots[lane][SW+15:SW+12] == source_id &&
                slots[lane][SW+11:SW+8] == channel_id &&
                slots[lane][SW+7:SW] == midi_note;
            wire occupied = slots[lane][WIDTH-1] || slots[lane][WIDTH-2];
            // MUTATION_PRIORITY: swap matching identity and IDLE precedence.
            assign select_class[N+lane] = (occupied && identity_match) ? 2'd0 :
                                           (!occupied) ? 2'd1 : 2'd2;
            assign select_age[N+lane] = slots[lane][SW-1:0];
            assign select_index[N+lane] = SW'(lane);
            assign off_valid[N+lane] = slots[lane][WIDTH-1] && identity_match;
            assign off_index[N+lane] = SW'(lane);

            // All tests use pre-edge state. Later writes override earlier ones.
            always_ff @(posedge sys_clk or negedge sys_rst_n) begin
                if (!sys_rst_n) begin
                    slots[lane] <= '0;
                    slots[lane][SW-1:0] <= SW'(lane);
                end else begin
                    if (release_done[lane] && slots[lane][WIDTH-2]) begin
                        slots[lane][WIDTH-1] <= 1'b0;
                        slots[lane][WIDTH-2] <= 1'b0;
                    end
                    if (note_on) begin
                        if (select_index[1] == SW'(lane)) begin
                            slots[lane][WIDTH-1] <= 1'b1;
                            slots[lane][WIDTH-2] <= 1'b0;
                            slots[lane][SW+15:SW+12] <= source_id;
                            slots[lane][SW+11:SW+8] <= channel_id;
                            slots[lane][SW+7:SW] <= midi_note;
                            slots[lane][SW-1:0] <= SW'(N-1);
                        end else if (slots[lane][SW-1:0] > select_age[1]) begin
                            slots[lane][SW-1:0] <= slots[lane][SW-1:0] - 1'b1;
                        end
                    end
                    if (note_off && off_valid[N+lane]) begin
                        slots[lane][WIDTH-1] <= 1'b0;
                        slots[lane][WIDTH-2] <= 1'b1;
                    end
                end
            end
        end
    endgenerate

    genvar branch;
    generate
        for (branch = 1; branch < N; branch = branch + 1) begin : g_reduce
            localparam integer L = 2 * branch;
            localparam integer R = 2 * branch + 1;
            wire same_class = select_class[L] == select_class[R];
            wire compare_age = same_class && select_class[L] == 2'd2;
            // MUTATION_TIE: reversing this comparison prefers the high slot.
            wire low_index_first = select_index[L] <= select_index[R];
            wire take_left = (select_class[L] < select_class[R]) ||
                (same_class && (!compare_age || select_age[L] == select_age[R]) &&
                 low_index_first) ||
                (compare_age && select_age[L] < select_age[R]);
            assign select_class[branch] = take_left ? select_class[L] : select_class[R];
            assign select_age[branch] = take_left ? select_age[L] : select_age[R];
            assign select_index[branch] = take_left ? select_index[L] : select_index[R];
            // Original NoteOff loop publishes its last (highest-index) match.
            assign off_valid[branch] = off_valid[L] || off_valid[R];
            assign off_index[branch] = off_valid[R] ? off_index[R] : off_index[L];
        end
    endgenerate

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            allocated_slot <= '0;
            slot_valid <= 1'b0;
            release_slot <= '0;
            release_target_valid <= 1'b0;
        end else begin
            slot_valid <= 1'b0;
            release_target_valid <= 1'b0;
            if (note_on) begin
                allocated_slot <= select_index[1];
                slot_valid <= 1'b1;
            end
            if (note_off && off_valid[1]) begin
                release_slot <= off_index[1];
                release_target_valid <= 1'b1;
            end
        end
    end
endmodule
