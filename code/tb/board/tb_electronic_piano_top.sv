// -----------------------------------------------------------------------------
// tb_electronic_piano_top.sv
// 顶层自检 testbench。对应任务 T007。
//
// 验证目标（逐项对应验收条件）：
//   1. 复位期间 pa_en 必须为 1（功放关闭）—— 上电爆音防护，最关键的一条；
//   2. 复位释放后 pa_en 必须变为 0（功放开启），否则没声音；
//   3. BCLK 频率正确（3.072 MHz），且 LRCK 与 BCLK 严格 64:1；
//   4. LRCK 频率为 48 kHz；
//   5. DIN 能解出正弦波，频率约 440 Hz、幅度约 8192；
//   6. 左右两声道数据一致（本工程为单音）；
//   7. uart_tx 空闲电平为高。
//
// 方法：在 testbench 内实现一个**独立的 LSBJ 解码器**，
//       不引用 DUT 内部信号，只从引脚上采样，
//       因此它同时验证了 i2s_tx 的相位约定。
//       解码逻辑与 tb_i2s_tx.sv 中的一致，但这里是从顶层引脚观察，
//       覆盖的是"顶层到引脚"这一段。
//
// 注意：本 testbench 只验证 RTL 行为，不能替代上板实测。
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_electronic_piano_top;

    // -------------------------------------------------------------------------
    // 时钟与复位
    // -------------------------------------------------------------------------
    localparam real CLK_PERIOD_NS = 20.0;   // 50 MHz

    logic sys_clk = 1'b0;
    logic sys_rst_n = 1'b0;

    // 全设计 50 MHz 时钟
    always #(CLK_PERIOD_NS/2.0) sys_clk = ~sys_clk;

    // -------------------------------------------------------------------------
    // DUT 端口
    // -------------------------------------------------------------------------
    logic i2s_bclk;
    logic i2s_lrck;
    logic i2s_din;
    logic pa_en;
    logic uart_tx;

    // T020: user keys, active low (pressed = 0). Idle high.
    //
    // The board has internal pull-ups only when the CST sets PULL_MODE=UP;
    // in simulation nothing drives them, so the testbench must hold them high.
    logic [1:0] key_n = 2'b11;

    // -------------------------------------------------------------------------
    // 测试参数
    //   实际频率断言需要足够长的观察窗。
    //   测 LRCK 频率：观察 N 个 LRCK 周期，误差应小于 1 个 sys_clk 周期。
    //   LRCK 周期 20833.33 ns，取 20 个周期约 416.7 us。
    // -------------------------------------------------------------------------
    localparam int  LRCK_MEAS_FRAMES = 20;
    localparam real EXPECT_BCLK_HZ   = 3_072_000.0;
    localparam real EXPECT_LRCK_HZ   = 48_000.0;
    localparam real EXPECT_TONE_HZ   = 440.0;

    // 频率容差：相位累加引入的误差在 ppm 级，这里放宽到 0.1% 以容纳
    // 测量窗口的量化误差（边界上可能差一个 sys_clk 周期）。
    localparam real FREQ_TOL_RATIO = 0.001;

    // 幅度容差：正弦表量化 + LSBJ 16 位截断，允许 2 个 LSB 的偏差。
    localparam int  AMP_TOL = 2;

    // -------------------------------------------------------------------------
    // 记分板
    // -------------------------------------------------------------------------
    int pass_count = 0;
    int fail_count = 0;

    task automatic check(input string name, input logic cond);
        if (cond) begin
            pass_count++;
            $display("  [PASS] %s", name);
        end else begin
            fail_count++;
            $display("  [FAIL] %s", name);
        end
    endtask

    task automatic check_eq_int(input string name, input int got, input int exp);
        if (got === exp) begin
            pass_count++;
            $display("  [PASS] %s (= %0d)", name, got);
        end else begin
            fail_count++;
            $display("  [FAIL] %s: got %0d, expected %0d", name, got, exp);
        end
    endtask

    // -------------------------------------------------------------------------
    // 例化 DUT
    // -------------------------------------------------------------------------
    electronic_piano_top #(
        .CLK_HZ        (50_000_000),
        .TEST_TONE_HZ  (440),
        .SINE_DEPTH    (256),
        .TEST_AMPLITUDE(16'sd8192),
        // T020: 0 = key-driven skeleton, 1 = T007 fixed tone.
        // This testbench validates the fixed-tone path (the one proven on
        // hardware in V0035) plus the new key path's event plumbing.
        // SOURCE_MODE=1 keeps the original assertions valid.
        .SOURCE_MODE   (1),
        // Shorten debounce so the simulation does not need 10 ms per press.
        // DEBOUNCE_CLK_HZ=16000 makes 1 ms equal 16 cycles, so DEBOUNCE_CNT=16
        // still maps to exactly 16 x 50 MHz clocks.
        .DEBOUNCE_CNT  (16),
        .DEBOUNCE_CLK_HZ (16_000)
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
    // 独立 LSBJ 解码器
    //
    // 只观察引脚，不引用 DUT 内部信号。
    //   - 在 BCLK 上升沿采样 DIN（PT8211 在 BCK 上升沿锁存数据）；
    //   - 每 32 个 BCLK 切换声道，LRCK 低=左、高=右；
    //   - 每声道的 32 位槽位中，低 16 位为有效数据（LSBJ）。
    //
    // 注意：DUT 中 BCLK 在 sys_clk 下降沿更新、DIN 在上升沿更新，
    // 因此 BCLK 上升沿采样 DIN 时数据已稳定。
    // =========================================================================
    localparam int SLOT_BITS = 32;

    int  bclk_cnt = 0;              // 帧内 BCLK 计数 0..63
    logic [SLOT_BITS-1:0] slot_shreg = '0;
    logic dec_left_valid  = 1'b0;
    logic dec_right_valid = 1'b0;
    logic signed [15:0] dec_left  = '0;
    logic signed [15:0] dec_right = '0;

    // 收集到的样本，用于统计频率与幅度
    localparam int MAX_SAMPLES = 4096;
    int  left_samples [0:MAX_SAMPLES-1];
    int  left_count = 0;
    int  mismatch_lr = 0;           // 左右声道不一致的次数

    always @(posedge i2s_bclk) begin
        // 移位：新位进低位，与 DUT 的 LSBJ 约定一致
        // 槽位内先移出 MSB，最后移出 LSB，因此 LSB 落在最低位。
        slot_shreg = {slot_shreg[SLOT_BITS-2:0], i2s_din};

        if (bclk_cnt == SLOT_BITS-1) begin
            // 槽位结束，取低 16 位为有效数据
            if (i2s_lrck == 1'b0) begin
                dec_left        = slot_shreg[15:0];
                dec_left_valid  = 1'b1;
                if (left_count < MAX_SAMPLES) begin
                    left_samples[left_count] = $signed(slot_shreg[15:0]);
                    left_count++;
                end
            end else begin
                dec_right       = slot_shreg[15:0];
                dec_right_valid = 1'b1;
                if (dec_left_valid && (dec_right !== dec_left)) mismatch_lr++;
            end
            bclk_cnt = 0;
        end else begin
            bclk_cnt = bclk_cnt + 1;
        end
    end

    // =========================================================================
    // 测试流程
    // =========================================================================
    int  bclk_edges;
    real bclk_hz;
    real lrck_hz;
    real meas_bclk_hz;
    real meas_lrck_hz;
    int  lrck_rises;
    time t_lrck_start, t_lrck_end;

    int  i;
    int  s_max, s_min, s_peak;
    int  zero_crossings;
    int  prev_sign, cur_sign;
    real tone_hz;

    initial begin
        $display("=========================================================");
        $display(" tb_electronic_piano_top : 顶层自检");
        $display(" 板卡: Tang Mega 60K 30354 + NEO Dock 31005");
        $display(" 时钟: 50 MHz, 测试音: 440 Hz, 幅度: 8192");
        $display("=========================================================");

        // ---------------------------------------------------------------------
        // 阶段 1：复位期间
        //
        // 这是最关键的一条。复位尚未释放时，pa_en 必须已经是 1。
        // 注意此处 sys_rst_n 仍为 0，时钟已在跑。
        // ---------------------------------------------------------------------
        $display("");
        $display("--- 阶段 1: 复位期间（sys_rst_n = 0）---");

        repeat (10) @(posedge sys_clk);
        check("pa_en = 1 (功放关闭) 于复位期间", pa_en === 1'b1);
        check("uart_tx = 1 (UART 空闲电平)",    uart_tx === 1'b1);

        // ---------------------------------------------------------------------
        // 阶段 2：复位释放
        // ---------------------------------------------------------------------
        $display("");
        $display("--- 阶段 2: 复位释放 ---");

        @(negedge sys_clk);
        sys_rst_n = 1'b1;

        // reset_sync 有 2 级同步，2 个时钟后 rst_sync_n 变高
        repeat (4) @(posedge sys_clk);
        check("pa_en = 0 (功放开启) 于复位释放后", pa_en === 1'b0);

        // 等 I2S 开始输出
        repeat (10) @(posedge sys_clk);

        // ---------------------------------------------------------------------
        // 阶段 3：BCLK / LRCK 频率
        //
        // 用长窗口计数测平均频率，避免单周期测量受相位累加抖动影响。
        // 同时测 BCLK 边沿数与 LRCK 上升沿数，验证 64:1 关系。
        // ---------------------------------------------------------------------
        $display("");
        $display("--- 阶段 3: 时钟频率 ---");

        bclk_edges  = 0;
        lrck_rises  = 0;

        // 等待一个 LRCK 上升沿对齐测量窗口起点
        @(posedge i2s_lrck);
        t_lrck_start = $time;

        // 监视 20 个 LRCK 周期
        fork
            begin : meas_bclk
                // 数 BCLK 上升沿
                while (1) begin
                    @(posedge i2s_bclk);
                    bclk_edges++;
                    if (bclk_edges > 100000) disable meas_bclk;
                end
            end
            begin : meas_lrck
                repeat (LRCK_MEAS_FRAMES) @(posedge i2s_lrck);
                t_lrck_end = $time;
                disable meas_bclk;
            end
        join

        // 在 t_lrck_end 时刻，bclk_edges 是这段时间内的 BCLK 上升沿数，
        // 可能多计一个（fork 竞态），故允许 +-1 的误差。
        meas_lrck_hz = (LRCK_MEAS_FRAMES * 1.0e9) / real'(t_lrck_end - t_lrck_start);
        meas_bclk_hz = (bclk_edges * 1.0e9) / real'(t_lrck_end - t_lrck_start);

        $display("  测量窗口: %0t ns, BCLK 上升沿 %0d 个", 
                 t_lrck_end - t_lrck_start, bclk_edges);
        $display("  实测 LRCK = %0.2f Hz (期望 %0.1f)", meas_lrck_hz, EXPECT_LRCK_HZ);
        $display("  实测 BCLK = %0.2f Hz (期望 %0.1f)", meas_bclk_hz, EXPECT_BCLK_HZ);

        check("LRCK 频率在 0.1% 以内",
              (meas_lrck_hz > EXPECT_LRCK_HZ*(1.0-FREQ_TOL_RATIO)) &&
              (meas_lrck_hz < EXPECT_LRCK_HZ*(1.0+FREQ_TOL_RATIO)));

        check("BCLK 频率在 0.1% 以内",
              (meas_bclk_hz > EXPECT_BCLK_HZ*(1.0-FREQ_TOL_RATIO)) &&
              (meas_bclk_hz < EXPECT_BCLK_HZ*(1.0+FREQ_TOL_RATIO)));

        // 64:1 关系：窗口内 BCLK 上升沿数应为 20*64 = 1280 (+-1)
        check("BCLK:LRCK = 64:1 (上升沿数 1280 +-1)",
              (bclk_edges >= LRCK_MEAS_FRAMES*64 - 1) &&
              (bclk_edges <= LRCK_MEAS_FRAMES*64 + 1));

        // ---------------------------------------------------------------------
        // 阶段 4：解码正弦波，验证频率与幅度
        //
        // 重新采集一批样本（前面的解码器一直在跑，这里清空重来）。
        // ---------------------------------------------------------------------
        $display("");
        $display("--- 阶段 4: DIN 解码（LSBJ）---");

        left_count = 0;
        @(posedge i2s_lrck);    // 对齐到帧边界
        // 采满 1024 个左声道样本：48 kHz 下约 21.3 ms，
        // 覆盖约 9.4 个 440 Hz 周期，零交叉统计精度足够
        // （9 个整周期 -> 频率量化误差约 1/9 = 11%，
        //   但零交叉计数误差只有 +-1 次，折算约 +-4 Hz，满足 1% 判据）。
        while (left_count < 1024) @(posedge i2s_lrck);

        check("采集到足够的样本", left_count >= 1024);

        // 幅度：最大值、最小值、峰峰值
        s_max = -32768;
        s_min =  32767;
        for (i = 0; i < left_count; i++) begin
            if (left_samples[i] > s_max) s_max = left_samples[i];
            if (left_samples[i] < s_min) s_min = left_samples[i];
        end
        s_peak = (s_max - s_min) / 2;

        $display("  样本数 %0d, 最大 %0d, 最小 %0d, 峰值 %0d (期望 %0d)",
                 left_count, s_max, s_min, s_peak, 8192);

        // 峰值应为 8192。由于正弦表 256 点采样，只有在恰好采到峰值点
        // 时才是 8192；440 Hz 与 48 kHz 不是整数比，实际峰值会略低。
        // 256 点表的最大值在同一量级，允许 5% 的偏差。
        check("输出峰值接近 8192 (5% 容差)",
              (s_peak > 8192*95/100) && (s_peak <= 8192));

        // 直流偏置：正弦波在**整数个周期**上的均值应为 0。
        //
        // 【为什么不能直接对 1024 个样点求均值】
        //   1024 个样点 = 21.33 ms，而 440 Hz 的周期是 2.273 ms，
        //   1024 个样点覆盖 9.39 个周期 —— 不是整数。
        //   截断的那 0.39 个周期贡献了一个非零的直流分量（实测均值 189），
        //   这是**测量窗口不整周期**造成的，不是 DUT 有直流偏置。
        //   正负半周各截一段，剩余部分不对称，均值自然不为 0。
        //
        //   正确做法是只取整数个周期。440 Hz、48 kHz 下，
        //   1 个周期 = 48000/440 = 109.09 个样点，取 109 个样点即
        //   近似整数周期（误差 0.08%），用 8 个周期 = 872 个样点，
        //   残余直流降到 1/8 以下。
        begin
            longint sum;
            int     win;
            win = (8 * 48000) / 440;      // 8 个周期对应的样点数 = 872
            if (win > left_count) win = left_count;
            sum = 0;
            for (i = 0; i < win; i++) sum += left_samples[i];
            $display("  直流偏置 = %0d (整数周期窗口 %0d 样点)", sum / win, win);
            check("直流偏置接近 0 (|均值| < 100)",
                  (sum / win < 100) && (sum / win > -100));
        end

        // 频率：用过零点的**线性插值**位置计算，而不是直接数过零次数。
        //
        // 【为什么不能只数次数】
        //   零交叉计数是整数，1024 样点覆盖 9.39 个周期时理想计数是
        //   18.8 次，取整到 19 次就相当于把频率抬高到 445.3 Hz（+1.2%），
        //   误差全部来自端点取整，与 DUT 无关。
        //   改为插值定位第一个和最后一个过零点的**亚样点位置**，
        //   两者之差就是整数个半周期，端点误差从 1 个样点降到远小于 1 个。
        zero_crossings = 0;
        begin
            real first_x, last_x, half_periods;
            real prev_v, cur_v;
            logic found_first;
            first_x = 0.0; last_x = 0.0; found_first = 1'b0;

            prev_v = real'(left_samples[0]);
            for (i = 1; i < left_count; i++) begin
                cur_v = real'(left_samples[i]);
                // 过零点（含穿过 0 的情况）：符号变化即认为跨越
                if ((prev_v < 0.0 && cur_v >= 0.0) ||
                    (prev_v >= 0.0 && cur_v < 0.0)) begin
                    zero_crossings++;
                    // 线性插值求过零时刻（以样点为单位，i-1 到 i 之间）
                    if (cur_v != prev_v) begin
                        real x;
                        x = real'(i - 1) + (-prev_v) / (cur_v - prev_v);
                        if (!found_first) begin
                            first_x = x;
                            found_first = 1'b1;
                        end
                        last_x = x;
                    end
                end
                prev_v = cur_v;
            end

            if (found_first && zero_crossings >= 2) begin
                // first_x 与 last_x 之间有 (zero_crossings-1) 个半周期
                half_periods = real'(zero_crossings - 1);
                tone_hz = (half_periods / 2.0) * EXPECT_LRCK_HZ
                          / (last_x - first_x);
            end else begin
                tone_hz = 0.0;
            end
        end

        $display("  零交叉 %0d 次, 实测音高 = %0.4f Hz (期望 %0.1f)",
                 zero_crossings, tone_hz, EXPECT_TONE_HZ);

        // 插值法端点误差远小于 1 个样点，此处仍留 1% 容差，
        // 主要容纳 256 点正弦表的相位量化（1/256 = 0.39%）。
        check("音高在 1% 以内",
              (tone_hz > EXPECT_TONE_HZ*0.99) && (tone_hz < EXPECT_TONE_HZ*1.01));

        // ---------------------------------------------------------------------
        // 阶段 5：左右声道一致性
        // ---------------------------------------------------------------------
        $display("");
        $display("--- 阶段 5: 左右声道 ---");

        $display("  左右不一致次数 = %0d", mismatch_lr);
        check("左右声道数据一致（单音）", mismatch_lr == 0);

        // ---------------------------------------------------------------------
        // 阶段 6：复位再次拉低，pa_en 应立即回到 1
        // ---------------------------------------------------------------------
        $display("");
        $display("--- 阶段 6: 运行中复位 ---");

        @(negedge sys_clk);
        sys_rst_n = 1'b0;
        repeat (4) @(posedge sys_clk);
        check("pa_en 立即回到 1 (运行中复位)", pa_en === 1'b1);

        // ---------------------------------------------------------------------
        // 汇总
        // ---------------------------------------------------------------------
        $display("");
        $display("=========================================================");
        $display(" 结果: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) begin
            $display(" >>> 顶层自检 PASS");
            $display("=========================================================");
            $finish;
        end else begin
            $display(" >>> 顶层自检 FAIL");
            $display("=========================================================");
            $fatal(1, "顶层自检失败: %0d 项未通过", fail_count);
        end
    end

    // 超时保护。
    //
    // 【曾经的值是 2 ms，那是错的，记录以免重犯】
    // 注释写"正常情况下整个测试在 1 ms 内完成"，但阶段 4 自己要采集
    // 2048 个 48 kHz 样本 —— 仅这一步就需要 2048 / 48000 = 42.7 ms，
    // 再加阶段 3 的 416 us 测量窗，整个测试至少 43 ms。
    // 两处注释自相矛盾，超时值取了小的那个，导致阶段 4 永远无法完成。
    // 现按实际最坏情况取值：阶段 3 的 20 帧 + 阶段 4 的 1024 样本
    // = 0.42 ms + 21.3 ms，留足余量到 60 ms。
    localparam int TIMEOUT_NS = 60_000_000;   // 60 ms

    initial begin
        #(TIMEOUT_NS);
        $display("");
        $display(" >>> 顶层自检 FAIL: 超时（%0d ms 未完成）", TIMEOUT_NS/1_000_000);
        $fatal(1, "testbench timeout");
    end

endmodule
