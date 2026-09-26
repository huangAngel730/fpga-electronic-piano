// T010 声部分配器Testbench
// 验证LRU策略、同音重触发、满载窃取
`timescale 1ns/1ps

module tb_voice_allocator;

    logic sys_clk;
    logic sys_rst_n;
    logic note_on;
    logic note_off;
    logic [7:0] midi_note;
    logic [1:0] allocated_slot;
    logic slot_valid;

    // 实例化DUT
    voice_allocator_4 u_dut (
        .sys_clk(sys_clk),
        .sys_rst_n(sys_rst_n),
        .note_on(note_on),
        .note_off(note_off),
        .midi_note(midi_note),
        .allocated_slot(allocated_slot),
        .slot_valid(slot_valid)
    );

    // 时钟生成
    initial begin
        sys_clk = 0;
        forever #10 sys_clk = ~sys_clk;
    end

    // 测试任务
    task trigger_note_on(input logic [7:0] note);
        @(posedge sys_clk);
        note_on = 1;
        midi_note = note;
        @(posedge sys_clk);
        note_on = 0;
        @(posedge sys_clk);
    endtask

    task trigger_note_off(input logic [7:0] note);
        @(posedge sys_clk);
        note_off = 1;
        midi_note = note;
        @(posedge sys_clk);
        note_off = 0;
        @(posedge sys_clk);
    endtask

    integer error_count;

    initial begin
        sys_rst_n = 0;
        note_on = 0;
        note_off = 0;
        midi_note = 8'h0;
        error_count = 0;

        repeat(10) @(posedge sys_clk);
        sys_rst_n = 1;
        repeat(10) @(posedge sys_clk);

        $display("=== T010 Voice Allocator Test ===");

        // 测试1: 顺序分配空闲槽
        $display("\nTest 1: Sequential allocation");
        trigger_note_on(8'd60);  // C4
        if (!slot_valid || allocated_slot != 0) begin
            $display("ERROR: Expected slot 0, got %d", allocated_slot);
            error_count++;
        end else $display("PASS: C4 -> slot 0");

        trigger_note_on(8'd64);  // E4
        if (!slot_valid || allocated_slot != 1) begin
            $display("ERROR: Expected slot 1, got %d", allocated_slot);
            error_count++;
        end else $display("PASS: E4 -> slot 1");

        trigger_note_on(8'd67);  // G4
        if (!slot_valid || allocated_slot != 2) begin
            $display("ERROR: Expected slot 2, got %d", allocated_slot);
            error_count++;
        end else $display("PASS: G4 -> slot 2");

        trigger_note_on(8'd72);  // C5
        if (!slot_valid || allocated_slot != 3) begin
            $display("ERROR: Expected slot 3, got %d", allocated_slot);
            error_count++;
        end else $display("PASS: C5 -> slot 3");

        // 测试2: 同音重触发
        $display("\nTest 2: Same-note retrigger");
        trigger_note_on(8'd64);  // E4再次触发
        if (!slot_valid || allocated_slot != 1) begin
            $display("ERROR: Same-note should return slot 1, got %d", allocated_slot);
            error_count++;
        end else $display("PASS: E4 retrigger -> slot 1");

        // 测试3: Note Off释放
        $display("\nTest 3: Note Off release");
        trigger_note_off(8'd64);  // 释放E4
        repeat(5) @(posedge sys_clk);

        trigger_note_on(8'd69);  // A4，应分配到slot 1
        if (!slot_valid || allocated_slot != 1) begin
            $display("ERROR: Expected freed slot 1, got %d", allocated_slot);
            error_count++;
        end else $display("PASS: A4 -> slot 1 (freed)");

        // 测试4: 满载LRU窃取
        $display("\nTest 4: Full slots LRU steal");
        // 当前槽位：0=C4, 1=A4, 2=G4, 3=C5
        repeat(100) @(posedge sys_clk);  // 让时间戳推进

        trigger_note_on(8'd76);  // E5，应窃取最旧槽（slot 0）
        if (!slot_valid || allocated_slot != 0) begin
            $display("ERROR: Expected LRU slot 0, got %d", allocated_slot);
            error_count++;
        end else $display("PASS: E5 -> slot 0 (LRU steal)");

        // 测试完成
        $display("\n=== Test Summary ===");
        $display("Errors: %d", error_count);

        if (error_count == 0) begin
            $display("PASS: T010 Voice allocator");
            $finish(0);
        end else begin
            $display("FAIL: T010 Voice allocator");
            $finish(1);
        end
    end

    initial begin
        #10ms;
        $display("ERROR: Simulation timeout");
        $finish(2);
    end

endmodule
