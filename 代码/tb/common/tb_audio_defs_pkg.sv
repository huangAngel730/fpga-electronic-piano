// -----------------------------------------------------------------------------
// tb_audio_defs_pkg.sv
// audio_defs_pkg 自检 testbench。对应任务 T019。
//
// 验证包内的函数与常量，重点是 MIDI 到统一事件的映射函数，
// 这些函数的正确性直接影响接口规范 3.2 与 3.2.1 节的实现。
//
// 运行（iverilog）：
//   iverilog -g2012 -Wall -o tb_audio_defs_pkg.vvp \
//       代码/rtl/common/audio_defs_pkg.sv 代码/tb/common/tb_audio_defs_pkg.sv
//   vvp tb_audio_defs_pkg.vvp
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_audio_defs_pkg;

    import audio_defs_pkg::*;

    int error_count = 0;
    int check_count = 0;

    task automatic check_int(
        input string name,
        input longint actual,
        input longint expected
    );
        check_count++;
        if (actual !== expected) begin
            error_count++;
            $display("  [FAIL] %-46s actual=%0d expected=%0d", name, actual, expected);
        end else begin
            $display("  [PASS] %-46s = %0d", name, actual);
        end
    endtask

    // 有符号比较
    task automatic check_signed(
        input string name,
        input longint signed actual,
        input longint signed expected
    );
        check_count++;
        if (actual !== expected) begin
            error_count++;
            $display("  [FAIL] %-46s actual=%0d expected=%0d", name, actual, expected);
        end else begin
            $display("  [PASS] %-46s = %0d", name, actual);
        end
    endtask

    // 结构体总位宽
    logic [63:0] probe;
    performance_event_t ev;

    int unsigned fclk;
    logic [31:0] step;

    initial begin
        $display("=== tb_audio_defs_pkg 开始 ===");

        // ---------------------------------------------------------------------
        $display("\n[1] performance_event_t 位宽必须为 64");
        // ---------------------------------------------------------------------
        check_int("performance_event_t 位宽", $bits(performance_event_t), 64);

        // 各字段位宽
        check_int("event_type 位宽",    $bits(ev.event_type),    3);
        check_int("source_id 位宽",     $bits(ev.source_id),     4);
        check_int("channel 位宽",       $bits(ev.channel),       4);
        check_int("note_number 位宽",   $bits(ev.note_number),   7);
        check_int("velocity 位宽",      $bits(ev.velocity),      10);
        check_int("expression 位宽",    $bits(ev.expression),    10);
        check_int("control_id 位宽",    $bits(ev.control_id),    8);
        check_int("control_value 位宽", $bits(ev.control_value), 12);
        check_int("reserved 位宽",      $bits(ev.reserved),      6);

        // ---------------------------------------------------------------------
        $display("\n[2] 常量值（接口规范 2.3、3.3、3.2.1 节）");
        // ---------------------------------------------------------------------
        check_int("SAMPLE_RATE_HZ", SAMPLE_RATE_HZ, 48000);
        check_int("EVENT_FIFO_DEPTH", EVENT_FIFO_DEPTH, 32);
        check_int("EVENT_NOTE_ON",  EVENT_NOTE_ON,  0);
        check_int("EVENT_NOTE_OFF", EVENT_NOTE_OFF, 1);
        check_int("CTRL_PITCH_BEND", CTRL_PITCH_BEND, 0);
        check_int("CTRL_MODULATION", CTRL_MODULATION, 1);
        check_int("CTRL_VOICE_SELECT", CTRL_VOICE_SELECT, 5);

        // ---------------------------------------------------------------------
        $display("\n[3] tick_phase_step：返回 2^32 * FS / FCLK");
        // ---------------------------------------------------------------------
        // 注意函数语义：返回相位步进，不是分频比。
        //   step = 2^32 * 48000 / FCLK
        // 98.304 MHz: 2^32 * 48000 / 98304000 = 2097152 = 2^21
        // 当 step 为 2 的整数次幂时，累加器恰好每 2^(32-21)=2048 拍溢出一次，
        // 退化为整数分频，无抖动。
        step = tick_phase_step(98_304_000);
        check_int("98.304 MHz -> step", step, 32'd2097152);
        // 49.152 MHz: 2^32 * 48000 / 49152000 = 4194304 = 2^22，溢出周期 1024
        step = tick_phase_step(49_152_000);
        check_int("49.152 MHz -> step", step, 32'd4194304);
        // 24.576 MHz: 2^32 * 48000 / 24576000 = 8388608 = 2^23，溢出周期 512
        step = tick_phase_step(24_576_000);
        check_int("24.576 MHz -> step", step, 32'd8388608);

        // 验证 step 与分频比的关系：step 为 2 的幂时，溢出周期等于 FCLK/FS
        begin
            int unsigned div_ratio;
            div_ratio = 98_304_000 / SAMPLE_RATE_HZ;   // 2048
            check_int("98.304 MHz 分频比", div_ratio, 2048);
            // 溢出周期 = 2^32 / step。step = 2^21 时周期为 2^11 = 2048，
            // 与分频比一致，说明该频率下相位累加等价于整数分频。
            check_int("98.304 MHz 溢出周期",
                      32'd1 << (32 - $clog2(tick_phase_step(98_304_000))),
                      div_ratio);
        end

        // 非整除频率：检查长期平均频率误差
        $display("  -- 非整除频率的长期频率 --");
        begin
            real actual_fs;
            real err_ppm;
            step = tick_phase_step(50_000_000);
            $display("     50.000 MHz -> step=%0d", step);
            actual_fs = step * 50_000_000.0 / 4294967296.0;
            err_ppm = (actual_fs - 48000.0) / 48000.0 * 1e6;
            $display("     长期平均频率 = %.6f Hz，误差 %.4f ppm", actual_fs, err_ppm);
            check_count++;
            if (err_ppm > 1.0 || err_ppm < -1.0) begin
                error_count++;
                $display("  [FAIL] 50 MHz 下频率误差超过 1 ppm");
            end else begin
                $display("  [PASS] 50 MHz 下频率误差在 1 ppm 内");
            end
        end

        // ---------------------------------------------------------------------
        $display("\n[4] midi_velocity_to_10bit：高位复制低 3 位");
        // ---------------------------------------------------------------------
        check_int("velocity 0   -> 10 位", midi_velocity_to_10bit(7'd0),   10'd0);
        check_int("velocity 1   -> 10 位", midi_velocity_to_10bit(7'd1),   10'd8);
        check_int("velocity 127 -> 10 位", midi_velocity_to_10bit(7'd127), 10'd1023);
        // 中间值：64 = 0b1000000，取 [6:4] = 0b100 = 4，
        // 拼接得 0b1000000100 = 516
        check_int("velocity 64  -> 10 位", midi_velocity_to_10bit(7'd64),  10'd516);
        // 边界：8 = 0b0001000，取 [6:4] = 0b000，拼接得 0b0001000000 = 64
        check_int("velocity 8   -> 10 位", midi_velocity_to_10bit(7'd8),   10'd64);

        // 单调性：velocity 增大时输出不得减小
        begin
            logic [9:0] prev;
            logic [9:0] cur;
            int unsigned i;
            int unsigned violations;
            violations = 0;
            prev = midi_velocity_to_10bit(7'd0);
            for (i = 1; i < 128; i++) begin
                cur = midi_velocity_to_10bit(i[6:0]);
                if (cur < prev) violations++;
                prev = cur;
            end
            check_int("velocity 映射单调（违规数）", violations, 0);
            check_int("velocity 127 达到满量程", midi_velocity_to_10bit(7'd127), 1023);
        end

        // ---------------------------------------------------------------------
        $display("\n[5] midi_bend_to_12bit：中心点与量程");
        // ---------------------------------------------------------------------
        check_signed("bend 8192（中心） -> 0",    midi_bend_to_12bit(14'd8192),  0);
        check_signed("bend 0（最低）   -> -2048", midi_bend_to_12bit(14'd0),     -2048);
        check_signed("bend 16383（最高）-> 2047", midi_bend_to_12bit(14'd16383), 2047);

        // 全量程单调且不重复
        begin
            logic signed [11:0] prev;
            logic signed [11:0] cur;
            int unsigned i;
            int unsigned non_monotonic;
            int unsigned duplicates;
            non_monotonic = 0;
            duplicates = 0;
            prev = midi_bend_to_12bit(14'd0);
            for (i = 1; i < 16384; i++) begin
                cur = midi_bend_to_12bit(i[13:0]);
                if (cur < prev) non_monotonic++;
                if (cur == prev) duplicates++;
                prev = cur;
            end
            check_int("全量程单调（违规数）", non_monotonic, 0);
            $display("     相邻值重复次数 = %0d（14 位到 12 位为 4:1 压缩，属预期）",
                     duplicates);
        end

        // 量程利用率：必须用满 -2048 至 2047
        begin
            int signed min_val;
            int signed max_val;
            int unsigned i;
            min_val = 32767;
            max_val = -32768;
            for (i = 0; i < 16384; i++) begin
                int signed v;
                v = midi_bend_to_12bit(i[13:0]);
                if (v < min_val) min_val = v;
                if (v > max_val) max_val = v;
            end
            check_signed("实测最小值", min_val, -2048);
            check_signed("实测最大值", max_val,  2047);
        end

        // ---------------------------------------------------------------------
        $display("\n[6] PCM 边界值");
        // ---------------------------------------------------------------------
        check_signed("PCM_MAX", PCM_MAX,  8388607);
        check_signed("PCM_MIN", PCM_MIN, -8388608);
        check_int("PCM_WIDTH", PCM_WIDTH, 24);

        // ---------------------------------------------------------------------
        $display("\n=== 结果 ===");
        $display("检查项 %0d，失败 %0d", check_count, error_count);
        if (error_count == 0) $display("PASS");
        else                  $display("FAIL");
        $display("=== tb_audio_defs_pkg 结束 ===");
        $finish;
    end

endmodule
