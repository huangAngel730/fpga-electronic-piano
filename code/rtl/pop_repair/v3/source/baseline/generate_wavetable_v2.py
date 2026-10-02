#!/usr/bin/env python3
"""Generate four lane-decorrelated V2 piano wavetable ROMs."""

from __future__ import annotations

import math
from pathlib import Path

TABLE_SIZE = 256
PEAK = 8191

# The four tables contain 10/7/5/1 integer harmonics.  The first coefficient
# is always positive so the fundamental remains present and pitch-correct.
TABLE_MAGNITUDES = (
    (1.00, 0.72, 0.52, 0.39, 0.30, 0.23, 0.17, 0.13, 0.095, 0.070),
    (1.00, 0.64, 0.45, 0.31, 0.22, 0.15, 0.10),
    (1.00, 0.48, 0.28, 0.16, 0.09),
    (1.00,),
)

# Only upper-partial polarity changes by lane.  0/pi phases preserve the
# common zero crossing used for click-safe attack-to-body transitions.
LANE_SIGNS = (
    (+1, +1, +1, +1, +1, +1, +1, +1, +1, +1),
    (+1, +1, +1, -1, +1, +1, -1, +1, +1, +1),
    (+1, +1, -1, -1, +1, -1, +1, -1, +1, -1),
    (+1, -1, -1, +1, -1, +1, +1, -1, -1, +1),
)


def build_table(magnitudes: tuple[float, ...], signs: tuple[int, ...]) -> list[int]:
    raw = []
    for index in range(TABLE_SIZE):
        phase = 2.0 * math.pi * index / TABLE_SIZE
        value = sum(
            magnitude * signs[harmonic] * math.sin((harmonic + 1) * phase)
            for harmonic, magnitude in enumerate(magnitudes)
        )
        raw.append(value)
    scale = PEAK / max(abs(value) for value in raw)
    return [max(-8192, min(8191, round(value * scale))) for value in raw]


def signed_hex16(value: int) -> str:
    return f"{value & 0xFFFF:04x}"


def main() -> None:
    output_dir = Path(__file__).resolve().parent / "generated" / "wavetables_v2"
    output_dir.mkdir(parents=True, exist_ok=True)
    for lane, signs in enumerate(LANE_SIGNS):
        words = [
            value
            for magnitudes in TABLE_MAGNITUDES
            for value in build_table(magnitudes, signs)
        ]
        assert len(words) == 1024
        assert min(words) >= -8192 and max(words) <= 8191
        output = output_dir / f"piano_v2_lane{lane}_4x256_8191.mem"
        output.write_text(
            "\n".join(map(signed_hex16, words)) + "\n", encoding="ascii"
        )
        print(f"PASS: lane {lane} wrote {len(words)} words to {output}")


if __name__ == "__main__":
    main()
