#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the 256-point packed sine wavetable used by the DDS.

Why this script exists
----------------------
The DDS needs a sine lookup table that BOTH iverilog and GowinSynthesis accept:

  * `real` + `$sin` (the original T007 approach) simulates fine but Gowin
    rejects it outright:
        ERROR (EX3956): Illegal operation with real number
        WARN  (EX2933): Function 'sine_sample' has no return value assignment
    so it can never produce a bitstream.

  * An unpacked array localparam is rejected by iverilog:
        sorry: unpacked array parameters are not supported yet

The working compromise is a *packed* vector holding all 256 entries, indexed
with a compile-time-unrolled function. This script emits that literal so the
table is reproducible instead of hand-edited.

Where the table lives
---------------------
The literal is emitted into a standalone header:

    code/rtl/common/sine_table.svh

That file defines ``SINE_TABLE_DEFAULT`` (256 entries) and
``SINE_TABLE_DEPTH``. Any module can ``include`` it, so the DDS reuses one
canonical table instead of each module carrying its own copy.

It used to be inlined straight into ``rtl/board/electronic_piano_top.sv``.
That made the table unreusable: a new synth module could only copy-paste the
256 literals, or refactor the top level first. Keeping it in ``rtl/common/``
decouples the two.

Usage
-----
    python -X utf8 code/scripts/gen_sine_table.py            # print to stdout
    python -X utf8 code/scripts/gen_sine_table.py --write    # write the .svh
    python -X utf8 code/scripts/gen_sine_table.py --check    # verify the .svh

`--check` recomputes the table and compares it against the literal in the .svh,
exiting non-zero on any mismatch. Run it after touching either file: a wrong
table does not break synthesis, it just silently detunes the tone or skews its
amplitude.

Rounding is half-away-from-zero, matching the original `$rtoi(v +/- 0.5)`
behaviour, so the regenerated table is bit-identical to the simulated one.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

DEPTH = 256
AMPLITUDE = 8192
PER_LINE = 8

# code/scripts/gen_sine_table.py -> repository root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
TABLE_SVH = REPO_ROOT / "code" / "rtl" / "common" / "sine_table.svh"


def sine_table(depth: int = DEPTH, amplitude: int = AMPLITUDE) -> list[int]:
    """round(sin(2*pi*i/depth) * amplitude), half away from zero."""
    values: list[int] = []
    for i in range(depth):
        v = math.sin(2.0 * math.pi * i / depth) * amplitude
        n = math.floor(abs(v) + 0.5)
        values.append(-n if v < 0 else n)
    return values


def _format(values: list[int], indent: str = "        ") -> str:
    lines = []
    for start in range(0, len(values), PER_LINE):
        chunk = values[start:start + PER_LINE]
        parts = [
            "-16'sd%d" % abs(x) if x < 0 else "16'sd%d" % x
            for x in chunk
        ]
        line = indent + ", ".join(parts)
        if start + PER_LINE < len(values):
            line += ","
        lines.append(line)
    return "\n".join(lines)


def render_svh(values: list[int]) -> str:
    """Build the full .svh text for a given table."""
    body = _format(values)
    return SVH_TEMPLATE.format(depth=len(values), width=16 * len(values), body=body)


SVH_TEMPLATE = """\
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
localparam int unsigned SINE_TABLE_DEPTH = {depth};

// Full table, packed. Total width = 16 * {depth} = {width} bits.
localparam logic signed [{width}-1:0] SINE_TABLE_DEFAULT = {{
{body}
}};

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
"""


def extract_from_svh(text: str) -> list[int]:
    """Pull the SINE_TABLE_DEFAULT literal out of the generated header."""
    m = re.search(
        r"localparam\s+logic\s+signed\s*\[[^\]]*\]\s*SINE_TABLE_DEFAULT\s*=\s*\{(.*?)\}\s*;",
        text,
        re.S,
    )
    if not m:
        raise SystemExit("FAIL: could not find SINE_TABLE_DEFAULT in %s" % TABLE_SVH)
    body = m.group(1)
    # Strip // comments so trailing notes cannot be mistaken for entries.
    body = re.sub(r"//[^\n]*", "", body)
    values: list[int] = []
    for tok in body.split(","):
        tok = tok.strip()
        if not tok:
            continue
        neg = tok.startswith("-")
        tok = tok.lstrip("-").strip()
        m2 = re.fullmatch(r"16'sd(\d+)", tok)
        if not m2:
            raise SystemExit("FAIL: unexpected table token %r" % tok)
        n = int(m2.group(1))
        values.append(-n if neg else n)
    return values


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="compare the generated header against a fresh computation",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="regenerate code/rtl/common/sine_table.svh in place",
    )
    args = ap.parse_args()

    if args.check and args.write:
        print("FAIL: --check and --write are mutually exclusive")
        return 2

    expected = sine_table()

    if args.write:
        TABLE_SVH.parent.mkdir(parents=True, exist_ok=True)
        TABLE_SVH.write_text(render_svh(expected), encoding="utf-8", newline="\n")
        print("wrote %s (%d entries)" % (TABLE_SVH, len(expected)))
        return 0

    if not args.check:
        print(_format(expected))
        return 0

    if not TABLE_SVH.exists():
        print("FAIL: %s not found" % TABLE_SVH)
        return 1

    actual = extract_from_svh(TABLE_SVH.read_text(encoding="utf-8"))

    ok = True
    if len(actual) != DEPTH:
        print("FAIL: table has %d entries, expected %d" % (len(actual), DEPTH))
        ok = False

    for i, (a, e) in enumerate(zip(actual, expected)):
        if a != e:
            print("FAIL: entry %d is %d, expected %d" % (i, a, e))
            ok = False
            if i > 12:
                break

    # The declaration width must agree with the entry count, otherwise the
    # top slice silently truncates and the last entries become unreachable.
    header_text = TABLE_SVH.read_text(encoding="utf-8")
    width_m = re.search(
        r"localparam\s+logic\s+signed\s*\[(\d+)-1:0\]\s*SINE_TABLE_DEFAULT",
        header_text,
    )
    if width_m and int(width_m.group(1)) != 16 * DEPTH:
        print("FAIL: declared width %s, expected %d" % (width_m.group(1), 16 * DEPTH))
        ok = False

    depth_m = re.search(
        r"localparam\s+int\s+unsigned\s+SINE_TABLE_DEPTH\s*=\s*(\d+)\s*;",
        header_text,
    )
    if depth_m and int(depth_m.group(1)) != DEPTH:
        print("FAIL: declared depth %s, expected %d" % (depth_m.group(1), DEPTH))
        ok = False

    if ok:
        peak = max(expected)
        trough = min(expected)
        print("PASS: sine table matches (%d entries, peak +%d, trough %d)"
              % (len(expected), peak, trough))
        return 0

    print("")
    print("Regenerate with:")
    print("  python -X utf8 code/scripts/gen_sine_table.py --write")
    return 1


if __name__ == "__main__":
    sys.exit(main())
