// T010 4声部分配器（LRU策略）
// 基于M1 Python模型: code/model/voice_manager.py
`timescale 1ns/1ps

module voice_allocator_4 (
    input  logic       sys_clk,
    input  logic       sys_rst_n,
    input  logic       note_on,        // Note On事件
    input  logic       note_off,       // Note Off事件
    input  logic [7:0] midi_note,      // MIDI音符号 (0-127)
    output logic [1:0] allocated_slot, // 分配的槽位 (0-3)
    output logic       slot_valid      // 分配成功标志
);

    // 4个槽位的状态
    typedef struct packed {
        logic       active;      // 槽位是否活跃
        logic [7:0] note;        // 当前音符
        logic [15:0] timestamp;  // LRU时间戳
    } voice_slot_t;

    voice_slot_t slots [0:3];
    logic [15:0] global_time;

    // 时间戳更新
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            global_time <= 16'h0;
        end else begin
            global_time <= global_time + 1;
        end
    end

    // 声部分配逻辑
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            for (int i = 0; i < 4; i++) begin
                slots[i].active <= 1'b0;
                slots[i].note <= 8'h0;
                slots[i].timestamp <= 16'h0;
            end
            allocated_slot <= 2'b00;
            slot_valid <= 1'b0;
        end else begin
            slot_valid <= 1'b0;

            if (note_on) begin
                // 查找是否已有该音符（同音重触发）
                logic found_same_note;
                logic [1:0] same_note_slot;
                found_same_note = 1'b0;

                for (int i = 0; i < 4; i++) begin
                    if (slots[i].active && slots[i].note == midi_note) begin
                        found_same_note = 1'b1;
                        same_note_slot = i[1:0];
                    end
                end

                if (found_same_note) begin
                    // 同音重触发：返回原槽
                    allocated_slot <= same_note_slot;
                    slots[same_note_slot].timestamp <= global_time;
                    slot_valid <= 1'b1;
                end else begin
                    // 查找空闲槽
                    logic found_idle;
                    logic [1:0] idle_slot;
                    found_idle = 1'b0;

                    for (int i = 0; i < 4; i++) begin
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
                        slots[idle_slot].timestamp <= global_time;
                        slot_valid <= 1'b1;
                    end else begin
                        // 窃取最旧槽（LRU）
                        logic [1:0] oldest_slot;
                        logic [15:0] oldest_time;
                        oldest_slot = 2'b00;
                        oldest_time = slots[0].timestamp;

                        for (int i = 1; i < 4; i++) begin
                            if (slots[i].timestamp < oldest_time) begin
                                oldest_time = slots[i].timestamp;
                                oldest_slot = i[1:0];
                            end
                        end

                        allocated_slot <= oldest_slot;
                        slots[oldest_slot].active <= 1'b1;
                        slots[oldest_slot].note <= midi_note;
                        slots[oldest_slot].timestamp <= global_time;
                        slot_valid <= 1'b1;
                    end
                end
            end else if (note_off) begin
                // Note Off：释放对应槽位
                for (int i = 0; i < 4; i++) begin
                    if (slots[i].active && slots[i].note == midi_note) begin
                        slots[i].active <= 1'b0;
                    end
                end
            end
        end
    end

endmodule
