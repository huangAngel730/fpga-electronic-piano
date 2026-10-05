module structure_probe(input wire [31:0] control_pending,
input wire parsed_control,input wire [4:0] parsed_control_index,
input wire parsed_control_keep_pending,input wire grant_control,
input wire [4:0] selected_index,output wire [31:0] observed);
    wire [31:0] control_pending_next;
    generate
        for (genvar slot = 0; slot < 32; slot = slot + 1) begin : g_pending_next
            wire parsed_here = parsed_control && (parsed_control_index == 5'(slot));
            wire granted_here = grant_control && (selected_index == 5'(slot));
            assign control_pending_next[slot] =
                (parsed_here ? 1'b1 : control_pending[slot]) &&
                !granted_here;
        end
    endgenerate


assign observed=control_pending_next;
endmodule
