// -----------------------------------------------------------------------------
// k4_reset_sync.sv
// 复位同步器。对应任务 T019，接口规范 v1.0 第 2.2 节。
//
// 行为：
//   - 外部 rst_n 低有效；
//   - 异步拉低，立即生效；
//   - 在目标时钟域同步释放，避免释放时的亚稳态和复位沿竞争。
//
// 每个真正独立的时钟域必须例化本模块，不跨域共享同步后的复位
// （接口规范 2.2 节）。
//
// 复位释放延迟：STAGES 个目标时钟周期。
// -----------------------------------------------------------------------------

`ifndef K4_RESET_SYNC_SV
`define K4_RESET_SYNC_SV

`timescale 1ns / 1ps

module k4_reset_sync #(
    // 同步级数。2 级是亚稳态防护的通行下限；
    // 高频或高可靠性场合可加大到 3。
    parameter int unsigned STAGES = 2
) (
    input  logic clk,       // 目标时钟域时钟
    input  logic rst_n,     // 外部异步复位，低有效
    output logic rst_sync_n // 同步释放后的复位，低有效
);

    // 上电时若 rst_n 尚未稳定，移位寄存器应处于复位状态。
    // 使用 (* async_reg *) 提示综合工具将其放入专用同步触发器，
    // 并避免被优化或重定时。
    (* async_reg = "true" *) logic [STAGES-1:0] sync_chain;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // 异步拉低：立即清零，不等时钟
            sync_chain <= '0;
        end else begin
            // 同步释放：逐级移入 1
            sync_chain <= {sync_chain[STAGES-2:0], 1'b1};
        end
    end

    assign rst_sync_n = sync_chain[STAGES-1];

endmodule

`endif  // K4_RESET_SYNC_SV
