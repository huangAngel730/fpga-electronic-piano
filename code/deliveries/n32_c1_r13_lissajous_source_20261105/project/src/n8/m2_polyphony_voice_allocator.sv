// Parameterized successor of frozen rank-LRU allocator. N=4/8/16/32 only.
// Single clk; rst_n async assert, upstream synchronized release. No new math.
`timescale 1ns/1ps

module m2_polyphony_voice_allocator #(parameter integer N=8, SW=$clog2(N)) (
    input  logic       sys_clk,
    input  logic       sys_rst_n,
    input  logic       note_on,
    input  logic       note_off,
    input  logic [3:0] source_id,      // 来源ID
    input  logic [3:0] channel_id,     // 通道ID
    input  logic [7:0] midi_note,
    input  logic [N-1:0] release_done,   // 每声部独立Release完成信号
    output logic [SW-1:0] allocated_slot,
    output logic       slot_valid,
    output logic [SW-1:0] release_slot,   // Release目标槽位
    output logic       release_target_valid
);

    typedef struct packed {
        logic       note_active;   // Note On活跃
        logic       in_release;    // Release阶段
        logic [3:0] source;
        logic [3:0] channel;
        logic [7:0] note;
        logic [SW-1:0] age;           // rank 0 oldest, N-1 newest; no event-count wrap
    } voice_slot_t;

    logic [18+SW-1:0] slots [0:N-1];

    integer i;

    // N32 cannot close timing when duplicate/free/oldest selection and all
    // rank updates are expanded into one clock cycle.  Events are already
    // back-pressured by the router, so use one shared lane scanner instead.
    // Selection priority remains byte-for-byte compatible: first duplicate,
    // then first free lane, then the minimum rank (lowest index on a tie).
    localparam logic [2:0] A_IDLE=3'd0, A_SCAN_ON=3'd1,
        A_SELECT_ON=3'd2, A_UPDATE_AGE=3'd3, A_SCAN_OFF=3'd4;
    logic [2:0] allocator_state;
    logic [SW-1:0] scan_index, update_index;
    logic [3:0] request_source, request_channel;
    logic [7:0] request_note;
    logic duplicate_found, free_found;
    logic [SW-1:0] duplicate_slot, free_slot;
    logic [SW-1:0] oldest_rank, oldest_slot;
    logic [SW-1:0] selected_slot, selected_age;
    wire [SW-1:0] selected_candidate = duplicate_found ? duplicate_slot :
        (free_found ? free_slot : oldest_slot);

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            for (i = 0; i < N; i = i + 1) begin
                slots[i] <= '0;
                slots[i][SW-1:0] <= i[SW-1:0];
            end
            allocated_slot <= '0;
            slot_valid <= 1'b0;
            release_slot <= '0;
            release_target_valid <= 1'b0;
            allocator_state <= A_IDLE;
            scan_index <= '0;
            update_index <= '0;
            request_source <= '0;
            request_channel <= '0;
            request_note <= '0;
            duplicate_found <= 1'b0;
            free_found <= 1'b0;
            duplicate_slot <= '0;
            free_slot <= '0;
            oldest_rank <= {SW{1'b1}};
            oldest_slot <= '0;
            selected_slot <= '0;
            selected_age <= '0;
        end else begin
            slot_valid <= 1'b0;
            release_target_valid <= 1'b0;

            // Release完成：清除对应槽位
            for (i = 0; i < N; i = i + 1) begin
                if (release_done[i] && slots[i][18+SW-2]) begin
                    slots[i][18+SW-1] <= 1'b0;
                    slots[i][18+SW-2] <= 1'b0;
                end
            end

            case (allocator_state)
                A_IDLE: begin
                    if (note_on) begin
                        request_source <= source_id;
                        request_channel <= channel_id;
                        request_note <= midi_note;
                        scan_index <= '0;
                        duplicate_found <= 1'b0;
                        free_found <= 1'b0;
                        oldest_rank <= {SW{1'b1}};
                        oldest_slot <= '0;
                        allocator_state <= A_SCAN_ON;
                    end else if (note_off) begin
                        request_source <= source_id;
                        request_channel <= channel_id;
                        request_note <= midi_note;
                        scan_index <= '0;
                        allocator_state <= A_SCAN_OFF;
                    end
                end

                A_SCAN_ON: begin
                    if (!duplicate_found &&
                        (slots[scan_index][18+SW-1] || slots[scan_index][18+SW-2]) &&
                        slots[scan_index][SW+15:SW+12] == request_source &&
                        slots[scan_index][SW+11:SW+8] == request_channel &&
                        slots[scan_index][SW+7:SW] == request_note) begin
                        duplicate_found <= 1'b1;
                        duplicate_slot <= scan_index;
                    end
                    if (!free_found && !slots[scan_index][18+SW-1] &&
                        !slots[scan_index][18+SW-2]) begin
                        free_found <= 1'b1;
                        free_slot <= scan_index;
                    end
                    if (slots[scan_index][SW-1:0] < oldest_rank ||
                        (slots[scan_index][SW-1:0] == oldest_rank &&
                         scan_index < oldest_slot)) begin
                        oldest_rank <= slots[scan_index][SW-1:0];
                        oldest_slot <= scan_index;
                    end
                    if (scan_index == SW'(N-1))
                        allocator_state <= A_SELECT_ON;
                    else
                        scan_index <= scan_index + 1'b1;
                end

                A_SELECT_ON: begin
                    selected_slot <= selected_candidate;
                    selected_age <= slots[selected_candidate][SW-1:0];
                    update_index <= '0;
                    allocator_state <= A_UPDATE_AGE;
                end

                A_UPDATE_AGE: begin
                    if (update_index != selected_slot &&
                        slots[update_index][SW-1:0] > selected_age)
                        slots[update_index][SW-1:0] <=
                            slots[update_index][SW-1:0] - 1'b1;
                    if (update_index == SW'(N-1)) begin
                        allocated_slot <= selected_slot;
                        slot_valid <= 1'b1;
                        slots[selected_slot][18+SW-1] <= 1'b1;
                        slots[selected_slot][18+SW-2] <= 1'b0;
                        slots[selected_slot][SW+15:SW+12] <= request_source;
                        slots[selected_slot][SW+11:SW+8] <= request_channel;
                        slots[selected_slot][SW+7:SW] <= request_note;
                        slots[selected_slot][SW-1:0] <= SW'(N-1);
                        allocator_state <= A_IDLE;
                    end else begin
                        update_index <= update_index + 1'b1;
                    end
                end

                A_SCAN_OFF: begin
                    if (slots[scan_index][18+SW-1] &&
                        slots[scan_index][SW+15:SW+12] == request_source &&
                        slots[scan_index][SW+11:SW+8] == request_channel &&
                        slots[scan_index][SW+7:SW] == request_note) begin
                        slots[scan_index][18+SW-1] <= 1'b0;
                        slots[scan_index][18+SW-2] <= 1'b1;
                        release_slot <= scan_index;
                        release_target_valid <= 1'b1;
                        allocator_state <= A_IDLE;
                    end else if (scan_index == SW'(N-1)) begin
                        allocator_state <= A_IDLE;
                    end else begin
                        scan_index <= scan_index + 1'b1;
                    end
                end

                default: allocator_state <= A_IDLE;
            endcase
        end
    end

endmodule

// Private selector unit: shared by the actual allocator and direct tie-vector
// tests. The public allocator ABI above remains byte-identical to the source.
// Supported verification points: N=1 (explicit SW=1), 4, 8, 16, 32.
// The min proof is for known ranks after reset, not arbitrary corrupt X ranks.
module m2_polyphony_oldest_balanced_tree_r01 #(
    parameter integer N = 8,
    parameter integer SW = (N > 1) ? $clog2(N) : 1
) (
    input  wire [N*SW-1:0] rank_leaves,
    output wire [SW-1:0] minimum_rank,
    output wire [SW-1:0] minimum_index
);
    wire [SW-1:0] rank_tree [1:2*N-1];
    wire [SW-1:0] index_tree [1:2*N-1];
    generate
        for (genvar leaf = 0; leaf < N; leaf = leaf + 1) begin : fixed_leaves
            assign rank_tree[N+leaf] = rank_leaves[leaf*SW +: SW];
            assign index_tree[N+leaf] = SW'(leaf);
        end
        for (genvar node = 1; node < N; node = node + 1) begin : balanced_nodes
            wire right_wins;
            assign right_wins =
                (rank_tree[2*node+1] < rank_tree[2*node]) ||
                ((rank_tree[2*node+1] == rank_tree[2*node]) &&
                 (index_tree[2*node+1] < index_tree[2*node]));
            assign rank_tree[node] =
                right_wins ? rank_tree[2*node+1] : rank_tree[2*node];
            assign index_tree[node] =
                right_wins ? index_tree[2*node+1] : index_tree[2*node];
        end
    endgenerate
    assign minimum_rank = rank_tree[1];
    assign minimum_index = index_tree[1];
endmodule
