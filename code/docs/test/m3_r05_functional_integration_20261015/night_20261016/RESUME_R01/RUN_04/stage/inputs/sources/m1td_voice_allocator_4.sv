// T010 4声部分配器（M2复核修正版）
// 修正：公共身份(source+channel+note)、Release生命周期、可靠LRU
`timescale 1ns/1ps

module m1td_voice_allocator_4 (
    input  logic       sys_clk,
    input  logic       sys_rst_n,
    input  logic       note_on,
    input  logic       note_off,
    input  logic [3:0] source_id,      // 来源ID
    input  logic [3:0] channel_id,     // 通道ID
    input  logic [7:0] midi_note,
    input  logic [3:0] release_done,   // 每声部独立Release完成信号
    output logic [1:0] allocated_slot,
    output logic       slot_valid,
    output logic [1:0] release_slot,   // Release目标槽位
    output logic       release_target_valid
);

    typedef struct packed {
        logic       note_active;   // Note On活跃
        logic       in_release;    // Release阶段
        logic [3:0] source;
        logic [3:0] channel;
        logic [7:0] note;
        logic [1:0] age;           // 0最旧，3最新；四槽相对顺序无回绕
    } voice_slot_t;

    voice_slot_t slots [0:3];

    integer i;

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            for (i = 0; i < 4; i = i + 1) begin
                slots[i] <= '0;
                slots[i].age <= i[1:0];
            end
            allocated_slot <= 2'h0;
            slot_valid <= 1'b0;
            release_slot <= 2'h0;
            release_target_valid <= 1'b0;
        end else begin
            slot_valid <= 1'b0;
            release_target_valid <= 1'b0;

            // Release完成：清除对应槽位
            for (i = 0; i < 4; i = i + 1) begin
                if (release_done[i] && slots[i].in_release) begin
                    slots[i].note_active <= 1'b0;
                    slots[i].in_release <= 1'b0;
                end
            end

            // Note On：分配槽位
            if (note_on) begin
                logic found;
                logic [1:0] target_slot;

                found = 1'b0;

                // 1. 查找同身份重触发（包括Release中的音）
                for (i = 0; i < 4; i = i + 1) begin
                    if ((slots[i].note_active || slots[i].in_release) &&
                        slots[i].source == source_id &&
                        slots[i].channel == channel_id &&
                        slots[i].note == midi_note && !found) begin
                        found = 1'b1;
                        target_slot = i[1:0];
                    end
                end

                // 2. 查找IDLE槽（既不活跃也不在Release）
                if (!found) begin
                    for (i = 0; i < 4; i = i + 1) begin
                        if (!slots[i].note_active && !slots[i].in_release && !found) begin
                            found = 1'b1;
                            target_slot = i[1:0];
                        end
                    end
                end

                // 3. 无空槽：按四槽相对顺序取最久未触发的槽。
                // age为秩0..3（0最旧、3最新），不会随事件次数回绕。
                if (!found) begin
                    target_slot = 2'd0;
                    for (i = 1; i < 4; i = i + 1) begin
                        if (slots[i].age < slots[target_slot].age)
                            target_slot = i[1:0];
                    end
                end

                // 目标移至最新；原本比目标新的槽统一前移一位。
                // 保持秩0..3为置换，重触发、窃取和空槽复用均相同。
                for (i = 0; i < 4; i = i + 1) begin
                    if (i != target_slot && slots[i].age > slots[target_slot].age)
                        slots[i].age <= slots[i].age - 2'd1;
                end

                // 分配
                allocated_slot <= target_slot;
                slot_valid <= 1'b1;
                slots[target_slot].note_active <= 1'b1;
                slots[target_slot].in_release <= 1'b0;
                slots[target_slot].source <= source_id;
                slots[target_slot].channel <= channel_id;
                slots[target_slot].note <= midi_note;
                slots[target_slot].age <= 2'd3;
            end

            // Note Off：进入Release
            if (note_off) begin
                for (i = 0; i < 4; i = i + 1) begin
                    if (slots[i].note_active &&
                        slots[i].source == source_id &&
                        slots[i].channel == channel_id &&
                        slots[i].note == midi_note) begin
                        slots[i].note_active <= 1'b0;
                        slots[i].in_release <= 1'b1;
                        release_slot <= i[1:0];
                        release_target_valid <= 1'b1;
                    end
                end
            end
        end
    end

endmodule
