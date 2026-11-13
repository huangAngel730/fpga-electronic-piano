// Electronic Organ: continuous Phase32 DDS, four 256-word signed16 banks.
// rst_n is asynchronous active-low; reset release is synchronized upstream.
// A request at E uses pre-increment phase and current FCW, returns at E+3.
// note_on/off are intentionally inert: neither resets nor stops the phase.
`timescale 1ns/1ps

module organ_dds_oscillator #(
    parameter ROM_FILE = "organ_band_4x256_8191.mem"
) (
    input  logic               clk,
    input  logic               rst_n,
    input  logic               sample_tick,
    input  logic               note_on,
    input  logic               note_off,
    input  logic [31:0]        fcw,
    output logic signed [15:0] sample_out,
    output logic               sample_valid
);
    localparam logic [31:0] BANK1_FCW = 32'd134217728;
    localparam logic [31:0] BANK2_FCW = 32'd268435456;
    localparam logic [31:0] BANK3_FCW = 32'd536870912;

    logic [31:0] phase_acc;
    logic [1:0] selected_bank;
    logic [9:0] request_addr;
    logic [2:0] valid_pipe;
    logic [2:0] mute_pipe;
    logic signed [15:0] rom_q;
    logic signed [15:0] data_q;
    logic signed [15:0] wave_rom [0:1023];

    // synthesis translate_off
    string organ_rom_path;
    integer rom_index;
    // synthesis translate_on
    initial begin
        // synthesis translate_off
        if ($value$plusargs("ORGAN_WAVETABLE_PATH=%s", organ_rom_path)) begin
            $readmemh(organ_rom_path, wave_rom);
        end else begin
            organ_rom_path = ROM_FILE;
        // synthesis translate_on
            $readmemh(ROM_FILE, wave_rom);
        // synthesis translate_off
        end
        for (rom_index = 0; rom_index < 1024; rom_index = rom_index + 1) begin
            if (^wave_rom[rom_index] === 1'bx)
                $fatal(1, "Missing Organ wave ROM word %0d in %s", rom_index, organ_rom_path);
            else if ((wave_rom[rom_index] < -16'sd8191) ||
                     (wave_rom[rom_index] > 16'sd8191))
                $fatal(1, "Organ wave ROM word %0d outside +/-8191 in %s", rom_index, organ_rom_path);
        end
        // synthesis translate_on
    end

    // Equality selects the next, sparser bank. The FCW and address selection
    // are captured together, so a later FCW change cannot alter a request.
    always_comb begin
        if (fcw < BANK1_FCW)
            selected_bank = 2'd0;
        else if (fcw < BANK2_FCW)
            selected_bank = 2'd1;
        else if (fcw < BANK3_FCW)
            selected_bank = 2'd2;
        else
            selected_bank = 2'd3;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase_acc    <= 32'd0;
            request_addr <= 10'd0;
            valid_pipe   <= 3'b000;
            mute_pipe    <= 3'b000;
            rom_q        <= 16'sd0;
            data_q       <= 16'sd0;
            sample_out   <= 16'sd0;
            sample_valid <= 1'b0;
        end else begin
            valid_pipe   <= {valid_pipe[1:0], sample_tick};
            mute_pipe    <= {mute_pipe[1:0], (sample_tick && fcw[31])};
            sample_valid <= valid_pipe[2];

            if (sample_tick) begin
                request_addr <= {selected_bank, phase_acc[31:24]};
                phase_acc <= phase_acc + fcw;
            end
            // E+1 synchronous ROM read, E+2 data, E+3 held output.
            // Each stage is independently enabled for consecutive requests.
            if (valid_pipe[0])
                rom_q <= wave_rom[request_addr];
            if (valid_pipe[1])
                data_q <= rom_q;
            if (valid_pipe[2])
                sample_out <= mute_pipe[2] ? 16'sd0 : data_q;
        end
    end
endmodule
