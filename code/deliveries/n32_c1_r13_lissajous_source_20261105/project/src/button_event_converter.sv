// -----------------------------------------------------------------------------
// button_event_converter.sv
// 按键脉冲转统一演奏事件。对应任务 T022（M3，rtl/input/）。
//
// 作者：M3（YunZhongDuShu），提交 7b836d0 "# 按键事件转换模块使用"。
// 本文件由 M2 在 T022 集成（合并进 develop）时迁入新结构，并把事件构造函数
// 改为调用 audio_defs_pkg 中的唯一实现。
//
// -----------------------------------------------------------------------------
// 迁移与集成记录（M2，2026-09-15，依据技术决策记录 D022）
// -----------------------------------------------------------------------------
//   原路径：代码/rtl/input/button_event_converter.sv
//   新路径：code/rtl/input/button_event_converter/button_event_converter.sv
//
//   M2 对本文件的改动（其余逻辑逐字保留）：
//     1. 删除本文件内自行逐字段拼装 performance_event_t 的局部函数，改为调用
//        audio_defs_pkg::make_note_event()。该包现为事件类型的唯一定义处，
//        重复定义的 perf_event_pkg.sv 已删除。
//     2. 局部函数名 make_note_event -> make_key_event。包内同名函数经
//        `import audio_defs_pkg::*` 引入后，保留原名会形成"局部声明遮蔽包
//        函数"的隐患——两者签名不同，编译器不会报错。
//     3. 修正对表达式直接取位选的非法写法：(a + b)[6:0]。iverilog 报
//        syntax error / Malformed statement，必须先存入中间变量。
//     4. 补充 `timescale 1ns / 1ps。本文件原缺，iverilog 会警告
//        "timescale inherited from another file"，且警告位置指向无关文件。
//
//   接口、参数名、FIFO 行为、溢出计数语义均未改动。
// -----------------------------------------------------------------------------

// 将去抖后的按键边沿转换为统一的 64 位演奏事件。
//
// 默认参数为两路按键：MIDI 60（中央 C）和 MIDI 62（D），即"每键相差 2 个
// 半音"的等间距映射。**等间距映射只适合按键编号连续的场合**；电子钢琴
// 顶层的两个实体按键是 A4 与 C5（相差 3 个半音），由
// electronic_piano_top.sv 在实例化时用 .BASE_NOTE_NUMBER(69) /
// .NOTE_STEP(3) 覆盖，不修改本模块默认值。
//
// 事件构造函数不再在本文件内重复实现：性能事件的字段拼装统一由
// audio_defs_pkg::make_note_event() 提供（见 D022）。
`timescale 1ns / 1ps

module button_event_converter #(
    parameter integer BUTTON_COUNT       = 2,
    parameter integer LOCAL_FIFO_DEPTH   = 4,
    parameter integer BASE_NOTE_NUMBER   = 60,
    parameter integer NOTE_STEP          = 2,
    parameter logic [3:0] SOURCE_ID       = 4'd0,
    parameter logic [3:0] CHANNEL         = 4'd0,
    parameter logic [9:0] NOTE_ON_VELOCITY = 10'd512
) (
    input  logic                                  clk,
    input  logic                                  rst_n,
    input  logic [BUTTON_COUNT-1:0]               button_press_pulse,
    input  logic [BUTTON_COUNT-1:0]               button_release_pulse,
    input  logic                                  event_ready,
    output logic                                  event_valid,
    output audio_defs_pkg::performance_event_t    event_data,
    output logic [31:0]                           overflow_count
);

    import audio_defs_pkg::*;

    localparam integer FIFO_COUNT_WIDTH =
        (LOCAL_FIFO_DEPTH <= 1) ? 1 : $clog2(LOCAL_FIFO_DEPTH + 1);

    performance_event_t fifo_mem      [0:LOCAL_FIFO_DEPTH-1];
    performance_event_t fifo_mem_next [0:LOCAL_FIFO_DEPTH-1];
    // Native03 private setup candidate: late ready only selects completed
    // pop/no-pop alternatives. No extra FF, event latency or interface change.
    // R02: packed temporary vectors, constant-slot writes; no temporary RAM arrays.
    localparam integer EVENT_W = $bits(performance_event_t);
    logic [LOCAL_FIFO_DEPTH*EVENT_W-1:0] mem_no_pop_flat;
    logic [LOCAL_FIFO_DEPTH*EVENT_W-1:0] mem_with_pop_flat;
    logic [FIFO_COUNT_WIDTH-1:0] occupancy_no_pop, occupancy_with_pop;


    logic [FIFO_COUNT_WIDTH-1:0] fifo_count;
    logic [FIFO_COUNT_WIDTH-1:0] fifo_count_next;
    localparam integer MAX_DROP_PER_CYCLE = 2*BUTTON_COUNT;
    localparam integer DROP_W = $clog2(MAX_DROP_PER_CYCLE+1);
    localparam integer TOTAL_W =
        ((FIFO_COUNT_WIDTH > DROP_W) ? FIFO_COUNT_WIDTH : DROP_W) + 1;
    logic [DROP_W-1:0] incoming_count, drops_no_pop, drops_with_pop;
    logic [TOTAL_W-1:0] total_no_pop, total_with_pop;
    logic [31:0] count_no_pop, count_with_pop;
    wire counter_pop = event_valid && event_ready;
    integer pulse_index;
    wire [31:0] overflow_result [0:MAX_DROP_PER_CYCLE];
    assign overflow_result[0] = overflow_count;
    // Parallel constant-increment adders depend only on registered count;
    // the event/ready chain ends at a bounded selection mux, not carry logic.
    for(genvar inc=1;inc<=MAX_DROP_PER_CYCLE;inc=inc+1) begin:g_overflow_result
        wire [32:0] candidate_sum = {1'b0,overflow_count} + 33'(inc);
        assign overflow_result[inc] = candidate_sum[32] ? 32'hffffffff : candidate_sum[31:0];
    end

    // Both branches depend ONLY on registered occupancy/count and input
    // pulses. The late ready handshake selects the final 32-bit value.
    // No ready-dependent counter CE and no additional sequential stage.
    always_comb begin
        incoming_count = '0;
        for (pulse_index = 0; pulse_index < BUTTON_COUNT; pulse_index = pulse_index + 1) begin
            incoming_count = incoming_count + DROP_W'(button_press_pulse[pulse_index]);
            incoming_count = incoming_count + DROP_W'(button_release_pulse[pulse_index]);
        end
        total_no_pop = TOTAL_W'(fifo_count) + TOTAL_W'(incoming_count);
        total_with_pop = total_no_pop;
        // The pop branch is reachable only if the FIFO is nonempty. Guard
        // the subtraction anyway so empty occupancy can never underflow.
        if (fifo_count != 0) total_with_pop = total_no_pop - TOTAL_W'(1);
        drops_no_pop = '0;
        drops_with_pop = '0;
        if (total_no_pop > TOTAL_W'(LOCAL_FIFO_DEPTH))
            drops_no_pop = DROP_W'(total_no_pop - TOTAL_W'(LOCAL_FIFO_DEPTH));
        if (total_with_pop > TOTAL_W'(LOCAL_FIFO_DEPTH))
            drops_with_pop = DROP_W'(total_with_pop - TOTAL_W'(LOCAL_FIFO_DEPTH));
        count_no_pop = overflow_result[drops_no_pop];
        count_with_pop = overflow_result[drops_with_pop];
    end

    integer comb_fifo_index;
    integer comb_button_index;
    integer seq_fifo_index;

    // 根据按键编号生成完整事件。
    //
    // 【D022 / 2026-09-15，M2 改动】原实现自行逐字段拼装 performance_event_t，
    // 与 audio_defs_pkg 内的构造函数重复。现改为调用包中**唯一**的构造函数
    // make_note_event()，使"velocity=0 的 Note On 必须转 Note Off"
    // （接口规范 3.4 节）这条规则由构造入口统一保证，调用方无法绕过。
    //
    // 函数名由 make_note_event 改为 make_key_event：包内同名函数已被
    // `import audio_defs_pkg::*` 引入，保留原名会形成"局部声明遮蔽包函数"
    // 的隐患（两者签名不同，编译器不报错）。
    // 松开事件按原实现传 velocity=0。
    function automatic performance_event_t make_key_event(
        input logic   is_on,
        input integer key_index
    );
        logic [31:0] note_sum;
        logic [6:0]  note_value;
        // 注意：不能对表达式直接取位选，(a + b)[6:0] 是非法语法。
        // 必须先算进中间变量再取位，否则 iverilog 报
        //   syntax error / Malformed statement
        note_sum   = BASE_NOTE_NUMBER + (key_index * NOTE_STEP);
        note_value = note_sum[6:0];
        return audio_defs_pkg::make_note_event(
            is_on,
            SOURCE_ID,
            CHANNEL,
            note_value,
            is_on ? NOTE_ON_VELOCITY : 10'd0
        );
    endfunction

    // 输出只由已寄存的 FIFO 头部决定，不形成 ready-valid 组合环路。
    always_comb begin
        event_valid = (fifo_count != {FIFO_COUNT_WIDTH{1'b0}});
        event_data  = '0;
        if (event_valid) begin
            event_data = fifo_mem[0];
        end
    end

    // All comparisons and append indices in this branch exclude event_ready.
    always_comb begin
        occupancy_no_pop = fifo_count;
        for (integer i=0; i<LOCAL_FIFO_DEPTH; i=i+1)
            mem_no_pop_flat[i*EVENT_W +: EVENT_W] = fifo_mem[i];
        for (integer key_index=0; key_index<BUTTON_COUNT; key_index=key_index+1) begin
            if (button_press_pulse[key_index] && occupancy_no_pop < LOCAL_FIFO_DEPTH) begin
                for (integer slot_index=0; slot_index<LOCAL_FIFO_DEPTH; slot_index=slot_index+1)
                    if (occupancy_no_pop == FIFO_COUNT_WIDTH'(slot_index))
                        mem_no_pop_flat[slot_index*EVENT_W +: EVENT_W] = make_key_event(1'b1, key_index);
                occupancy_no_pop = occupancy_no_pop + 1'b1;
            end
            if (button_release_pulse[key_index] && occupancy_no_pop < LOCAL_FIFO_DEPTH) begin
                for (integer slot_index=0; slot_index<LOCAL_FIFO_DEPTH; slot_index=slot_index+1)
                    if (occupancy_no_pop == FIFO_COUNT_WIDTH'(slot_index))
                        mem_no_pop_flat[slot_index*EVENT_W +: EVENT_W] = make_key_event(1'b0, key_index);
                occupancy_no_pop = occupancy_no_pop + 1'b1;
            end
        end
    end

    // All comparisons and append indices in this branch exclude event_ready.
    always_comb begin
        occupancy_with_pop = fifo_count;
        for (integer i=0; i<LOCAL_FIFO_DEPTH; i=i+1)
            mem_with_pop_flat[i*EVENT_W +: EVENT_W] = fifo_mem[i];
        if (fifo_count != 0) begin
            for (integer i=0; i<LOCAL_FIFO_DEPTH-1; i=i+1)
                mem_with_pop_flat[i*EVENT_W +: EVENT_W] = fifo_mem[i+1];
            mem_with_pop_flat[(LOCAL_FIFO_DEPTH-1)*EVENT_W +: EVENT_W] = '0;
            occupancy_with_pop = fifo_count - 1'b1;
        end
        for (integer key_index=0; key_index<BUTTON_COUNT; key_index=key_index+1) begin
            if (button_press_pulse[key_index] && occupancy_with_pop < LOCAL_FIFO_DEPTH) begin
                for (integer slot_index=0; slot_index<LOCAL_FIFO_DEPTH; slot_index=slot_index+1)
                    if (occupancy_with_pop == FIFO_COUNT_WIDTH'(slot_index))
                        mem_with_pop_flat[slot_index*EVENT_W +: EVENT_W] = make_key_event(1'b1, key_index);
                occupancy_with_pop = occupancy_with_pop + 1'b1;
            end
            if (button_release_pulse[key_index] && occupancy_with_pop < LOCAL_FIFO_DEPTH) begin
                for (integer slot_index=0; slot_index<LOCAL_FIFO_DEPTH; slot_index=slot_index+1)
                    if (occupancy_with_pop == FIFO_COUNT_WIDTH'(slot_index))
                        mem_with_pop_flat[slot_index*EVENT_W +: EVENT_W] = make_key_event(1'b0, key_index);
                occupancy_with_pop = occupancy_with_pop + 1'b1;
            end
        end
    end

    // The late handshake reaches only this final bounded selection.
    always_comb begin
        fifo_count_next = counter_pop ? occupancy_with_pop : occupancy_no_pop;
        for (integer i=0; i<LOCAL_FIFO_DEPTH; i=i+1)
            fifo_mem_next[i] = counter_pop ? mem_with_pop_flat[i*EVENT_W +: EVENT_W] : mem_no_pop_flat[i*EVENT_W +: EVENT_W];
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            fifo_count     <= {FIFO_COUNT_WIDTH{1'b0}};
            overflow_count <= 32'd0;
            for (seq_fifo_index = 0; seq_fifo_index < LOCAL_FIFO_DEPTH; seq_fifo_index = seq_fifo_index + 1) begin
                fifo_mem[seq_fifo_index] <= '0;
            end
        end else begin
            fifo_count <= fifo_count_next;
            for (seq_fifo_index = 0; seq_fifo_index < LOCAL_FIFO_DEPTH; seq_fifo_index = seq_fifo_index + 1) begin
                fifo_mem[seq_fifo_index] <= fifo_mem_next[seq_fifo_index];
            end

            // 溢出计数采用饱和方式，避免计数器回绕后掩盖历史错误。
            // With no drop, the selected table entry is the old count.
            // Unconditional assignment avoids a late ready-derived enable.
            overflow_count <= counter_pop ? count_with_pop : count_no_pop;
        end
    end

endmodule
