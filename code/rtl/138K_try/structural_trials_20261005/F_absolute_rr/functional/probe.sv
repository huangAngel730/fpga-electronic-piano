module structure_probe(input wire [31:0]control_pending,
input wire[4:0]round_robin_index,input wire parsed_control,
input wire[4:0]parsed_control_index,input wire[11:0]value_in,
output logic selected_valid,output logic[4:0]selected_index,output logic[11:0]selected_value);
import audio_defs_pkg::*;
performance_event_t parsed_event_data;
wire performance_event_t locked_event='0;
wire control_locked=0;wire[4:0]locked_index=0;
wire[15:0]mod_sent_valid=16'hffff;wire[11:0]mod_sent_value[0:15];
wire[11:0]pending_value[0:31];
for(genvar k=0;k<16;k++)assign mod_sent_value[k]=0;
for(genvar k=0;k<32;k++)assign pending_value[k]=12'(k+1);
always_comb begin parsed_event_data='0;parsed_event_data.control_value=value_in;end
logic parsed_control_keep_pending,grant_control;
wire[15:0]control_cooldown=1;wire[3:0]fifo_count=0;
wire parsed_discrete=0,discrete_handshake=0,burst_limit_reached=0;
    // ISOLATED F: two absolute-index priority trees, no barrel rotation and
    // no RR+rank feedback adder. Suffix [RR,31] precedes prefix [0,RR-1].
    // Both first and second candidates remain combinational, same cycle.
    wire suffix_first_valid [1:63], suffix_second_valid [1:63];
    wire prefix_first_valid [1:63], prefix_second_valid [1:63];
    wire [4:0] suffix_first_index [1:63], suffix_second_index [1:63];
    wire [4:0] prefix_first_index [1:63], prefix_second_index [1:63];
    generate
        for (genvar slot = 0; slot < 32; slot = slot + 1) begin : g_rr_leaf
            wire in_suffix = 5'(slot) >= round_robin_index;
            assign suffix_first_valid[32 + slot] = control_pending[slot] && in_suffix;
            assign prefix_first_valid[32 + slot] = control_pending[slot] && !in_suffix;
            assign suffix_first_index[32 + slot] = 5'(slot);
            assign prefix_first_index[32 + slot] = 5'(slot);
            assign suffix_second_valid[32 + slot] = 1'b0;
            assign prefix_second_valid[32 + slot] = 1'b0;
            assign suffix_second_index[32 + slot] = '0;
            assign prefix_second_index[32 + slot] = '0;
        end
        for (genvar node = 1; node < 32; node = node + 1) begin : g_rr_branch
            assign suffix_first_valid[node] = suffix_first_valid[2*node] || suffix_first_valid[2*node+1];
            assign suffix_first_index[node] = suffix_first_valid[2*node] ?
                suffix_first_index[2*node] : suffix_first_index[2*node+1];
            assign suffix_second_valid[node] = suffix_second_valid[2*node] ||
                (suffix_first_valid[2*node] && suffix_first_valid[2*node+1]) || suffix_second_valid[2*node+1];
            assign suffix_second_index[node] = suffix_second_valid[2*node] ?
                suffix_second_index[2*node] : (suffix_first_valid[2*node] ?
                suffix_first_index[2*node+1] : suffix_second_index[2*node+1]);
            assign prefix_first_valid[node] = prefix_first_valid[2*node] || prefix_first_valid[2*node+1];
            assign prefix_first_index[node] = prefix_first_valid[2*node] ?
                prefix_first_index[2*node] : prefix_first_index[2*node+1];
            assign prefix_second_valid[node] = prefix_second_valid[2*node] ||
                (prefix_first_valid[2*node] && prefix_first_valid[2*node+1]) || prefix_second_valid[2*node+1];
            assign prefix_second_index[node] = prefix_second_valid[2*node] ?
                prefix_second_index[2*node] : (prefix_first_valid[2*node] ?
                prefix_first_index[2*node+1] : prefix_second_index[2*node+1]);
        end
    endgenerate
    wire first_valid_tree [1:1], second_valid_tree [1:1];
    assign first_valid_tree[1] = suffix_first_valid[1] || prefix_first_valid[1];
    assign second_valid_tree[1] = suffix_second_valid[1] ||
        (suffix_first_valid[1] && prefix_first_valid[1]) || prefix_second_valid[1];
    wire [4:0] old_first_index = suffix_first_valid[1] ? suffix_first_index[1] : prefix_first_index[1];
    wire [4:0] old_second_index = suffix_second_valid[1] ? suffix_second_index[1] :
        (suffix_first_valid[1] ? prefix_first_index[1] : prefix_second_index[1]);
    wire [11:0] old_first_value = pending_value[old_first_index];
    wire [11:0] old_second_value = pending_value[old_second_index];
    wire parsed_in_suffix = parsed_control_index >= round_robin_index;
    wire old_first_in_suffix = old_first_index >= round_robin_index;
    wire parsed_precedes_first = (parsed_in_suffix == old_first_in_suffix) ?
        (parsed_control_index <= old_first_index) : parsed_in_suffix;

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
        if (first_valid_tree[1]) begin
            selected_valid = 1'b1;
            selected_index = old_first_index;
            selected_value = old_first_value;
        end
        // One byte can change only one slot. Insertion/newest-value capture
        // competes with the old first; cancellation of that first falls back
        // to the old second. Other updates cannot change the winner.
        if (parsed_control) begin
            if (parsed_control_keep_pending &&
                (!first_valid_tree[1] ||
                 parsed_precedes_first)) begin
                selected_valid = 1'b1;
                selected_index = parsed_control_index;
                selected_value = parsed_event_data.control_value;
            end else if (!parsed_control_keep_pending && first_valid_tree[1] &&
                         parsed_control_index == old_first_index) begin
                selected_valid = second_valid_tree[1];
                selected_index = second_valid_tree[1] ? old_second_index : 5'd0;
                selected_value = second_valid_tree[1] ? old_second_value : 12'd0;
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
