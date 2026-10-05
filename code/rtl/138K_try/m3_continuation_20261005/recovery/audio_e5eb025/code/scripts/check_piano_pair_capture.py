"""Compare actual formal sine/V1 captures with identical ADSR and velocity ROM.
Requires NumPy for least-squares spectrum decomposition; no synthetic PCM.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np


def read_capture(path):
    blocks = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields[0] == "BEGIN":
            current = fields[1]
            blocks[current] = {"count": int(fields[2]), "voices": int(fields[3]), "data": []}
        elif fields[0] == "PCM" and current:
            left, right, voices = map(int, fields[1:])
            if left != right or voices != blocks[current]["voices"] or not -8388608 <= left <= 8388607:
                raise ValueError("Invalid channel/voice/amplitude capture")
            blocks[current]["data"].append(left / 256.0)
        else:
            raise ValueError("Malformed capture")
    if {key: value["count"] for key, value in blocks.items()} != {
            "pair_attack": 1920, "pair_steady": 16384, "one_after_release": 8192}:
        raise ValueError("Incomplete capture sections")
    for value in blocks.values():
        if len(value["data"]) != value["count"]:
            raise ValueError("Incomplete PCM capture")
        value["data"] = np.asarray(value["data"], dtype=float)
    return blocks


def metrics(samples):
    f0 = 440 * 2 ** ((60 - 69) / 12)
    f1 = 440 * 2 ** ((61 - 69) / 12)
    n = np.arange(len(samples))
    columns = [np.ones(len(samples))]
    for f in [f0, f1]:
        columns.extend([np.sin(2 * np.pi * f * n / 48000), np.cos(2 * np.pi * f * n / 48000)])
    design = np.column_stack(columns)
    coefficients = np.linalg.lstsq(design, samples, rcond=None)[0]
    fundamental = design[:, 1:] @ coefficients[1:]
    power = float(np.mean((samples - np.mean(samples)) ** 2))
    dominance = float(np.mean(fundamental ** 2) / power)
    block = samples[:len(samples) // 256 * 256].reshape(-1, 256)
    rms = np.sqrt(np.mean(block ** 2, axis=1))
    modulation = float(np.std(rms) / np.mean(rms))
    magnitudes = [float(math.hypot(coefficients[1], coefficients[2])),
                  float(math.hypot(coefficients[3], coefficients[4]))]
    return {"fundamental_power_fraction": dominance, "block_RMS_coefficient_of_variation": modulation,
            "two_fundamental_amplitudes": magnitudes, "target_frequencies_hz": [f0, f1],
            "physical_difference_hz": f1 - f0, "sample_peak": float(np.max(np.abs(samples)))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sine", type=Path)
    parser.add_argument("piano", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline, piano = read_capture(args.sine), read_capture(args.piano)
    report = {"scope": "actual RTL PCM A/B; same source, events, formal ADSR/velocity ROM",
              "sine_capture_sha256": hashlib.sha256(args.sine.read_bytes()).hexdigest(),
              "piano_capture_sha256": hashlib.sha256(args.piano.read_bytes()).hexdigest(),
              "sine": metrics(baseline["pair_steady"]["data"]),
              "piano": metrics(piano["pair_steady"]["data"])}
    report["dominance_relative_reduction"] = 1 - report["piano"]["fundamental_power_fraction"] / report["sine"]["fundamental_power_fraction"]
    report["block_RMS_modulation_relative_reduction"] = 1 - report["piano"]["block_RMS_coefficient_of_variation"] / report["sine"]["block_RMS_coefficient_of_variation"]
    # Same gate as existing spectrum tests: both independent fundamentals must
    # remain present, not a subjective quality threshold or beat elimination.
    if min(report["piano"]["two_fundamental_amplitudes"]) < 100:
        raise ValueError("An adjacent fundamental disappeared")
    if report["dominance_relative_reduction"] <= 0:
        raise ValueError("V1 did not reduce pure-fundamental pair dominance")
    for name, block in [("sine", baseline), ("piano", piano)]:
        attack = block["pair_attack"]["data"]
        report[name]["attack_max_sample_step"] = float(np.max(np.abs(np.diff(attack))))
        report[name]["remaining_voice_nonzero_after_release"] = bool(np.max(np.abs(block["one_after_release"]["data"])) > 100)
        if not report[name]["remaining_voice_nonzero_after_release"]:
            raise ValueError("Independent Release killed remaining note")
    report["interpretation"] = "Both pitches remain; beat frequency persists. Metrics are digital comparison, not human listening or guaranteed no-click proof."
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PASS formal pair fundamentals preserved / remaining voice survives Release")
    print("Dominance relative reduction:", report["dominance_relative_reduction"])
    print("Block RMS modulation relative reduction:", report["block_RMS_modulation_relative_reduction"])
    print("Report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
