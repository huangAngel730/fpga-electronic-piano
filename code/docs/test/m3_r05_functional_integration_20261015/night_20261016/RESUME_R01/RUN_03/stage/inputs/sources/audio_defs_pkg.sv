// -----------------------------------------------------------------------------
// audio_defs_pkg.sv
// 音频通公共定义包。对应任务 T019，接口规范 v1.0 第二、三节。
//
// 依据：code/docs/模块接口规范.md
//   - 2.3 节 sample_tick 频率 48 kHz，单周期宽
//   - 3.1 节 performance_event_t 64 位
//   - 3.3 节 事件类型编码
//   - 3.2.1 节 control_id 编码
//
// 注意：本包只定义类型、常量与纯组合函数，不含任何时序逻辑。
//
// -----------------------------------------------------------------------------
// 【D022 / 2026-09-15】本包是统一演奏事件类型的**唯一**定义处
// -----------------------------------------------------------------------------
//   2026-09-14 曾在 rtl/common/perf_event_pkg.sv 内重复定义过一份逐字段
//   完全相同的 performance_event_t。两份并存时编译器与仿真都不报错，
//   属"静默分叉"风险：任一侧单独改动都会让发送方与接收方位域不一致，
//   而仿真只会表现为音高/力度全错，不会给出任何错误信息。
//
//   2026-09-15 按 D022 收敛：perf_event_pkg.sv 中的事件构造函数
//   make_note_event() 与 make_all_notes_off() 迁入本包，该包已删除。
//
//   **此后新增任何事件字段或事件类型编码，只允许修改本文件。**
//   不得再在任何其他文件或包内重新定义 performance_event_t。
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
    // 远优于音频可感知范围，见 code/scripts/analyze_clock_plan.py。
    // -------------------------------------------------------------------------
    localparam int unsigned TICK_ACC_BITS = 32;

    // 相位步进计算函数：step = round(2^ACC_BITS * TARGET_HZ / FCLK_HZ)
    //
    // 当 FCLK 可被 TARGET_HZ 整除时（例如 24.576 MHz 对 48 kHz），
    // 结果为精确整数，相位累加器退化为整数分频器，无量化误差、无间隔抖动。
    // 当不能整除时（例如板载的 50 MHz），仍能给出最接近的长期平均频率，
    // 代价是间隔存在 +-1 个时钟周期的抖动。
    //
    // 注意 TARGET_HZ 必须显式传入，不要依赖默认值：
    // I2S 的 BCLK（3.072 MHz）也用它计算步进，
    // 若函数内部写死 48 kHz 会得到完全错误的结果。
    function automatic logic [TICK_ACC_BITS-1:0] phase_step_for(
        input int unsigned fclk_hz,
        input int unsigned target_hz
    );
        longint unsigned full_scale;
        longint unsigned numer;
        full_scale = 64'h1 << TICK_ACC_BITS;
        numer = full_scale * target_hz;
        // 四舍五入：(numer + fclk/2) / fclk
        return (numer + (fclk_hz >> 1)) / fclk_hz;
    endfunction

    // 48 kHz sample_tick 专用包装，便于调用处保持简洁。
    function automatic logic [TICK_ACC_BITS-1:0] tick_phase_step(
        input int unsigned fclk_hz
    );
        return phase_step_for(fclk_hz, SAMPLE_RATE_HZ);
    endfunction

    // -------------------------------------------------------------------------
    // 板载实际参数（2026-09-12 确认）
    //
    // 板载晶振 50 MHz，见 code/docs/板级硬件事实.md 3.3 节。
    // 50 MHz 不能被 48 kHz 整除，故 PHASE_STEP 不是 2 的幂：
    //   step = round(2^32 * 48000 / 50000000) = 4123169 (0x003EEA21)
    //   实际平均采样率 = 48000.004608 Hz，误差 +0.096 ppm
    //   tick 间隔在 1041 与 1042 个时钟之间交替，峰峰抖动 20 ns
    //
    // 该抖动可接受：sample_tick 在本项目中是"处理节拍"而非 DAC 时钟，
    // 音频输出的采样率由 I2S 的 BCLK/LRCLK 保证。
    // 详见 code/scripts/analyze_clock_50m.py。
    // -------------------------------------------------------------------------
    localparam int unsigned BOARD_CLK_HZ       = 50_000_000;
    localparam logic [TICK_ACC_BITS-1:0]
                            BOARD_TICK_PHASE_STEP = 32'd4_123_169;

    // I2S 位时钟目标频率（接口规范 2.4 节）
    localparam int unsigned I2S_BCLK_HZ = 3_072_000;

    // I2S BCLK 的相位步进。
    //
    // 【关键 1】BCLK 不能用 50 MHz 整数分频产生：
    //   50e6 / 3.072e6 = 16.276042，非整数；
    //   除以 16 得 3.125 MHz，误差 +17253 ppm，音高偏高约 0.29 半音，
    //   人耳可直接察觉，故必须用相位累加。
    //
    // 【关键 2：本参数是「翻转率」不是「周期率」】
    //   i2s_tx 中 bclk 每个 bclk_ce 翻转一次，一个完整 BCLK 周期需要
    //   两次翻转（一高、一低）。因此
    //     BCLK 频率 = PHASE_STEP x FCLK / 2^ACC_BITS / 2
    //   要得到 3.072 MHz，必须按 **6.144 MHz** 的翻转率计算步进：
    //     step = round(2^32 x 6.144e6 / 50e6) = 527765581 (0x1F750C4D)
    //   实际翻转率 6.143999996 MHz，折合 BCLK = 3.071999998 MHz，
    //   误差 -0.0006 ppm。
    //
    //   曾经写成 3.072 MHz 对应的 263882791，注释还自称
    //   "实际 BCLK = 3.072000004 MHz" —— 语义错了一半，实际 BCLK 只有
    //   1.536 MHz。该错误无法被 T005 的模块级 testbench 发现（它用
    //   BCLK_PHASE_STEP=1 的合成参数，只验证比例不验证绝对频率），
    //   直到 T007 顶层测量引脚周期才暴露。见 验证记录.md V0029。
    localparam logic [TICK_ACC_BITS-1:0]
                            I2S_BCLK_PHASE_STEP   = 32'd527_765_581;

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
    localparam logic [7:0] CTRL_SUSTAIN      = 8'd6;
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
    // 定量依据见 code/scripts/analyze_event_fifo_budget.py
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

    // CC64: preserve source/channel, raw7>=64 equals expanded12>=2048.
    function automatic logic [11:0] midi_cc_to_12bit(input logic [6:0] value);
        return {value, value[6:2]};
    endfunction

    function automatic performance_event_t make_sustain_event(
        input logic [3:0] source_id,
        input logic [3:0] channel,
        input logic [6:0] value
    );
        performance_event_t ev;
        ev = '0;
        ev.event_type = EVENT_CONTROL_CHANGE;
        ev.source_id = source_id;
        ev.channel = channel;
        ev.control_id = CTRL_SUSTAIN;
        ev.control_value = midi_cc_to_12bit(value);
        return ev;
    endfunction

    // MIDI 14 位 Pitch Bend 转换为 12 位有符号
    // 中心 8192 映射到 0；>>> 2 使输出恰好用满 -2048 至 2047，无需饱和
    function automatic logic signed [11:0] midi_bend_to_12bit(
        input logic [13:0] bend_14bit
    );
        return $signed({1'b0, bend_14bit} - 15'sd8192) >>> 2;
    endfunction

    // -------------------------------------------------------------------------
    // 事件构造函数（原 perf_event_pkg.sv，2026-09-15 按 D022 迁入）
    // -------------------------------------------------------------------------

    // 构造一个 Note On 或 Note Off 事件。
    //
    // 【velocity 不得为 0】
    //   规范 3.4 节：输入适配层收到 velocity=0 的 Note On 时，必须在进入
    //   公共事件 FIFO 前转换成 Note Off；音频核心不接收 velocity 为 0 的
    //   Note On。因此本函数在 velocity=0 时**返回 Note Off**，把该规则
    //   固化在构造入口，避免调用方遗漏。
    //   返回的 Note Off 保留原 note_number 与 source_id。
    function automatic performance_event_t make_note_event(
        input logic               is_on,
        input logic [3:0]         source_id,
        input logic [3:0]         channel,
        input logic [6:0]         note_number,
        input logic [9:0]         velocity
    );
        performance_event_t ev;
        ev.event_type    = (is_on && (velocity != 10'd0)) ? EVENT_NOTE_ON
                                                          : EVENT_NOTE_OFF;
        ev.source_id     = source_id;
        ev.channel       = channel;
        ev.note_number   = note_number;
        ev.velocity      = velocity;
        ev.expression    = 10'd0;
        ev.control_id    = 8'd0;
        ev.control_value = 12'd0;
        ev.reserved      = 6'd0;
        return ev;
    endfunction

    // 构造全部音符关闭事件（规范 3.4 节，用于异常恢复与演示前清空挂音）
    function automatic performance_event_t make_all_notes_off(
        input logic [3:0] source_id
    );
        performance_event_t ev;
        ev.event_type    = EVENT_ALL_NOTES_OFF;
        ev.source_id     = source_id;
        ev.channel       = 4'd0;
        ev.note_number   = 7'd0;
        ev.velocity      = 10'd0;
        ev.expression    = 10'd0;
        ev.control_id    = 8'd0;
        ev.control_value = 12'd0;
        ev.reserved      = 6'd0;
        return ev;
    endfunction

endpackage

`endif  // AUDIO_DEFS_PKG_SV
