// -----------------------------------------------------------------------------
// perf_event_pkg.sv
// 统一演奏事件的类型定义。对应任务 T014（统一演奏事件接口测试桩）。
//
// 本文件是 code/docs/模块接口规范.md 第三章的**可综合落地**。
// 接口规范是唯一权威来源；本文件只做编码，不得引入规范未定义的字段或取值。
//
// -----------------------------------------------------------------------------
// 为什么要有这个包
// -----------------------------------------------------------------------------
//   规范里 performance_event_t 是 64 位。若每个模块各自写一遍位域拼接，
//   任何一次改动都会出现"发送方和接收方位域不一致"的静默错误——
//   仿真不会报错，只是音高/力度全错。集中定义可以让工具替我们发现不一致。
//
// -----------------------------------------------------------------------------
// 固定的 64 位布局（规范 3.1 节，不得改动）
// -----------------------------------------------------------------------------
//   [63:61] event_type   3 bit
//   [60:57] source_id    4 bit
//   [56:53] channel      4 bit
//   [52:46] note_number  7 bit
//   [45:36] velocity    10 bit
//   [35:26] expression  10 bit
//   [25:18] control_id   8 bit
//   [17: 6] control_value 12 bit
//   [ 5: 0] reserved      6 bit
//   合计 3+4+4+7+10+10+8+12+6 = 64
//
//   第一版 reserved 必须写 0，不得用保留位私传模块内部状态（规范 3.1）。
// -----------------------------------------------------------------------------

`ifndef PERF_EVENT_PKG_SV
`define PERF_EVENT_PKG_SV

package perf_event_pkg;

    // -------------------------------------------------------------------------
    // 事件类型（规范 3.3 节）
    // -------------------------------------------------------------------------
    localparam logic [2:0] EVENT_NOTE_ON        = 3'd0;
    localparam logic [2:0] EVENT_NOTE_OFF       = 3'd1;
    localparam logic [2:0] EVENT_AFTERTOUCH     = 3'd2;
    localparam logic [2:0] EVENT_PITCH_BEND     = 3'd3;
    localparam logic [2:0] EVENT_CONTROL_CHANGE = 3'd4;
    localparam logic [2:0] EVENT_ALL_NOTES_OFF  = 3'd5;
    // 编码 6 和 7 保留

    // -------------------------------------------------------------------------
    // control_id（规范 3.2.1 节）。未列出的编码保留，第一版不得使用。
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
    // 统一演奏事件结构（规范 3.1 节）
    //
    // 用 packed struct 而不是手工拼位：字段名可读，且位宽由编译器检查。
    // 综合工具与 iverilog 均支持 packed struct。
    // -------------------------------------------------------------------------
    typedef struct packed {
        logic [2:0]  event_type;     // [63:61]
        logic [3:0]  source_id;      // [60:57]
        logic [3:0]  channel;        // [56:53]
        logic [6:0]  note_number;    // [52:46]
        logic [9:0]  velocity;       // [45:36]
        logic [9:0]  expression;     // [35:26]
        logic [7:0]  control_id;     // [25:18]
        logic [11:0] control_value;  // [17: 6]
        logic [5:0]  reserved;       // [ 5: 0]
    } performance_event_t;

    // -------------------------------------------------------------------------
    // 构造一个 Note On 事件
    //
    // 【velocity 不得为 0】
    //   规范 3.4 节：输入适配层收到 velocity=0 的 Note On 时，
    //   必须在进入公共事件 FIFO 前转换成 Note Off；
    //   音频核心不接收 velocity 为 0 的 Note On。
    //   因此本函数在 velocity=0 时**返回 Note Off**，把该规则固化在构造入口，
    //   避免调用方遗漏。返回的 Note Off 保留原 note_number 与 source_id。
    // -------------------------------------------------------------------------
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

    // -------------------------------------------------------------------------
    // 构造全部音符关闭事件（规范 3.4 节，用于异常恢复与演示前清空挂音）
    // -------------------------------------------------------------------------
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

`endif // PERF_EVENT_PKG_SV
