// B-specific top around the frozen B2C stimulus. The stimulus and its original
// capture rows remain unchanged; b_n32_observer adds K rows for accurate clip.
`timescale 1ns/1ps
module tb_b_n32_r1;
    // Required by the exact Gowin pROM simulation model.  This is simulator
    // infrastructure only and is not a second DUT reset or a board interface.
    GSR GSR(.GSRI(1'b1));
    tb_b2d_event_audio core();
    b_n32_observer observer(
        .clk(core.clk), .rst_n(core.rst_n), .cancel(core.cancel),
        .aborted(core.aborted), .result_valid(core.result_valid),
        .result_ready(core.result_ready), .publish(core.publish),
        .result_id(core.result_id), .left(core.left), .right(core.right),
        .late(core.late), .clipped(core.dut.clipped)
    );
endmodule
