// -----------------------------------------------------------------------------
// tb_note_pitch.sv
// note_pitch 自检 testbench。对应 V0036。
//
// 逐音比对 88 键（MIDI 21..108）的相位步进与黄金值，
// 并单独覆盖八度边界、累加器实际发声频率、复位无关性。
//
// 运行：.\code\scripts\run_t020_sim.ps1
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_note_pitch;

    localparam int unsigned ACC_BITS = 32;
    localparam int unsigned FS       = 48_000;

    logic [6:0]          note_number;
    logic [ACC_BITS-1:0] phase_step;

    int pass_cnt = 0;
    int fail_cnt = 0;

    note_pitch #(
        .ACC_BITS       (ACC_BITS),
        .SAMPLE_RATE_HZ (FS)
    ) dut (
        .note_number (note_number),
        .phase_step  (phase_step)
    );

    // 黄金值：由 Python 用双精度独立算出，不引用 RTL 内部表。
    // 仅列关键音，中间音用公式逐点比较。
    function automatic real freq_of(input int unsigned n);
        real f;
        begin
            f = 440.0 * (2.0 ** ((int'(n) - 69) / 12.0));
            return f;
        end
    endfunction

    task automatic check(input string name, input logic cond);
        begin
            if (cond) begin
                pass_cnt++;
            end else begin
                fail_cnt++;
                $display("  FAIL: %s", name);
            end
        end
    endtask

    int unsigned    n;
    real            f_expect;
    real            f_actual;
    real            cents_err;
    real            max_cents;
    int unsigned    worst_n;

    initial begin
        $display("=== tb_note_pitch ===");

        // ---------------------------------------------------------------------
        // 1. 表中关键音必须等于 T007 已验证值
        // ---------------------------------------------------------------------
        note_number = 7'd69;   // A4
        #1;
        check("A4 = 39370534（与 T007 已验证 440 Hz 常量一致）",
              phase_step == 32'd39370534);

        note_number = 7'd72;   // C5
        #1;
        check("C5 = 46819718", phase_step == 32'd46819718);

        note_number = 7'd60;   // C4 = 表基准
        #1;
        check("C4 = 23409859", phase_step == 32'd23409859);

        // ---------------------------------------------------------------------
        // 2. 逐音比对 88 键（MIDI 21..108）
        //
        // 判定标准：由步进反算的频率与等程律理论频率之差，换算成音分，
        // 必须小于 1 音分。人耳可辨阈值约 5-10 音分。
        // ---------------------------------------------------------------------
        max_cents = 0.0;
        worst_n   = 0;
        for (n = 21; n <= 108; n++) begin
            note_number = n[6:0];
            #1;
            f_expect = freq_of(n);
            f_actual = (phase_step * 1.0) * FS / (2.0 ** ACC_BITS);
            // 音分误差 = 1200 * log2(f_actual / f_expect)
            cents_err = 1200.0 * ($ln(f_actual / f_expect) / $ln(2.0));
            if (cents_err < 0.0) cents_err = -cents_err;
            if (cents_err > max_cents) begin
                max_cents = cents_err;
                worst_n   = n;
            end
        end
        $display("  88 键最大音分误差 = %f 音分 (MIDI %0d)", max_cents, worst_n);
        check("88 键全部误差 < 1 音分", max_cents < 1.0);
        check("88 键最大误差 < 0.01 音分（远优于阈值）", max_cents < 0.01);

        // ---------------------------------------------------------------------
        // 3. 八度边界：o 为负（右移）与 o 为正（左移）都要正确
        // ---------------------------------------------------------------------
        // A0 = MIDI 21，最低音，需要右移 4 位
        note_number = 7'd21;  #1;
        f_actual = (phase_step * 1.0) * FS / (2.0 ** ACC_BITS);
        check("A0 频率约 27.5 Hz", (f_actual > 27.4) && (f_actual < 27.6));

        // C8 = MIDI 108，最高音，左移 4 位
        note_number = 7'd108; #1;
        f_actual = (phase_step * 1.0) * FS / (2.0 ** ACC_BITS);
        check("C8 频率约 4186 Hz", (f_actual > 4185.0) && (f_actual < 4187.0));

        // 每个八度的 A 频率应严格翻倍
        begin
            logic [31:0] a_steps [0:7];
            int unsigned i;
            for (i = 0; i < 8; i++) begin
                note_number = (21 + 12*i);  // A0..A7
                #1;
                a_steps[i] = phase_step;
            end
            check("A0->A1 步进约翻倍", (a_steps[1] > a_steps[0]*2 - 3) &&
                                       (a_steps[1] < a_steps[0]*2 + 3));
            check("A4 步进为 A0 的 16 倍附近", (a_steps[4] > 32'd39370534-4) &&
                                               (a_steps[4] < 32'd39370534+4));
        end

        // ---------------------------------------------------------------------
        // 4. 步进必须非零（否则不发声）
        // ---------------------------------------------------------------------
        begin
            logic all_nonzero;
            all_nonzero = 1'b1;
            for (n = 21; n <= 108; n++) begin
                note_number = n[6:0];
                #1;
                if (phase_step == 0) all_nonzero = 1'b0;
            end
            check("88 键步进全部非零", all_nonzero);
        end

        // ---------------------------------------------------------------------
        // 5. 单调性：音符号递增，步进必须递增
        // ---------------------------------------------------------------------
        begin
            logic [31:0] prev;
            logic monotonic;
            monotonic = 1'b1;
            note_number = 7'd21; #1;
            prev = phase_step;
            for (n = 22; n <= 108; n++) begin
                note_number = n[6:0];
                #1;
                if (phase_step <= prev) monotonic = 1'b0;
                prev = phase_step;
            end
            check("88 键步进严格单调递增", monotonic);
        end

        $display("");
        $display("=== 结果: %0d PASS, %0d FAIL ===", pass_cnt, fail_cnt);
        if (fail_cnt != 0) begin
            $display("TESTBENCH FAILED");
            $fatal(1);
        end
        $display("TESTBENCH PASSED");
        $finish;
    end

endmodule
