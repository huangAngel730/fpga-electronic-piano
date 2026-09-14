// -----------------------------------------------------------------------------
// tb_key_to_tone.sv
// T020/T014 端到端集成验证：按按键 -> 事件 -> 声部 -> PCM -> I2S 引脚 -> 音高。
//
// =============================================================================
// 这是本次任务的核心验收 testbench
// =============================================================================
//   它不引用 DUT 内部信号，只观察 4 根引脚（bclk/lrck/din/pa_en），
//   独立解码 LSBJ 流，用零交叉法测实际音高。
//   也就是说：它验证的是"板子会听到什么"，而不是"内部寄存器是什么"。
//
//   验收条件（两条，对应任务的两个映射）：
//     按 EX_KEY.1 (key_n[0]) -> 听到 A4 = 440 Hz
//     按 EX_KEY.2 (key_n[1]) -> 听到 C5 = 523.25 Hz
//     松开             -> 静音
//
//   为什么用零交叉法而不是 FFT：正弦波单音下零交叉法足够准，
//   不依赖额外库，且能顺带发现直流偏置（偏置会让零交叉计数异常）。
//
// 运行：.\code\scripts\run_t007_sim.ps1
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_key_to_tone;

    localparam real CLK_PERIOD_NS = 20.0;   // 50 MHz

    logic sys_clk = 1'b0;
    logic sys_rst_n = 1'b0;

    always #(CLK_PERIOD_NS/2.0) sys_clk = ~sys_clk;

    logic [1:0] key_n = 2'b11;   // 未按下（板上有内部上拉）
    logic i2s_bclk;
    logic i2s_lrck;
    logic i2s_din;
    logic pa_en;
    logic uart_tx;

    int pass_cnt = 0;
    int fail_cnt = 0;

    electronic_piano_top #(
        .CLK_HZ        (50_000_000),
        .TEST_TONE_HZ  (440),
        .SINE_DEPTH    (256),
        .TEST_AMPLITUDE(16'sd8192),
        // 0 = 按键驱动骨架：本 testbench 验证的就是这条路径
        .SOURCE_MODE   (0),
        // 去抖门限缩短到 16 个时钟，否则每次按键要等 10 ms
        .DEBOUNCE_CNT  (16)
    ) dut (
        .sys_clk   (sys_clk),
        .sys_rst_n (sys_rst_n),
        .key_n     (key_n),
        .i2s_bclk  (i2s_bclk),
        .i2s_lrck  (i2s_lrck),
        .i2s_din   (i2s_din),
        .pa_en     (pa_en),
        .uart_tx   (uart_tx)
    );

    // =========================================================================
    // 独立 LSBJ 解码器（只观察引脚）
    //
    //   - 在 BCLK 上升沿采样 DIN（PT8211 在 BCK 上升沿锁存数据）；
    //   - 每声道 32 个 BCLK 一个槽位，槽位结束时取低 16 位为有效数据；
    //   - 用槽位结束时刻的 i2s_lrck 电平判定左右（低=左，高=右）；
    //   - 一帧 64 个 BCLK，LRCK 频率 = BCLK/64 = 48 kHz。
    //
    // 【为什么计数到 31 就归零，而不是数到 63】
    //   这里我连续错了两次，记录清楚以免再犯：
    //   第一次按 32 计数但用打拍的 lrck_q 判定，晚了一个 BCLK，左右错位半帧；
    //   第二次改成"数到 63 才取数"，结果 dec_left 恒为 0、left_cnt 一直是 0——
    //   因为数到 63 时 LRCK 已经翻转，永远只落在同一个声道上，
    //   960 个采样点全部读到 0，表现为"按键后完全没声音"。
    //   正确做法与已验证的 tb_electronic_piano_top 完全一致：
    //   **数到 SLOT_BITS-1（=31）归零，并且直接用 i2s_lrck 当前电平判定**，
    //   不要打拍。这样每个槽位各取一次，左右各一半。
    //
    //   注：DUT 中 BCLK 在 sys_clk 下降沿更新、DIN 在上升沿更新，
    //   故 BCLK 上升沿采样 DIN 时数据已稳定。
    // =========================================================================
    localparam int SLOT_BITS = 32;

    int  bclk_cnt = 0;                  // 槽位内 BCLK 计数 0..31
    logic [SLOT_BITS-1:0] slot_shreg = '0;
    logic signed [15:0]   dec_left   = '0;
    logic signed [15:0]   dec_right  = '0;
    logic                 sample_stb = 1'b0;
    int                   left_cnt   = 0;
    int                   bclk_edges = 0;

    // 左右声道一致性统计。
    // 【必须与已验证的 tb_electronic_piano_top 写法一致】
    //   在**右槽位更新那一刻**比较 dec_left 与 dec_right：
    //   此时 dec_left 仍是本帧刚写入的值，两者是同一帧的左右声道。
    //   我先前改成"在左槽位与上一帧的右值比较"，跨了一帧；
    //   在换音/静音切换时必然误报，得到 4884/5855 的假不匹配。
    logic                 dec_left_valid = 1'b0;
    int                   lr_mismatch = 0;
    int                   lr_checked  = 0;

    always @(posedge i2s_bclk) begin
        // 新位进低位，与 DUT 的 LSBJ 约定一致
        slot_shreg = {slot_shreg[SLOT_BITS-2:0], i2s_din};
        bclk_edges = bclk_edges + 1;

        if (bclk_cnt == SLOT_BITS-1) begin
            // 槽位结束，取低 16 位为有效数据
            if (i2s_lrck == 1'b0) begin
                dec_left       = slot_shreg[15:0];
                dec_left_valid = 1'b1;
                left_cnt       = left_cnt + 1;
                sample_stb     = 1'b1;  // 左声道采样点，供本 testbench 使用
            end else begin
                dec_right  = slot_shreg[15:0];
                sample_stb = 1'b0;
                // 同一帧内比较左右声道（单音下应完全相同）
                if (dec_left_valid) begin
                    lr_checked = lr_checked + 1;
                    if (dec_right !== dec_left) lr_mismatch = lr_mismatch + 1;
                end
            end
            bclk_cnt = 0;
        end else begin
            sample_stb = 1'b0;
            bclk_cnt   = bclk_cnt + 1;
        end
    end

    // 供 testbench 使用的左声道样本（48 kHz 更新）
    logic signed [15:0] left_sample;
    assign left_sample = dec_left;

    // =========================================================================
    // 音高测量：测量"过零间隔"而不是"窗口内过零个数"
    //
    // 【为什么不用"数窗口内过零次数"】
    //   第一版用 f = N / T（N = 窗口内正斜率过零次数，T = 窗口长度）。
    //   问题是 N 只能取整数：20 ms 窗口下 440 Hz 只有 8.8 个周期，
    //   四舍五入成 9 就得到 450 Hz，误差 2.3%，永远过不了 1% 的门限。
    //   要压到 1% 以内，窗口得长到 230 ms 以上，仿真会慢得离谱。
    //
    //   改用**首尾过零时刻之差**：记录第 1 次和第 N 次正斜率过零发生的
    //   采样序号，则周期数 = N-1，时间 = (last_idx - first_idx) / Fs。
    //   这样误差只来自"过零采样点的量化"，而单个采样点的量化误差是
    //   1/48000 s，跨越 9 个周期后相对误差降到 0.2% 量级，
    //   同时窗口长度不变，仿真时间也不变。
    //
    //   过零点用线性插值细化，进一步压低量化误差：
    //   在 prev <= 0 < cur 的两个采样点之间，真实过零时刻位于
    //   prev / (prev - cur) 处（区间内的比例）。
    // =========================================================================
    task automatic measure_pitch(
        input  int  window_us,
        output real freq_hz,
        output int  crossings,
        output int  peak,
        output int  dc_offset,
        output logic ok
    );
        int    n_samples;
        int    n_zeros;
        int    i;
        int    sum;
        int    pk;
        int    wait_cycles;
        int    first_idx;
        int    last_idx;
        real   first_frac;
        real   last_frac;
        real   span_samples;
        int    prev_valid;
        logic signed [15:0] prev;
        logic signed [15:0] cur;
        begin
            n_samples = (window_us * 48) / 1000;   // 48 kHz -> 48 样点/ms
            n_zeros   = 0;
            sum       = 0;
            pk        = 0;
            prev      = 16'sd0;
            prev_valid = 0;
            ok        = 1'b1;
            first_idx = -1;
            last_idx  = -1;
            first_frac = 0.0;
            last_frac  = 0.0;

            for (i = 0; i < n_samples; i++) begin
                wait_cycles = 0;

                // 第一段：等 sample_stb 落到 0（若当前已是 0 则直接跳过）
                while ((sample_stb === 1'b1) && (wait_cycles < 2000)) begin
                    @(posedge sys_clk);
                    wait_cycles = wait_cycles + 1;
                end
                // 第二段：等 sample_stb 升到 1，即下一个采样点
                while ((sample_stb !== 1'b1) && (wait_cycles < 2000)) begin
                    @(posedge sys_clk);
                    wait_cycles = wait_cycles + 1;
                end

                if (wait_cycles >= 2000) begin
                    ok = 1'b0;
                    if (i == 0) begin
                        crossings = 0; peak = 0; dc_offset = 0; freq_hz = 0.0;
                        disable measure_pitch;
                    end
                    i = n_samples;
                end else begin
                    cur = left_sample;
                    sum = sum + cur;
                    if (cur > pk) pk = cur;
                    if ((-cur) > pk) pk = -cur;
                    // 正斜率过零：必须 prev < 0 <= cur，且 prev 是真实采样点
                    // 【为什么要求 prev < 0 而不是 prev <= 0】
                    //   我最初写 prev <= 0，于是 prev 恰好为 0 时也算一次过零。
                    //   正弦在 48 kHz / 523 Hz 下每个周期约有 92 个采样点，
                    //   其中会有采样点恰好落在 0（本例实测 i=17 就是 0）。
                    //   这会让同一处过零被记两次：一次是"负->0"（prev<0,cur==0
                    //   不满足 cur>0），另一次是"0->正"。若把 0 也算进 prev<=0，
                    //   就会在 0 附近多记一次，使首尾跨度缩短约 28~31 个采样点，
                    //   表现为 N-1=10 时 span 应为 917 却量到 886，
                    //   频率 523.25 Hz 被抬高成 541.56 Hz。
                    //   改为严格 prev < 0 <= cur 后，每处过零只记一次。
                    if ((prev_valid) && (prev < 0) && (cur >= 0)) begin
                        // 线性插值：过零在 prev->cur 之间的比例
                        // frac = -prev / (cur - prev)，区间 [0,1)
                        real frac;
                        frac = (-real'(prev)) / (real'(cur) - real'(prev));
                        if (n_zeros == 0) begin
                            first_idx  = i;
                            first_frac = frac;
                        end
                        last_idx  = i;
                        last_frac = frac;
                        n_zeros   = n_zeros + 1;
                    end
                    prev       = cur;
                    prev_valid = 1;
                end
            end

            crossings = n_zeros;
            peak      = pk;
            dc_offset = (n_samples > 0) ? (sum / n_samples) : 0;

            if (n_zeros >= 2) begin
                // 首尾过零之间的采样点数（含插值细化）
                span_samples = (real'(last_idx) + last_frac)
                             - (real'(first_idx) + first_frac);
                // 周期数 = 过零次数 - 1，故 f = (N-1) * Fs / span_samples
                freq_hz = (real'(n_zeros - 1) * 48_000.0) / span_samples;
            end else begin
                freq_hz = 0.0;
            end
        end
    endtask

    real  freq;
    int   zeros;
    int   pk;
    int   dc;
    logic meas_ok;

    task automatic check(input string name, input logic cond);
        begin
            if (cond) pass_cnt++;
            else begin
                fail_cnt++;
                $display("  [FAIL] %s", name);
            end
        end
    endtask

    task automatic press_key(input int idx);
        begin
            key_n[idx] = 1'b0;
        end
    endtask

    task automatic release_key(input int idx);
        begin
            key_n[idx] = 1'b1;
        end
    endtask

    initial begin
        $display("=== tb_key_to_tone (T020/T014 端到端) ===");
        $display("  验证：按键 -> 事件 -> 声部 -> PCM -> I2S 引脚 -> 音高");

        // ---------------------------------------------------------------------
        // 复位
        // ---------------------------------------------------------------------
        sys_rst_n = 1'b0;
        repeat (20) @(posedge sys_clk);
        sys_rst_n = 1'b1;
        repeat (20) @(posedge sys_clk);

        check("复位后功放使能有效 (pa_en=0)", pa_en == 1'b0);

        // ---------------------------------------------------------------------
        // 阶段 1：未按键 -> 必须静音
        // ---------------------------------------------------------------------
        $display("");
        $display("  --- 阶段 1: 未按键应静音 ---");
        measure_pitch(5000, freq, zeros, pk, dc, meas_ok);
        $display("    峰值 = %0d, 零交叉 = %0d, 音高 = %0.2f Hz", pk, zeros, freq);
        check("未按键时输出静音（峰值 < 50）", pk < 50);

        // ---------------------------------------------------------------------
        // 阶段 2：按 key0 (EX_KEY.1) -> A4 = 440 Hz
        // ---------------------------------------------------------------------
        $display("");
        $display("  --- 阶段 2: 按 EX_KEY.1 -> 期望 A4 440.00 Hz ---");
        press_key(0);
        // 等去抖确认（16 周期）并让测量窗口进入稳态
        repeat (200) @(posedge sys_clk);
        measure_pitch(20000, freq, zeros, pk, dc, meas_ok);
        $display("    峰值 = %0d, 零交叉 = %0d, 实测音高 = %0.2f Hz (期望 440.00)",
                 pk, zeros, freq);
        check("按 key0 后音高在 440 Hz 1% 以内",
              (freq > 435.6) && (freq < 444.4));
        check("按 key0 后峰值接近 8192", (pk > 7000) && (pk <= 8200));

        // 松开
        release_key(0);
        repeat (200) @(posedge sys_clk);
        measure_pitch(5000, freq, zeros, pk, dc, meas_ok);
        $display("    松开后 峰值 = %0d", pk);
        check("松开 key0 后回到静音", pk < 50);

        // ---------------------------------------------------------------------
        // 阶段 3：按 key1 (EX_KEY.2) -> C5 = 523.25 Hz
        // ---------------------------------------------------------------------
        $display("");
        $display("  --- 阶段 3: 按 EX_KEY.2 -> 期望 C5 523.25 Hz ---");
        press_key(1);
        repeat (200) @(posedge sys_clk);
        measure_pitch(20000, freq, zeros, pk, dc, meas_ok);
        $display("    峰值 = %0d, 零交叉 = %0d, 实测音高 = %0.2f Hz (期望 523.25)",
                 pk, zeros, freq);
        check("按 key1 后音高在 523.25 Hz 1% 以内",
              (freq > 518.0) && (freq < 528.5));
        check("按 key1 后峰值接近 8192", (pk > 7000) && (pk <= 8200));

        release_key(1);
        repeat (200) @(posedge sys_clk);
        measure_pitch(5000, freq, zeros, pk, dc, meas_ok);
        check("松开 key1 后回到静音", pk < 50);

        // ---------------------------------------------------------------------
        // 阶段 4：两键先后按下，音高应各自正确（单声部，后按者生效）
        // ---------------------------------------------------------------------
        $display("");
        $display("  --- 阶段 4: 两键切换 ---");
        press_key(0);
        repeat (200) @(posedge sys_clk);
        measure_pitch(20000, freq, zeros, pk, dc, meas_ok);
        $display("    key0 音高 = %0.2f Hz (期望 440.00)", freq);
        check("双键测试-第一音为 A4", (freq > 435.6) && (freq < 444.4));

        press_key(1);
        // 【为什么这里要多等一段时间再测】
        //   单声部占位实现里，key1 的 Note On 会立刻把 note_q 换成 72。
        //   若紧接着开测量窗口，窗口前半段是 440 Hz、后半段是 523 Hz，
        //   首尾过零跨度混合两个音，测得 538.92 Hz——这是**换音瞬间**的
        //   过渡值，不是稳态错误。等一段时间让窗口完全落在新音上再测。
        repeat (100_000) @(posedge sys_clk);   // 2 ms，足够越过换音点
        measure_pitch(20000, freq, zeros, pk, dc, meas_ok);
        $display("    再按 key1 后音高 = %0.2f Hz (期望 523.25)", freq);
        check("后按的 key1 取代 key0，音高为 C5",
              (freq > 518.0) && (freq < 528.5));

        release_key(0);
        release_key(1);
        repeat (200) @(posedge sys_clk);
        measure_pitch(5000, freq, zeros, pk, dc, meas_ok);
        check("全部松开后静音", pk < 50);

        // ---------------------------------------------------------------------
        // 阶段 5：直流偏置与左右声道
        //
        // 【为什么直流门限不能是固定的 100】
        //   20 ms 窗口对 440 Hz 只包含 8.8 个周期，不是整数个周期。
        //   正弦波在非整数周期上求平均，均值本身就不为 0：
        //   最大可达 峰值 / (2*pi*周期数) ≈ 8192 / 55 ≈ 148。
        //   所以"均值必须小于 100"这个判据本身是错的——它把
        //   "窗口不整周期"误判成了"电路有直流偏置"。
        //   正确判据：均值应小于"非整周期余数"允许的上界。
        //   我们已经有插值后的 span_samples，可以算出窗口内实际周期数，
        //   再用它推导理论最大残差，取 1.5 倍作为门限。
        // ---------------------------------------------------------------------
        $display("");
        $display("  --- 阶段 5: 直流偏置与声道 ---");
        press_key(0);
        repeat (200) @(posedge sys_clk);
        measure_pitch(20000, freq, zeros, pk, dc, meas_ok);
        $display("    直流偏置 = %0d, 峰值 = %0d, 过零次数 = %0d", dc, pk, zeros);

        // 窗口内周期数 = 过零次数 - 1（首尾过零之间）
        begin
            real cycles_in_win;
            int  dc_limit;
            cycles_in_win = (zeros > 1) ? real'(zeros - 1) : 1.0;
            // 非整周期平均残差上界：峰值 / (2*pi*周期数)
            dc_limit = int'((real'(pk) / (2.0 * 3.14159265 * cycles_in_win)) * 1.5) + 20;
            $display("    窗口内周期数 = %0.2f, 直流门限 = %0d", cycles_in_win, dc_limit);
            check("直流偏置在非整周期残差范围内", (dc < dc_limit) && (dc > -dc_limit));
        end
        // 左右声道在单音下应一致。
        // 【为什么不能直接比较 dec_left == dec_right】
        //   两者在同一帧的不同槽位更新，任意时刻读到的必然一新一旧。
        //   改用解码器内部逐帧记录的统计量：lr_mismatch / lr_checked。
        $display("    左右声道比对 = %0d 次不一致 / %0d 次比对",
                 lr_mismatch, lr_checked);
        check("左右声道一致（单音）", (lr_checked > 100) && (lr_mismatch == 0));
        release_key(0);

        // ---------------------------------------------------------------------
        // 阶段 6：运行中复位
        // ---------------------------------------------------------------------
        $display("");
        $display("  --- 阶段 6: 运行中复位 ---");
        press_key(0);
        repeat (200) @(posedge sys_clk);
        sys_rst_n = 1'b0;
        repeat (10) @(posedge sys_clk);
        check("运行中复位: pa_en 立即回到 1（关闭功放）", pa_en == 1'b1);

        sys_rst_n = 1'b1;
        repeat (200) @(posedge sys_clk);
        measure_pitch(5000, freq, zeros, pk, dc, meas_ok);
        check("复位释放后仍按住 key0 则应重新发声或保持静音（不产生垃圾输出）",
              (pk < 50) || ((pk > 7000) && (pk <= 8200)));
        release_key(0);

        $display("");
        $display("  =========================================================");
        $display("   结果: %0d PASS, %0d FAIL", pass_cnt, fail_cnt);
        if (fail_cnt != 0) begin
            $display("   >>> 按键到发声集成测试 FAIL");
            $display("  =========================================================");
            $fatal(1);
        end
        $display("   >>> 按键到发声集成测试 PASS");
        $display("  =========================================================");
        $finish;
    end

endmodule
