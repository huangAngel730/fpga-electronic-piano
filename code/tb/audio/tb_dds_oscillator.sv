// T004 DDS振荡器Testbench
// 验证策略：逐样本对比M1 Python模型输出
`timescale 1ns/1ps

module tb_dds_oscillator;

    // 时钟和复位
    logic sys_clk;
    logic sys_rst_n;
    logic sample_tick;

    // DDS接口
    logic [31:0] fcw;
    logic signed [15:0] wt_sample;

    // 实例化DUT
    dds_oscillator u_dut (
        .sys_clk(sys_clk),
        .sys_rst_n(sys_rst_n),
        .sample_tick(sample_tick),
        .fcw(fcw),
        .wt_sample(wt_sample)
    );

    // 时钟生成：50MHz
    initial begin
        sys_clk = 0;
        forever #10 sys_clk = ~sys_clk;  // 20ns周期
    end

    // 采样时钟生成：48kHz
    // 50MHz / 48kHz ≈ 1042周期
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
    integer golden_file, error_count, sample_count;
    logic signed [15:0] expected_sample;
    integer scan_ret;

    initial begin
        // 初始化
        sys_rst_n = 0;
        fcw = 32'h0;
        error_count = 0;
        sample_count = 0;

        // 复位
        repeat(10) @(posedge sys_clk);
        sys_rst_n = 1;
        repeat(10) @(posedge sys_clk);

        $display("=== T004 DDS Oscillator Test ===");
        $display("Testing A4 (440Hz) for 1000 samples");

        // 设置FCW: A4 (440Hz)
        // FCW = (440 * 2^32) / 48000 = 39224903
        fcw = 32'd39224903;

        // 打开黄金参考文件
        golden_file = $fopen("../../../model/generated/dds_test/dds_a4_440hz.txt", "r");
        if (golden_file == 0) begin
            $display("ERROR: Cannot open golden reference file");
            $finish;
        end

        // 跳过文件头
        while (!$feof(golden_file)) begin
            scan_ret = $fscanf(golden_file, "%d\n", expected_sample);
            if (scan_ret == 1 && expected_sample != 0) break;
        end
        $fseek(golden_file, 0, 0);  // 重置到文件开头

        // 逐样本验证（前1000样本）
        repeat(1000) begin
            @(posedge sys_clk);
            if (sample_tick) begin
                // 等待1个时钟让波表输出稳定
                @(posedge sys_clk);

                scan_ret = $fscanf(golden_file, "%d\n", expected_sample);
                if (scan_ret != 1) begin
                    $display("ERROR: Failed to read golden reference at sample %0d", sample_count);
                    error_count++;
                    break;
                end

                // 对比输出
                if (wt_sample !== expected_sample) begin
                    $display("MISMATCH at sample %0d: DUT=%0d, Expected=%0d",
                             sample_count, wt_sample, expected_sample);
                    error_count++;
                    if (error_count >= 10) begin
                        $display("ERROR: Too many mismatches, stopping test");
                        break;
                    end
                end

                sample_count++;
                if (sample_count % 100 == 0) begin
                    $display("Progress: %0d samples verified", sample_count);
                end
            end
        end

        $fclose(golden_file);

        // 结果报告
        $display("");
        $display("=== Test Summary ===");
        $display("Total samples: %0d", sample_count);
        $display("Errors: %0d", error_count);

        if (error_count == 0) begin
            $display("PASS: T004 DDS oscillator matches Python model");
            $finish(0);
        end else begin
            $display("FAIL: T004 DDS oscillator has mismatches");
            $finish(1);
        end
    end

    // 超时保护
    initial begin
        #100ms;
        $display("ERROR: Simulation timeout");
        $finish(2);
    end

endmodule
