#!/usr/bin/env python3
"""Generate the four 256-sample signed-Q13 piano tables used by the RTL."""

from __future__ import annotations

import math
from pathlib import Path

TABLE_SIZE = 256
PEAK = 8191
TABLES = (
    (1.00, 0.55, 0.34, 0.23, 0.16, 0.11, 0.075, 0.05),
    (1.00, 0.50, 0.28, 0.16, 0.09),
    (1.00, 0.38, 0.16),
    (1.00,),
)


def build_table(coefficients: tuple[float, ...]) -> list[int]:
    raw = []
    for index in range(TABLE_SIZE):
        phase = 2.0 * math.pi * index / TABLE_SIZE
        value = sum(
            coefficient * math.sin((harmonic + 1) * phase)
            for harmonic, coefficient in enumerate(coefficients)
        )
        raw.append(value)
    scale = PEAK / max(abs(value) for value in raw)
    return [max(-8192, min(8191, round(value * scale))) for value in raw]


def signed_hex16(value: int) -> str:
    return f"{value & 0xFFFF:04x}"


def main() -> None:
    output = (
        Path(__file__).resolve().parent
        / "generated"
        / "wavetables"
        / "piano_band_4x256_8191.mem"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    words = [value for coefficients in TABLES for value in build_table(coefficients)]
    assert len(words) == 1024
    assert min(words) >= -8192 and max(words) <= 8191
    output.write_text("\n".join(map(signed_hex16, words)) + "\n", encoding="ascii")
    print(f"PASS: wrote {len(words)} words to {output}")


if __name__ == "__main__":
    main()

