#!/usr/bin/env python3
"""Read actual-core PCM and verify four tones, release isolation and velocity.

Only standard-library analysis. This is simulated core-output evidence, not
T052 on-board FFT, pure instrument sound quality or physical latency proof.
"""
from pathlib import Path
import argparse
import json
import math
import statistics

SAMPLE_RATE = 48000
NOTES = (57, 62, 68, 73)

def read_capture(path):
    blocks = {}
    active = None
    expected = 0
    voices = 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split()
        if len(fields) == 4 and fields[0] == "BEGIN":
            if active is not None and len(blocks[active]) != expected:
                raise ValueError(f"Incomplete block {active}")
            active = fields[1]
            if active in blocks:
                raise ValueError(f"Duplicate block {active}")
            expected, voices = int(fields[2]), int(fields[3])
            blocks[active] = []
        elif len(fields) == 4 and fields[0] == "PCM" and active is not None:
            left, right, occupied = map(int, fields[1:])
            if left != right or occupied != voices or not -8388608 <= left <= 8388607:
                raise ValueError(f"Invalid stereo/voice/amplitude row {number}")
            blocks[active].append(left / 256.0)
        else:
            raise ValueError(f"Malformed capture row {number}")
    if active is None or len(blocks[active]) != expected:
        raise ValueError("Incomplete final block")
    lengths = {"four_notes": 32768, "three_after_release": 16384,
               "soft_a4": 16384, "hard_a4": 16384}
    if {name: len(values) for name, values in blocks.items()} != lengths:
        raise ValueError("Unexpected capture sections or lengths")
    return blocks

def frequency(note):
    return 440.0 * 2.0 ** ((note - 69) / 12.0)

def prepare(samples):
    n = len(samples)
    mean = statistics.fmean(samples)
    return [(value - mean) * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)))
            for i, value in enumerate(samples)]

def magnitude(windowed, bin_number):
    angle = -2.0 * math.pi * bin_number / len(windowed)
    rotate = complex(math.cos(angle), math.sin(angle))
    phase = 1.0 + 0.0j
    value = 0.0 + 0.0j
    for sample in windowed:
        value += sample * phase
        phase *= rotate
    return abs(value)

def tone(windowed, wanted):
    target = wanted * len(windowed) / SAMPLE_RATE
    center = round(target)
    bins = {index: magnitude(windowed, index) for index in range(center - 3, center + 4)}
    peak = max(range(center - 2, center + 3), key=lambda index: bins[index])
    left, middle, right = [math.log(max(bins[index], 1e-30)) for index in (peak - 1, peak, peak + 1)]
    denominator = left - 2.0 * middle + right
    offset = 0.5 * (left - right) / denominator if denominator else 0.0
    measured = (peak + offset) * SAMPLE_RATE / len(windowed)
    error_cents = 1200.0 * math.log2(measured / wanted)
    return {"target_hz": wanted, "measured_hz": measured,
            "error_cents": error_cents, "nearby_peak_magnitude": bins[peak]}

def analyze(blocks):
    full = prepare(blocks["four_notes"])
    released = prepare(blocks["three_after_release"])
    four = [tone(full, frequency(note)) for note in NOTES]
    three = [tone(released, frequency(note)) for note in NOTES]
    strongest = max(row["nearby_peak_magnitude"] for row in four)
    for note, row in zip(NOTES, four):
        relative_db = 20.0 * math.log10(max(row["nearby_peak_magnitude"], 1e-30) / strongest)
        row.update({"note": note, "relative_peak_db": relative_db})
        if abs(row["error_cents"]) > 1.0 or relative_db < -12.0:
            raise ValueError(f"Four-tone capability missing or wrong note {note}: {row}")
    # Absent A3 neighbourhood compared with weakest remaining tone: do not
    # interpolate an absent noise peak and treat it as a meaningful pitch.
    remaining_min = min(row["nearby_peak_magnitude"] for row in three[1:])
    absent_db = 20.0 * math.log10(max(three[0]["nearby_peak_magnitude"], 1e-30) / remaining_min)
    if absent_db > -40.0:
        raise ValueError(f"Released A3 still audible in simulated PCM spectrum: {absent_db}dB")
    for note, row in zip(NOTES[1:], three[1:]):
        row["note"] = note
        if abs(row["error_cents"]) > 1.0:
            raise ValueError(f"Held voice changed pitch after another Note Off: {row}")
    soft, hard = blocks["soft_a4"], blocks["hard_a4"]
    rms = lambda data: math.sqrt(statistics.fmean(value * value for value in data))
    actual_ratio = rms(soft) / rms(hard)
    target_ratio = int(32767 * (0.2 + 0.8 * (128 / 1023) ** 2)) / 32767
    if abs(actual_ratio / target_ratio - 1.0) > 0.005:
        raise ValueError(f"Velocity gain mismatch {actual_ratio} vs {target_ratio}")
    pitches = {name: tone(prepare(values), 440.0) for name, values in [("soft", soft), ("hard", hard)]}
    if any(abs(row["error_cents"]) > 1.0 for row in pitches.values()):
        raise ValueError("Velocity incorrectly affects pitch")
    return {"scope": "actual four-lane RTL PCM simulation; no board FFT or T052 implementation",
            "sample_rate_interpretation_hz": SAMPLE_RATE,
            "analysis": "Hann-weighted DTFT nearby bins plus log-parabolic peak interpolation",
            "criteria": {"pitch_error_cents_max": 1.0, "four_peaks_relative_db_min": -12.0,
                         "released_tone_relative_db_max": -40.0, "velocity_ratio_relative_error_max": 0.005},
            "four_note_peaks": four, "remaining_three_peaks": three[1:],
            "released_note57_vs_remaining_db": absent_db,
            "velocity": {"soft": 128, "hard": 1023, "rms_soft": rms(soft), "rms_hard": rms(hard),
                         "measured_rms_ratio": actual_ratio, "model_gain_ratio": target_ratio,
                         "measured_gain_db": 20.0 * math.log10(actual_ratio), "pitches": pitches}}

def negative_checks(blocks):
    failures = {}
    # Explicit synthetic mutations of analysis inputs, never the accepted
    # RTL capture. A forged voice count4 cannot substitute for four tones.
    missing_voice = dict(blocks)
    missing_voice["four_notes"] = [
        sum(1000.0 * math.sin(2.0 * math.pi * frequency(note) * i / SAMPLE_RATE)
            for note in NOTES[1:]) for i in range(len(blocks["four_notes"]))
    ]
    equal_velocity = dict(blocks)
    equal_velocity["soft_a4"] = list(blocks["hard_a4"])
    for name, altered in [("missing_one_tone", missing_voice), ("velocity_ignored", equal_velocity)]:
        try:
            analyze(altered)
        except ValueError as error:
            failures[name] = str(error)
        else:
            raise ValueError(f"Analysis negative check falsely passed: {name}")
    return failures

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--negative-tests", action="store_true", help="Reject missing-tone and ignored-velocity input mutations")
    args = parser.parse_args()
    blocks = read_capture(args.capture)
    result = analyze(blocks)
    if args.negative_tests:
        result["negative_checks_rejected"] = negative_checks(blocks)
        print("PASS missing-tone and ignored-velocity mutations rejected")
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in result["four_note_peaks"]:
        print(f"PASS note{row['note']} {row['measured_hz']:.4f}Hz error{row['error_cents']:+.3f}cent")
    print(f"PASS released tone isolation {result['released_note57_vs_remaining_db']:.2f}dB")
    print(f"PASS velocity RMS ratio {result['velocity']['measured_rms_ratio']:.6f}, model {result['velocity']['model_gain_ratio']:.6f}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print("FAIL T024 audio capabilities:", error)
        raise SystemExit(1)