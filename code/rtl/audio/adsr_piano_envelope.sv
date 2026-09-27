// T009 钢琴式ADSR包络生成器（修正版）
// 基于M1 Python模型: code/model/adsr_piano.py
// 修正：避免同拍读取ROM导致的跳变
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

    adsr_state_t state;
    assign state_out = state;

    // 内部寄存器
    logic [31:0] level;           // 32位内部精度（高16位为Q1.15）
    logic [15:0] target_gain;     // 目标峰值增益
    logic [31:0] start_level;     // Attack起始电平
    logic [31:0] decay_target;    // Decay目标电平
    logic [31:0] release_start;   // Release开始时的电平
    logic [15:0] sample_counter;

    // Velocity到增益的ROM（同步读取）
    logic [9:0]  rom_addr;
    logic [15:0] rom_dout;
    logic [15:0] velocity_gain_rom [0:1023];
    string rom_path;

    initial begin
        // 默认路径
        rom_path = "model/generated/wavetables/velocity_gain_rom.mem";

        if ($test$plusargs("VELOCITY_ROM_PATH")) begin
            void'($value$plusargs("VELOCITY_ROM_PATH=%s", rom_path));
        end

        $readmemh(rom_path, velocity_gain_rom);

        if (velocity_gain_rom[0] === 16'bx) begin
            $display("ERROR: Failed to load velocity ROM from: %s", rom_path);
            $finish(1);
        end else begin
            $display("INFO: Loaded velocity ROM from: %s", rom_path);
        end
    end

    always_ff @(posedge sys_clk) begin
        rom_dout <= velocity_gain_rom[rom_addr];
    end

    // 主状态机
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            state <= IDLE;
            level <= 32'h0;
            sample_counter <= 16'h0;
            target_gain <= 16'h0;
            start_level <= 32'h0;
            decay_target <= 32'h0;
            release_start <= 32'h0;
            rom_addr <= 10'h0;
        end else begin
            // Note On事件：启动ROM查表
            if (note_on) begin
                rom_addr <= velocity;
                // 捕获当前电平用于重触发
                start_level <= (state == RELEASE) ? level : 32'h0;
                // 等待下一拍ROM输出稳定后进入ATTACK
                state <= IDLE;  // 临时进入IDLE等待ROM
                sample_counter <= 16'hFFFF;  // 标记为等待ROM
            end
            // Note Off事件
            else if (note_off && state != IDLE) begin
                state <= RELEASE;
                sample_counter <= 16'h0;
                release_start <= level;  // 保存Release开始时的电平
            end
            // 采样时钟：更新包络
            else if (sample_tick) begin
                case (state)
                    IDLE: begin
                        // 检查是否刚从note_on进来，等待ROM输出
                        if (sample_counter == 16'hFFFF) begin
                            // ROM输出已稳定，进入ATTACK
                            target_gain <= rom_dout;
                            level <= start_level;
                            state <= ATTACK;
                            sample_counter <= 16'h0;
                        end else begin
                            level <= 32'h0;
                        end
                    end

                    ATTACK: begin
                        // 线性上升：level += (target_gain - start_level) / ATTACK_SAMPLES
                        if (sample_counter < ATTACK_SAMPLES) begin
                            // 使用32位精度计算
                            level <= start_level +
                                     (({target_gain, 16'h0} - start_level) * (sample_counter + 1)) / ATTACK_SAMPLES;
                            sample_counter <= sample_counter + 1;
                        end else begin
                            // Attack完成，进入Decay
                            level <= {target_gain, 16'h0};
                            decay_target <= {SUSTAIN_LEVEL_Q15, 16'h0};
                            state <= DECAY;
                            sample_counter <= 16'h0;
                        end
                    end

                    DECAY: begin
                        if (sample_counter < DECAY_SAMPLES) begin
                            // 线性下降到Sustain电平
                            level <= {target_gain, 16'h0} -
                                     (({target_gain, 16'h0} - decay_target) * (sample_counter + 1)) / DECAY_SAMPLES;
                            sample_counter <= sample_counter + 1;
                        end else begin
                            // Decay完成，进入Sustain
                            level <= decay_target;
                            state <= SUSTAIN;
                            sample_counter <= 16'h0;
                        end
                    end

                    SUSTAIN: begin
                        // 缓慢指数衰减：每100样本 × 0.997
                        // 近似: level -= level >> 8
                        sample_counter <= sample_counter + 1;
                        if (sample_counter >= 100) begin
                            sample_counter <= 16'h0;
                            level <= level - (level >> 8);
                        end
                    end

                    RELEASE: begin
                        if (sample_counter < RELEASE_SAMPLES) begin
                            // 线性下降到0，从release_start开始
                            level <= release_start - (release_start * (sample_counter + 1)) / RELEASE_SAMPLES;
                            sample_counter <= sample_counter + 1;
                        end else begin
                            // Release完成
                            level <= 32'h0;
                            state <= IDLE;
                            sample_counter <= 16'h0;
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
