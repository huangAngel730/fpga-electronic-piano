// T009 钢琴式ADSR包络生成器
// 基于M1 Python模型: code/model/adsr_piano.py
// 支持Release重触发平滑过渡
`timescale 1ns/1ps

module adsr_piano_envelope (
    input  logic        sys_clk,
    input  logic        sys_rst_n,
    input  logic        sample_tick,    // 48kHz采样时钟
    input  logic        note_on,        // Note On事件
    input  logic        note_off,       // Note Off事件
    input  logic [9:0]  velocity,       // MIDI velocity (0-1023)
    output logic [15:0] envelope_level, // Q1.15格式 (0-32767)
    output logic [2:0]  state_out       // 状态输出（调试用）
);

    // ADSR参数（与Python模型一致）
    localparam int ATTACK_SAMPLES  = 240;   // 5ms @ 48kHz
    localparam int DECAY_SAMPLES   = 4800;  // 100ms
    localparam int RELEASE_SAMPLES = 4800;  // 100ms
    localparam int SUSTAIN_LEVEL_Q15 = 13107; // 0.4 * 32767

    // 状态编码
    typedef enum logic [2:0] {
        IDLE    = 3'b000,
        ATTACK  = 3'b001,
        DECAY   = 3'b010,
        SUSTAIN = 3'b011,
        RELEASE = 3'b100
    } adsr_state_t;

    adsr_state_t state, state_next;
    assign state_out = state;

    // 内部寄存器
    logic [31:0] level;           // 32位内部精度（高16位为Q1.15）
    logic [15:0] velocity_gain;   // 从ROM查表得到的峰值增益
    logic [31:0] attack_delta;    // Attack阶段的增量
    logic [31:0] decay_slope;     // Decay斜率
    logic [31:0] release_slope;   // Release斜率
    logic [15:0] sample_counter;
    logic [31:0] retrigger_level; // Release重触发起始电平

    // Velocity到增益的ROM查表
    logic [15:0] velocity_gain_rom [0:1023];
    initial begin
        $readmemh("../../../model/generated/wavetables/velocity_gain_rom.mem", velocity_gain_rom);
    end

    // 状态机和包络生成
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            state <= IDLE;
            level <= 32'h0;
            sample_counter <= 16'h0;
            velocity_gain <= 16'h0;
            attack_delta <= 32'h0;
            decay_slope <= 32'h0;
            release_slope <= 32'h0;
            retrigger_level <= 32'h0;
        end else begin
            // Note On事件处理
            if (note_on) begin
                velocity_gain <= velocity_gain_rom[velocity];

                // Release重触发：从当前电平开始
                if (state == RELEASE) begin
                    retrigger_level <= level;
                end else begin
                    retrigger_level <= 32'h0;
                end

                state <= ATTACK;
                level <= retrigger_level;
                sample_counter <= 16'h0;

                // 计算Attack增量：(velocity_gain - retrigger_level) / ATTACK_SAMPLES
                // 为避免除法，使用移位近似：delta = (gain - retrigger) << 16 / 240
                attack_delta <= ((velocity_gain - retrigger_level[31:16]) << 16) / ATTACK_SAMPLES;
            end
            // Note Off事件处理
            else if (note_off && state != IDLE) begin
                state <= RELEASE;
                sample_counter <= 16'h0;
                // Release斜率基于当前电平
                release_slope <= level / RELEASE_SAMPLES;
            end
            // 采样时钟：更新包络
            else if (sample_tick) begin
                case (state)
                    IDLE: begin
                        level <= 32'h0;
                    end

                    ATTACK: begin
                        level <= level + attack_delta;
                        sample_counter <= sample_counter + 1;

                        // 到达峰值，进入Decay
                        if (level[31:16] >= velocity_gain || sample_counter >= ATTACK_SAMPLES) begin
                            level <= {velocity_gain, 16'h0};
                            state <= DECAY;
                            sample_counter <= 16'h0;

                            // 计算Decay斜率
                            decay_slope <= ({velocity_gain, 16'h0} - {SUSTAIN_LEVEL_Q15, 16'h0}) / DECAY_SAMPLES;
                        end
                    end

                    DECAY: begin
                        if (level > {SUSTAIN_LEVEL_Q15, 16'h0}) begin
                            level <= level - decay_slope;
                        end else begin
                            level <= {SUSTAIN_LEVEL_Q15, 16'h0};
                            state <= SUSTAIN;
                            sample_counter <= 16'h0;
                        end
                        sample_counter <= sample_counter + 1;

                        if (sample_counter >= DECAY_SAMPLES) begin
                            level <= {SUSTAIN_LEVEL_Q15, 16'h0};
                            state <= SUSTAIN;
                            sample_counter <= 16'h0;
                        end
                    end

                    SUSTAIN: begin
                        // 缓慢指数衰减：每100样本 × 0.997
                        // 简化：每100样本减去 level * 0.003
                        sample_counter <= sample_counter + 1;
                        if (sample_counter >= 100) begin
                            sample_counter <= 16'h0;
                            // level *= 0.997 近似为 level -= level >> 8
                            level <= level - (level >> 8);
                        end
                    end

                    RELEASE: begin
                        if (level > release_slope) begin
                            level <= level - release_slope;
                        end else begin
                            level <= 32'h0;
                            state <= IDLE;
                        end
                        sample_counter <= sample_counter + 1;

                        if (sample_counter >= RELEASE_SAMPLES) begin
                            level <= 32'h0;
                            state <= IDLE;
                        end
                    end

                    default: begin
                        state <= IDLE;
                        level <= 32'h0;
                    end
                endcase
            end
        end
    end

    // 输出Q1.15格式（取高16位）
    assign envelope_level = level[31:16];

endmodule
