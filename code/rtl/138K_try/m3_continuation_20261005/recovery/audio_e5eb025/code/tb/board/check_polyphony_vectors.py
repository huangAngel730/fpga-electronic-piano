#!/usr/bin/env python3
"""M2 preflight of M1's T010 PCM vector, independent of RTL port names.

This checks the *coverage and encoding* of a vector. It cannot establish
four distinct sounding pitches or substitute for a sample-by-sample RTL test.
"""

import argparse
import sys
from pathlib import Path

DEFAULT_VECTOR = (
    Path(__file__).resolve().parents[2]
    / "model/generated/polyphony_test/polyphony_4voice.txt"
)
PCM_MIN = -(1 << 23)
PCM_MAX = (1 << 23) - 1


class VectorError(ValueError):
    """A malformed or insufficient integration vector."""


def check_vector(path: Path) -> tuple[int, int, int]:
    """Return (frames, peak_active_voices, audible_four_voice_frames)."""
    frames = 0
    peak_active = 0
    audible_four = 0
    with path.open("r", encoding="utf-8") as vector:
        for lineno, raw in enumerate(vector, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 8:
                raise VectorError(f"line {lineno}: expected 8 columns, got {len(fields)}")
            index, pcm_hex, pcm_text, *flags = fields
            try:
                sample_idx = int(index, 10)
                pcm = int(pcm_text, 10)
                encoded = int(pcm_hex, 16)
                bits = [int(flag, 10) for flag in flags]
            except ValueError as exc:
                raise VectorError(f"line {lineno}: invalid numeric field") from exc
            if sample_idx != frames:
                raise VectorError(f"line {lineno}: frame {sample_idx}, expected {frames}")
            if len(pcm_hex) != 6 or any(c not in "0123456789abcdefABCDEF" for c in pcm_hex):
                raise VectorError(f"line {lineno}: PCM hex must be six digits")
            if not PCM_MIN <= pcm <= PCM_MAX:
                raise VectorError(f"line {lineno}: signed PCM outside 24-bit range")
            if encoded != (pcm & 0xFFFFFF):
                raise VectorError(f"line {lineno}: PCM decimal/hex mismatch")
            if any(flag not in (0, 1) for flag in bits):
                raise VectorError(f"line {lineno}: active/clipped flags must be 0 or 1")
            active = sum(bits[:4])
            if bits[4] and pcm not in (PCM_MIN, PCM_MAX):
                raise VectorError(f"line {lineno}: clipping flag without saturated PCM")
            peak_active = max(peak_active, active)
            if active == 4 and pcm != 0:
                audible_four += 1
            frames += 1
    if frames == 0:
        raise VectorError("no PCM frames")
    if peak_active < 4 or audible_four == 0:
        raise VectorError(
            f"four-voice scenario absent: peak_active={peak_active}, "
            f"nonzero_four_voice_frames={audible_four}"
        )
    return frames, peak_active, audible_four


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vector", nargs="?", type=Path, default=DEFAULT_VECTOR)
    args = parser.parse_args(argv)
    try:
        frames, peak, audible = check_vector(args.vector)
    except (OSError, UnicodeError, VectorError) as exc:
        print(f"FAIL {args.vector}: {exc}", file=sys.stderr)
        return 1
    print(f"PASS {args.vector}: frames={frames}, peak_active={peak}, "
          f"nonzero_four_voice_frames={audible}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
