#!/usr/bin/env python3
"""Deterministic independent golden vectors from M1's Python mixer model."""

import random
import sys
from pathlib import Path

MODEL = Path(__file__).resolve().parents[2] / "model"
sys.path.insert(0, str(MODEL))
from mixer import mix_voices  # noqa: E402

PCM_MAX = (1 << 23) - 1
PCM_MIN = -(1 << 23)


def samples():
    p = 2_097_152
    # Zero, D028 one-LSB positive clip, exact negative limit,
    # negative overflow, independent stereo, exact boundary and cancellation.
    yield [0] * 4, [0] * 4
    yield [p] * 4, [-p] * 4
    yield [-p - 1] * 4, [p - 1] * 4
    yield [PCM_MAX] * 4, [PCM_MIN] * 4
    yield [PCM_MAX - 1, 1, 0, 0], [PCM_MIN + 1, -1, 0, 0]
    yield [PCM_MAX - 1, 2, 0, 0], [PCM_MIN + 1, -2, 0, 0]
    yield [PCM_MAX, PCM_MIN, 1, 0], [PCM_MIN, PCM_MAX, -1, 0]
    yield [4_000_000, -3_000_000, 2_000_000, -1_000_000], [1, -1, 2, -2]
    rng = random.Random(0x23A5)
    for _ in range(3000):
        yield ([rng.randint(PCM_MIN, PCM_MAX) for _ in range(4)],
               [rng.randint(PCM_MIN, PCM_MAX) for _ in range(4)])


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate_pcm_mixer_vectors.py OUTPUT_PATH")
    path = Path(sys.argv[1])
    count = 0
    with path.open("w", encoding="ascii", newline="\n") as target:
        for left, right in samples():
            result_left, clip_left = mix_voices(left)
            result_right, clip_right = mix_voices(right)
            words = left + right + [result_left, result_right]
            row = " ".join(f"{word & 0xffffff:06x}" for word in words)
            target.write(f"{row} {int(clip_left)} {int(clip_right)} "
                         f"{int(clip_left or clip_right)}\n")
            count += 1
    print(f"PASS generated {count} stereo reference frames: {path}")


if __name__ == "__main__":
    main()
