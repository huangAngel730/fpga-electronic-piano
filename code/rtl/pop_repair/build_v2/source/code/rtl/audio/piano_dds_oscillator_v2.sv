// V2 isolated beat-perception repair oscillator.
//
// Pitch remains phase_acc += fcw.  Each lane receives a ROM with identical
// harmonic magnitudes but a distinct 0/pi upper-partial phase pattern.  This
// decorrelates harmonic beat envelopes without detuning or suppressing any
// fundamental.  The table transition remains phase-wrap aligned.
`timescale 1ns/1ps

module piano_dds_oscillator_v2 #(
    parameter integer VOICE_INDEX = 0,
    parameter ROM_FILE = "model/generated/wavetables_v2/piano_v2_lane0_4x256_8191.mem"
) (
    input  logic               sys_clk,
    input  logic               sys_rst_n,
    input  logic               sample_tick,
    input  logic               note_on,
    input  logic [9:0]         velocity,
    input  logic [31:0]        fcw,
    output logic signed [15:0] wt_sample
);
    localparam logic [31:0] FCW_1500_HZ = 32'd134_217_728;
    localparam logic [31:0] FCW_3000_HZ = 32'd268_435_456;
    localparam logic [31:0] FCW_4400_HZ = 32'd393_705_335;
    localparam logic [1:0] TABLE_RICH_10 = 2'd0;
    localparam logic [1:0] TABLE_MED_7   = 2'd1;
    localparam logic [1:0] TABLE_LITE_5  = 2'd2;
    localparam logic [1:0] TABLE_SINE_1  = 2'd3;
    localparam logic [10:0] ATTACK_STAGGER_SAMPLES = VOICE_INDEX * 11'd48;

    logic [31:0] phase_acc;
    logic [10:0] attack_samples_left;
    logic [10:0] attack_base_samples;
    logic [10:0] attack_load_samples;
    logic [1:0] body_table;
    logic [1:0] attack_table;
    logic [1:0] selected_table;
    logic [1:0] active_table;
    logic [1:0] pending_table;
    logic       table_change_pending;
    logic       phase_wrap;
    logic [9:0] rom_addr;

    always_comb begin
        if (fcw <= FCW_1500_HZ) begin
            body_table   = TABLE_MED_7;
            attack_table = TABLE_RICH_10;
        end else if (fcw <= FCW_3000_HZ) begin
            body_table   = TABLE_LITE_5;
            attack_table = TABLE_MED_7;
        end else if (fcw <= FCW_4400_HZ) begin
            body_table   = TABLE_LITE_5;
            attack_table = TABLE_LITE_5;
        end else begin
            body_table   = TABLE_SINE_1;
            attack_table = TABLE_SINE_1;
        end

        if (velocity >= 10'd768)
            attack_base_samples = 11'd1440;
        else if (velocity >= 10'd512)
            attack_base_samples = 11'd960;
        else if (velocity >= 10'd256)
            attack_base_samples = 11'd480;
        else
            attack_base_samples = 11'd0;

        if (attack_base_samples > ATTACK_STAGGER_SAMPLES)
            attack_load_samples = attack_base_samples - ATTACK_STAGGER_SAMPLES;
        else
            attack_load_samples = 11'd0;

        selected_table = active_table;
        phase_wrap = ((phase_acc + fcw) < phase_acc);
        rom_addr = {selected_table, phase_acc[31:24]};
    end

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            phase_acc             <= 32'd0;
            attack_samples_left   <= 11'd0;
            active_table          <= TABLE_SINE_1;
            pending_table         <= TABLE_SINE_1;
            table_change_pending  <= 1'b0;
        end else begin
            if (note_on) begin
                attack_samples_left <= attack_load_samples;
                if (attack_load_samples != 0)
                    active_table <= attack_table;
                else
                    active_table <= body_table;
                table_change_pending <= 1'b0;
            end
            if (sample_tick)
                phase_acc <= phase_acc + fcw;
            if (!note_on && sample_tick) begin
                if (table_change_pending && phase_wrap) begin
                    active_table <= pending_table;
                    table_change_pending <= 1'b0;
                end else if (attack_samples_left != 0) begin
                    attack_samples_left <= attack_samples_left - 1'b1;
                    if (attack_samples_left == 11'd1) begin
                        if (phase_wrap) begin
                            active_table <= body_table;
                        end else begin
                            pending_table <= body_table;
                            table_change_pending <= 1'b1;
                        end
                    end
                end
            end
        end
    end

    piano_v2_wavetable_1024 #(.ROM_FILE(ROM_FILE)) u_table (
        .clk(sys_clk), .addr(rom_addr), .dout(wt_sample)
    );
endmodule

module piano_v2_wavetable_1024 #(
    parameter ROM_FILE = "model/generated/wavetables_v2/piano_v2_lane0_4x256_8191.mem"
) (
    input  logic               clk,
    input  logic [9:0]         addr,
    output logic signed [15:0] dout
);
    logic signed [15:0] rom_data [0:1023];
    // synthesis translate_off
    string wavetable_path;
    integer rom_index;
    // synthesis translate_on

    initial begin
        // synthesis translate_off
        if ($value$plusargs("WAVETABLE_PATH=%s", wavetable_path)) begin
            $readmemh(wavetable_path, rom_data);
        end else begin
            wavetable_path = ROM_FILE;
        // synthesis translate_on
            $readmemh(ROM_FILE, rom_data);
        // synthesis translate_off
        end
        for (rom_index = 0; rom_index < 1024; rom_index = rom_index + 1)
            if (^rom_data[rom_index] === 1'bx)
                $fatal(1, "Uninitialized V2 wavetable word %0d in %s",
                       rom_index, wavetable_path);
        // synthesis translate_on
    end

    always_ff @(posedge clk)
        dout <= rom_data[addr];
endmodule
