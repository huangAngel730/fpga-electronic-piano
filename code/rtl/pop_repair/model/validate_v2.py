#!/usr/bin/env python3
"""Quantitative V1/V2 comparison for the isolated beat-perception repair."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import wave
from dataclasses import dataclass
from pathlib import Path

import generate_wavetable_v2 as wavetable_v2
import validate_prototype as v1

SAMPLE_RATE = v1.SAMPLE_RATE
PHASE_SCALE = v1.PHASE_SCALE
PCM24_MIN = v1.PCM24_MIN
PCM24_MAX = v1.PCM24_MAX
V1_TABLES = v1.TABLES
V2_TABLES = tuple(
    tuple(
        wavetable_v2.build_table(magnitudes, signs)
        for magnitudes in wavetable_v2.TABLE_MAGNITUDES
    )
    for signs in wavetable_v2.LANE_SIGNS
)


def table_pair_v2(fcw: int) -> tuple[int, int]:
    if fcw <= 134_217_728:
        return 1, 0
    if fcw <= 268_435_456:
        return 2, 1
    if fcw <= 393_705_335:
        return 2, 2
    return 3, 3


def attack_length_v2(velocity: int, lane: int) -> int:
    return max(0, v1.attack_length(velocity) - lane * 48)


@dataclass
class Voice:
    lane: int
    mode: str
    note: int = 0
    velocity: int = 0
    phase: int = 0
    age: int = 0
    release_age: int | None = None
    release_start_q15: int = 0
    occupied: bool = False
    active_table: int = 3
    pending_table: int = 3
    table_change_pending: bool = False
    attack_left: int = 0

    def note_on(self, note: int, velocity: int) -> None:
        self.note = note
        self.velocity = velocity
        self.age = 0
        self.release_age = None
        self.release_start_q15 = 0
        self.occupied = True
        fcw = v1.note_fcw(note)
        if self.mode == "v1":
            body, attack = v1.table_pair(fcw)
            self.attack_left = v1.attack_length(velocity)
        else:
            body, attack = table_pair_v2(fcw)
            self.attack_left = attack_length_v2(velocity, self.lane)
        self.active_table = attack if self.attack_left else body
        self.pending_table = body
        self.table_change_pending = False

    def envelope_q15(self) -> int:
        if not self.occupied:
            return 0
        gain = v1.q15_velocity(self.velocity)
        if self.age < v1.ATTACK_SAMPLES:
            level = gain * (self.age + 1) // v1.ATTACK_SAMPLES
        elif self.age < v1.ATTACK_SAMPLES + v1.DECAY_SAMPLES:
            decay_age = self.age - v1.ATTACK_SAMPLES
            level = gain + (gain * 2 // 5 - gain) * decay_age // v1.DECAY_SAMPLES
        else:
            sustain_age = self.age - v1.ATTACK_SAMPLES - v1.DECAY_SAMPLES
            level = round((gain * 0.4) * math.exp(-sustain_age / (SAMPLE_RATE * 2.5)))
        if self.release_age is not None:
            remaining = max(0, v1.RELEASE_SAMPLES - self.release_age)
            level = self.release_start_q15 * remaining // v1.RELEASE_SAMPLES
        return max(0, min(32767, level))

    def note_off(self) -> None:
        if self.occupied and self.release_age is None:
            self.release_start_q15 = self.envelope_q15()
            self.release_age = 0

    def sample(self) -> int:
        if not self.occupied:
            return 0
        fcw = v1.note_fcw(self.note)
        tables = V1_TABLES if self.mode == "v1" else V2_TABLES[self.lane]
        wave_sample = tables[self.active_table][(self.phase >> 24) & 0xFF]
        pcm16 = (wave_sample * self.envelope_q15()) >> 15
        next_phase = (self.phase + fcw) & 0xFFFF_FFFF
        phase_wrap = next_phase < self.phase
        self.phase = next_phase
        if self.table_change_pending and phase_wrap:
            self.active_table = self.pending_table
            self.table_change_pending = False
        elif self.attack_left:
            self.attack_left -= 1
            if self.attack_left == 0:
                body = (v1.table_pair(fcw) if self.mode == "v1" else table_pair_v2(fcw))[0]
                if phase_wrap:
                    self.active_table = body
                else:
                    self.pending_table = body
                    self.table_change_pending = True
        self.age += 1
        if self.release_age is not None:
            self.release_age += 1
            if self.release_age >= v1.RELEASE_SAMPLES:
                self.occupied = False
        return pcm16 << 8


class Engine:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.voices = [Voice(lane=lane, mode=mode) for lane in range(4)]
        self.clip_count = 0
        self.max_accumulator = 0

    def note_on(self, slot: int, note: int, velocity: int) -> None:
        self.voices[slot].note_on(note, velocity)

    def note_off(self, slot: int) -> None:
        self.voices[slot].note_off()

    def step(self) -> int:
        accumulator = sum(voice.sample() for voice in self.voices)
        self.max_accumulator = max(self.max_accumulator, abs(accumulator))
        pcm, clipped = v1.saturate_pcm24(accumulator)
        self.clip_count += int(clipped)
        return pcm


def render(mode: str, notes: tuple[int, ...], velocity: int, count: int) -> tuple[list[int], Engine]:
    engine = Engine(mode)
    for lane, note in enumerate(notes):
        engine.note_on(lane, note, velocity)
    return [engine.step() for _ in range(count)], engine


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


def scenario_metrics(samples: list[int], notes: tuple[int, ...], clip_count: int) -> dict[str, object]:
    start = SAMPLE_RATE // 2
    stop = start + SAMPLE_RATE
    steady = samples[start:stop]
    signal_rms = v1.rms(steady)
    powers = {
        str(note): v1.goertzel_power(steady, v1.midi_frequency(note))
        for note in notes
    }
    total = sum(value * value for value in steady) * len(steady)
    return {
        "envelope_modulation": v1.envelope_modulation(steady),
        "peak_abs_pcm24": max(abs(value) for value in samples),
        "rms_pcm24": signal_rms,
        "dc_to_rms": abs(statistics.mean(steady)) / max(1.0, signal_rms),
        "clip_count": clip_count,
        "fundamental_powers": powers,
        "fundamental_share": sum(powers.values()) / max(1.0, total),
    }


def require(condition: bool, name: str, detail: str, checks: list[dict[str, str]]) -> None:
    if not condition:
        raise AssertionError(f"FAIL {name}: {detail}")
    print(f"PASS {name}: {detail}")
    checks.append({"name": name, "status": "PASS", "details": detail})


def validate(output_dir: Path) -> dict[str, object]:
    checks: list[dict[str, str]] = []
    scenarios = {
        "low_adjacent_c3_cs3": (48, 49),
        "mid_adjacent_c4_cs4": (60, 61),
        "upper_adjacent_c5_cs5": (72, 73),
        "high_adjacent_c6_cs6": (84, 85),
        "very_high_adjacent_c7_cs7": (96, 97),
        "top_adjacent_b7_c8": (107, 108),
        "major_second_c4_d4": (60, 62),
        "major_third_c4_e4": (60, 64),
        "four_voice_cluster": (60, 61, 64, 67),
        "four_voice_upper": (72, 73, 76, 79),
    }
    duration = 2 * SAMPLE_RATE
    comparison: dict[str, object] = {}
    adjacent_improvements = []
    rms_ratios = []
    min_fundamental_ratio = float("inf")
    min_rms_ratio = float("inf")
    max_dc_ratio = 0.0
    max_partial = 0.0
    max_accumulator = 0

    for name, notes in scenarios.items():
        v1_samples, v1_engine = render("v1", notes, 850, duration)
        v2_samples, v2_engine = render("v2", notes, 850, duration)
        v1_metrics = scenario_metrics(v1_samples, notes, v1_engine.clip_count)
        v2_metrics = scenario_metrics(v2_samples, notes, v2_engine.clip_count)
        improvement = 1.0 - (
            float(v2_metrics["envelope_modulation"])
            / max(1e-12, float(v1_metrics["envelope_modulation"]))
        )
        fundamental_ratios = {
            str(note): float(v2_metrics["fundamental_powers"][str(note)])
            / max(1.0, float(v1_metrics["fundamental_powers"][str(note)]))
            for note in notes
        }
        min_fundamental_ratio = min(min_fundamental_ratio, *fundamental_ratios.values())
        rms_ratio = float(v2_metrics["rms_pcm24"]) / max(1.0, float(v1_metrics["rms_pcm24"]))
        rms_ratios.append(rms_ratio)
        min_rms_ratio = min(min_rms_ratio, rms_ratio)
        max_dc_ratio = max(max_dc_ratio, float(v1_metrics["dc_to_rms"]), float(v2_metrics["dc_to_rms"]))
        max_accumulator = max(max_accumulator, v1_engine.max_accumulator, v2_engine.max_accumulator)
        if "adjacent" in name:
            adjacent_improvements.append(improvement)
        comparison[name] = {
            "notes": list(notes),
            "v1": v1_metrics,
            "v2": v2_metrics,
            "envelope_modulation_reduction": improvement,
            "v2_to_v1_fundamental_power": fundamental_ratios,
        }
        print(
            f"INFO {name}: modulation {v1_metrics['envelope_modulation']:.4f} -> "
            f"{v2_metrics['envelope_modulation']:.4f} ({improvement:+.1%})"
        )
        if name == "mid_adjacent_c4_cs4":
            write_wav(output_dir / "adjacent_c4_cs4_v1.wav", v1_samples)
            write_wav(output_dir / "adjacent_c4_cs4_v2.wav", v2_samples)
        if name == "four_voice_cluster":
            write_wav(output_dir / "four_voice_cluster_v1.wav", v1_samples)
            write_wav(output_dir / "four_voice_cluster_v2.wav", v2_samples)

    max_cents = 0.0
    for note in range(21, 109):
        actual = v1.note_fcw(note) * SAMPLE_RATE / PHASE_SCALE
        max_cents = max(max_cents, abs(1200.0 * math.log2(actual / v1.midi_frequency(note))))
        _, attack_table = table_pair_v2(v1.note_fcw(note))
        max_partial = max(
            max_partial,
            v1.midi_frequency(note) * len(wavetable_v2.TABLE_MAGNITUDES[attack_table]),
        )

    c4_improvement = float(comparison["mid_adjacent_c4_cs4"]["envelope_modulation_reduction"])
    median_adjacent = statistics.median(adjacent_improvements)
    median_rms_ratio = statistics.median(rms_ratios)
    all_clips = sum(
        int(item[version]["clip_count"])
        for item in comparison.values()
        for version in ("v1", "v2")
    )
    require(max_cents < 0.001, "pitch", f"MIDI 21..108 max FCW error {max_cents:.6f} cents", checks)
    require(min_fundamental_ratio > 0.10, "fundamentals",
            f"all tested fundamentals retained; minimum V2/V1 power ratio {min_fundamental_ratio:.3f}", checks)
    require(min_rms_ratio > 0.80 and median_rms_ratio > 0.95, "level_fairness",
            f"minimum/median V2-to-V1 steady RMS ratio {min_rms_ratio:.3f}/{median_rms_ratio:.3f}; improvement is not global attenuation", checks)
    require(c4_improvement > 0.05, "c4_cs4",
            f"V2 envelope modulation reduction {c4_improvement:.1%}", checks)
    require(median_adjacent > 0.05, "multi_register_adjacent",
            f"median across six adjacent-note registers {median_adjacent:.1%}", checks)
    require(max_dc_ratio < 0.01, "dc", f"maximum |DC|/RMS {max_dc_ratio:.6f}", checks)
    require(max_partial < SAMPLE_RATE / 2, "alias_guard",
            f"maximum enabled attack partial {max_partial:.1f} Hz < 24000 Hz", checks)
    require(all_clips == 0 and max_accumulator < (1 << 31), "clip_and_width",
            f"all scenarios unclipped; max 32-bit accumulator magnitude {max_accumulator}", checks)
    require(len(Engine("v2").voices) == 4, "polyphony", "four independent voices remain enabled", checks)

    report = {
        "version": "V2",
        "sample_rate_hz": SAMPLE_RATE,
        "checks": checks,
        "summary": {
            "max_pitch_error_cents": max_cents,
            "c4_cs4_envelope_modulation_reduction": c4_improvement,
            "median_adjacent_envelope_modulation_reduction": median_adjacent,
            "minimum_v2_to_v1_fundamental_power": min_fundamental_ratio,
            "minimum_v2_to_v1_rms": min_rms_ratio,
            "median_v2_to_v1_rms": median_rms_ratio,
            "maximum_dc_to_rms": max_dc_ratio,
            "maximum_attack_partial_hz": max_partial,
            "maximum_accumulator_magnitude": max_accumulator,
            "clip_count_all_scenarios": all_clips,
        },
        "scenarios": comparison,
        "interpretation": (
            "V2 retains exact FCWs and every tested fundamental. It changes upper-partial "
            "magnitudes and lane-specific 0/pi phases, plus slightly staggers harmonic attack "
            "decay. Physical difference-frequency beating remains; only its perceptual dominance "
            "is reduced."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "validation_v2.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS report: {report_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "output" / "v2",
    )
    args = parser.parse_args()
    validate(args.output.resolve())


if __name__ == "__main__":
    main()
