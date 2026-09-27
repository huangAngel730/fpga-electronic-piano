// T010 4声部分配器（修正版）
// 基于M1 Python模型: code/model/voice_manager.py
// 修正：Icarus兼容、时间戳回绕、来源/通道身份、Release槽位
`timescale 1ns/1ps

module voice_allocator_4 (
    input  logic       sys_clk,
    input  logic       sys_rst_n,
    input  logic       note_on,        // Note On事件
    input  logic       note_off,       // Note Off事件
    input  logic [7:0] midi_note,      // MIDI音符号 (0-127)
    input  logic [3:0] source_id,      // 来源/通道ID (0-15)
    output logic [1:0] allocated_slot, // 分配的槽位 (0-3)
    output logic       slot_valid,     // 分配成功标志
    output logic [3:0] slot_states     // 4个槽位的active状态（调试用）
);

    // 每个槽位的状态
    typedef struct packed {
        logic       active;       // 槽位是否活跃
        logic [7:0] note;         // 当前音符
        logic [3:0] source;       // 来源/通道ID
        logic [15:0] timestamp;   // LRU时间戳
    } voice_slot_t;

    voice_slot_t slots [0:3];
    logic [15:0] global_time;

    // 输出槽位状态
    assign slot_states = {slots[3].active, slots[2].active, slots[1].active, slots[0].active};

    // 时间戳更新（带回绕检测）
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            global_time <= 16'h0;
        end else begin
            // 时间戳递增，自然回绕
            global_time <= global_time + 16'h1;
        end
    end

    // 声部分配逻辑
    integer i;
    logic found_same;
    logic [1:0] same_slot;
    logic found_idle;
    logic [1:0] idle_slot;
    logic [1:0] oldest_slot;
    logic [15:0] oldest_time;

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            for (i = 0; i < 4; i = i + 1) begin
                slots[i].active <= 1'b0;
                slots[i].note <= 8'h0;
                slots[i].source <= 4'h0;
                slots[i].timestamp <= 16'h0;
            end
            allocated_slot <= 2'b00;
            slot_valid <= 1'b0;
        end else begin
            slot_valid <= 1'b0;

            if (note_on) begin
                // 查找是否已有该音符+来源（同音同源重触发）
                found_same = 1'b0;
                same_slot = 2'b00;

                for (i = 0; i < 4; i = i + 1) begin
                    if (slots[i].active &&
                        slots[i].note == midi_note &&
                        slots[i].source == source_id) begin
                        if (!found_same) begin
                            found_same = 1'b1;
                            same_slot = i[1:0];
                        end
                    end
                end

                if (found_same) begin
                    // 同音同源重触发：返回原槽
                    allocated_slot <= same_slot;
                    slots[same_slot].timestamp <= global_time;
                    slot_valid <= 1'b1;
                end else begin
                    // 查找空闲槽
                    found_idle = 1'b0;
                    idle_slot = 2'b00;

                    for (i = 0; i < 4; i = i + 1) begin
                        if (!slots[i].active && !found_idle) begin
                            found_idle = 1'b1;
                            idle_slot = i[1:0];
                        end
                    end

                    if (found_idle) begin
                        // 分配空闲槽
                        allocated_slot <= idle_slot;
                        slots[idle_slot].active <= 1'b1;
                        slots[idle_slot].note <= midi_note;
                        slots[idle_slot].source <= source_id;
                        slots[idle_slot].timestamp <= global_time;
                        slot_valid <= 1'b1;
                    end else begin
                        // 窃取最旧槽（LRU，考虑时间戳回绕）
                        oldest_slot = 2'b00;
                        oldest_time = slots[0].timestamp;

                        for (i = 1; i < 4; i = i + 1) begin
                            // 使用有符号比较处理回绕
                            if ($signed(slots[i].timestamp - oldest_time) < 0) begin
                                oldest_time = slots[i].timestamp;
                                oldest_slot = i[1:0];
                            end
                        end

                        allocated_slot <= oldest_slot;
                        slots[oldest_slot].active <= 1'b1;
                        slots[oldest_slot].note <= midi_note;
                        slots[oldest_slot].source <= source_id;
                        slots[oldest_slot].timestamp <= global_time;
                        slot_valid <= 1'b1;
                    end
                end
            end else if (note_off) begin
                // Note Off：释放对应槽位（匹配音符+来源）
                for (i = 0; i < 4; i = i + 1) begin
                    if (slots[i].active &&
                        slots[i].note == midi_note &&
                        slots[i].source == source_id) begin
                        // 标记为非活跃，但保留note/source用于Release阶段
                        slots[i].active <= 1'b0;
                    end
                end
            end
        end
    end

endmodule
