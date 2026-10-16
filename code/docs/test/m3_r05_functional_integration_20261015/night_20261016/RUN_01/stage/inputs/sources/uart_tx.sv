// -----------------------------------------------------------------------------
// uart_tx.sv
// 参数化 UART 发送器（默认 8N1）。纯 RTL，不使用门控时钟，不产生新时钟。
//
// 定位：UART 状态通道的发送侧。本文件是 UART RX 诊断工程
// （code/rtl/board/uart_rx_probe.sv）的报告输出，也是后续 MIDI/调试状态通道
// 的发送侧基础模块。按 code/rtl/AGENTS.md，UART 状态通道的协议与顶层实现
// 归 M2。
//
// 为什么需要它：在本次改动之前，顶层 uart_tx 只有一句
//   assign uart_tx = 1'b1;
// 即"空闲高、从不发送"，板载 USB-UART 的发送方向从未被真正使用过。
// 要观察 RX 有没有收到数据，必须先有一个能发字的发送器。
//
// -----------------------------------------------------------------------------
// 接口与时序约定
// -----------------------------------------------------------------------------
//   tx_ready = 1 表示可以接受一个新字节。
//   tx_valid 与 tx_ready 在同一个时钟上升沿同时为 1 时，该字节被接受，
//   随后 tx_ready 拉低，直到整个帧（起始位 + DATA_BITS 个数据位 + STOP_BITS
//   个停止位）发送完毕才重新拉高。
//   调用方必须遵守握手：tx_valid 保持到被接受，不要在 tx_ready=0 时改数据。
//
//   tx 空闲时为高电平（UART 空闲态）。数据位 LSB 先发（标准 UART）。
//
//   位周期 = DIV 个 clk，DIV = round(CLK_HZ / BAUD)。
//   50 MHz / 115200 -> DIV = 434，实际波特率 50000000 / 434 = 115207.4 bps，
//   相对 115200 偏差 +0.0064%，远小于 UART 允许的 ±2%。
//   50 MHz / 31250（MIDI）-> DIV = 1600，实际 31250.0 bps，偏差 0。
//
//   clk 与 rst_n 必须同域；rst_n 同步、低有效。
//
// -----------------------------------------------------------------------------
// 实现说明
// -----------------------------------------------------------------------------
//   一个 4 态状态机（IDLE/START/DATA/STOP）+ 一个 0..DIV-1 的位内计数器。
//   不用"每 DIV 拍产生一个使能"的写法，而是直接在状态机里数满一个位周期，
//   这样每个状态的分支条件都只依赖一个比较器，资源更省，也更容易逐拍核对。
//
//   寄存器位的初值不参与功能：全部由 rst_n 复位，不依赖上电初值。
//
// -----------------------------------------------------------------------------
// 限制
// -----------------------------------------------------------------------------
//   1. DIV 必须 >= 2（CLK_HZ >= 2 * BAUD）。
//   2. 位内计数器是 16 位，要求 CLK_HZ / BAUD < 65536。
//      50 MHz 下等同于 BAUD > 763，覆盖 9600 / 19200 / 31250 / 115200 等。
//   3. DIV 的舍入误差应 < 2%，否则对端可能采错位。
//
// 自检 testbench：code/tb/common/tb_uart_tx.sv
// -----------------------------------------------------------------------------
`ifndef UART_TX_SV
`define UART_TX_SV

`timescale 1ns / 1ps

module uart_tx #(
    parameter int unsigned CLK_HZ    = 50_000_000,
    parameter int unsigned BAUD      = 115_200,
    parameter int unsigned DATA_BITS = 8,
    parameter int unsigned STOP_BITS = 1
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic [DATA_BITS-1:0] tx_data,
    input  logic                 tx_valid,
    output logic                 tx_ready,
    output logic                 tx
);

    // 位周期（clk 数），四舍五入。
    localparam int unsigned DIV = (CLK_HZ + (BAUD / 2)) / BAUD;

    // 先把 DIV 落成定宽向量再做算术，避免对参数做位选。
    localparam logic [15:0] DIV16     = DIV;
    localparam logic [15:0] DIV_LAST  = DIV16 - 16'd1;

    typedef enum logic [1:0] {
        ST_IDLE  = 2'd0,   // tx=1，等待新字节
        ST_START = 2'd1,   // 发送起始位（低）
        ST_DATA  = 2'd2,   // 发送 DATA_BITS 个数据位，LSB 先发
        ST_STOP  = 2'd3    // 发送 STOP_BITS 个停止位（高）
    } tx_state_e;

    tx_state_e            state;
    logic [15:0]          baud_cnt;   // 当前位内已持续的 clk 数，0..DIV-1
    logic [DATA_BITS-1:0] shifter;    // 待发数据，从 bit 0 起逐位送出
    logic [7:0]           bit_idx;    // 当前正在发送的数据位序号
    logic [7:0]           stop_cnt;   // 已发送的停止位数

    // 当前位是否已持续满 DIV 个 clk（即到达位边界）
    logic bit_last;
    assign bit_last = (baud_cnt == DIV_LAST);

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state    <= ST_IDLE;
            baud_cnt <= 16'd0;
            shifter  <= '0;
            bit_idx  <= 8'd0;
            stop_cnt <= 8'd0;
            tx       <= 1'b1;
            tx_ready <= 1'b1;
        end else begin
            case (state)
                // ------------------------------------------------------------
                // 空闲：tx 保持高。握手成功的那一拍立即拉低进入起始位，
                // 所以从"被接受"到起始位下降沿之间没有额外空拍。
                // ------------------------------------------------------------
                ST_IDLE: begin
                    tx <= 1'b1;
                    if (tx_valid && tx_ready) begin
                        shifter  <= tx_data;
                        baud_cnt <= 16'd0;
                        bit_idx  <= 8'd0;
                        stop_cnt <= 8'd0;
                        tx       <= 1'b0;
                        tx_ready <= 1'b0;
                        state    <= ST_START;
                    end
                end

                // ------------------------------------------------------------
                // 起始位：持续 DIV 拍后送出数据位 0。
                // ------------------------------------------------------------
                ST_START: begin
                    if (bit_last) begin
                        baud_cnt <= 16'd0;
                        tx       <= shifter[0];
                        bit_idx  <= 8'd0;
                        state    <= ST_DATA;
                    end else begin
                        baud_cnt <= baud_cnt + 16'd1;
                    end
                end

                // ------------------------------------------------------------
                // 数据位：每 DIV 拍推进一步。发完最后一位直接进入停止位。
                // ------------------------------------------------------------
                ST_DATA: begin
                    if (bit_last) begin
                        baud_cnt <= 16'd0;
                        if (bit_idx == DATA_BITS - 1) begin
                            tx       <= 1'b1;
                            stop_cnt <= 8'd0;
                            state    <= ST_STOP;
                        end else begin
                            bit_idx <= bit_idx + 8'd1;
                            tx      <= shifter[bit_idx + 8'd1];
                        end
                    end else begin
                        baud_cnt <= baud_cnt + 16'd1;
                    end
                end

                // ------------------------------------------------------------
                // 停止位：发满 STOP_BITS 位后释放 tx_ready，允许背靠背发送。
                // ------------------------------------------------------------
                ST_STOP: begin
                    if (bit_last) begin
                        baud_cnt <= 16'd0;
                        if (stop_cnt == STOP_BITS - 1) begin
                            tx_ready <= 1'b1;
                            state    <= ST_IDLE;
                        end else begin
                            stop_cnt <= stop_cnt + 8'd1;
                        end
                    end else begin
                        baud_cnt <= baud_cnt + 16'd1;
                    end
                end

                default: begin
                    state    <= ST_IDLE;
                    tx       <= 1'b1;
                    tx_ready <= 1'b1;
                end
            endcase
        end
    end

endmodule

`endif  // UART_TX_SV
