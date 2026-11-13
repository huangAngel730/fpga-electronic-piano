// T027 双音色振荡器模块（修正版）
//
// 修正内容：
// 1. ROM 数据与 sample_valid 对齐
// 2. Note Off 后继续相位推进（支持 ADSR Release）
// 3. Note On 时锁存音色选择（不跟随切换）
// 4. Note On 时保持相位连续（不清零）
// 5. 可配置 ROM 文件路径
//
// 参数：
// - WAVETABLE_SIZE: 1024
// - PHASE_BITS: 32
// - SAMPLE_BITS: 16
// - 波表范围：±8192
//
// 流水线口径（以真实边沿为准，勿再沿用旧的“2 周期 / 3 级”说法）：
// 采样边沿 E 接收相位与锁存音色，输出落在 E+3，共 4 个寄存阶段：
//   E   : addr_pipe[0] <- wt_addr；timbre_pipe[0] <- timbre_latched；valid_pipe[0] <- sample_tick
//   E+1 : addr_pipe[1] <- addr_pipe[0]；timbre_pipe[1]、valid_pipe[1] 同步移位
//   E+2 : 同步 ROM 数据寄存器 <- ROM[addr_pipe[1]]（sine_data / triangle_data）
//   E+3 : sample_out <- 音色选择(ROM 数据)；sample_valid <- valid_pipe[2]
// Note On 与 sample_tick 同沿时：本拍仍用旧 timbre_latched，下一拍生效。

`timescale 1ns/1ps

module m1td_timbre_oscillator #(
    parameter PHASE_BITS = 32,
    parameter ADDR_BITS = 10,  // log2(1024)
    parameter SAMPLE_BITS = 16,
    parameter SINE_ROM_FILE = "sine_wavetable.hex",
    parameter TRIANGLE_ROM_FILE = "triangle_wavetable.hex"
) (
    input logic clk,
    input logic rst_n,
    input logic sample_tick,

    // 频率控制
    input logic [PHASE_BITS-1:0] fcw,

    // 音色选择（0=Sine, 1=Triangle）
    input logic timbre_select,

    // Note On/Off
    input logic note_on,
    input logic note_off,

    // 输出
    output logic signed [SAMPLE_BITS-1:0] sample_out,
    output logic sample_valid
);

    // 相位累加器
    logic [PHASE_BITS-1:0] phase_acc;

    // 波表地址（相位高10位）
    logic [ADDR_BITS-1:0] wt_addr;

    // ROM 读取流水线（2 周期延迟）
    logic [ADDR_BITS-1:0] addr_pipe [0:2];
    logic timbre_pipe [0:2];
    logic valid_pipe [0:2];

    // ROM 输出
    logic signed [SAMPLE_BITS-1:0] sine_data;
    logic signed [SAMPLE_BITS-1:0] triangle_data;

    // 音符状态
    logic note_active;

    // 锁存的音色选择
    logic timbre_latched;


    // 音符状态管理
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            note_active <= 1'b0;
        end else begin
            if (note_on) begin
                note_active <= 1'b1;
            end else if (note_off) begin
                note_active <= 1'b0;
            end
        end
    end


    // Note On 时锁存音色选择
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            timbre_latched <= 1'b0;
        end else if (note_on) begin
            timbre_latched <= timbre_select;
        end
    end


    // 相位累加器（先取样、后累加）
    // 修正：Note On 时不清零，保持相位连续
    // 修正：Note Off 后继续推进，支持 Release
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase_acc <= '0;
        end else if (sample_tick) begin
            // 始终累加，不管 Note On/Off 状态
            phase_acc <= phase_acc + fcw;
        end
    end


    // 波表地址（相位高10位）
    assign wt_addr = phase_acc[PHASE_BITS-1:PHASE_BITS-ADDR_BITS];


    // ROM 读取流水线（3 级：地址、ROM、输出）
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            addr_pipe[0] <= '0;
            addr_pipe[1] <= '0;
            addr_pipe[2] <= '0;
            timbre_pipe[0] <= 1'b0;
            timbre_pipe[1] <= 1'b0;
            timbre_pipe[2] <= 1'b0;
            valid_pipe[0] <= 1'b0;
            valid_pipe[1] <= 1'b0;
            valid_pipe[2] <= 1'b0;
        end else begin
            // 第 0 级：输入
            addr_pipe[0] <= wt_addr;
            timbre_pipe[0] <= timbre_latched;
            valid_pipe[0] <= sample_tick;

            // 第 1 级：ROM 读取
            addr_pipe[1] <= addr_pipe[0];
            timbre_pipe[1] <= timbre_pipe[0];
            valid_pipe[1] <= valid_pipe[0];

            // 第 2 级：数据输出
            addr_pipe[2] <= addr_pipe[1];
            timbre_pipe[2] <= timbre_pipe[1];
            valid_pipe[2] <= valid_pipe[1];
        end
    end


    // Native13 -> R14: shared complete ROM read-address consumer only.
    // Each ADDR_BITS bit traverses two kept identity LUTs; both synchronous
    // ROMs keep their existing E+2 capture. Raw addr/valid/timbre pipeline,
    // phase accumulation, NoteOn policy and E+3 sample output are unchanged.
    wire [ADDR_BITS-1:0] rom_read_addr;
    for(genvar rom_bit=0;rom_bit<ADDR_BITS;rom_bit=rom_bit+1)begin:g_rom_read_address_hold
        (* syn_keep=1, syn_dont_touch=1 *)wire[2:0]chain;
        assign chain[0]=addr_pipe[1][rom_bit];
        for(genvar rom_stage=0;rom_stage<2;rom_stage=rom_stage+1)begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *)LUT1 #(.INIT(2'h2))u_identity(
                .I0(chain[rom_stage]),.F(chain[rom_stage+1]));
        end
        assign rom_read_addr[rom_bit]=chain[2];
    end

    // 正弦波 ROM
    logic signed [SAMPLE_BITS-1:0] sine_rom [0:2**ADDR_BITS-1];
    initial begin
        $readmemh(SINE_ROM_FILE, sine_rom);
    end

    always_ff @(posedge clk) begin
        sine_data <= sine_rom[rom_read_addr];
    end


    // 三角波 ROM
    logic signed [SAMPLE_BITS-1:0] triangle_rom [0:2**ADDR_BITS-1];
    initial begin
        $readmemh(TRIANGLE_ROM_FILE, triangle_rom);
    end

    always_ff @(posedge clk) begin
        triangle_data <= triangle_rom[rom_read_addr];
    end


    // 音色选择多路复用器（与数据对齐）
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_out <= '0;
            sample_valid <= 1'b0;
        end else begin
            sample_out <= timbre_pipe[2] ? triangle_data : sine_data;
            sample_valid <= valid_pipe[2];
        end
    end

endmodule
