// -----------------------------------------------------------------------------
// key_debounce.sv
// 按键去抖 + 边沿检测。对应任务 T020（可综合集成骨架）的输入前端。
//
// 定位：本模块是集成骨架的**占位实现**。正式的按键与去抖属于 T021（M3，
// rtl/input/），本模块放在 rtl/common/ 是因为骨架需要一个可综合、可上板的
// 输入前端来打通"按键 -> 事件 -> 音高"这条链路；T021 落地后可由 M3 替换，
// 接口保持不变。
//
// -----------------------------------------------------------------------------
// 去抖策略：计数器式稳定判定
// -----------------------------------------------------------------------------
//   对每个按键独立计数。当前电平与已确认电平不同时计数递增，相同则清零；
//   计数达到 DEBOUNCE_CNT 时才把该电平确认为新的稳定值，并产生一次跳变脉冲。
//
//   为什么不用"移位寄存器取多数"：计数器法只占一个寄存器加一个计数器，
//   且门限时间可直接由参数算出，便于按板子实际抖动调整。
//
//   门限计算：DEBOUNCE_CNT = CLK_HZ * DEBOUNCE_MS / 1000
//     本板 50 MHz、默认 10 ms -> 500000 个时钟。
//     按键机械抖动典型 5-20 ms，取 10 ms 是常规折中：
//     太短会重复触发，太长会让快速连奏丢音。
//
// -----------------------------------------------------------------------------
// 电平时序（关键，与板级事实一致）
// -----------------------------------------------------------------------------
//   板载用户按键 EX_KEY.1/EX_KEY.2 为**低有效**：按下接地 = 0，松开上拉 = 1。
//   官方 README 明确要求内部上拉（"there aren't any pull-up on the dock board"），
//   故 CST 里必须写 PULL_MODE=UP，漏掉会导致悬空乱跳。
//
//   本模块的 key_n 输入即该低有效原始电平；内部统一转换成
//   **高有效的 pressed**（1 = 按下）后再对外输出，
//   使上层不必再关心极性，减少下游写反的机会。
//
// -----------------------------------------------------------------------------
// 复位
// -----------------------------------------------------------------------------
//   异步复位、同步释放（由顶层 reset_sync 统一产生），低有效。
//   复位时把所有已确认电平置为"松开"（1），并且不产生任何跳变脉冲，
//   避免上电瞬间因为按键初始电平被判成一次假按键。
// -----------------------------------------------------------------------------

`ifndef KEY_DEBOUNCE_SV
`define KEY_DEBOUNCE_SV

`timescale 1ns / 1ps

module key_debounce #(
    // 按键位宽（本工程用 2：EX_KEY.1 / EX_KEY.2）
    parameter int unsigned KEYS = 2,
    // 去抖门限（时钟周期数）。必须 >= 2，否则计数器无法工作。
    // 默认 500000 对应 50 MHz 下的 10 ms。
    parameter int unsigned DEBOUNCE_CNT = 500_000,
    // 计数位宽。留 1 位余量以便容纳 DEBOUNCE_CNT 本身。
    parameter int unsigned CNT_BITS = $clog2(DEBOUNCE_CNT + 1)
) (
    input  logic              clk,
    input  logic              rst_n,
    // 原始按键输入，低有效（按下 = 0），已在 CST 中配置内部上拉
    input  logic [KEYS-1:0]   key_n,
    // 去抖后的稳定状态，高有效（按下 = 1）
    output logic [KEYS-1:0]   pressed,
    // 每键一个单周期脉冲：确认按下 / 确认松开
    output logic [KEYS-1:0]   press_pulse,
    output logic [KEYS-1:0]   release_pulse
);

    // 把低有效的原始输入转成高有效的"原始按下"。
    // 只做电平取反，不做任何同步——按键是异步输入，
    // 但去抖计数器本身就要求输入稳定 DEBOUNCE_CNT 个周期，
    // 因此天然滤掉了亚稳态，不需要额外的两级同步器。
    logic [KEYS-1:0] raw_pressed;
    assign raw_pressed = ~key_n;

    // 每个按键一个计数器和一个已确认状态
    logic [CNT_BITS-1:0] cnt [KEYS];
    logic [KEYS-1:0]     stable_q;

    // 下一拍的稳定值（组合），用于比较与输出
    logic [KEYS-1:0] stable_d;
    logic [KEYS-1:0] press_d;
    logic [KEYS-1:0] release_d;

    always_comb begin
        stable_d  = stable_q;
        press_d   = '0;
        release_d = '0;
        for (int unsigned i = 0; i < KEYS; i++) begin
            // 原始电平与已确认电平不同 -> 正在变化，计数；相同 -> 清零
            // 计数达到门限 -> 确认新电平，并产生对应方向的单周期脉冲
            if (cnt[i] >= CNT_BITS'(DEBOUNCE_CNT - 1)) begin
                if (raw_pressed[i] != stable_q[i]) begin
                    stable_d[i] = raw_pressed[i];
                    if (raw_pressed[i]) press_d[i]   = 1'b1;
                    else                release_d[i] = 1'b1;
                end
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // 复位时按"松开"处理（低有效输入在复位期间被上拉为 1）。
            // 令 stable_q = 0 表示"未按下"，与 raw_pressed=0 一致，
            // 这样复位释放后不会误判出一次按下脉冲。
            stable_q      <= '0;
            press_pulse   <= '0;
            release_pulse <= '0;
            for (int unsigned i = 0; i < KEYS; i++) begin
                cnt[i] <= '0;
            end
        end else begin
            stable_q      <= stable_d;
            press_pulse   <= press_d;
            release_pulse <= release_d;
            for (int unsigned i = 0; i < KEYS; i++) begin
                if (raw_pressed[i] == stable_q[i]) begin
                    cnt[i] <= '0;
                end else if (cnt[i] < CNT_BITS'(DEBOUNCE_CNT - 1)) begin
                    cnt[i] <= cnt[i] + 1'b1;
                end else begin
                    // 已到门限且已在本拍确认，保持满值直到 stable_q 更新
                    cnt[i] <= CNT_BITS'(DEBOUNCE_CNT - 1);
                end
            end
        end
    end

    assign pressed = stable_q;

endmodule

`endif // KEY_DEBOUNCE_SV
