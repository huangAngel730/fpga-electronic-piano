// -----------------------------------------------------------------------------
// audio_defs_pkg.sv
// 音频通公共定义包。对应任务 T019，接口规范 v1.0 第二、三节。
//
// 依据：代码/docs/模块接口规范.md
//   - 2.3 节 sample_tick 频率 48 kHz，单周期宽
//   - 3.1 节 performance_event_t 64 位
//   - 3.3 节 事件类型编码
//   - 3.2.1 节 control_id 编码
//
// 注意：本包只定义类型与常量，不含任何时序逻辑。
// -----------------------------------------------------------------------------

`ifndef AUDIO_DEFS_PKG_SV
`define AUDIO_DEFS_PKG_SV

package audio_defs_pkg;

    // -------------------------------------------------------------------------
    // 采样率（接口规范 2.3 节）
    // -------------------------------------------------------------------------
    localparam int unsigned SAMPLE_RATE_HZ = 48_000;

    // -------------------------------------------------------------------------
    // sample_tick 相位累加器参数
    //
    // 相位累加器位宽。32 位足以使最坏情况（100 MHz）的频率误差低于 0.15 ppm，
    // 远优于音频可感知范围，见 代码/scripts/analyze_clock_plan.py。
    // -------------------------------------------------------------------------
    localparam int unsigned TICK_ACC_BITS = 32;

    // 相位步进计算函数：step = round(2^ACC_BITS * FS / FCLK)
    //
    // 当 FCLK 可被 FS 整除时（例如 98.304 MHz），结果为精确整数，
    // 相位累加器退化为整数分频器，无量化误差、无间隔抖动。
    function automatic logic [TICK_ACC_BITS-1:0] tick_phase_step(
        input int unsigned fclk_hz
    );
        longint unsigned full_scale;
        longint unsigned numer;
        full_scale = 64'h1 << TICK_ACC_BITS;
        numer = full_scale * SAMPLE_RATE_HZ;
        // 四舍五入：(numer + fclk/2) / fclk
        return (numer + (fclk_hz >> 1)) / fclk_hz;
    endfunction

    // -------------------------------------------------------------------------
    // 统一演奏事件（接口规范 3.1 节）
    // 合计 3+4+4+7+10+10+8+12+6 = 64 位
    // -------------------------------------------------------------------------
    typedef struct packed {
        logic [2:0]  event_type;
        logic [3:0]  source_id;
        logic [3:0]  channel;
        logic [6:0]  note_number;
        logic [9:0]  velocity;
        logic [9:0]  expression;
        logic [7:0]  control_id;
        logic [11:0] control_value;
        logic [5:0]  reserved;
    } performance_event_t;

    // -------------------------------------------------------------------------
    // 事件类型（接口规范 3.3 节）
    // -------------------------------------------------------------------------
    localparam logic [2:0] EVENT_NOTE_ON        = 3'd0;
    localparam logic [2:0] EVENT_NOTE_OFF       = 3'd1;
    localparam logic [2:0] EVENT_AFTERTOUCH     = 3'd2;
    localparam logic [2:0] EVENT_PITCH_BEND     = 3'd3;
    localparam logic [2:0] EVENT_CONTROL_CHANGE = 3'd4;
    localparam logic [2:0] EVENT_ALL_NOTES_OFF  = 3'd5;

    // -------------------------------------------------------------------------
    // control_id 编码（接口规范 3.2.1 节）
    // -------------------------------------------------------------------------
    localparam logic [7:0] CTRL_PITCH_BEND   = 8'd0;
    localparam logic [7:0] CTRL_MODULATION   = 8'd1;
    localparam logic [7:0] CTRL_VOLUME       = 8'd2;
    localparam logic [7:0] CTRL_PAN          = 8'd3;
    localparam logic [7:0] CTRL_PITCH_RANGE  = 8'd4;
    localparam logic [7:0] CTRL_VOICE_SELECT = 8'd5;
    localparam logic [7:0] CTRL_EFFECT_DELAY = 8'd16;
    localparam logic [7:0] CTRL_EFFECT_MIX   = 8'd17;

    // -------------------------------------------------------------------------
    // PCM 与数值边界（接口规范 4.1 节）
    // -------------------------------------------------------------------------
    localparam int unsigned PCM_WIDTH = 24;
    localparam logic signed [PCM_WIDTH-1:0] PCM_MAX =  24'sh7FFFFF;  //  8388607
    localparam logic signed [PCM_WIDTH-1:0] PCM_MIN = -24'sh800000;  // -8388608

    // -------------------------------------------------------------------------
    // 事件 FIFO 深度（接口规范 3.6 节）
    // 定量依据见 代码/scripts/analyze_event_fifo_budget.py
    // -------------------------------------------------------------------------
    localparam int unsigned EVENT_FIFO_DEPTH = 32;

    // -------------------------------------------------------------------------
    // MIDI 到统一事件的映射函数（接口规范 3.2 与 3.2.1 节）
    // -------------------------------------------------------------------------

    // MIDI 7 位 Velocity 扩展到 10 位：高位复制低 3 位
    function automatic logic [9:0] midi_velocity_to_10bit(
        input logic [6:0] velocity_7bit
    );
        return {velocity_7bit, velocity_7bit[6:4]};
    endfunction

    // MIDI 14 位 Pitch Bend 转换为 12 位有符号
    // 中心 8192 映射到 0；>>> 2 使输出恰好用满 -2048 至 2047，无需饱和
    function automatic logic signed [11:0] midi_bend_to_12bit(
        input logic [13:0] bend_14bit
    );
        return $signed({1'b0, bend_14bit} - 15'sd8192) >>> 2;
    endfunction

endpackage

`endif  // AUDIO_DEFS_PKG_SV
