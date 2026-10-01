#!/usr/bin/env python3
"""Search lane-1 upper-partial signs against several adjacent-note registers."""

from __future__ import annotations

import itertools
import statistics

import generate_wavetable_v2 as generator
import validate_v2 as model


def modulation(mode: str, notes: tuple[int, int]) -> float:
    samples, _ = model.render(mode, notes, 850, model.SAMPLE_RATE)
    return model.v1.envelope_modulation(samples[model.SAMPLE_RATE // 4:])


def main() -> None:
    pairs = ((48, 49), (60, 61), (72, 73), (84, 85), (96, 97))
    v1_values = {pair: modulation("v1", pair) for pair in pairs}
    original = model.V2_TABLES
    candidates = []
    try:
        # Steady piano-range bodies use at most the seven-partial table, so
        # only harmonics 2..7 affect this search.  Attack-only signs 8..10 are
        # left positive and evaluated later by the full transient model.
        for upper_signs in itertools.product((-1, 1), repeat=6):
            signs = (1,) + upper_signs + (1, 1, 1)
            lane1 = tuple(
                generator.build_table(magnitudes, signs)
                for magnitudes in generator.TABLE_MAGNITUDES
            )
            model.V2_TABLES = (original[0], lane1, original[2], original[3])
            improvements = [
                1.0 - modulation("v2", pair) / v1_values[pair]
                for pair in pairs
            ]
            score = min(improvements) + 0.5 * statistics.mean(improvements)
            candidates.append((score, min(improvements), statistics.mean(improvements), signs, improvements))
    finally:
        model.V2_TABLES = original
    for item in sorted(candidates, reverse=True)[:12]:
        score, worst, mean, signs, improvements = item
        formatted = ", ".join(f"{value:+.1%}" for value in improvements)
        print(f"score={score:+.4f} worst={worst:+.1%} mean={mean:+.1%} signs={signs} [{formatted}]")


if __name__ == "__main__":
    main()
