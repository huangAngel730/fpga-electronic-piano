// -----------------------------------------------------------------------------
// sine_table.svh  (GENERATED FILE -- DO NOT EDIT BY HAND)
// -----------------------------------------------------------------------------
// 256-point packed sine wavetable, 16-bit signed, amplitude +/-8192.
//
// Regenerate with:
//     python -X utf8 code/scripts/gen_sine_table.py --write
// Verify without touching the file (used by check_repo / regression):
//     python -X utf8 code/scripts/gen_sine_table.py --check
//
// Why a packed vector instead of an unpacked array
// ------------------------------------------------
// Two independent tool limits force this shape -- see gen_sine_table.py for
// the full story. Short version:
//   * `real` + `$sin` is rejected by GowinSynthesis (EX3956), so the table
//     MUST be precomputed integer constants;
//   * an unpacked array parameter is rejected by iverilog, so the table
//     MUST be a packed vector.
// A packed vector is plain Verilog-2001 and both tools accept it.
//
// Entry k occupies bits [16*k +: 16]; entry 0 is the LSB slice (rightmost).
//
// Guard: including this file twice is harmless, but a module that also
// defines its own SINE_TABLE_DEFAULT would collide. Do not redefine it.
// -----------------------------------------------------------------------------

`ifndef SINE_TABLE_SVH
`define SINE_TABLE_SVH

// Number of entries in the table. Must be a power of two so that the DDS can
// slice the phase accumulator with a plain bit-select (no divider, no modulo).
localparam int unsigned SINE_TABLE_DEPTH = 256;

// Full table, packed. Total width = 16 * 256 = 4096 bits.
localparam logic signed [4096-1:0] SINE_TABLE_DEFAULT = {
        16'sd0, 16'sd201, 16'sd402, 16'sd603, 16'sd803, 16'sd1003, 16'sd1202, 16'sd1401,
        16'sd1598, 16'sd1795, 16'sd1990, 16'sd2185, 16'sd2378, 16'sd2570, 16'sd2760, 16'sd2948,
        16'sd3135, 16'sd3320, 16'sd3503, 16'sd3683, 16'sd3862, 16'sd4038, 16'sd4212, 16'sd4383,
        16'sd4551, 16'sd4717, 16'sd4880, 16'sd5040, 16'sd5197, 16'sd5351, 16'sd5501, 16'sd5649,
        16'sd5793, 16'sd5933, 16'sd6070, 16'sd6203, 16'sd6333, 16'sd6458, 16'sd6580, 16'sd6698,
        16'sd6811, 16'sd6921, 16'sd7027, 16'sd7128, 16'sd7225, 16'sd7317, 16'sd7405, 16'sd7489,
        16'sd7568, 16'sd7643, 16'sd7713, 16'sd7779, 16'sd7839, 16'sd7895, 16'sd7946, 16'sd7993,
        16'sd8035, 16'sd8071, 16'sd8103, 16'sd8130, 16'sd8153, 16'sd8170, 16'sd8182, 16'sd8190,
        16'sd8192, 16'sd8190, 16'sd8182, 16'sd8170, 16'sd8153, 16'sd8130, 16'sd8103, 16'sd8071,
        16'sd8035, 16'sd7993, 16'sd7946, 16'sd7895, 16'sd7839, 16'sd7779, 16'sd7713, 16'sd7643,
        16'sd7568, 16'sd7489, 16'sd7405, 16'sd7317, 16'sd7225, 16'sd7128, 16'sd7027, 16'sd6921,
        16'sd6811, 16'sd6698, 16'sd6580, 16'sd6458, 16'sd6333, 16'sd6203, 16'sd6070, 16'sd5933,
        16'sd5793, 16'sd5649, 16'sd5501, 16'sd5351, 16'sd5197, 16'sd5040, 16'sd4880, 16'sd4717,
        16'sd4551, 16'sd4383, 16'sd4212, 16'sd4038, 16'sd3862, 16'sd3683, 16'sd3503, 16'sd3320,
        16'sd3135, 16'sd2948, 16'sd2760, 16'sd2570, 16'sd2378, 16'sd2185, 16'sd1990, 16'sd1795,
        16'sd1598, 16'sd1401, 16'sd1202, 16'sd1003, 16'sd803, 16'sd603, 16'sd402, 16'sd201,
        16'sd0, -16'sd201, -16'sd402, -16'sd603, -16'sd803, -16'sd1003, -16'sd1202, -16'sd1401,
        -16'sd1598, -16'sd1795, -16'sd1990, -16'sd2185, -16'sd2378, -16'sd2570, -16'sd2760, -16'sd2948,
        -16'sd3135, -16'sd3320, -16'sd3503, -16'sd3683, -16'sd3862, -16'sd4038, -16'sd4212, -16'sd4383,
        -16'sd4551, -16'sd4717, -16'sd4880, -16'sd5040, -16'sd5197, -16'sd5351, -16'sd5501, -16'sd5649,
        -16'sd5793, -16'sd5933, -16'sd6070, -16'sd6203, -16'sd6333, -16'sd6458, -16'sd6580, -16'sd6698,
        -16'sd6811, -16'sd6921, -16'sd7027, -16'sd7128, -16'sd7225, -16'sd7317, -16'sd7405, -16'sd7489,
        -16'sd7568, -16'sd7643, -16'sd7713, -16'sd7779, -16'sd7839, -16'sd7895, -16'sd7946, -16'sd7993,
        -16'sd8035, -16'sd8071, -16'sd8103, -16'sd8130, -16'sd8153, -16'sd8170, -16'sd8182, -16'sd8190,
        -16'sd8192, -16'sd8190, -16'sd8182, -16'sd8170, -16'sd8153, -16'sd8130, -16'sd8103, -16'sd8071,
        -16'sd8035, -16'sd7993, -16'sd7946, -16'sd7895, -16'sd7839, -16'sd7779, -16'sd7713, -16'sd7643,
        -16'sd7568, -16'sd7489, -16'sd7405, -16'sd7317, -16'sd7225, -16'sd7128, -16'sd7027, -16'sd6921,
        -16'sd6811, -16'sd6698, -16'sd6580, -16'sd6458, -16'sd6333, -16'sd6203, -16'sd6070, -16'sd5933,
        -16'sd5793, -16'sd5649, -16'sd5501, -16'sd5351, -16'sd5197, -16'sd5040, -16'sd4880, -16'sd4717,
        -16'sd4551, -16'sd4383, -16'sd4212, -16'sd4038, -16'sd3862, -16'sd3683, -16'sd3503, -16'sd3320,
        -16'sd3135, -16'sd2948, -16'sd2760, -16'sd2570, -16'sd2378, -16'sd2185, -16'sd1990, -16'sd1795,
        -16'sd1598, -16'sd1401, -16'sd1202, -16'sd1003, -16'sd803, -16'sd603, -16'sd402, -16'sd201
};

// Look up entry `index` (0 .. SINE_TABLE_DEPTH-1).
//
// MUST be called with a constant or an elaborated-loop index: the for-loop
// below unrolls at compile time into a chain of bit-selects, which maps to
// pure combinational muxing. With a 256-entry table that is a wide mux;
// see the DDS module for the registered/pipelined usage that keeps timing.
function automatic logic signed [15:0] sine_lookup(
    input logic [31:0] index
);
    logic signed [15:0] value;
    integer k;
    begin
        value = 16'sd0;
        for (k = 0; k < SINE_TABLE_DEPTH; k = k + 1) begin
            if (index == k[31:0]) begin
                value = SINE_TABLE_DEFAULT[16*k +: 16];
            end
        end
    end
    return value;
endfunction

`endif  // SINE_TABLE_SVH
