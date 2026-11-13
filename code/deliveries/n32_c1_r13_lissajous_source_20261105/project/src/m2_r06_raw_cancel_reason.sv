// C7 diagnostic-only raw control encoding. No state, clock, or reset.
// 00 NONE; 01 FRAME_BOUNDARY; 10/11 reserved and never generated here.
// raw_cancel X/Z is preserved as 0X/0Z, never silently changed to NONE.
// It neither identifies a request nor authorizes transaction cleanup.
module m2_r06_raw_cancel_reason (
    input  wire raw_cancel,
    output wire [1:0] raw_reason
);
    assign raw_reason = {1'b0, raw_cancel};
endmodule
