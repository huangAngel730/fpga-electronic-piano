// -----------------------------------------------------------------------------
// key_event_source.sv
// 按键 -> 统一演奏事件。对应任务 T014（统一演奏事件接口测试桩）。
//
// 定位：把去抖后的按键脉冲翻译成模块接口规范第三章的 performance_event_t。
// 这是**接口测试桩**，不是最终输入方案——最终方案是 MIDI 键盘（方案 B）。
// 但事件结构、握手时序与 source_id 用法都是最终的，
// 后续接 MIDI 时只需替换本模块，下游的声部管理与算法层不用改。
//
// -----------------------------------------------------------------------------
// 按键到音符号的映射（由顶层参数给出，本模块不写死）
// -----------------------------------------------------------------------------
//   每个按键对应一个固定的 MIDI 音符号。按下发 Note On，松开发 Note Off。
//   力度固定为 NOMINAL_VELOCITY：普通按键没有压力信息，
//   用固定力度是诚实的做法（真正的力度检测属于加分档"每键压力检测"）。
//
// -----------------------------------------------------------------------------
// source_id 的用法
// -----------------------------------------------------------------------------
//   规范 3.2 节要求 Note Off 用 source_id + channel + note_number 三者匹配声部。
//   本模块所有事件共用同一个 SOURCE_ID，channel 固定 0，
//   故匹配退化为"按音符号匹配"，对单一声部键盘是充分的。
//
// -----------------------------------------------------------------------------
// 握手（规范 3.5 节）
// -----------------------------------------------------------------------------
//   event_valid / event_ready。
//   本桩每次只暂存一个待发事件：若上一事件未被接收又来了新事件，
//   新事件会覆盖旧的。对本场景（人手按键，间隔远大于 50 MHz 下的几个周期）
//   这是安全的；真正的 MIDI 输入需要 FIFO，属于 T014 之后的输入适配层。
//   这里如实记录该限制，不假装有 FIFO。
// -----------------------------------------------------------------------------

`ifndef KEY_EVENT_SOURCE_SV
`define KEY_EVENT_SOURCE_SV

`timescale 1ns / 1ps

module key_event_source #(
    parameter int unsigned KEYS = 2,
    // 本输入源编号。规范 3.2：按键、UART、MIDI 或传感器适配器各有编号。
    // 0 保留给调试/仿真桩，故本板载按键取 1。
    parameter logic [3:0]  SOURCE_ID = 4'd1,
    // 固定力度。"宁大勿小"会削波，取中值附近保证多声部相加有余量。
    parameter logic [9:0]  NOMINAL_VELOCITY = 10'd512,
    // -------------------------------------------------------------------------
    // 每个按键对应的 MIDI 音符号。
    //
    // 【为什么是打包向量而不是数组】
    //   iverilog 不支持 unpacked array parameter，报
    //     "sorry: unpacked array parameters are not supported yet."
    //   与 note_pitch / sine_table.svh 同一约束。打包向量是纯
    //   Verilog-2001，iverilog 与 GowinSynthesis 都接受。
    //   位序：最低 7 位是 key0，故取值用 NOTE_MAP[7*i +: 7]。
    //   默认 {key1=C5(72), key0=A4(69)}。
    // -------------------------------------------------------------------------
    parameter logic [7*KEYS-1:0] NOTE_MAP = {7'd72, 7'd69}
) (
    input  logic                    clk,
    input  logic                    rst_n,
    // 去抖后的单周期脉冲（来自 rtl/input/button_debouncer.sv，T021）
    input  logic [KEYS-1:0]         press_pulse,
    input  logic [KEYS-1:0]         release_pulse,
    // 统一演奏事件输出（规范 3.5 的 valid/ready 握手）
    output logic                    event_valid,
    input  logic                    event_ready,
    output perf_event_pkg::performance_event_t event_data
);

    import perf_event_pkg::*;

    logic                    pending_q;
    performance_event_t      event_q;

    // -------------------------------------------------------------------------
    // 事件生成
    //
    // 优先级：按下优先于松开。两键同时按下时只处理最低位按键，
    // 其余按键的事件在后续时钟周期补发（因为脉冲只持续一个周期，
    // 严格来说同时按下会有按键事件丢失）。
    //
    // 【如实记录该限制】本桩不保证同时按键时全部事件都被发送。
    // 真正的多键输入适配层需要给每个按键配一个待发事件槽，
    // 属于 T014 之后的工作。对"单键试音"的验证目标是充分的。
    // -------------------------------------------------------------------------
    logic               has_new;
    performance_event_t new_event;

    always_comb begin
        has_new   = 1'b0;
        new_event = make_note_event(1'b0, SOURCE_ID, 4'd0,
                                    NOTE_MAP[0 +: 7], NOMINAL_VELOCITY);

        for (int unsigned i = 0; i < KEYS; i++) begin
            if (press_pulse[i]) begin
                new_event = make_note_event(1'b1, SOURCE_ID, 4'd0,
                                            NOTE_MAP[7*i +: 7], NOMINAL_VELOCITY);
                has_new   = 1'b1;
            end else if (release_pulse[i]) begin
                new_event = make_note_event(1'b0, SOURCE_ID, 4'd0,
                                            NOTE_MAP[7*i +: 7], NOMINAL_VELOCITY);
                has_new   = 1'b1;
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pending_q <= 1'b0;
            event_q   <= '0;
        end else begin
            if (pending_q && event_ready) begin
                // 已被下游接收，清空
                pending_q <= 1'b0;
            end
            if (has_new) begin
                event_q   <= new_event;
                pending_q <= 1'b1;
            end
        end
    end

    assign event_valid = pending_q;
    assign event_data  = event_q;

endmodule

`endif // KEY_EVENT_SOURCE_SV
