// -----------------------------------------------------------------------------
// echo_fifo.sv
// 8 位（WIDTH 可配）同步 FIFO，首字直通读出 + 饱和丢弃计数。纯 RTL，单时钟域。
//
// 定位：UART 回传诊断工程（code/rtl/board/uart_echo_probe.sv）里，
// 接收侧与回传发送侧之间的解耦缓冲。
//
// -----------------------------------------------------------------------------
// 为什么需要它
// -----------------------------------------------------------------------------
//   回传的做法是"收到一帧 -> 立刻用同波特率重新发一帧"。接收器在**停止位
//   采样点**给出 rx_valid，发送器则要发满 10 位（1 起始 + 8 数据 + 1 停止）。
//
//   对端背靠背连发、且双方位周期**完全相同**时，收发刚好咬合成"零余量"：
//   第 k 帧发完的那一拍，第 k+1 帧的解码结果正好到达。这里**没有一拍余量**，
//   任何一点偏差都会让接收持续快于发送：
//     * 对端波特率比本地快（UART 允许 ±2~3% 偏差，这是正常工况不是异常）；
//     * 本地 DIV 取整后偏慢（50 MHz 下 115200 的 DIV 是 434 而不是 434.03）；
//     * rx_valid 相对 tx_ready 晚若干拍。
//   一旦"接收快于发送"，这个偏差就**逐字节累积**，累积满一个位周期
//   （115200 下 4340 拍）就丢一个字节。没有缓冲的话，丢字节是静默的：
//   电脑发 100 个字节，只回来 99 个，且错位看不出原因。
//
//   深度 8 把"零余量"变成"8 字节余量"。按对端快 2% 估算，约 50 字节才
//   积累 1 个字节，8 深足以覆盖实测中的连续发送。万一真的不够，
//   drop_count 会如实报出来（报告里的 dr 字段），而不是静默丢字节。
//
//   必须说明的是：本模块**不改变**回传的波特率，也不校验内容；
//   它只吸收收发之间的相位差。
//
// 深度不够时的行为
//   丢弃**新**到达的字节（不覆盖队内旧数据），drop_count 饱和加一。
//   这样"回声内容"与"已经发出去的内容"始终是前缀关系，便于定位。
// -----------------------------------------------------------------------------
// 接口与时序约定
// -----------------------------------------------------------------------------
//   * 单时钟域：wr_en / rd_en 都在 clk 上升沿采样。
//   * 读出是**首字直通**（first-word fall-through）：
//     rd_data 组合地等于队首字节，rd_en 与 !empty 同拍有效时队首被弹出。
//     UART 发送器要求 tx_data 与 tx_valid 同拍有效，所以必须直通，
//     不能做成"先给读脉冲、下一拍才出数据"的寄存器输出。
//   * full 时 wr_en 被忽略，且 drop_count 加 1（饱和，不复位不清零）。
//     drop_count 是"被丢掉的字节数"，是本模块唯一的状态告警：
//     回传诊断里它以 dr 字段出现在串口报告里，非 0 即说明缓冲不够，
//     回声内容不可信。
//   * empty / full 是组合输出，直接接握手信号，不要再过寄存器。
//   * rst_n 同步、低有效。复位后 empty=1、drop_count=0。
//
// -----------------------------------------------------------------------------
// 资源
// -----------------------------------------------------------------------------
//   DEPTH 个 WIDTH 位寄存器 + (AW+1) 位读写指针各一 + AW+1 位计数 + 16 位丢弃计数。
//   按 DEPTH=8 / WIDTH=8 计约 64 个寄存器，Gowin 综合为分布式 RAM 或寄存器组均可。
//
// 限制
//   1. DEPTH 必须是 2 的幂（用 $clog2 定位宽，非 2 的幂会浪费且回绕语义不清）。
//   2. 不做 almost_full / 水线输出：回传诊断不需要，需要时再加，不要预留。
//
// 自检 testbench：code/tb/common/tb_echo_fifo.sv
// -----------------------------------------------------------------------------
`ifndef ECHO_FIFO_SV
`define ECHO_FIFO_SV

`timescale 1ns / 1ps

module echo_fifo #(
    parameter int unsigned WIDTH = 8,
    parameter int unsigned DEPTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             wr_en,
    input  logic [WIDTH-1:0] wr_data,
    input  logic             rd_en,
    output logic [WIDTH-1:0] rd_data,
    output logic             empty,
    output logic             full,
    output logic [15:0]      drop_count
);

    // 地址位宽与计数位宽。计数比地址多一位，才能区分"空"和"满"。
    localparam int unsigned AW  = $clog2(DEPTH);
    localparam logic [AW:0] DEPTH_C = DEPTH[AW:0];

    logic [WIDTH-1:0] mem [0:DEPTH-1];
    logic [AW:0]      wptr;   // 写指针，只用低 AW 位做地址
    logic [AW:0]      rptr;   // 读指针
    logic [AW:0]      cnt;    // 当前存留字节数，0..DEPTH

    assign empty   = (cnt == '0);
    assign full    = (cnt == DEPTH_C);
    assign rd_data = mem[rptr[AW-1:0]];

    // 本拍是否真的写入 / 读出（满时不写、空时不读）
    logic do_wr, do_rd;
    assign do_wr = wr_en && !full;
    assign do_rd = rd_en && !empty;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            wptr       <= '0;
            rptr       <= '0;
            cnt        <= '0;
            drop_count <= 16'd0;
        end else begin
            if (do_wr) begin
                mem[wptr[AW-1:0]] <= wr_data;
                wptr              <= wptr + 1'b1;
            end

            if (do_rd) begin
                rptr <= rptr + 1'b1;
            end

            // 计数：同时读写则不变
            case ({do_wr, do_rd})
                2'b10:   cnt <= cnt + 1'b1;
                2'b01:   cnt <= cnt - 1'b1;
                default: cnt <= cnt;
            endcase

            // 满时来的写请求被丢弃：计数饱和，作为唯一告警
            if (wr_en && full && (drop_count != 16'hFFFF)) begin
                drop_count <= drop_count + 16'd1;
            end
        end
    end

endmodule

`endif  // ECHO_FIFO_SV
