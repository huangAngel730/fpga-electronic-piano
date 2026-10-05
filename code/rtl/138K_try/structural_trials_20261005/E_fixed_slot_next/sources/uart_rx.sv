// -----------------------------------------------------------------------------
// uart_rx.sv
// 参数化 UART 接收器（默认 8N1）。纯 RTL，不使用门控时钟，不产生新时钟。
//
// 定位：UART 状态通道的接收侧，也是本次"UART RX 是否可用"诊断的核心被测模块。
// MIDI 直读方案（31250 bps，8N1）用的就是它。
//
// -----------------------------------------------------------------------------
// 帧格式
// -----------------------------------------------------------------------------
//   固定 1 位起始位（低）+ DATA_BITS 位数据（LSB 先到）+ 1 位停止位（高）。
//   停止位只校验第一位。对端若发 2 位停止位也能正确接收，只是第二位不校验
//   （第二位一定是高，若不校验也不会误判）。
//
// -----------------------------------------------------------------------------
// 采样策略：中点采样
// -----------------------------------------------------------------------------
//   1. rx 先过两级触发器同步，避免亚稳态。
//   2. 空闲态检测到 rx 为低（电平判断，不是边沿判断）即认为起始位开始。
//      用电平判断是为了支持背靠背字节：上一帧停止位采样结束的那一刻，
//      下一帧的起始位可能已经到来，边沿判断会漏掉它。
//   3. 计满半个位周期后采样，此时正落在起始位中点；若仍为低则确认起始位有效，
//      否则判为假起始位（毛刺）并回到空闲态。
//   4. 此后每计满一个整位周期采样一次，正好落在每个数据位和停止位的中点。
//
//   与"16 倍过采样"相比，中点采样的等效采样点在位中心，对边沿抖动同样有
//   半个位周期的余量。50 MHz / 115200 下位周期 434 拍、中心余量 ±217 拍
//   （±4.34 us），远超任何实际的边沿抖动。因此本模块不做三点表决：
//   表决只在位周期很短（例如 50 MHz 下 BAUD > 1 Mbps）时才有意义，
//   当前用途下它只增加逻辑而不改变判定结果。
//
//   clk 与 rst_n 必须同域，rst_n 同步、低有效。
//
// -----------------------------------------------------------------------------
// 输出时序
// -----------------------------------------------------------------------------
//   rx_valid 是一拍脉冲，出现在停止位采样点所在的那一拍。它与 frame_err
//   同拍输出：rx_valid=1 表示"一帧结束"，frame_err=1 表示该帧停止位不是高。
//   调用方若只想要正确帧，应筛 rx_valid && !frame_err。
//   这样区分是必要的：引脚被拉低时，接收器会不断地假接收出 0x00 并给出
//   frame_err，若把这种帧也算作"收到数据"，诊断结论就会反过来。
//
//   rx_data 与 frame_err 在 rx_valid 有效期间保持稳定。
//
// -----------------------------------------------------------------------------
// 限制
// -----------------------------------------------------------------------------
//   1. DIV >= 4（位周期至少 4 拍）才能可靠取到中点。
//   2. 计数为 16 位，要求 CLK_HZ / BAUD < 65536（50 MHz 下 BAUD > 763）。
//   3. 不支持奇偶校验、不支持 9 位数据、不支持半双工总线仲裁。
//   4. 帧错误后若对端把线路一直按在低电平（break），接收器会连续判出
//      frame_err 帧；等线路恢复高电平时，还可能多出**一帧**判为正确的
//      0xFF。原因是恢复时接收器正处在某一帧中途，剩下的位全采到高电平。
//      这不是缺陷，是"无起始位超时保护"的必然结果：本模块只在停止位
//      判帧错误，不做线路空闲超时。诊断判读时按这个规律看 by/fe：
//      持续拉低期间 by 不增、fe 快涨；线路释放那一刻 by 至多多 +1。
//      排除方法：把线路拉低期间收到的帧一律按 fe>0 看待即可，
//      真实的 0x55 测试帧不会和这一帧同时出现。
//
// 自检 testbench：code/tb/common/tb_uart_rx.sv
// -----------------------------------------------------------------------------
`ifndef UART_RX_SV
`define UART_RX_SV

`timescale 1ns / 1ps

module uart_rx #(
    parameter int unsigned CLK_HZ    = 50_000_000,
    parameter int unsigned BAUD      = 115_200,
    parameter int unsigned DATA_BITS = 8
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 rx,
    output logic [DATA_BITS-1:0] rx_data,
    output logic                 rx_valid,
    output logic                 frame_err,
    output logic                 rx_busy
);

    // 位周期（clk 数），四舍五入。
    localparam int unsigned DIV = (CLK_HZ + (BAUD / 2)) / BAUD;

    // 先把 DIV 落成定宽向量再做算术，避免对参数做位选。
    localparam logic [15:0] DIV16     = DIV;
    localparam logic [15:0] FULL_LAST  = DIV16 - 16'd1;            // 整位周期的最后一拍

    // 起始位采样点的相位补偿。
    //   从"真实边沿"到"采样拍"之间固定有 4 拍延迟：
    //     2 拍 = rx 的两级同步器；
    //     1 拍 = IDLE 检测到低电平后转入 START 的那一拍；
    //     1 拍 = 计数器从 0 数到 HALF_LAST 的起点。
    //   所以位内计数目标值要取 DIV/2 - 4，采样点才落在位中心。
    //   DIV 很小时扣不动，钳到 0（即进入 START 后的第一拍就采），
    //   此时采样点仍然落在起始位内，只是略偏前。
    localparam logic [15:0] HALF_RAW  = DIV16 >> 1;
    localparam logic [15:0] HALF_LAST = (HALF_RAW > 16'd4) ? (HALF_RAW - 16'd4)
                                                           : 16'd0;

    typedef enum logic [1:0] {
        ST_IDLE  = 2'd0,   // 等起始位
        ST_START = 2'd1,   // 半位周期后确认起始位
        ST_DATA  = 2'd2,   // 逐位采样数据
        ST_STOP  = 2'd3    // 采样停止位并输出结果
    } rx_state_e;

    rx_state_e            state;
    logic [15:0]          cnt;        // 当前位内的 clk 计数
    logic [DATA_BITS-1:0] shifter;    // 已采到的数据位
    logic [7:0]           bit_idx;    // 下一位要写入的序号

    // -------------------------------------------------------------------------
    // 输入同步：两级触发器。
    // 复位时置 1 是按"线路空闲为高"处理（CST 里该脚带内部上拉）。
    // -------------------------------------------------------------------------
    (* async_reg = "true" *) logic rx_meta;
    (* async_reg = "true" *) logic rx_sync;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            rx_meta <= 1'b1;
            rx_sync <= 1'b1;
        end else begin
            rx_meta <= rx;
            rx_sync <= rx_meta;
        end
    end

    assign rx_busy = (state != ST_IDLE);

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state     <= ST_IDLE;
            cnt       <= 16'd0;
            shifter   <= '0;
            bit_idx   <= 8'd0;
            rx_data   <= '0;
            rx_valid  <= 1'b0;
            frame_err <= 1'b0;
        end else begin
            // rx_valid 默认拉低，只有停止位采样那一拍才置起。
            rx_valid <= 1'b0;

            case (state)
                // ------------------------------------------------------------
                // 空闲：等 rx 变低。用电平而不是边沿，见文件头说明。
                // ------------------------------------------------------------
                ST_IDLE: begin
                    cnt <= 16'd0;
                    if (!rx_sync) begin
                        state <= ST_START;
                    end
                end

                // ------------------------------------------------------------
                // 起始位：半个位周期后到中点，此时仍应为低。
                // ------------------------------------------------------------
                ST_START: begin
                    if (cnt == HALF_LAST) begin
                        cnt <= 16'd0;
                        if (rx_sync) begin
                            state <= ST_IDLE;   // 假起始位，丢弃
                        end else begin
                            bit_idx <= 8'd0;
                            state   <= ST_DATA;
                        end
                    end else begin
                        cnt <= cnt + 16'd1;
                    end
                end

                // ------------------------------------------------------------
                // 数据位：每个整位周期采一次，落在位中点。
                // ------------------------------------------------------------
                ST_DATA: begin
                    if (cnt == FULL_LAST) begin
                        cnt              <= 16'd0;
                        shifter[bit_idx] <= rx_sync;
                        if (bit_idx == DATA_BITS - 1) begin
                            state <= ST_STOP;
                        end else begin
                            bit_idx <= bit_idx + 8'd1;
                        end
                    end else begin
                        cnt <= cnt + 16'd1;
                    end
                end

                // ------------------------------------------------------------
                // 停止位：中点采样，应为高。为低即帧错误。
                // 注意是取反：frame_err = !停止位电平。
                // 无论正确与否都输出这一帧，用 frame_err 区分。
                // ------------------------------------------------------------
                ST_STOP: begin
                    if (cnt == FULL_LAST) begin
                        cnt       <= 16'd0;
                        rx_data   <= shifter;
                        frame_err <= ~rx_sync;
                        rx_valid  <= 1'b1;
                        state     <= ST_IDLE;
                    end else begin
                        cnt <= cnt + 16'd1;
                    end
                end

                default: begin
                    state <= ST_IDLE;
                    cnt   <= 16'd0;
                end
            endcase
        end
    end

endmodule

`endif  // UART_RX_SV
