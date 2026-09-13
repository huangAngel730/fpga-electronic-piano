// -----------------------------------------------------------------------------
// tb_i2s_tx.sv
// i2s_tx 自检 testbench。对应任务 T005。
//
// 验证策略：
//   不"肉眼看波形"，而是写一个独立的 LSBJ 解码器，从 bclk/lrck/din 三个
//   引脚信号还原出 16 位样点，再与输入比对。解码器只依据接口规范 v1.1
//   第五节描述的时序写，不复用 DUT 的任何内部信号，因此能真正发现相位错误。
//
// 时序模型（重要）：
//   ACC_BITS=8、PHASE_STEP=1 -> 累加器每 2^ACC_BITS = 256 个 clk 进位一次，
//   每次进位使 bclk 翻转，故一个完整 BCLK 周期 = 512 clk。
//   一帧 = 64 BCLK = 32768 clk，半帧 = 16384 clk。
//   该数值由独立诊断 TB 实测确认，不是推导猜测。
//
// 采样同步（重要）：
//   本 TB 全部等待都基于「已解码帧计数」，不用固定延时去猜采样时刻。
//   流程固定为：设置输入 -> 等 N 帧解码完成 -> 读数。
//   解码器每完成一帧把 dec_frames 加一，因此这个等待是事件驱动的。
//
// 覆盖：复位、帧比例、LSBJ 相位、饱和边界、200 组随机样点、运行中复位。
//
// 运行：代码/scripts/run_t005_sim.ps1
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_i2s_tx;

    // -------------------------------------------------------------------------
    // 参数（与上面的时序模型说明保持一致）
    // -------------------------------------------------------------------------
    localparam int unsigned ACC_BITS  = 8;
    localparam logic [ACC_BITS-1:0] BCLK_PHASE_STEP = 8'd1;
    localparam int unsigned PCM_WIDTH = 24;
    localparam int unsigned DAC_WIDTH = 16;
    localparam int unsigned SHIFT     = PCM_WIDTH - DAC_WIDTH;

    // 相位累加器溢出所需 clk 数 = 2^ACC_BITS
    localparam int unsigned CLK_PER_BCLK_HALF = 1 << ACC_BITS;      // 256
    localparam int unsigned CLK_PER_BCLK      = CLK_PER_BCLK_HALF * 2;  // 512
    localparam int unsigned CLK_PER_FRAME     = CLK_PER_BCLK * 64;  // 32768

    localparam real CLK_PERIOD = 10.0;

    // 等待帧数：留足余量让输入经过 frame_start 采样并串出
    localparam int unsigned WAIT_FRAMES = 4;

    logic clk;
    logic rst_n;
    logic valid;
    logic signed [PCM_WIDTH-1:0] pcm_left;
    logic signed [PCM_WIDTH-1:0] pcm_right;
    logic bclk;
    logic lrck;
    logic din;
    logic ready;

    int error_count = 0;
    int check_count = 0;

    i2s_tx #(
        .ACC_BITS        (ACC_BITS),
        .BCLK_PHASE_STEP (BCLK_PHASE_STEP),
        .PCM_WIDTH       (PCM_WIDTH),
        .DAC_WIDTH       (DAC_WIDTH)
    ) dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .valid     (valid),
        .pcm_left  (pcm_left),
        .pcm_right (pcm_right),
        .bclk      (bclk),
        .lrck      (lrck),
        .din       (din),
        .ready     (ready)
    );

    initial clk = 1'b0;
    always #(CLK_PERIOD/2) clk = ~clk;

    task automatic check(input string name, input logic cond);
        check_count++;
        if (!cond) begin
            error_count++;
            $display("  [FAIL] %s", name);
        end else begin
            $display("  [PASS] %s", name);
        end
    endtask

    // =========================================================================
    // 参考模型：24 -> 16 位舍入与饱和
    //
    // 用 64 位整数独立实现，写法与 RTL 完全不同，便于发现 RTL 错误。
    // =========================================================================
    function automatic logic [15:0] ref_round_sat(input int signed src);
        int signed biased;
        int signed result;
        begin
            biased = src + (1 << (SHIFT-1));   // 加半个 LSB
            result = biased >>> SHIFT;         // 算术右移
            if (result >  32767) result =  32767;
            if (result < -32768) result = -32768;
            ref_round_sat = result[15:0];
        end
    endfunction

    // =========================================================================
    // LSBJ 解码器
    //
    // 依据接口规范 v1.1：每声道 16 位有效数据右对齐，LSB 紧贴 LRCK 跳变沿。
    //
    // 在 BCLK 上升沿采样 DIN，按帧内边沿序号确定位序：
    //   edge  0..31 -> 左声道槽位（LRCK 低），slot 低 16 位为有效数据
    //   edge 32..63 -> 右声道槽位（LRCK 高），slot 低 16 位为有效数据
    // 与 DUT 内部实现完全独立，不复用任何内部信号。
    // =========================================================================
    int unsigned dec_edge   = 0;
    int unsigned dec_frames = 0;
    logic [31:0] dec_slot   = '0;
    logic [15:0] dec_left   = '0;
    logic [15:0] dec_right  = '0;

    always @(posedge bclk) begin
        if (rst_n) begin
            if (dec_edge == 0) dec_slot = '0;
            dec_slot = {dec_slot[30:0], din};

            if (dec_edge == 31) begin
                dec_left = dec_slot[15:0];
            end else if (dec_edge == 63) begin
                dec_right  = dec_slot[15:0];
                dec_frames = dec_frames + 1;
            end

            if (dec_edge == 63) dec_edge = 0;
            else                dec_edge = dec_edge + 1;
        end
    end

    // =========================================================================
    // 等待 n 帧解码完成。以 dec_frames 为基准，事件驱动而非固定延时。
    // =========================================================================
    task automatic wait_frames(input int unsigned n);
        int unsigned target;
        begin
            target = dec_frames + n;
            while (dec_frames < target) @(posedge clk);
        end
    endtask

    // =========================================================================
    // 发送一组样点并取回解码结果。
    // 先设输入、等若干帧，再读数，确保读到的就是当前输入对应的帧。
    // =========================================================================
    task automatic send_and_read(input logic signed [PCM_WIDTH-1:0] l_in,
                                 input logic signed [PCM_WIDTH-1:0] r_in,
                                 output logic [15:0] l_out,
                                 output logic [15:0] r_out);
        begin
            pcm_left  = l_in;
            pcm_right = r_in;
            wait_frames(WAIT_FRAMES);
            l_out = dec_left;
            r_out = dec_right;
        end
    endtask

    logic [15:0] cap_left, cap_right;

    initial begin
        $display("=== tb_i2s_tx 开始 ===");
        $display("参数：ACC_BITS=%0d PHASE_STEP=%0d PCM=%0d DAC=%0d SHIFT=%0d",
                 ACC_BITS, BCLK_PHASE_STEP, PCM_WIDTH, DAC_WIDTH, SHIFT);
        $display("时序：CLK_PER_BCLK=%0d CLK_PER_FRAME=%0d",
                 CLK_PER_BCLK, CLK_PER_FRAME);

        // ---------------------------------------------------------------------
        $display("\n[1] 复位期间输出必须为确定值");
        // ---------------------------------------------------------------------
        rst_n     = 1'b0;
        valid     = 1'b0;
        pcm_left  = '0;
        pcm_right = '0;
        #(CLK_PERIOD * 50);
        check("复位期间 bclk=0",  bclk === 1'b0);
        check("复位期间 lrck=0",  lrck === 1'b0);
        check("复位期间 din=0",   din  === 1'b0);
        check("ready 始终为 1",   ready === 1'b1);

        // ---------------------------------------------------------------------
        $display("\n[2] 释放后 BCLK 翻转，LRCK 与 BCLK 保持 64:1");
        // ---------------------------------------------------------------------
        rst_n = 1'b1;
        begin
            int unsigned bclk_tog = 0;
            int unsigned lrck_tog = 0;
            logic bclk_p, lrck_p;
            // 以解码器帧计数对齐，避免从帧中间开始计数导致差 1。
            // 先等到一个新帧的起点，再统计接下来的 8 帧。
            wait_frames(1);
            bclk_p = bclk; lrck_p = lrck;
            begin
                int unsigned f0;
                f0 = dec_frames;
                while (dec_frames < f0 + 8) begin
                    @(posedge clk);
                    if (bclk !== bclk_p) begin bclk_tog++; bclk_p = bclk; end
                    if (lrck !== lrck_p) begin lrck_tog++; lrck_p = lrck; end
                end
            end
            // LRCK 的期望值：8 帧 = 8 个完整 LRCK 周期（一帧就是一个
            // LRCK 周期：前半帧左声道、后半帧右声道）。一个方波周期必然
            // 有 2 个边沿，因此 8 帧应有 2 x 8 = 16 次翻转。
            //
            // 【本断言曾经是错的，记录以免重犯】
            // 原期望写成 8（即假设「每帧翻转一次」），而 RTL 当时确实
            // 每帧翻转一次——但那是 bug：它把 LRCK 周期拉长到两帧，
            // 实测 LRCK 只有 24 kHz 而非 48 kHz。testbench 的错误期望
            // 反而把这个 bug 固化成「正确行为」，使 T005 一直 PASS。
            // 同期的 BCLK 断言（8*64*2）用的是「每周期 2 次翻转」的正确
            // 约定，两者自相矛盾却都没被发现。
            // 修复后 LRCK 直接跟随 right_ch，一帧内翻转一次，
            // 8 帧 16 次翻转。见 验证记录.md V0029。
            $display("  8 帧内 BCLK 翻转 %0d 次（期望 %0d），LRCK 翻转 %0d 次（期望 16）",
                     bclk_tog, 8*64*2, lrck_tog);
            check("BCLK 翻转次数对应 64 BCLK/帧", bclk_tog == 8*64*2);
            check("LRCK 翻转次数对应 8 帧（2 次/帧）", lrck_tog == 8*2);
        end

        // ---------------------------------------------------------------------
        $display("\n[3] LSBJ 相位：解码两个声道的样点并与输入比对");
        // ---------------------------------------------------------------------
        valid = 1'b1;
        // 左 0x123456 -> 期望 0x1234；右 -0x012345 -> 期望 0xFEDD
        send_and_read(24'sh123456, -24'sh012345, cap_left, cap_right);
        $display("  左 输入 0x%06X -> 解码 0x%04X，期望 0x%04X",
                 24'sh123456, cap_left, ref_round_sat(24'sh123456));
        $display("  右 输入 0x%06X -> 解码 0x%04X，期望 0x%04X",
                 -24'sh012345, cap_right, ref_round_sat(-24'sh012345));
        check("左声道解码值正确", cap_left  == ref_round_sat(24'sh123456));
        check("右声道解码值正确", cap_right == ref_round_sat(-24'sh012345));

        // 左右互换，确认没有声道串位
        send_and_read(-24'sh012345, 24'sh123456, cap_left, cap_right);
        check("交换输入后左声道跟随", cap_left  == ref_round_sat(-24'sh012345));
        check("交换输入后右声道跟随", cap_right == ref_round_sat(24'sh123456));

        // ---------------------------------------------------------------------
        $display("\n[4] 边界：满量程、舍入进位、零");
        // ---------------------------------------------------------------------
        begin
            logic [15:0] l, r;
            send_and_read(24'sh7FFFFF, 24'sh7FFFFF, l, r);
            $display("  +FS 解码 0x%04X，期望 0x7FFF", l);
            check("正满量程饱和到 0x7FFF", l == 16'h7FFF);

            send_and_read(-24'sh800000, -24'sh800000, l, r);
            $display("  -FS 解码 0x%04X，期望 0x8000", l);
            check("负满量程到 0x8000 不溢出", l == 16'h8000);

            // 正好在舍入进位边界：低位全 1 应向上进位
            send_and_read(24'sh0000FF, 24'sh0000FF, l, r);
            $display("  0x0000FF 解码 0x%04X，期望 0x0001", l);
            check("低位全 1 正确进位", l == 16'h0001);

            send_and_read('0, '0, l, r);
            check("零输入解码为 0", l == 16'h0000 && r == 16'h0000);
        end

        // ---------------------------------------------------------------------
        $display("\n[5] 逐样本一致性：200 组随机样点");
        // ---------------------------------------------------------------------
        begin
            int unsigned i;
            int unsigned errors = 0;
            logic [15:0] l, r;
            logic signed [PCM_WIDTH-1:0] li, ri;
            for (i = 0; i < 200; i++) begin
                li = $random();
                ri = $random();
                send_and_read(li, ri, l, r);
                if (l !== ref_round_sat(li) || r !== ref_round_sat(ri)) begin
                    errors++;
                    if (errors <= 3)
                        $display("  [MISMATCH] L 0x%06X -> 0x%04X 期望 0x%04X | R 0x%06X -> 0x%04X 期望 0x%04X",
                                 li, l, ref_round_sat(li),
                                 ri, r, ref_round_sat(ri));
                end
            end
            $display("  随机样点 200 组，失配 %0d 组", errors);
            check("200 组随机样点全部一致", errors == 0);
        end

        // ---------------------------------------------------------------------
        $display("\n[6] 异常场景：运行中复位");
        // ---------------------------------------------------------------------
        @(negedge clk);
        rst_n = 1'b0;
        #(CLK_PERIOD * 20);
        check("运行中复位后 bclk=0", bclk === 1'b0);
        check("运行中复位后 lrck=0", lrck === 1'b0);
        check("运行中复位后 din=0",  din  === 1'b0);

        @(negedge clk);
        rst_n = 1'b1;
        begin
            logic [15:0] l, r;
            send_and_read(24'sh0F0F0F, -24'sh0F0F0F, l, r);
            $display("  恢复后解码 0x%04X / 0x%04X，期望 0x%04X / 0x%04X",
                     l, r, ref_round_sat(24'sh0F0F0F), ref_round_sat(-24'sh0F0F0F));
            check("复位后可恢复正确发送",
                  l == ref_round_sat(24'sh0F0F0F) &&
                  r == ref_round_sat(-24'sh0F0F0F));
        end

        // ---------------------------------------------------------------------
        $display("\n=== 结果 ===");
        $display("检查项 %0d，失败 %0d", check_count, error_count);
        if (error_count == 0) $display("PASS");
        else                  $display("FAIL");
        $display("=== tb_i2s_tx 结束 ===");
        $finish;
    end

    // 超时看门狗：正常应远早于此。
    // 200 组随机样点每组等 4 帧，加上边界与复位用例，总帧数约 1000 帧，
    // 因此上限取 3000 帧留足余量。
    initial begin
        #(CLK_PERIOD * CLK_PER_FRAME * 3000);
        $display("FAIL: 仿真超时");
        $finish;
    end

endmodule
