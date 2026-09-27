// T010 4声部分配器（M2复核修正版）
// 修正：公共身份(source+channel+note)、Release生命周期、可靠LRU
`timescale 1ns/1ps

module voice_allocator_4 (
    input  logic       sys_clk,
    input  logic       sys_rst_n,
    input  logic       note_on,
    input  logic       note_off,
    input  logic [3:0] source_id,      // 来源ID
    input  logic [3:0] channel_id,     // 通道ID
    input  logic [7:0] midi_note,
    input  logic       release_done,   // Release完成信号
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
        logic [2:0] age;           // 0-7年龄，越小越旧
    } voice_slot_t;

    voice_slot_t slots [0:3];
    logic [2:0] global_age;

    integer i;

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            global_age <= 3'h0;
            for (i = 0; i < 4; i = i + 1) begin
                slots[i] <= '0;
            end
            allocated_slot <= 2'h0;
            slot_valid <= 1'b0;
            release_slot <= 2'h0;
            release_target_valid <= 1'b0;
        end else begin
            slot_valid <= 1'b0;
            release_target_valid <= 1'b0;

            // Release完成：清除槽位
            if (release_done) begin
                for (i = 0; i < 4; i = i + 1) begin
                    if (slots[i].in_release) begin
                        slots[i].note_active <= 1'b0;
                        slots[i].in_release <= 1'b0;
                    end
                end
            end

            // Note On：分配槽位
            if (note_on) begin
                logic found;
                logic [1:0] target_slot;

                found = 1'b0;

                // 1. 查找同身份重触发
                for (i = 0; i < 4; i = i + 1) begin
                    if (slots[i].note_active &&
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

                // 3. LRU窃取：选最小age
                if (!found) begin
                    logic [2:0] oldest_age;
                    oldest_age = slots[0].age;
                    target_slot = 2'h0;

                    for (i = 1; i < 4; i = i + 1) begin
                        if (slots[i].age < oldest_age) begin
                            oldest_age = slots[i].age;
                            target_slot = i[1:0];
                        end
                    end
                end

                // 分配
                allocated_slot <= target_slot;
                slot_valid <= 1'b1;
                slots[target_slot].note_active <= 1'b1;
                slots[target_slot].in_release <= 1'b0;
                slots[target_slot].source <= source_id;
                slots[target_slot].channel <= channel_id;
                slots[target_slot].note <= midi_note;
                slots[target_slot].age <= global_age;
                global_age <= global_age + 1;
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
