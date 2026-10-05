`timescale 1ns/1ps
module exact_mask_selector(input logic[31:0]control_pending,
input logic[4:0]round_robin_index,parsed_control_index,locked_index,
input logic parsed_control,control_locked,
input logic[11:0]new_value,held_value,
input logic[15:0]control_cooldown,input logic[3:0]fifo_count,
input logic parsed_discrete,event_ready,burst_limit_reached,
output logic selected_valid,output logic[4:0]selected_index,
output logic[11:0]selected_value,output logic[31:0]selected_mask,
output logic grant_control,output wire[31:0]control_pending_next);
import audio_defs_pkg::*;
performance_event_t parsed_event_data,locked_event;
wire[11:0]pending_value[0:31];wire[11:0]mod_sent_value[0:15];
for(genvar i=0;i<32;i++)assign pending_value[i]=12'(256+17*i);
for(genvar j=0;j<16;j++)assign mod_sent_value[j]=0;
wire[15:0]mod_sent_valid=16'hffff;
logic parsed_control_keep_pending;
localparam FIFO_COUNT_WIDTH=4;
wire discrete_handshake=!control_locked && fifo_count!=0 && event_ready;
always_comb begin parsed_event_data='0;parsed_event_data.control_value=new_value;
locked_event='0;locked_event.control_value=held_value;end
    // Precompute the first TWO candidates from registered state only. Rotate
    // the pending bitmap into RR order, then use a five-level priority tree.
    // No current-byte decode/CC1 cancellation enters this tree. The second
    // candidate is needed if this byte cancels the old first candidate.
    wire [31:0] registered_rr_pending =
        32'({control_pending, control_pending} >> round_robin_index);
    wire first_valid_tree [1:63];
    wire second_valid_tree [1:63];
    wire [4:0] first_rank_tree [1:63];
    wire [4:0] second_rank_tree [1:63];
    // Parallel one-hot grants in RR rank coordinates. These are combinational
    // masks, not new registers or state. The binary rank remains for payload
    // reading and the unchanged round-robin update only.
    wire [31:0] first_mask_tree [1:63];
    wire [31:0] second_mask_tree [1:63];
    generate
        for (genvar slot = 0; slot < 32; slot = slot + 1) begin : g_rr_leaf
            assign first_valid_tree[32 + slot] = registered_rr_pending[slot];
            assign first_rank_tree[32 + slot] = 5'(slot);
            assign second_valid_tree[32 + slot] = 1'b0;
            assign second_rank_tree[32 + slot] = '0;
            assign first_mask_tree[32 + slot] = 32'd1 << slot;
            assign second_mask_tree[32 + slot] = 32'd0;
        end
        for (genvar node = 1; node < 32; node = node + 1) begin : g_rr_branch
            assign first_valid_tree[node] =
                first_valid_tree[2*node] || first_valid_tree[2*node+1];
            assign first_rank_tree[node] = first_valid_tree[2*node] ?
                first_rank_tree[2*node] : first_rank_tree[2*node+1];
            assign second_valid_tree[node] = second_valid_tree[2*node] ||
                (first_valid_tree[2*node] && first_valid_tree[2*node+1]) ||
                second_valid_tree[2*node+1];
            assign second_rank_tree[node] = second_valid_tree[2*node] ?
                second_rank_tree[2*node] : (first_valid_tree[2*node] ?
                first_rank_tree[2*node+1] : second_rank_tree[2*node+1]);
            assign first_mask_tree[node] = first_valid_tree[2*node] ?
                first_mask_tree[2*node] : first_mask_tree[2*node+1];
            assign second_mask_tree[node] = second_valid_tree[2*node] ?
                second_mask_tree[2*node] : (first_valid_tree[2*node] ?
                first_mask_tree[2*node+1] : second_mask_tree[2*node+1]);
        end
    endgenerate
    wire [4:0] old_first_index = round_robin_index + first_rank_tree[1];
    wire [4:0] old_second_index = round_robin_index + second_rank_tree[1];
    wire [11:0] old_first_value = pending_value[old_first_index];
    wire [11:0] old_second_value = pending_value[old_second_index];
    wire [4:0] parsed_control_rank = parsed_control_index - round_robin_index;
    // Rotate masks back to absolute slots without passing through the binary
    // winner index. For RR=0 this is a 32-bit shift of a repeated bitmap.
    wire [5:0] rr_mask_shift = 6'd32 - {1'b0, round_robin_index};
    wire [31:0] old_first_mask = first_valid_tree[1] ?
        32'({first_mask_tree[1], first_mask_tree[1]} >> rr_mask_shift) : 32'd0;
    wire [31:0] old_second_mask = second_valid_tree[1] ?
        32'({second_mask_tree[1], second_mask_tree[1]} >> rr_mask_shift) : 32'd0;
    wire [31:0] parsed_update_mask;
    for(genvar update_slot=0; update_slot<32; update_slot++) begin:g_pending_mask
        assign parsed_update_mask[update_slot] = parsed_control &&
            parsed_control_index == 5'(update_slot);
        // Same-edge parsed updates supersede prior pending state, but an
        // actually granted same-slot newest value is already consumed.
        assign control_pending_next[update_slot] =
            parsed_update_mask[update_slot] ?
                parsed_control_keep_pending :
                (control_pending[update_slot] && !(grant_control && selected_mask[update_slot]));
    end


    always_comb begin
        parsed_control_keep_pending = 1'b0;
        if (parsed_control) begin
            parsed_control_keep_pending = !(
                parsed_control_index[0] &&
                ((control_locked && locked_index == parsed_control_index) ?
                 (locked_event.control_value == parsed_event_data.control_value) :
                 (mod_sent_valid[parsed_control_index[4:1]] &&
                  mod_sent_value[parsed_control_index[4:1]] ==
                      parsed_event_data.control_value)));
        end

        selected_valid = 1'b0;
        selected_index = '0;
        selected_value = '0;
        selected_mask = 32'd0;
        if (first_valid_tree[1]) begin
            selected_valid = 1'b1;
            selected_index = old_first_index;
            selected_value = old_first_value;
            selected_mask = old_first_mask;
        end
        // One byte can change only one slot. Insertion/newest-value capture
        // competes with the old first; cancellation of that first falls back
        // to the old second. Other updates cannot change the winner.
        if (parsed_control) begin
            if (parsed_control_keep_pending &&
                (!first_valid_tree[1] ||
                 parsed_control_rank <= first_rank_tree[1])) begin
                selected_valid = 1'b1;
                selected_index = parsed_control_index;
                selected_value = parsed_event_data.control_value;
                selected_mask = parsed_update_mask;
            end else if (!parsed_control_keep_pending && first_valid_tree[1] &&
                         parsed_control_index == old_first_index) begin
                selected_valid = second_valid_tree[1];
                selected_index = second_valid_tree[1] ? old_second_index : 5'd0;
                selected_value = second_valid_tree[1] ? old_second_value : 12'd0;
                selected_mask = old_second_mask;
            end
        end

        // A discrete event already presented to the receiver is never
        // pre-empted. The continuous grant is locked on the same edge as the
        // Nth successful discrete handshake, so the next presented event is
        // the control and the bound cannot slip by one event.
        grant_control = !control_locked && (control_cooldown == 0) &&
            selected_valid &&
            (((fifo_count == 0) && !parsed_discrete) ||
             (discrete_handshake && burst_limit_reached));
    end

endmodule
