// T028 延迟效果器（Delay/Echo Effect）- 独立 RTL（2026-10-02）
//
// 算法合同：
//   output = ((input * dry_gain) >> 15) + ((delayed * wet_gain) >> 15), saturate 24-bit
//   buffer[wr] = input + ((delayed * feedback) >> 15), saturate 24-bit
//   rd_ptr = (wr_ptr - delay_samples) % depth
//
// 定点格式：
//   PCM：24-bit signed [-8388608, 8388607]
//   Gain：Q0.15 unsigned [0, 32767]，表示 [0.0, 0.999969]
//
// 接口时序：
//   - sample_enable：1 脉冲 per 音频样本（48 kHz）
//   - pcm_out/valid：sample_enable 后 2 周期有效（流水延迟 E→E+2）
//
// 参数：
//   - DEPTH：缓存深度（样本数），必须是 2 的幂（简化取模）
//   - 小深度验证（100/1024），最大规模交 M2 核预算

`timescale 1ns/1ps

module delay_effect #(
    parameter DEPTH = 1024          // 缓存深度（必须是 2 的幂）
) (
    input  logic               sys_clk,
    input  logic               sys_rst_n,      // async assert, low active
    input  logic               sample_enable,  // 1 pulse per audio sample
    input  logic signed [23:0] pcm_in,         // 输入 PCM，24-bit signed
    input  logic [15:0]        delay_samples,  // 延迟样本数 [0, DEPTH-1]
    input  logic [14:0]        dry_gain,       // 干信号增益，Q0.15 [0, 32767]
    input  logic [14:0]        wet_gain,       // 湿信号增益，Q0.15 [0, 32767]
    input  logic [14:0]        feedback,       // 反馈增益，Q0.15 [0, 32767]
    output logic signed [23:0] pcm_out,
    output logic               pcm_valid
);

    // 参数检查
    initial begin
        if (DEPTH == 0 || (DEPTH & (DEPTH - 1)) != 0) begin
            $fatal(1, "DEPTH must be power of 2, got %0d", DEPTH);
        end
    end

    localparam ADDR_BITS = $clog2(DEPTH);

    // --------------------------------------------------------- 循环缓冲
    logic signed [23:0] buffer [0:DEPTH-1];
    logic [ADDR_BITS-1:0] wr_ptr;
    logic [ADDR_BITS-1:0] rd_ptr;

    always_comb begin
        rd_ptr = (wr_ptr - delay_samples[ADDR_BITS-1:0]) & (DEPTH - 1);
    end

    // --------------------------------------------------------- 流水级 1：读延迟样本
    logic signed [23:0] delayed_reg;
    logic signed [23:0] input_reg;
    logic [14:0] dry_gain_reg, wet_gain_reg, feedback_reg;
    logic stage1_valid;

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            delayed_reg <= 24'd0;
            input_reg <= 24'd0;
            dry_gain_reg <= 15'd0;
            wet_gain_reg <= 15'd0;
            feedback_reg <= 15'd0;
            stage1_valid <= 1'b0;
        end else if (sample_enable) begin
            delayed_reg <= buffer[rd_ptr];
            input_reg <= pcm_in;
            dry_gain_reg <= dry_gain;
            wet_gain_reg <= wet_gain;
            feedback_reg <= feedback;
            stage1_valid <= 1'b1;
        end else begin
            stage1_valid <= 1'b0;
        end
    end

    // --------------------------------------------------------- 流水级 2：乘法
    logic signed [38:0] dry_prod, wet_prod, fb_prod;
    logic signed [23:0] input_s2;
    logic stage2_valid;

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            dry_prod <= 39'd0;
            wet_prod <= 39'd0;
            fb_prod <= 39'd0;
            input_s2 <= 24'd0;
            stage2_valid <= 1'b0;
        end else if (stage1_valid) begin
            // 24-bit signed × 15-bit unsigned = 39-bit
            dry_prod <= input_reg * $signed({1'b0, dry_gain_reg});
            wet_prod <= delayed_reg * $signed({1'b0, wet_gain_reg});
            fb_prod <= delayed_reg * $signed({1'b0, feedback_reg});
            input_s2 <= input_reg;
            stage2_valid <= 1'b1;
        end else begin
            stage2_valid <= 1'b0;
        end
    end

    // --------------------------------------------------------- 流水级 3：移位、加法、饱和
    logic signed [23:0] dry_contrib, wet_contrib, fb_contrib;
    logic signed [24:0] output_raw, fb_raw;
    logic signed [23:0] output_sat, fb_sat;

    always_comb begin
        // 截断右移 15 位
        dry_contrib = dry_prod[38:15];
        wet_contrib = wet_prod[38:15];
        fb_contrib = fb_prod[38:15];

        // 干湿混合
        output_raw = $signed(dry_contrib) + $signed(wet_contrib);
        // 饱和到 24-bit（M2 修正：25-bit 常量匹配 25-bit 变量）
        if (output_raw > 25'sd8388607)
            output_sat = 24'sd8388607;
        else if (output_raw < -25'sd8388608)
            output_sat = -24'sd8388608;
        else
            output_sat = output_raw[23:0];

        // 反馈信号
        fb_raw = $signed(input_s2) + $signed(fb_contrib);
        if (fb_raw > 25'sd8388607)
            fb_sat = 24'sd8388607;
        else if (fb_raw < -25'sd8388608)
            fb_sat = -24'sd8388608;
        else
            fb_sat = fb_raw[23:0];
    end

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            pcm_out <= 24'd0;
            pcm_valid <= 1'b0;
        end else begin
            pcm_valid <= stage2_valid;
            if (stage2_valid) begin
                pcm_out <= output_sat;
            end
        end
    end

    // --------------------------------------------------------- 写缓存
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            wr_ptr <= {ADDR_BITS{1'b0}};
            for (int i = 0; i < DEPTH; i++) begin
                buffer[i] <= 24'd0;
            end
        end else if (stage2_valid) begin
            buffer[wr_ptr] <= fb_sat;
            wr_ptr <= (wr_ptr + 1) & (DEPTH - 1);
        end
    end

endmodule
