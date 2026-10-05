// Isolated beat-perception repair prototype.
//
// 32-bit DDS phase and 48 kHz FCW semantics are unchanged.  The original
// 1024x16 sine ROM is replaced by four 256x16 band-limited piano-like tables
// packed into the same 1024-word ROM footprint.  note_on and velocity are
// private lane inputs; the public polyphonic_audio_core interface is unchanged.
`timescale 1ns/1ps

module piano_dds_oscillator #(
    parameter ROM_FILE = "E:/FPGA/GAOYUNFPGA/138K_try/reproduction_20261005/138K_B_frozen_constraints/rom/piano_band_4x256_8191.mem"
) (
    input  logic               sys_clk,
    input  logic               sys_rst_n,
    input  logic               sample_tick,
    input  logic               note_on,
    input  logic [9:0]         velocity,
    input  logic [31:0]        fcw,
    output logic signed [15:0] wt_sample
);
    // FCW = round(f * 2^32 / 48000).  These boundaries guarantee that the
    // selected table's highest partial stays comfortably below Nyquist.
    localparam logic [31:0] FCW_1500_HZ = 32'd134_217_728;
    localparam logic [31:0] FCW_3000_HZ = 32'd268_435_456;
    localparam logic [31:0] FCW_6000_HZ = 32'd536_870_912;

    localparam logic [1:0] TABLE_RICH_8 = 2'd0;
    localparam logic [1:0] TABLE_MED_5  = 2'd1;
    localparam logic [1:0] TABLE_LITE_3 = 2'd2;
    localparam logic [1:0] TABLE_SINE_1 = 2'd3;

    logic [31:0] phase_acc;
    logic [10:0] attack_samples_left;
    logic [1:0] body_table;
    logic [1:0] attack_table;
    logic [1:0] selected_table;
    logic [1:0] active_table;
    logic [1:0] pending_table;
    logic       table_change_pending;
    logic       phase_wrap;
    logic [9:0] rom_addr;

    // Body gets progressively simpler with pitch.  The attack may use one
    // brighter (more-partial) table, but only when velocity justifies it.
    always_comb begin
        if (fcw <= FCW_1500_HZ) begin
            body_table   = TABLE_MED_5;
            attack_table = TABLE_RICH_8;
        end else if (fcw <= FCW_3000_HZ) begin
            body_table   = TABLE_LITE_3;
            attack_table = TABLE_MED_5;
        end else if (fcw <= FCW_6000_HZ) begin
            body_table   = TABLE_SINE_1;
            attack_table = TABLE_LITE_3;
        end else begin
            body_table   = TABLE_SINE_1;
            attack_table = TABLE_SINE_1;
        end

        // Table changes at note_on are intentional articulation changes.  The
        // later attack-to-body transition is deferred to phase wrap, where all
        // generated sine-series tables cross zero, avoiding a mid-cycle step.
        selected_table = active_table;
        phase_wrap = ((phase_acc + fcw) < phase_acc);

        // Four 256-sample tables occupy exactly 1024 signed 16-bit words.
        rom_addr = {selected_table, phase_acc[31:24]};
    end

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            phase_acc          <= 32'd0;
            attack_samples_left <= 11'd0;
            active_table       <= TABLE_SINE_1;
            pending_table      <= TABLE_SINE_1;
            table_change_pending <= 1'b0;
        end else begin
            if (note_on) begin
                // 10/20/30 ms at 48 kHz.  Velocity affects brightness duration,
                // not the fundamental FCW or the public Q15 amplitude contract.
                if (velocity >= 10'd768) begin
                    attack_samples_left <= 11'd1440;
                    active_table <= attack_table;
                end else if (velocity >= 10'd512) begin
                    attack_samples_left <= 11'd960;
                    active_table <= attack_table;
                end else if (velocity >= 10'd256) begin
                    attack_samples_left <= 11'd480;
                    active_table <= attack_table;
                end else begin
                    attack_samples_left <= 11'd0;
                    active_table <= body_table;
                end
                table_change_pending <= 1'b0;
            end
            if (sample_tick)
                phase_acc <= phase_acc + fcw;
            // A retrigger wins if an integration ever presents note_on and
            // sample_tick together; do not shorten the newly loaded attack.
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

    piano_band_wavetable_1024 #(.ROM_FILE(ROM_FILE)) u_table (
        .clk(sys_clk),
        .addr(rom_addr),
        .dout(wt_sample)
    );
endmodule

module piano_band_wavetable_1024 #(
    parameter ROM_FILE = "E:/FPGA/GAOYUNFPGA/138K_try/reproduction_20261005/138K_B_frozen_constraints/rom/piano_band_4x256_8191.mem"
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
                $fatal(1, "Uninitialized piano wavetable word %0d in %s",
                       rom_index, wavetable_path);
        // synthesis translate_on
    end

    always_ff @(posedge clk)
        dout <= rom_data[addr];
endmodule

