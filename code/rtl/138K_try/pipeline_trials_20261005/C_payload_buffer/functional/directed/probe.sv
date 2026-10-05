`timescale 1ns/1ps
module prepared_selector_probe(input logic clk,rst_n,input logic[31:0]control_pending,input logic[4:0]round_robin_index,input logic parsed_control,input logic[4:0]parsed_control_index,input logic[11:0]value_in,output logic selected_valid,output logic[4:0]selected_index,output logic[11:0]selected_value);
import audio_defs_pkg::*;
performance_event_t parsed_event_data;
wire performance_event_t locked_event='0;
wire control_locked=1'b0;wire[4:0]locked_index=0;
wire[15:0]mod_sent_valid=16'hffff;
wire[11:0]mod_sent_value[0:15];
wire[11:0]pending_value[0:31];
for(genvar k=0;k<16;k++)assign mod_sent_value[k]=0;
for(genvar k=0;k<32;k++)assign pending_value[k]=12'(k+1);
always_comb begin parsed_event_data='0;parsed_event_data.control_value=value_in;end
logic parsed_control_keep_pending,grant_control;
wire[15:0]control_cooldown=16'd1;
wire[3:0]fifo_count=0;
wire parsed_discrete=0,discrete_handshake=0,burst_limit_reached=0;
    // ISOLATED M2 candidate: register the first three RR candidates.
    // No current byte or ready enters the preparation tree. Its snapshot is
    // one cycle old; at most one previous parsed update needs repair. A grant
    // changes RR/pending while locked, and the lock supplies the refresh cycle.
    wire [31:0] prepare_rr_pending =
        32'({control_pending, control_pending} >> round_robin_index);
    wire [2:0] prep_valid [1:63];
    wire [4:0] prep_rank0 [1:63], prep_rank1 [1:63], prep_rank2 [1:63];
    generate
        for(genvar leaf=0;leaf<32;leaf=leaf+1) begin:g_prepare_leaf
            assign prep_valid[32+leaf] = {2'b00,prepare_rr_pending[leaf]};
            assign prep_rank0[32+leaf] = 5'(leaf);
            assign prep_rank1[32+leaf] = '0;
            assign prep_rank2[32+leaf] = '0;
        end
        for(genvar node=1;node<32;node=node+1) begin:g_prepare_node
            wire a0=prep_valid[2*node][0], a1=prep_valid[2*node][1], a2=prep_valid[2*node][2];
            wire b0=prep_valid[2*node+1][0], b1=prep_valid[2*node+1][1], b2=prep_valid[2*node+1][2];
            assign prep_valid[node][0]=a0||b0;
            assign prep_valid[node][1]=a1||(a0&&b0)||b1;
            assign prep_valid[node][2]=a2||(a1&&b0)||(a0&&b1)||b2;
            assign prep_rank0[node]=a0?prep_rank0[2*node]:prep_rank0[2*node+1];
            assign prep_rank1[node]=a1?prep_rank1[2*node]:(a0?prep_rank0[2*node+1]:prep_rank1[2*node+1]);
            assign prep_rank2[node]=a2?prep_rank2[2*node]:(a1?prep_rank0[2*node+1]:(a0?prep_rank1[2*node+1]:prep_rank2[2*node+1]));
        end
    endgenerate
    logic [2:0] prepared_valid;
    logic [4:0] prepared_rank0,prepared_rank1,prepared_rank2;
    logic [4:0] prepared_index0,prepared_index1,prepared_index2;
    logic [11:0] prepared_value0,prepared_value1,prepared_value2;
    logic [11:0] previous_value;
    logic previous_update, previous_keep;
    logic [4:0] previous_index;
    wire [4:0] previous_rank=previous_index-round_robin_index;
    logic first_prepared_valid,second_prepared_valid;
    logic [4:0] first_prepared_rank,second_prepared_rank;
    logic [4:0] old_first_index,old_second_index;
    always_comb begin
        first_prepared_valid=prepared_valid[0];
        second_prepared_valid=prepared_valid[1];
        first_prepared_rank=prepared_rank0;
        second_prepared_rank=prepared_rank1;
        old_first_index=prepared_index0;
        old_second_index=prepared_index1;
        if(previous_update) begin
            if(previous_keep) begin
                if(!prepared_valid[0] || previous_rank<=prepared_rank0) begin
                    first_prepared_valid=1'b1;
                    first_prepared_rank=previous_rank;
                    old_first_index=previous_index;
                    if(previous_index!=prepared_index0 || !prepared_valid[0]) begin
                        second_prepared_valid=prepared_valid[0];
                        second_prepared_rank=prepared_rank0;
                        old_second_index=prepared_index0;
                    end
                end else if(!prepared_valid[1] || previous_rank<=prepared_rank1) begin
                    second_prepared_valid=1'b1;
                    second_prepared_rank=previous_rank;
                    old_second_index=previous_index;
                end
            end else if(prepared_valid[0] && previous_index==prepared_index0) begin
                first_prepared_valid=prepared_valid[1];
                first_prepared_rank=prepared_rank1;
                old_first_index=prepared_index1;
                second_prepared_valid=prepared_valid[2];
                second_prepared_rank=prepared_rank2;
                old_second_index=prepared_index2;
            end else if(prepared_valid[1] && previous_index==prepared_index1) begin
                second_prepared_valid=prepared_valid[2];
                second_prepared_rank=prepared_rank2;
                old_second_index=prepared_index2;
            end
        end
    end
    // Snapshot the payload at the SAME boundary as its candidate index.
    // A previous parsed update repairs both identity and value; the current
    // byte still overrides these candidates in the unchanged arbitration.
    wire [11:0] old_first_value = previous_update && old_first_index==previous_index ?
        previous_value : old_first_index==prepared_index0 ? prepared_value0 :
        old_first_index==prepared_index1 ? prepared_value1 : prepared_value2;
    wire [11:0] old_second_value = previous_update && old_second_index==previous_index ?
        previous_value : old_second_index==prepared_index0 ? prepared_value0 :
        old_second_index==prepared_index1 ? prepared_value1 : prepared_value2;
    wire [4:0] parsed_control_rank = parsed_control_index - round_robin_index;
    // Preparation is speculative: this changes no public event latency/state.
    always_ff @(posedge clk) begin
        if(!rst_n) begin
            prepared_valid<='0;
            prepared_rank0<='0;prepared_rank1<='0;prepared_rank2<='0;
            prepared_index0<='0;prepared_index1<='0;prepared_index2<='0;
            prepared_value0<='0;prepared_value1<='0;prepared_value2<='0;
            previous_value<='0;
            previous_update<=1'b0;previous_keep<=1'b0;previous_index<='0;
        end else begin
            prepared_valid<=prep_valid[1];
            prepared_rank0<=prep_rank0[1];prepared_rank1<=prep_rank1[1];prepared_rank2<=prep_rank2[1];
            prepared_index0<=round_robin_index+prep_rank0[1];
            prepared_index1<=round_robin_index+prep_rank1[1];
            prepared_index2<=round_robin_index+prep_rank2[1];
            prepared_value0<=pending_value[5'(round_robin_index+prep_rank0[1])];
            prepared_value1<=pending_value[5'(round_robin_index+prep_rank1[1])];
            prepared_value2<=pending_value[5'(round_robin_index+prep_rank2[1])];
            previous_value<=parsed_event_data.control_value;
            previous_update<=parsed_control;
            previous_index<=parsed_control_index;
            previous_keep<=parsed_control_keep_pending &&
                !(grant_control && parsed_control_index==selected_index);
        end
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
        if (first_prepared_valid) begin
            selected_valid = 1'b1;
            selected_index = old_first_index;
            selected_value = old_first_value;
        end
        // One byte can change only one slot. Insertion/newest-value capture
        // competes with the old first; cancellation of that first falls back
        // to the old second. Other updates cannot change the winner.
        if (parsed_control) begin
            if (parsed_control_keep_pending &&
                (!first_prepared_valid ||
                 parsed_control_rank <= first_prepared_rank)) begin
                selected_valid = 1'b1;
                selected_index = parsed_control_index;
                selected_value = parsed_event_data.control_value;
            end else if (!parsed_control_keep_pending && first_prepared_valid &&
                         parsed_control_index == old_first_index) begin
                selected_valid = second_prepared_valid;
                selected_index = second_prepared_valid ? old_second_index : 5'd0;
                selected_value = second_prepared_valid ? old_second_value : 12'd0;
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
