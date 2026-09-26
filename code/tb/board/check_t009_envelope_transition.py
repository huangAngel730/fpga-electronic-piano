#!/usr/bin/env python3
"""Independent T009 envelope-transition acceptance gate for M1's Python model.

Run from the repository root. A nonzero exit means a real continuity defect;
this gate never changes the M1-owned reference model or generated vectors.
"""

import math
import sys
from pathlib import Path

MODEL = Path(__file__).resolve().parents[2] / "model"
if str(MODEL) not in sys.path:
    sys.path.insert(0, str(MODEL))

from adsr_piano import (  # noqa: E402
    ATTACK_SAMPLES,
    DECAY_SAMPLES,
    ENVELOPE_MAX,
    RELEASE_SAMPLES,
    PianoADSREnvelope,
    apply_envelope,
)

# Maximum gain rise of the existing 5 ms attack at full velocity, plus
# one integer LSB for quantization. A future different attack specification
# must revise this bound with M1's approval, not silently weaken the test.
ATTACK_STEP_BOUND = math.ceil(ENVELOPE_MAX / ATTACK_SAMPLES) + 1
FIXED_TEST_WAVE = 8192  # D028's single-voice wavetable peak, signed 16-bit.


def continuity_error(before: int, after: int, bound: int, label: str) -> str | None:
    if not 0 <= before <= ENVELOPE_MAX or not 0 <= after <= ENVELOPE_MAX:
        return f"{label}: envelope outside Q1.15 range ({before}->{after})"
    jump = abs(after - before)
    if jump > bound:
        return f"{label}: envelope jump {before}->{after}, delta={jump} > {bound}"
    return None


def evaluate() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    details: list[str] = []

    env = PianoADSREnvelope()
    env.note_on(velocity=1023)
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 1000):
        before = env.step()
    if before < 1000:
        errors.append("precondition: sustained note did not reach a nonzero level")

    env.note_off()
    after = env.step()
    release_bound = math.ceil(before / RELEASE_SAMPLES) + 1
    problem = continuity_error(before, after, release_bound, "Note Off")
    if problem:
        errors.append(problem)
    if after > before:
        errors.append("Note Off: release moved upward")
    details.append(f"Note Off: Q15 {before}->{after}, bound={release_bound}")

    for _ in range(RELEASE_SAMPLES // 2 - 1):
        release_before = env.step()
    if release_before < 1000 or env.get_state()[0] != "RELEASE":
        errors.append("precondition: not in a nonzero Release before retrigger")
    env.note_on(velocity=512)
    retrigger_after = env.step()
    problem = continuity_error(
        release_before, retrigger_after, ATTACK_STEP_BOUND, "Release retrigger"
    )
    if problem:
        errors.append(problem)
    # Use a fixed nonzero wavetable sample to isolate an envelope discontinuity
    # from an ordinary oscillator zero crossing. This is a diagnostic, not
    # a substitute for the eventual real waveform/analog-output measurement.
    pcm_before = apply_envelope(FIXED_TEST_WAVE, release_before) << 8
    pcm_after = apply_envelope(FIXED_TEST_WAVE, retrigger_after) << 8
    details.append(
        "Release retrigger: Q15 "
        f"{release_before}->{retrigger_after}, bound={ATTACK_STEP_BOUND}; "
        f"fixed-wave PCM24 {pcm_before}->{pcm_after}"
    )

    tail = PianoADSREnvelope()
    tail.note_on(velocity=1023)
    for _ in range(ATTACK_SAMPLES + DECAY_SAMPLES + 1000):
        tail.step()
    tail.note_off()
    previous = tail.get_state()[1]
    for index in range(RELEASE_SAMPLES):
        current = tail.step()
        if current > previous:
            errors.append(f"Release sample {index}: level rose {previous}->{current}")
            break
        previous = current
    if previous != 0 or tail.get_state()[0] != "IDLE":
        errors.append("Release tail: did not reach zero and IDLE by 4800 samples")
    details.append(f"Release tail: final Q15={previous}, state={tail.get_state()[0]}")
    return errors, details


def main() -> int:
    errors, details = evaluate()
    for line in details:
        print(line)
    if errors:
        for error in errors:
            print(f"FAIL T009: {error}", file=sys.stderr)
        return 1
    print("PASS T009: Note Off, retrigger and Release tail continuity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
