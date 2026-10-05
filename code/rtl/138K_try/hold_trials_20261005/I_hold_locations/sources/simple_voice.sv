// -----------------------------------------------------------------------------
// simple_voice.sv
// 单声部占位实现。对应任务 T020（可综合集成骨架）。
//
// =============================================================================
// 【重要】这是占位实现，不是最终算法
// =============================================================================
//   正式的 DDS 归 T004（M1），ADSR 归 T009（M1），多声部管理归 T010（M1）。
//   本模块放在 rtl/common/ 的唯一目的是：让"按键 -> 事件 -> 音高变化"这条
//   链路先跑通并可上板验证，从而给 M1/M3 一个已经打通的集成骨架。
//
//   T004/T009/T010 落地后，本模块应由 M1 的正式实现替换。
//   接口（事件入、PCM 出）刻意与规范一致，替换时下游不用改。
//
// -----------------------------------------------------------------------------
// 本模块实现的语义（规范 3.4 节的最小子集）
// -----------------------------------------------------------------------------
//   Note On : 若该音符号与当前发声音相同 -> 重新触发（相位归零）；
//             否则切换到新音高。第一版单声部，不做声部抢占。
//   Note Off: 若与当前发声音匹配 -> 进入释放（本占位实现为立即静音，
//             **不含真正的 ADSR 包络**，故会有轻微的开关爆音，
//             这是 T009 要解决的问题，如实记录）。
//   All Notes Off: 立即静音。
//   其他事件类型（AFTERTOUCH / PITCH_BEND / CONTROL_CHANGE）:
//             本占位实现忽略，但**不阻塞握手**（仍然接收），
//             避免上游因为下游不接而卡死。
//
// -----------------------------------------------------------------------------
// 为什么"立即静音"会有爆音，以及为什么现在可以接受
// -----------------------------------------------------------------------------
//   方波式的通断会在波形中引入高频分量，听感上是"咔"的一声。
//   真正的消除办法是 ADSR 包络（T009）或至少一段淡入淡出。
//   当前阶段的目标是验证"按键能改变音高"，不是验证音质，
//   故如实记录该缺陷而不在此处临时打补丁——临时补丁会与 T009 冲突。
//
// -----------------------------------------------------------------------------
// 相位累加器：与 T007 已验证的实现同构
// -----------------------------------------------------------------------------
//   只在 sample_tick 上累加，步进由 note_pitch 给出。
//   取相位高位作查表索引。
// -----------------------------------------------------------------------------

`ifndef SIMPLE_VOICE_SV
`define SIMPLE_VOICE_SV

`timescale 1ns / 1ps

module simple_voice #(
    parameter int unsigned ACC_BITS       = 32,
    parameter int unsigned SINE_DEPTH     = 256,
    parameter int unsigned PCM_WIDTH      = 24,
    parameter int unsigned SAMPLE_RATE_HZ = 48_000,
    // 幅度（16 位有符号）。与 T007 一致取满量程 1/4，便于对比听感。
    parameter logic signed [15:0] AMPLITUDE = 16'sd8192
) (
    input  logic                    clk,
    input  logic                    rst_n,
    // 48 kHz 采样节拍（时钟使能，不是时钟）
    input  logic                    sample_tick,
    // 统一演奏事件输入（规范 3.5 握手）
    input  logic                    event_valid,
    output logic                    event_ready,
    input  audio_defs_pkg::performance_event_t event_data,
    // PCM 输出（规范第四章）
    output logic signed [PCM_WIDTH-1:0] pcm_left,
    output logic signed [PCM_WIDTH-1:0] pcm_right,
    // 便于验证与调试的状态输出
    output logic                    voice_active,
    output logic [6:0]              current_note
);

    // 事件类型常量原属 perf_event_pkg，2026-09-15 按 D022 收敛到
    // audio_defs_pkg。此处用**显式命名导入**而不是 import *：
    // audio_defs_pkg 还导出 PCM_WIDTH、SAMPLE_RATE_HZ 等同名常量，
    // 与本模块自己的参数重名，显式导入可避免歧义。
    import audio_defs_pkg::EVENT_NOTE_ON;
    import audio_defs_pkg::EVENT_NOTE_OFF;
    import audio_defs_pkg::EVENT_ALL_NOTES_OFF;

    // -------------------------------------------------------------------------
    // 正弦表
    //
    // 【为什么把表放在这里，而不是让顶层传进来】
    //   顶层 electronic_piano_top.sv 和本模块都需要正弦表。看起来"顶层
    //   include 一次、通过参数传给各声部"最省资源，但 iverilog 不允许
    //   覆盖由 localparam 派生的参数：
    //     error: Cannot override parameter `SINE_TABLE' in `...u_simple_voice'.
    //            Parameter cannot be overridden in the scope it has been declared in.
    //   原因是 sine_table.svh 里的 SINE_TABLE_DEFAULT 是 localparam，
    //   顶层传给本模块时它已被固化。
    //
    //   采用的做法：**只有本模块 include 头文件**。
    //   sine_table.svh 的 ifndef 卫士是全局的，同一编译单元内第二次 include
    //   会被直接跳过（不会报重复定义，但也不会提供任何定义）。
    //   因此全设计里正弦表只能有一个 include 点——就是这里。
    //   顶层的固定测试音分支改为使用本模块提供的查表函数，
    //   见 electronic_piano_top.sv 的 g_fixed_tone 分支。
    // -------------------------------------------------------------------------
    `include "E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/I_hold_locations/include/sine_table.svh"
    localparam logic signed [16*SINE_DEPTH-1:0] SINE_TABLE = SINE_TABLE_DEFAULT;

    localparam int unsigned SINE_IDX_BITS = $clog2(SINE_DEPTH);

    function automatic logic signed [15:0] sine_sample(
        input logic [SINE_IDX_BITS-1:0] index
    );
        return sine_lookup({{(32-SINE_IDX_BITS){1'b0}}, index});
    endfunction

    // -------------------------------------------------------------------------
    // 音高查表
    // -------------------------------------------------------------------------
    logic [6:0]              note_q;
    logic [ACC_BITS-1:0]     step_q;
    logic                    active_q;

    note_pitch #(
        .ACC_BITS       (ACC_BITS),
        .SAMPLE_RATE_HZ (SAMPLE_RATE_HZ)
    ) u_note_pitch (
        .note_number (note_q),
        .phase_step  (step_q)
    );

    // 握手：本模块每个周期都能接收（不产生背压）。
    // 事件本身不会丢失，因为相位与步进在采样节拍前保持稳定。
    assign event_ready = 1'b1;

    // -------------------------------------------------------------------------
    // 事件处理：更新音符号与激活状态
    // -------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            note_q   <= 7'd69;      // 复位后默认 A4
            active_q <= 1'b0;       // 复位后不发声
        end else if (event_valid) begin
            unique case (event_data.event_type)
                EVENT_NOTE_ON: begin
                    note_q   <= event_data.note_number;
                    active_q <= 1'b1;
                end
                EVENT_NOTE_OFF: begin
                    // 单声部：只有音符号匹配才关闭，避免"关了别的音"
                    if (event_data.note_number == note_q) begin
                        active_q <= 1'b0;
                    end
                end
                EVENT_ALL_NOTES_OFF: begin
                    active_q <= 1'b0;
                end
                default: begin
                    // AFTERTOUCH / PITCH_BEND / CONTROL_CHANGE 暂不处理。
                    // 保持 active_q 不变，且不影响握手。
                end
            endcase
        end
    end

    // -------------------------------------------------------------------------
    // 相位累加（仅在 sample_tick 上推进）
    // -------------------------------------------------------------------------
    logic [ACC_BITS-1:0] phase_q;
    logic [ACC_BITS:0]   phase_sum;

    assign phase_sum = {1'b0, phase_q} + {1'b0, step_q};

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase_q <= '0;
        end else if (sample_tick) begin
            // 未激活时相位保持为 0，这样下一次 Note On 从上电相位开始，
            // 避免残留相位造成的起始噪声
            phase_q <= active_q ? phase_sum[ACC_BITS-1:0] : '0;
        end
    end

    logic [SINE_IDX_BITS-1:0] sine_index;
    assign sine_index = phase_q[ACC_BITS-1 -: SINE_IDX_BITS];

    logic signed [15:0] sample;
    assign sample = active_q ? sine_sample(sine_index) : 16'sd0;

    // -------------------------------------------------------------------------
    // 24 位 PCM 组装（与 T007 相同：左移 8 位，低 8 位补 0）
    //
    // i2s_tx 内部是"加半 LSB 后右移 8 位"，低 8 位为 0 时恰好还原原值，
    // 不引入舍入误差。
    // -------------------------------------------------------------------------
    always_comb begin
        pcm_left  = $signed({sample, 8'b0});
        pcm_right = $signed({sample, 8'b0});
    end

    assign voice_active = active_q;
    assign current_note = note_q;

endmodule

`endif // SIMPLE_VOICE_SV
