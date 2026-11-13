// Electronic Organ envelope: Attack128 -> indefinite Sustain -> Release1024.
// Unsigned Q1.15 output; internal unsigned Q15.16, signed33 step arithmetic.
// sys_rst_n is asynchronous active-low; release is synchronized upstream.
// Event priority: note_on > note_off > sample_tick. A note_on-coincident tick
// is skipped. The synchronous velocity ROM is prepared in two sys_clk stages;
// at most one later sample tick is retained while those stages settle.
`timescale 1ns/1ps

module organ_envelope #(
    parameter VELOCITY_ROM_FILE = "organ_velocity_gain_1024.mem"
) (
    input  logic        sys_clk,
    input  logic        sys_rst_n,
    input  logic        sample_tick,
    input  logic        note_on,
    input  logic        note_off,
    input  logic [9:0]  velocity,
    output logic [15:0] envelope_level,
    output logic [2:0]  state_out
);
    localparam logic [2:0] IDLE    = 3'd0;
    localparam logic [2:0] ATTACK  = 3'd1;
    localparam logic [2:0] LOAD_1  = 3'd2;
    localparam logic [2:0] SUSTAIN = 3'd3;
    localparam logic [2:0] RELEASE = 3'd4;
    localparam logic [2:0] LOAD_2  = 3'd5;
    localparam logic [31:0] LEVEL_MAX_Q16 = 32'h7fff0000;

    logic [2:0] state;
    logic [31:0] level_q16;
    logic [31:0] target_q16;
    logic signed [32:0] step_q16;
    logic [9:0] elapsed;
    logic [9:0] rom_addr;
    logic [15:0] rom_dout;
    logic [15:0] gain_rom [0:1023];
    logic [31:0] start_q16;
    logic pending_tick;
    logic [31:0] load_target_q16;
    logic signed [32:0] load_step_q16;
    logic signed [32:0] load_first_q16;
    logic signed [32:0] release_delta_q16;
    logic signed [32:0] next_level_q16;
    logic [31:0] attack_clamped_q16;

    // synthesis translate_off
    string organ_gain_path;
    integer rom_index;
    // synthesis translate_on
    initial begin
        // synthesis translate_off
        if ($value$plusargs("ORGAN_VELOCITY_ROM_PATH=%s", organ_gain_path)) begin
            $readmemh(organ_gain_path, gain_rom);
        end else begin
            organ_gain_path = VELOCITY_ROM_FILE;
        // synthesis translate_on
            $readmemh(VELOCITY_ROM_FILE, gain_rom);
        // synthesis translate_off
        end
        for (rom_index = 0; rom_index < 1024; rom_index = rom_index + 1) begin
            if (^gain_rom[rom_index] === 1'bx)
                $fatal(1, "Missing Organ velocity ROM word %0d in %s", rom_index, organ_gain_path);
            else if (gain_rom[rom_index] > 16'd32767)
                $fatal(1, "Organ velocity ROM word %0d exceeds32767 in %s", rom_index, organ_gain_path);
        end
        // synthesis translate_on
    end

    always_ff @(posedge sys_clk)
        rom_dout <= gain_rom[rom_addr];

    assign envelope_level = level_q16[31:16];
    always_comb begin
        case (state)
            IDLE:            state_out = 3'd0;
            LOAD_1, LOAD_2,
            ATTACK:          state_out = 3'd1;
            SUSTAIN:         state_out = 3'd3;
            RELEASE:         state_out = 3'd4;
            default:         state_out = 3'd0;
        endcase
    end

    // The ROM output is registered, matching the proven R18 piano-envelope
    // inference style. Constant shifts keep the selected 128/1024-sample
    // Attack/Release arithmetic unchanged.
    always_comb begin
        load_target_q16 = {rom_dout, 16'd0};
        load_step_q16 = ($signed({1'b0, load_target_q16}) -
                         $signed({1'b0, start_q16})) >>> 7;
        load_first_q16 = $signed({1'b0, start_q16}) + load_step_q16;
        release_delta_q16 = -$signed({1'b0, level_q16});
        next_level_q16 = $signed({1'b0, level_q16}) + step_q16;

        // Negative steps permit a lower-velocity retrigger from the current
        // level. Floor rounding may reach the target early; state duration
        // is still exactly128 consumed ticks.
        if ((step_q16 < 33'sd0) &&
            (next_level_q16 < $signed({1'b0, target_q16})))
            attack_clamped_q16 = target_q16;
        else if ((step_q16 >= 33'sd0) &&
                 (next_level_q16 > $signed({1'b0, target_q16})))
            attack_clamped_q16 = target_q16;
        else if (next_level_q16 < 33'sd0)
            attack_clamped_q16 = 32'd0;
        else if (next_level_q16 > $signed({1'b0, LEVEL_MAX_Q16}))
            attack_clamped_q16 = LEVEL_MAX_Q16;
        else
            attack_clamped_q16 = next_level_q16[31:0];
    end

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            state      <= IDLE;
            level_q16  <= 32'd0;
            target_q16 <= 32'd0;
            step_q16   <= 33'sd0;
            elapsed    <= 10'd0;
            rom_addr   <= 10'd0;
            start_q16  <= 32'd0;
            pending_tick <= 1'b0;
        end else if (note_on) begin
            rom_addr   <= velocity;
            start_q16  <= level_q16;
            elapsed    <= 10'd0;
            pending_tick <= 1'b0;
            state      <= LOAD_1;
            // level_q16 holds: retrigger starts from the current level.
        end else if (note_off) begin
            elapsed <= 10'd0;
            pending_tick <= 1'b0;
            if (level_q16 == 32'd0) begin
                level_q16 <= 32'd0;
                step_q16  <= 33'sd0;
                state     <= IDLE;
            end else begin
                step_q16 <= release_delta_q16 >>> 10;
                state    <= RELEASE;
            end
        end else if (state == LOAD_1) begin
            if (sample_tick)
                pending_tick <= 1'b1;
            state <= LOAD_2;
        end else if (state == LOAD_2) begin
            target_q16 <= load_target_q16;
            step_q16 <= load_step_q16;
            if (pending_tick || sample_tick) begin
                if ((load_step_q16 < 33'sd0) &&
                    (load_first_q16 < $signed({1'b0, load_target_q16})))
                    level_q16 <= load_target_q16;
                else if ((load_step_q16 >= 33'sd0) &&
                         (load_first_q16 > $signed({1'b0, load_target_q16})))
                    level_q16 <= load_target_q16;
                else if (load_first_q16 < 33'sd0)
                    level_q16 <= 32'd0;
                else if (load_first_q16 > $signed({1'b0, LEVEL_MAX_Q16}))
                    level_q16 <= LEVEL_MAX_Q16;
                else
                    level_q16 <= load_first_q16[31:0];
                elapsed <= 10'd1;
            end else begin
                elapsed <= 10'd0;
            end
            pending_tick <= 1'b0;
            state <= ATTACK;
        end else if (sample_tick) begin
            case (state)
                ATTACK: begin
                    if (elapsed == 10'd127) begin
                        level_q16 <= target_q16;
                        step_q16  <= 33'sd0;
                        elapsed   <= 10'd0;
                        state     <= SUSTAIN;
                    end else begin
                        level_q16 <= attack_clamped_q16;
                        elapsed   <= elapsed + 10'd1;
                    end
                end
                SUSTAIN: begin
                    level_q16 <= target_q16;
                end
                RELEASE: begin
                    if (elapsed == 10'd1023) begin
                        level_q16 <= 32'd0;
                        step_q16  <= 33'sd0;
                        elapsed   <= 10'd0;
                        state     <= IDLE;
                    end else begin
                        if (next_level_q16 <= 33'sd0)
                            level_q16 <= 32'd0;
                        else
                            level_q16 <= next_level_q16[31:0];
                        elapsed <= elapsed + 10'd1;
                    end
                end
                default: begin
                    level_q16 <= 32'd0;
                    target_q16 <= 32'd0;
                    step_q16 <= 33'sd0;
                    elapsed <= 10'd0;
                    state <= IDLE;
                end
            endcase
        end
    end

    // synthesis translate_off
    always @(posedge sys_clk) begin
        if (sys_rst_n && pending_tick && sample_tick &&
            (state == LOAD_1 || state == LOAD_2) && !note_on && !note_off)
            $fatal(1, "Organ envelope received two ticks during ROM preparation");
    end
    // synthesis translate_on
endmodule
