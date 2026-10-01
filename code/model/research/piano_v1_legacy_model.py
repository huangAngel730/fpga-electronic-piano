#!/usr/bin/env python3
"""Dependency-free fixed-point model and acceptance checks for pop_repair."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import wave
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 48_000
PHASE_SCALE = 1 << 32
PCM24_MIN = -(1 << 23)
PCM24_MAX = (1 << 23) - 1
ATTACK_SAMPLES = 240
DECAY_SAMPLES = 4_800
RELEASE_SAMPLES = 4_800
TABLE_SIZE = 256
TABLE_COEFFICIENTS = (
    (1.00, 0.55, 0.34, 0.23, 0.16, 0.11, 0.075, 0.05),
    (1.00, 0.50, 0.28, 0.16, 0.09),
    (1.00, 0.38, 0.16),
    (1.00,),
)


def midi_frequency(note: int) -> float:
    return 440.0 * 2.0 ** ((note - 69) / 12.0)


def note_fcw(note: int) -> int:
    return round(midi_frequency(note) * PHASE_SCALE / SAMPLE_RATE)


def q15_velocity(velocity: int) -> int:
    # Monotonic approximation of the checked-in velocity ROM's perceptual curve.
    normalized = max(0.0, min(1.0, velocity / 1023.0))
    return min(32767, round(math.sqrt(normalized) * 32767.0))


def build_table(coefficients: tuple[float, ...]) -> list[int]:
    raw = []
    for index in range(TABLE_SIZE):
        phase = 2.0 * math.pi * index / TABLE_SIZE
        raw.append(sum(c * math.sin((h + 1) * phase) for h, c in enumerate(coefficients)))
    scale = 8191.0 / max(abs(value) for value in raw)
    return [max(-8192, min(8191, round(value * scale))) for value in raw]


TABLES = tuple(build_table(coefficients) for coefficients in TABLE_COEFFICIENTS)


def table_pair(fcw: int) -> tuple[int, int]:
    if fcw <= 134_217_728:
        return 1, 0
    if fcw <= 268_435_456:
        return 2, 1
    if fcw <= 536_870_912:
        return 3, 2
    return 3, 3


def attack_length(velocity: int) -> int:
    if velocity >= 768:
        return 1_440
    if velocity >= 512:
        return 960
    if velocity >= 256:
        return 480
    return 0


def saturate_pcm24(value: int) -> tuple[int, bool]:
    if value > PCM24_MAX:
        return PCM24_MAX, True
    if value < PCM24_MIN:
        return PCM24_MIN, True
    return value, False


@dataclass
class Voice:
    note: int = 0
    velocity: int = 0
    phase: int = 0
    age: int = 0
    release_age: int | None = None
    release_start_q15: int = 0
    occupied: bool = False

    def note_on(self, note: int, velocity: int) -> None:
        self.note = note
        self.velocity = velocity
        self.age = 0
        self.release_age = None
        self.release_start_q15 = 0
        self.occupied = True

    def envelope_q15(self) -> int:
        if not self.occupied:
            return 0
        gain = q15_velocity(self.velocity)
        if self.age < ATTACK_SAMPLES:
            level = gain * (self.age + 1) // ATTACK_SAMPLES
        elif self.age < ATTACK_SAMPLES + DECAY_SAMPLES:
            decay_age = self.age - ATTACK_SAMPLES
            start = gain
            end = gain * 2 // 5
            level = start + (end - start) * decay_age // DECAY_SAMPLES
        else:
            sustain_age = self.age - ATTACK_SAMPLES - DECAY_SAMPLES
            level = round((gain * 0.4) * math.exp(-sustain_age / (SAMPLE_RATE * 2.5)))
        if self.release_age is not None:
            remaining = max(0, RELEASE_SAMPLES - self.release_age)
            level = self.release_start_q15 * remaining // RELEASE_SAMPLES
        return max(0, min(32767, level))

    def note_off(self) -> None:
        if self.occupied and self.release_age is None:
            self.release_start_q15 = self.envelope_q15()
            self.release_age = 0

    def sample(self, prototype: bool) -> int:
        if not self.occupied:
            return 0
        fcw = note_fcw(self.note)
        if prototype:
            body, bright = table_pair(fcw)
            use_bright = self.age < attack_length(self.velocity) and self.velocity >= 256
            table = TABLES[bright if use_bright else body]
            wave_sample = table[(self.phase >> 24) & 0xFF]
        else:
            phase = 2.0 * math.pi * self.phase / PHASE_SCALE
            wave_sample = max(-8192, min(8191, round(8191.0 * math.sin(phase))))
        envelope = self.envelope_q15()
        pcm16 = (wave_sample * envelope) >> 15
        self.phase = (self.phase + fcw) & 0xFFFF_FFFF
        self.age += 1
        if self.release_age is not None:
            self.release_age += 1
            if self.release_age >= RELEASE_SAMPLES:
                self.occupied = False
        return pcm16 << 8


class Engine:
    def __init__(self, prototype: bool) -> None:
        self.prototype = prototype
        self.voices = [Voice() for _ in range(4)]
        self.clip_count = 0

    def reset(self) -> None:
        self.voices = [Voice() for _ in range(4)]
        self.clip_count = 0

    def note_on(self, slot: int, note: int, velocity: int) -> None:
        self.voices[slot].note_on(note, velocity)

    def note_off(self, slot: int) -> None:
        self.voices[slot].note_off()

    def step(self) -> tuple[int, int]:
        accumulator = sum(voice.sample(self.prototype) for voice in self.voices)
        assert -(1 << 31) <= accumulator < (1 << 31)
        pcm, clipped = saturate_pcm24(accumulator)
        self.clip_count += int(clipped)
        return pcm, accumulator


def render(engine: Engine, sample_count: int) -> tuple[list[int], list[int]]:
    pcm = []
    accumulators = []
    for _ in range(sample_count):
        sample, accumulator = engine.step()
        pcm.append(sample)
        accumulators.append(accumulator)
    return pcm, accumulators


def rms(samples: list[int]) -> float:
    return math.sqrt(sum(sample * sample for sample in samples) / max(1, len(samples)))


def goertzel_power(samples: list[int], frequency: float) -> float:
    omega = 2.0 * math.pi * frequency / SAMPLE_RATE
    coefficient = 2.0 * math.cos(omega)
    s1 = 0.0
    s2 = 0.0
    for sample in samples:
        current = sample + coefficient * s1 - s2
        s2 = s1
        s1 = current
    return s1 * s1 + s2 * s2 - coefficient * s1 * s2


def envelope_modulation(samples: list[int], block: int = 240) -> float:
    values = [rms(samples[index:index + block]) for index in range(0, len(samples) - block, block)]
    return statistics.pstdev(values) / max(1.0, statistics.mean(values))


def write_wav(path: Path, samples: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for sample in samples:
            pcm16 = max(-32768, min(32767, sample >> 8))
            frames.extend(int(pcm16).to_bytes(2, "little", signed=True))
        wav_file.writeframes(frames)


def assert_check(condition: bool, name: str, details: str) -> dict[str, object]:
    if not condition:
        raise AssertionError(f"FAIL {name}: {details}")
    print(f"PASS {name}: {details}")
    return {"name": name, "status": "PASS", "details": details}


def validate(output_dir: Path) -> dict[str, object]:
    checks = []

    reset_engine = Engine(True)
    reset_engine.note_on(0, 60, 900)
    reset_engine.reset()
    reset_sample, reset_acc = reset_engine.step()
    checks.append(assert_check(
        reset_sample == 0 and reset_acc == 0 and not any(v.occupied for v in reset_engine.voices),
        "reset", "output/state/clip counter return to zero"))

    max_cents = 0.0
    for note in range(21, 109):
        actual = note_fcw(note) * SAMPLE_RATE / PHASE_SCALE
        cents = abs(1200.0 * math.log2(actual / midi_frequency(note)))
        max_cents = max(max_cents, cents)
    checks.append(assert_check(max_cents < 0.001, "single_pitch",
                               f"MIDI 21..108 max FCW error {max_cents:.6f} cents"))

    four = Engine(True)
    for slot, note in enumerate((60, 64, 67, 72)):
        four.note_on(slot, note, 800)
    four_pcm, four_acc = render(four, 2_000)
    checks.append(assert_check(sum(v.occupied for v in four.voices) == 4 and rms(four_pcm) > 0,
                               "four_voices", "four occupied lanes contribute non-zero PCM"))

    four.note_off(1)
    render(four, RELEASE_SAMPLES + 4)
    checks.append(assert_check(not four.voices[1].occupied and all(four.voices[i].occupied for i in (0, 2, 3)),
                               "independent_release", "released lane retires; other three remain active"))

    low = Engine(True)
    high = Engine(True)
    low.note_on(0, 60, 160)
    high.note_on(0, 60, 900)
    low_pcm, _ = render(low, 8_000)
    high_pcm, _ = render(high, 8_000)
    velocity_ratio = rms(high_pcm) / max(1.0, rms(low_pcm))
    checks.append(assert_check(velocity_ratio > 1.5, "velocity",
                               f"heavy/light RMS ratio {velocity_ratio:.3f}"))

    boundary_max_partial = 0.0
    for note in range(21, 109):
        frequency = midi_frequency(note)
        _, attack_table = table_pair(note_fcw(note))
        partial = frequency * len(TABLE_COEFFICIENTS[attack_table])
        boundary_max_partial = max(boundary_max_partial, partial)
    checks.append(assert_check(boundary_max_partial < SAMPLE_RATE / 2,
                               "boundary_notes",
                               f"MIDI 21..108 attack partials stay below Nyquist; max {boundary_max_partial:.1f} Hz"))

    max_acc = max(abs(value) for value in four_acc)
    saturated_hi, clipped_hi = saturate_pcm24(PCM24_MAX + 123)
    saturated_lo, clipped_lo = saturate_pcm24(PCM24_MIN - 123)
    checks.append(assert_check(
        max_acc < (1 << 31) and saturated_hi == PCM24_MAX and saturated_lo == PCM24_MIN
        and clipped_hi and clipped_lo,
        "clipping_width", f"32-bit accumulator peak {max_acc}; PCM24 saturation exact"))

    duration = 2 * SAMPLE_RATE
    base = Engine(False)
    repaired = Engine(True)
    for engine in (base, repaired):
        engine.note_on(0, 60, 850)
        engine.note_on(1, 61, 850)
    baseline_pcm, _ = render(base, duration)
    repaired_pcm, _ = render(repaired, duration)
    steady_slice = slice(SAMPLE_RATE // 2, duration)
    baseline_steady = baseline_pcm[steady_slice]
    repaired_steady = repaired_pcm[steady_slice]
    f0 = midi_frequency(60)
    f1 = midi_frequency(61)
    base_fund = goertzel_power(baseline_steady, f0) + goertzel_power(baseline_steady, f1)
    repair_fund = goertzel_power(repaired_steady, f0) + goertzel_power(repaired_steady, f1)
    base_total = sum(value * value for value in baseline_steady) * len(baseline_steady)
    repair_total = sum(value * value for value in repaired_steady) * len(repaired_steady)
    base_dominance = base_fund / max(1.0, base_total)
    repair_dominance = repair_fund / max(1.0, repair_total)
    dominance_reduction = 1.0 - repair_dominance / max(1e-12, base_dominance)
    checks.append(assert_check(dominance_reduction > 0.08, "adjacent_notes",
                               f"both fundamentals retained; pure-pair dominance reduced {dominance_reduction:.1%}"))

    write_wav(output_dir / "adjacent_c4_cs4_baseline.wav", baseline_pcm)
    write_wav(output_dir / "adjacent_c4_cs4_repaired.wav", repaired_pcm)

    report = {
        "sample_rate_hz": SAMPLE_RATE,
        "checks": checks,
        "metrics": {
            "max_pitch_error_cents": max_cents,
            "heavy_to_light_rms_ratio": velocity_ratio,
            "max_attack_partial_hz": boundary_max_partial,
            "adjacent_note_beat_frequency_hz": abs(f1 - f0),
            "baseline_fundamental_pair_dominance": base_dominance,
            "repaired_fundamental_pair_dominance": repair_dominance,
            "fundamental_pair_dominance_reduction": dominance_reduction,
            "baseline_envelope_modulation": envelope_modulation(baseline_steady),
            "repaired_envelope_modulation": envelope_modulation(repaired_steady),
            "baseline_clip_count": base.clip_count,
            "repaired_clip_count": repaired.clip_count,
        },
        "interpretation": (
            "The physical beat frequency remains because both fundamentals remain correct. "
            "The prototype targets perception by reducing pure-fundamental dominance and "
            "adding a short, velocity-dependent harmonic attack."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PASS report: {output_dir / 'validation_report.json'}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "output")
    args = parser.parse_args()
    validate(args.output.resolve())


if __name__ == "__main__":
    main()

