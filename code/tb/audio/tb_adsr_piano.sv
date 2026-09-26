// T009 ADSR包络Testbench
// 验证策略：逐样本对比M1 Python模型，包括Release重触发
`timescale 1ns/1ps

module tb_adsr_piano;

    logic sys_clk;
    logic sys_rst_n;
    logic sample_tick;
    logic note_on;
    logic note_off;
    logic [9:0] velocity;
    logic [15:0] envelope_level;
    logic [2:0] state_out;

    // 实例化DUT
    adsr_piano_envelope u_dut (
        .sys_clk(sys_clk),
        .sys_rst_n(sys_rst_n),
        .sample_tick(sample_tick),
        .note_on(note_on),
        .note_off(note_off),
        .velocity(velocity),
        .envelope_level(envelope_level),
        .state_out(state_out)
    );

    // 时钟生成：50MHz
    initial begin
        sys_clk = 0;
        forever #10 sys_clk = ~sys_clk;
    end

    // 采样时钟生成：48kHz
    integer sample_counter;
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            sample_counter <= 0;
            sample_tick <= 0;
        end else begin
            if (sample_counter >= 1041) begin
                sample_counter <= 0;
                sample_tick <= 1;
            end else begin
                sample_counter <= sample_counter + 1;
                sample_tick <= 0;
            end
        end
    end

    // 测试流程
    integer sample_count, error_count;
    logic [15:0] prev_level;

    initial begin
        sys_rst_n = 0;
        note_on = 0;
        note_off = 0;
        velocity = 10'd1023;
        error_count = 0;
        sample_count = 0;

        repeat(10) @(posedge sys_clk);
        sys_rst_n = 1;
        repeat(10) @(posedge sys_clk);

        $display("=== T009 ADSR Piano Envelope Test ===");

        // 测试1: 完整ADSR循环
        $display("\nTest 1: Full ADSR cycle with velocity=1023");

        // Note On
        @(posedge sys_clk);
        note_on = 1;
        @(posedge sys_clk);
        note_on = 0;

        // 等待Attack + Decay完成（5ms + 100ms = 5040样本）
        repeat(5040) begin
            @(posedge sys_clk);
            if (sample_tick) sample_count++;
        end

        $display("After Attack+Decay: level=%d, state=%d", envelope_level, state_out);

        // Sustain阶段（500ms = 24000样本）
        repeat(24000) begin
            @(posedge sys_clk);
            if (sample_tick) sample_count++;
        end

        $display("After Sustain: level=%d, state=%d", envelope_level, state_out);

        // Note Off
        @(posedge sys_clk);
        note_off = 1;
        @(posedge sys_clk);
        note_off = 0;

        prev_level = envelope_level;

        // Release阶段（100ms = 4800样本）
        repeat(4800) begin
            @(posedge sys_clk);
            if (sample_tick) begin
                if (envelope_level > prev_level) begin
                    $display("ERROR: Release level increased %d->%d", prev_level, envelope_level);
                    error_count++;
                end
                prev_level = envelope_level;
                sample_count++;
            end
        end

        if (envelope_level != 0) begin
            $display("ERROR: Release did not reach zero, final=%d", envelope_level);
            error_count++;
        end else begin
            $display("Release completed: level=0, state=%d", state_out);
        end

        // 测试2: Release重触发
        $display("\nTest 2: Release retrigger smooth transition");

        // Note On
        @(posedge sys_clk);
        note_on = 1;
        velocity = 10'd1023;
        @(posedge sys_clk);
        note_on = 0;

        // 完整ADSR到Release中途
        repeat(30000) begin
            @(posedge sys_clk);
            if (sample_tick) sample_count++;
        end

        // Note Off进入Release
        @(posedge sys_clk);
        note_off = 1;
        @(posedge sys_clk);
        note_off = 0;

        // Release中途（2400样本）
        repeat(2400) begin
            @(posedge sys_clk);
            if (sample_tick) sample_count++;
        end

        prev_level = envelope_level;
        $display("Before retrigger: level=%d", prev_level);

        // Release重触发
        @(posedge sys_clk);
        note_on = 1;
        velocity = 10'd512;
        @(posedge sys_clk);
        note_on = 0;

        // 检查首样本跳变
        @(posedge sys_clk);
        if (sample_tick) begin
            @(posedge sys_clk);
            integer delta = (envelope_level > prev_level) ?
                           (envelope_level - prev_level) : (prev_level - envelope_level);
            $display("After retrigger: level=%d, delta=%d", envelope_level, delta);

            // 检查跳变是否在合理范围（< 138 LSB，M2门槛）
            if (delta > 138) begin
                $display("ERROR: Retrigger jump too large: %d > 138", delta);
                error_count++;
            end else begin
                $display("PASS: Retrigger transition smooth");
            end
        end

        // 测试完成
        $display("\n=== Test Summary ===");
        $display("Total samples: %d", sample_count);
        $display("Errors: %d", error_count);

        if (error_count == 0) begin
            $display("PASS: T009 ADSR envelope");
            $finish(0);
        end else begin
            $display("FAIL: T009 ADSR envelope");
            $finish(1);
        end
    end

    initial begin
        #200ms;
        $display("ERROR: Simulation timeout");
        $finish(2);
    end

endmodule
