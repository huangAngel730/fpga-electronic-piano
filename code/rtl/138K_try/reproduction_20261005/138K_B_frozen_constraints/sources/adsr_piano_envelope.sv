// T009 M2 implementation of the M1 piano envelope reference.
// sys_rst_n is asynchronous active-low; note_on/off are one-clock pulses.
// Output is unsigned Q1.15 in [0, 32767]. One tick advances one audio sample.
// M2 isolated pipeline candidate: delta register -> product register -> apply.
// NoteOn to Attack initialization E+4; NoteOff precompute E+2.
// Events win over old in-flight work. One pending sample during preparation.
// Normal sample ticks add the unchanged signed Q16 step; ROM is unchanged.
`timescale 1ns/1ps
module adsr_piano_envelope (
    input logic sys_clk, sys_rst_n, sample_tick, note_on, note_off,
    input logic [9:0] velocity,
    output logic [15:0] envelope_level,
    output logic [2:0] state_out
);
    localparam int ATTACK_SAMPLES = 240;
    localparam int DECAY_SAMPLES = 4800;
    localparam int RELEASE_SAMPLES = 4800;
    localparam logic signed [25:0] ATTACK_RECIP_Q32 = 26'sd17895697;
    localparam logic signed [25:0] LONG_RECIP_Q32 = 26'sd894785;
    localparam logic [13:0] SUSTAIN_RATE_Q32 = 14'd13422;
    localparam logic [3:0] IDLE=0, LOAD_1=1, LOAD_2=2, ATTACK=3,
                           DECAY=4, SUSTAIN=5, RELEASE=6,
                           LOAD_3=7, LOAD_4=8, RELEASE_1=9, RELEASE_2=10;
    logic [3:0] state;
    logic [31:0] level_q16, start_q16, peak_q16, sustain_q16;
    logic signed [32:0] step_q16;
    logic [12:0] elapsed;
    logic pending_tick;
    logic [31:0] release_start_q16;
    logic [9:0] rom_addr;
    logic [15:0] rom_dout;
    logic [15:0] gain_rom [0:1023];
    // synthesis translate_off
    string rom_path;
    integer rom_index;
    // synthesis translate_on
    initial begin
        // synthesis translate_off
        if ($value$plusargs("VELOCITY_ROM_PATH=%s", rom_path)) begin
            $readmemh(rom_path, gain_rom);
        end else begin
            rom_path="E:/FPGA/GAOYUNFPGA/138K_try/reproduction_20261005/138K_B_frozen_constraints/rom/velocity_gain_rom.mem";
        // synthesis translate_on
            $readmemh("E:/FPGA/GAOYUNFPGA/138K_try/reproduction_20261005/138K_B_frozen_constraints/rom/velocity_gain_rom.mem", gain_rom);
        // synthesis translate_off
        end
        for (rom_index=0; rom_index<1024; rom_index=rom_index+1)
            if (^gain_rom[rom_index] === 1'bx)
                $fatal(1, "Missing gain ROM word %0d: %s", rom_index, rom_path);
        // synthesis translate_on
    end
    always_ff @(posedge sys_clk) rom_dout <= gain_rom[rom_addr];

    // Preserve M1's public debug encoding (IDLE=0, ATTACK=1,
    // DECAY=2, SUSTAIN=3, RELEASE=4). LOAD_1/2 are private ROM stages;
    // from the event consumer's perspective they belong to Attack.
    always_comb begin
        case (state)
            IDLE: state_out = 3'd0;
            LOAD_1, LOAD_2, LOAD_3, LOAD_4, ATTACK: state_out = 3'd1;
            DECAY: state_out = 3'd2;
            SUSTAIN: state_out = 3'd3;
            RELEASE_1, RELEASE_2, RELEASE: state_out = 3'd4;
            default: state_out = 3'd0;
        endcase
    end
    assign envelope_level = level_q16[31:16];
    logic signed [32:0] step_delta;
    logic signed [25:0] reciprocal;
    logic signed [32:0] step_delta_q;
    logic signed [25:0] reciprocal_q;
    logic signed [58:0] step_product_q;
    logic signed [32:0] step_quotient;
    logic signed [32:0] next_level;
    logic signed [32:0] first_level;
    logic [44:0] sustain_product_q;
    logic [31:0] sustain_drop;
    // One precompute multiplier is shared across Attack, Decay and Release.
    always_comb begin
        step_delta = 33'sd0;
        reciprocal = LONG_RECIP_Q32;
        if (note_off && state!=IDLE) begin
            step_delta = -$signed({1'b0,level_q16});
        end else if (state==LOAD_2) begin
            step_delta = $signed({1'b0,rom_dout,16'b0})-$signed({1'b0,start_q16});
            reciprocal = ATTACK_RECIP_Q32;
        end // Precompute throughout Attack; step_q16 still latches only at its boundary.
        else if (state==ATTACK) begin
            step_delta = $signed({1'b0,sustain_q16})-$signed({1'b0,peak_q16});
        end
        step_quotient = {{6{step_product_q[58]}},step_product_q[58:32]};
        next_level = $signed({1'b0,level_q16})+step_q16;
        first_level = $signed({1'b0,start_q16})+$signed(step_quotient);
        sustain_drop = {1'b0,sustain_product_q} >> 32;
    end
    // Each stage has independent registers. No path spans subtract+multiply+add.
    // Decay precompute is stable for the whole Attack between boundary ticks.
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if(!sys_rst_n) begin
            step_delta_q <= 0; reciprocal_q <= LONG_RECIP_Q32; step_product_q <= 0;
        end else begin
            step_delta_q <= step_delta;
            reciprocal_q <= reciprocal;
            step_product_q <= step_delta_q * reciprocal_q;
        end
    end
    // Audio requests are separated by many sys_clk cycles; one stage isolates
    // the constant sustain multiplier from the sample update path.
    always_ff @(posedge sys_clk) begin
        sustain_product_q <= level_q16[30:0] * SUSTAIN_RATE_Q32;
    end
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            state<=IDLE;level_q16<=0;start_q16<=0;peak_q16<=0;
            sustain_q16<=0;elapsed<=0;rom_addr<=0;step_q16<=0;pending_tick<=0;release_start_q16<=0;
        end else if (note_on) begin
            rom_addr<=velocity;
            // 任何状态重触发都保留当前电平作为起点（同步Python模型）
            start_q16 <= level_q16;
            elapsed<=0;
            pending_tick<=sample_tick;
            state<=LOAD_1;
        end else if (note_off && state!=IDLE) begin
            release_start_q16<=level_q16;
            pending_tick<=sample_tick;
            elapsed<=0;
            state<=RELEASE_1;
        end else if (state==RELEASE_1) begin
            if(sample_tick) pending_tick<=1;
            state<=RELEASE_2;
        end else if (state==RELEASE_2) begin
            step_q16<=step_quotient;
            if(pending_tick || sample_tick) begin
                if($signed({1'b0,release_start_q16})+step_quotient<=0) level_q16<=0;
                else level_q16<=$signed({1'b0,release_start_q16})+step_quotient;
                elapsed<=1;
            end else elapsed<=0;
            pending_tick<=0;
            state<=RELEASE;
        end else if (state==LOAD_1) begin
            if (sample_tick) pending_tick<=1;
            state<=LOAD_2;
        end else if (state==LOAD_2) begin
            peak_q16<={rom_dout,16'b0};
            // M1 model: floor(13107 * gain / 32767); reciprocal approximation
            // via power-of-two scaling differs by at most 1 Q15 LSB.
            sustain_q16<=((((32'(rom_dout)*32'd13108))>>15))<<16;
            if(sample_tick) pending_tick<=1;
            state<=LOAD_3;
        end else if(state==LOAD_3) begin
            if(sample_tick) pending_tick<=1;
            state<=LOAD_4;
        end else if(state==LOAD_4) begin
            step_q16<=step_quotient;
            if (pending_tick || sample_tick) begin
                level_q16<=first_level[31:0];
                elapsed<=1;
            end else begin
                level_q16<=start_q16;
                elapsed<=0;
            end
            pending_tick<=0;
            state<=ATTACK;
        end else if (sample_tick) begin
            case (state)
                ATTACK: begin
                    if (elapsed==ATTACK_SAMPLES-1) begin
                        level_q16<=peak_q16;
                        step_q16<=step_quotient;
                        elapsed<=0;state<=DECAY;
                    end else begin
                        level_q16<=next_level[31:0];
                        elapsed<=elapsed+1'b1;
                    end
                end
                DECAY: begin
                    if (elapsed==DECAY_SAMPLES) begin
                        level_q16<=sustain_q16;
                        elapsed<=0;state<=SUSTAIN;
                    end else begin
                        level_q16<=next_level[31:0];
                        elapsed<=elapsed+1'b1;
                    end
                end
                SUSTAIN: begin
                    if (level_q16<32'd65536) begin
                        level_q16<=0;state<=IDLE;
                    end else begin
                        level_q16<=level_q16-sustain_drop;
                    end
                end
                RELEASE: begin
                    if (elapsed==RELEASE_SAMPLES-1) begin
                        level_q16<=0;elapsed<=0;state<=IDLE;
                    end else begin
                        if (next_level<=0) level_q16<=0;
                        else level_q16<=next_level[31:0];
                        elapsed<=elapsed+1'b1;
                    end
                end
                default: level_q16<=0;
            endcase
        end
    end
    // synthesis translate_off
    always @(posedge sys_clk) if(sys_rst_n && sample_tick && pending_tick &&
       (state==LOAD_1 || state==LOAD_2 || state==LOAD_3 || state==LOAD_4 ||
        state==RELEASE_1 || state==RELEASE_2) && !note_on && !note_off)
        $fatal(1,"ADSR pipeline received two samples before event preparation settled");
    // synthesis translate_on
endmodule
