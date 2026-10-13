// Preparation only; M2 has not selected this resource profile.
// Single clk, async low reset assertion; reset release synchronized upstream.
module m2_n32_prom_resource (
    input wire clk, rst_n, cancel,
    input wire event_valid, input wire [63:0] event_data,
    output wire event_ready,
    input wire sample_valid, input wire [31:0] sample_id,
    output wire sample_ready, result_valid,
    input wire result_ready,
    output wire [31:0] result_id,
    output wire signed [23:0] left, right,
    output wire late, clipped, aborted, idle, fault, publish,
    output wire [1:0] abort_reason,
    input wire read_valid, input wire [4:0] read_slot,
    output wire read_ready, read_out_valid,
    output wire [73:0] read_context
);
    m2_b2d_event_audio_prom #(.N(32), .RESPONSE(1)) candidate (
        .clk(clk), .rst_n(rst_n), .cancel(cancel),
        .event_valid(event_valid), .event_data(event_data), .event_ready(event_ready),
        .sample_valid(sample_valid), .sample_id(sample_id), .sample_ready(sample_ready),
        .result_valid(result_valid), .result_ready(result_ready), .result_id(result_id),
        .left(left), .right(right), .late(late), .clipped(clipped), .aborted(aborted),
        .abort_reason(abort_reason), .idle(idle), .fault(fault), .publish(publish),
        .read_valid(read_valid), .read_slot(read_slot), .read_ready(read_ready),
        .read_out_valid(read_out_valid), .read_context(read_context),
        .inject_valid(1'b0), .inject_tag(77'd0), .inject_context(74'd0)
    );
endmodule
