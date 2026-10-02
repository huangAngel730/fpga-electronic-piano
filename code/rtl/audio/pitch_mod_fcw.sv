// M1 Pitch + Modulation FCW controller  (M2 V0147 最终修正版，2026-10-02)
//
// 修正内容（针对 M2 V0147 返修反馈）：
//   1. 仿真字符串移至模块声明区，无automatic；不影响综合常量ROM初始化
//   2. NoteOn 时序：同拍读 0 推进 1 次；异拍只清 0，下次采样推进
//   3. FCW_MAX 恢复 0x80000000（2^31，24 kHz）
//   4. 向量数量同步 62279
//   5. SHA 重新计算
//
// 原数学、LUT 初始化、深度参数保持 V0143 修正。

`timescale 1ns/1ps

module pitch_mod_fcw #(
    parameter OCT_FILE = "model/generated/pitch_mod/oct_ratio_q16.mem",
    parameter SUB_FILE = "model/generated/pitch_mod/sub_ratio_q16.mem",
    parameter LFO_FILE = "model/generated/pitch_mod/lfo_sine_q15.mem",
    parameter logic [31:0] LFO_INC = 32'd447392,         // 5.0 Hz @ 48 kHz
    parameter logic [31:0] FCW_MAX = 32'd2147483648,     // 2^31, 24 kHz (M2 V0147)
    parameter logic [9:0]  MOD_DEPTH_MAX_Q10 = 10'd512   // ±50 cents
) (
    input  logic               sys_clk,
    input  logic               sys_rst_n,      // async assert, low active
    input  logic               sample_enable,  // 1 pulse per audio sample
    input  logic               note_on,        // 1 pulse; restarts vibrato LFO
    input  logic signed [11:0] bend,           // signed12, centre 0
    input  logic [11:0]        modulation,     // unsigned12, 0..4095
    input  logic [4:0]         pitch_range,    // semitones, 0..24
    input  logic [31:0]        base_fcw,       // from the note-pitch table
    output logic [31:0]        fcw_out,
    output logic               fcw_valid       // 1 sys_clk after sample_enable
);

    // ------------------------------------------------------------ LUT storage
    logic [19:0] oct_lut [0:49];               // 2 ** (q/12), Q16, q in [-25,24]
    logic [19:0] sub_lut [0:1023];             // 2 ** (r/12288), Q16
    logic signed [15:0] lfo_lut [0:1023];      // sine, +/-32767 Q15

    // LUT 可综合初始化（V0143）：恒定参数在综合可见区
    // synthesis translate_off
    string oct_path, sub_path, lfo_path;
    // synthesis translate_on
    initial begin
        $readmemh(OCT_FILE, oct_lut);
        $readmemh(SUB_FILE, sub_lut);
        $readmemh(LFO_FILE, lfo_lut);
        // synthesis translate_off
  // M2 V0147: automatic
        if ($value$plusargs("OCT_PATH=%s", oct_path)) $readmemh(oct_path, oct_lut);
        if ($value$plusargs("SUB_PATH=%s", sub_path)) $readmemh(sub_path, sub_lut);
        if ($value$plusargs("LFO_PATH=%s", lfo_path)) $readmemh(lfo_path, lfo_lut);
        for (int i = 0; i < 50; i++)
            if (^oct_lut[i] === 1'bx)
                $fatal(1, "OCT[%0d] uninitialized", i);
        for (int i = 0; i < 1024; i++) begin
            if (^sub_lut[i] === 1'bx)
                $fatal(1, "SUB[%0d] uninitialized", i);
            if (^lfo_lut[i] === 1'bx)
                $fatal(1, "LFO[%0d] uninitialized", i);
        end
        // synthesis translate_on
    end

    // --------------------------------------------------------- LFO phase state
    // M2 V0147: NoteOn 时序修正
    // - 同拍 note_on + sample_enable：读 0 相位，推进到 INC
    // - 异拍 note_on：只清零，下次 sample_enable 读 0 后推进
    logic [31:0] lfo_phase;

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            lfo_phase <= 32'd0;
        end else if (sample_enable) begin
            lfo_phase <= (note_on ? 32'd0 : lfo_phase) + LFO_INC;
        end else if (note_on) begin
            lfo_phase <= 32'd0;
        end
    end

    // -------------------------------------------------------- Pitch / Mod math
    logic signed [16:0] bend_x_range, semi_q10;
    logic        [21:0] mod_x_depth;
    logic        [9:0]  depth_q10;
    logic signed [25:0] sine_x_depth;
    logic signed [16:0] vib_q10;
    logic signed [17:0] total_q10, q_semi;
    logic        [9:0]  r_frac;
    logic        [5:0]  oct_idx;
    logic        [39:0] ratio_prod;
    logic        [24:0] factor_q16;
    logic        [24:0] oct_val, sub_val;
    logic signed [15:0] sine_q15;
    logic        [56:0] fcw_prod;
    logic        [32:0] fcw_raw;

    always_comb begin
        bend_x_range = $signed(bend) * $signed({1'b0, pitch_range});
        semi_q10     = bend_x_range >>> 1;

        // 深度参数可配置（V0143）
        mod_x_depth  = modulation * {12'd0, MOD_DEPTH_MAX_Q10};
        depth_q10    = (mod_x_depth + 22'd2048) >>> 12;

        sine_q15     = lfo_lut[note_on ? 10'd0 : lfo_phase[31:22]];
        sine_x_depth = sine_q15 * $signed({1'b0, depth_q10});
        vib_q10      = sine_x_depth >>> 15;

        total_q10    = $signed(semi_q10) + $signed(vib_q10);

        q_semi       = total_q10 >>> 10;
        r_frac       = total_q10[9:0];
        oct_idx      = (q_semi > 18'sd24) ? 6'd49 :
                       (q_semi < -18'sd25) ? 6'd0  :
                       (q_semi[5:0] + 6'd25);

        oct_val      = oct_lut[oct_idx];
        sub_val      = sub_lut[r_frac];
        ratio_prod   = oct_val * sub_val;
        factor_q16   = ratio_prod[39:16];

        fcw_prod     = base_fcw * factor_q16;
        fcw_raw      = (fcw_prod + 57'd32768) >> 16;
    end

    // ------------------------------------------------------------ output stage
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            fcw_out   <= 32'd0;
            fcw_valid <= 1'b0;
        end else begin
            fcw_valid <= sample_enable;
            if (sample_enable)
                fcw_out <= (fcw_raw > FCW_MAX) ? FCW_MAX : fcw_raw[31:0];
        end
    end

endmodule
