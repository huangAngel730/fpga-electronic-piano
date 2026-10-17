// L0/NOT_RUN passive companion for the existing R7-A observer.
module r8_async_reset_edges_component (
    input logic core_clk,
    input logic rst_n,
    input logic pll_locked,
    output logic raw_assert_toggle,
    output logic sampled_rst_n,
    output logic sampled_pll_locked
);
    initial raw_assert_toggle = 1'b0;

    always @(negedge rst_n) begin
        raw_assert_toggle <= ~raw_assert_toggle;
    end

    always_ff @(posedge core_clk) begin
        sampled_rst_n <= rst_n;
        sampled_pll_locked <= pll_locked;
    end
endmodule
