// T028 延迟效果器 TB - 逐样本自检（2026-10-02）
//
// 读取黄金模型生成的向量，逐样本对比 RTL 输出。
// 向量格式（每行）：reset_before input_pcm delay_samples dry_gain wet_gain feedback expected_pcm
//
// Run:  iverilog -g2012 -o tb.vvp tb_delay_effect.sv delay_effect.sv
//       vvp tb.vvp +VECTORS=<path>/delay_effect_vectors.txt

`timescale 1ns/1ps

module tb_delay_effect;
    logic               clk = 0;
    logic               rst_n = 0;
    logic               sample_enable = 0;
    logic signed [23:0] pcm_in = 0;
    logic [15:0]        delay_samples = 0;
    logic [14:0]        dry_gain = 0;
    logic [14:0]        wet_gain = 0;
    logic [14:0]        feedback = 0;
    logic signed [23:0] pcm_out;
    logic               pcm_valid;

    integer fvec, r, errors, samples;
    integer v_reset, v_in, v_delay, v_dry, v_wet, v_fb, v_expect;
    string vec_path;

    // M2 修正：防空跑，向量数量下限
    localparam int MIN_VECTORS = 555;

    // DUT：小深度验证（1024 样本）
    delay_effect #(.DEPTH(1024)) dut (
        .sys_clk(clk), .sys_rst_n(rst_n), .sample_enable(sample_enable),
        .pcm_in(pcm_in), .delay_samples(delay_samples),
        .dry_gain(dry_gain), .wet_gain(wet_gain), .feedback(feedback),
        .pcm_out(pcm_out), .pcm_valid(pcm_valid)
    );

    always #10 clk = ~clk;   // 50 MHz

    task automatic reset_history;
        begin
            @(negedge clk);
            sample_enable = 0;
            rst_n = 0;
            #1;
            if (pcm_valid !== 0 || pcm_out !== 0)
                $fatal(1, "reset must clear output and valid immediately");
            repeat (3) @(negedge clk);
            rst_n = 1;
        end
    endtask

    task drive_sample(input integer inp, input integer dly, input integer dry,
                      input integer wet, input integer fb, input integer exp);
        begin
            @(negedge clk);
            pcm_in = inp[23:0];
            delay_samples = dly[15:0];
            dry_gain = dry[14:0];
            wet_gain = wet[14:0];
            feedback = fb[14:0];
            sample_enable = 1;
            @(posedge clk);
            @(negedge clk);
            sample_enable = 0;

            // 等待 pcm_valid（流水延迟 2 周期：M2 修正）
            repeat (2) @(posedge clk);
            #1;

            samples = samples + 1;
            if (!pcm_valid) begin
                $display("FAIL: sample %0d pcm_valid not asserted", samples);
                errors = errors + 1;
            end else if (pcm_out !== exp[23:0]) begin
                if (errors < 10)
                    $display("FAIL: sample %0d in=%0d dly=%0d dry=%0d wet=%0d fb=%0d got=%0d exp=%0d",
                             samples, inp, dly, dry, wet, fb, pcm_out, exp);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        errors = 0; samples = 0;
        if (!$value$plusargs("VECTORS=%s", vec_path)) begin
            $display("FAIL: +VECTORS=<path> is required");
            $fatal(1, "missing VECTORS");
        end

        fvec = $fopen(vec_path, "r");
        if (fvec == 0) begin
            $display("FAIL: cannot open %s", vec_path);
            $fatal(1, "cannot open vectors");
        end

        repeat (3) @(negedge clk);
        rst_n = 1;
        @(negedge clk);

        // check 1: reset state
        if (pcm_out !== 24'd0) begin
            $display("FAIL: reset did not clear pcm_out (%0d)", pcm_out);
            errors = errors + 1;
        end

        // check 2..N: 逐样本对比
        while (!$feof(fvec)) begin
            r = $fscanf(fvec, "%d %d %d %d %d %d %d\n",
                        v_reset, v_in, v_delay, v_dry, v_wet, v_fb, v_expect);
            if (r == 7) begin
                if (v_reset != 0 && v_reset != 1)
                    $fatal(1, "reset_before must be 0 or 1");
                if (v_reset == 1) reset_history();
                drive_sample(v_in, v_delay, v_dry, v_wet, v_fb, v_expect);
            end else if (r != -1) begin
                $fatal(1, "malformed vector line near sample %0d", samples);
            end
        end
        $fclose(fvec);

        // M2 修正：防空跑检查
        if (samples != MIN_VECTORS) begin
            $display("FAIL: %0d vectors, exactly %0d required",
                     samples, MIN_VECTORS);
            errors = errors + 1;
        end

        // check N+1: async reset
        rst_n = 0;
        @(negedge clk);
        #1;
        if (pcm_out !== 24'd0) begin
            $display("FAIL: async reset did not clear pcm_out");
            errors = errors + 1;
        end
        rst_n = 1;

        if (errors == 0) begin
            $display("PASS: tb_delay_effect (%0d samples matched golden model)",
                     samples);
            $finish;
        end
        $fatal(1, "FAIL: tb_delay_effect %0d/%0d samples mismatched",
               errors, samples);
    end
    initial begin #100000000; $fatal(1, "testbench timeout"); end
endmodule
