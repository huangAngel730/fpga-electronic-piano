// T027 双音色振荡器 真实 RTL 自检（M1 自建，替代原纯打印脚本）
//
// 数据路径口径（与 M2 独立复核一致，勿再沿用旧“E+2 / 3 级”说法）：
//   采样边沿 E 接收相位与锁存音色
//     E   : addr_pipe[0] <- wt_addr,    timbre_pipe[0] <- timbre_latched, valid_pipe[0] <- sample_tick
//     E+1 : addr_pipe[1] <- addr_pipe[0], ...
//     E+2 : 同步 ROM 数据寄存器 <- ROM[addr_pipe[1]], ...
//     E+3 : sample_out <- 音色选择(ROM 数据), sample_valid <- valid_pipe[2]
//   共 4 个寄存阶段。
//
// 本 TB 内含独立参考模型（不用 DUT 内部寄存器做期望），并在捕获文件中
// 逐周期导出完整激励与输出，供 test_t027_rtl.py 做逐样本对照（L3）。
//
// 失败一律 $fatal(1) —— 真实非零退出，不是 $finish 参数。

`timescale 1ns/1ps

module tb_t027_timbre_rtl;

    logic clk = 0;
    always #10 clk = ~clk;

    logic        rst_n = 0;
    logic [3:0]  sample_tick = 0;
    logic [3:0]  note_on     = 0;
    logic [3:0]  note_off    = 0;
    logic [3:0]  timbre_select = 0;
    logic [31:0] fcw [0:3];

    wire signed [15:0] sample_out [0:3];
    wire [3:0]         sample_valid;

    // 参考 ROM（由 TB 自行加载，不从 DUT 内部取）
    logic signed [15:0] sine     [0:1023];
    logic signed [15:0] triangle [0:1023];

    // 独立参考模型
    logic [31:0] ph_ref    [0:3];
    logic        latch_ref [0:3];
    logic [9:0]  a_ref     [0:3][0:3];
    logic        t_ref     [0:3][0:3];
    logic        v_ref     [0:3][0:3];

    integer checks = 0;
    integer valid_outputs = 0;
    integer cycles = 0;
    integer latches = 0;
    integer fd = 0;

    string  capture;
    logic   corrupt;
    logic signed [15:0] expected_value;

    for (genvar i = 0; i < 4; i++) begin : g_lane
        timbre_oscillator dut (
            .clk           (clk),
            .rst_n         (rst_n),
            .sample_tick   (sample_tick[i]),
            .fcw           (fcw[i]),
            .timbre_select (timbre_select[i]),
            .note_on       (note_on[i]),
            .note_off      (note_off[i]),
            .sample_out    (sample_out[i]),
            .sample_valid  (sample_valid[i])
        );
    end

    task automatic fail(input string msg);
        $fatal(1, "FAIL tb_t027_timbre_rtl %s cycle=%0d", msg, cycles);
    endtask

    // 参考模型推进 + 输出比对
    always @(posedge clk) begin
        cycles++;
        if (!rst_n) begin
            for (integer i = 0; i < 4; i++) begin
                ph_ref[i] = 32'd0;
                latch_ref[i] = 1'b0;
                for (integer j = 0; j < 4; j++) begin
                    a_ref[i][j] = 10'd0;
                    t_ref[i][j] = 1'b0;
                    v_ref[i][j] = 1'b0;
                end
            end
        end else begin
            for (integer i = 0; i < 4; i++) begin
                for (integer j = 3; j > 0; j--) begin
                    a_ref[i][j] = a_ref[i][j-1];
                    t_ref[i][j] = t_ref[i][j-1];
                    v_ref[i][j] = v_ref[i][j-1];
                end
                a_ref[i][0] = ph_ref[i][31:22];
                t_ref[i][0] = latch_ref[i];
                v_ref[i][0] = sample_tick[i];
                if (sample_tick[i]) ph_ref[i] = ph_ref[i] + fcw[i];
                if (note_on[i]) begin
                    latch_ref[i] = timbre_select[i];
                    latches++;
                end
            end
        end

        #1;

        for (integer i = 0; i < 4; i++) begin
            if (sample_valid[i] !== v_ref[i][3])
                fail($sformatf("valid alignment lane=%0d", i));
            checks++;
            if (!rst_n) begin
                if (sample_out[i] !== 16'sd0)
                    fail($sformatf("reset must clear output lane=%0d", i));
            end else if (sample_valid[i]) begin
                expected_value = t_ref[i][3] ? triangle[a_ref[i][3]] : sine[a_ref[i][3]];
                if (corrupt) expected_value = expected_value ^ 16'h0001;
                if (sample_out[i] !== expected_value)
                    fail($sformatf("PCM mismatch lane=%0d addr=%0d timbre=%0d exp=%0d act=%0d",
                                   i, a_ref[i][3], t_ref[i][3], expected_value, sample_out[i]));
                checks++;
                valid_outputs++;
                if (sample_out[i] < -8192 || sample_out[i] > 8192)
                    fail($sformatf("amplitude out of frozen +-8192 lane=%0d value=%0d",
                                   i, sample_out[i]));
            end
        end

        // 逐周期导出激励与输出，供 Python 独立复算
        if (fd != 0) begin
            $fdisplay(fd, "C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                cycles, rst_n,
                sample_tick, note_on, note_off, timbre_select,
                fcw[0], fcw[1], fcw[2], fcw[3],
                sample_out[0], sample_out[1], sample_out[2], sample_out[3],
                sample_valid);
        end
    end

    task automatic cyc;
        @(posedge clk);
        #2;
        @(negedge clk);
    endtask

    task automatic do_reset;
        rst_n = 0;
        sample_tick = 0; note_on = 0; note_off = 0; timbre_select = 0;
        repeat (5) cyc();
        rst_n = 1;
        repeat (2) cyc();
    endtask

    initial begin
        corrupt = $test$plusargs("CORRUPT");
        if (!$value$plusargs("CAPTURE=%s", capture))
            $fatal(1, "FAIL tb_t027_timbre_rtl +CAPTURE=<path> is required");
        fd = $fopen(capture, "w");
        if (fd == 0)
            $fatal(1, "FAIL tb_t027_timbre_rtl cannot open capture %s", capture);

        $readmemh("sine_wavetable.hex", sine);
        $readmemh("triangle_wavetable.hex", triangle);
        for (integer i = 0; i < 1024; i++) begin
            if (^sine[i] === 1'bx || ^triangle[i] === 1'bx)
                $fatal(1, "FAIL tb_t027_timbre_rtl incomplete reference ROM at %0d", i);
        end

        for (integer i = 0; i < 4; i++) fcw[i] = 32'h00400000;

        @(negedge clk);
        do_reset();

        // 1) 四路并发，两种音色混排
        timbre_select = 4'b1010;
        note_on       = 4'b1111;
        sample_tick   = 4'b1111;
        repeat (4) cyc();
        note_on = 4'b0000;
        repeat (600) cyc();

        // 2) 全局音色切换不得改变已锁存声部
        timbre_select = 4'b0101;
        repeat (300) cyc();

        // 3) 仅 lane1 重触发并重新锁存；相位不得清零
        note_on = 4'b0010;
        repeat (4) cyc();
        note_on = 4'b0000;
        repeat (300) cyc();

        // 4) Note Off 后相位继续推进（外部 ADSR Release 需要持续波形）
        note_off = 4'b1111;
        repeat (4) cyc();
        note_off = 4'b0000;
        repeat (600) cyc();

        // 5) 四路独立稀疏使能 + 变化 FCW + 运行中切换音色
        for (integer n = 0; n < 300; n++) begin
            sample_tick = {n % 7 == 0, n % 5 == 0, n % 3 == 0, n % 2 == 0};
            fcw[0] = 32'hfc012345;
            fcw[1] = 32'h00400000;
            fcw[2] = 32'h0f123456;
            fcw[3] = 32'h7f000001;
            if (n % 31 == 0) begin
                timbre_select = ~timbre_select;
                note_on       = 4'b0101;
            end else begin
                note_on = 4'b0000;
            end
            cyc();
        end

        // 6) 最低 / 最高合法音符（MIDI 21 = 27.5 Hz，MIDI 108 = 4186.009 Hz）
        do_reset();
        fcw[0] = 32'd2460658;
        fcw[1] = 32'd39370534;
        fcw[2] = 32'd374557749;
        fcw[3] = 32'd19685267;
        timbre_select = 4'b1010;
        note_on       = 4'b1111;
        sample_tick   = 4'b1111;
        repeat (4) cyc();
        note_on = 4'b0000;
        repeat (1200) cyc();

        // 7) 流水线仍有在途数据时复位，必须冲刷
        do_reset();

        // 8) 稳态 440 Hz 固定窗口，供 Python 做真实测频
        for (integer i = 0; i < 4; i++) fcw[i] = 32'd39370534;
        timbre_select = 4'b1010;
        note_on       = 4'b1111;
        sample_tick   = 4'b1111;
        repeat (4) cyc();
        note_on = 4'b0000;
        repeat (8192) cyc();

        do_reset();
        $fclose(fd);

        // 防空跑：必须有足够多的真实输出参与比对
        if (valid_outputs < 40000)
            fail($sformatf("non-vacuous coverage not reached valid_outputs=%0d", valid_outputs));
        if (latches < 20)
            fail($sformatf("too few timbre latch events latches=%0d", latches));

        $display("PASS tb_t027_timbre_rtl checks=%0d valid_outputs=%0d latches=%0d cycles=%0d",
                 checks, valid_outputs, latches, cycles);
        $finish;
    end

    initial begin
        #10000000;
        $fatal(1, "FAIL tb_t027_timbre_rtl timeout");
    end

endmodule
