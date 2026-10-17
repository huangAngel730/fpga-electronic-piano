"""Preserve historical A bytes and derive an independent fixed-left oracle."""
from pathlib import Path
from decimal import Decimal
import base64
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def main():
    raw_dir = ROOT / "code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence"
    reference = ROOT / "code/tb/input/pcm_waveform_candidate/reference.py"
    spec = importlib.util.spec_from_file_location("old_reference", reference)
    ref = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref)
    real, source = ref.sealed_samples("normal")
    raw = base64.b64decode((raw_dir / "normal_capture.b64").read_bytes())
    write(HERE / "normal_capture.original.txt", raw.decode("utf-8"))
    stamps = [Decimal(line.split()[1]) for line in raw.decode().splitlines()
              if line.startswith("A ")]
    deltas = [0] + [(stamps[i] - stamps[i-1]) / Decimal(25)
                    for i in range(1, len(stamps))]
    assert set(deltas[1:]) == {Decimal(833), Decimal(834)}
    rows = [(left, right, int(delta)) for (_, left, right), delta in zip(real, deltas)]
    extremes = [-8388608, -65537, -65536, -1, 0, 1, 65535, 65536, 8388607]
    synth_a = [(extremes[i % len(extremes)], -1-extremes[i % len(extremes)], 32)
               for i in range(2048)]
    synth_b = [(65536, -524288, 32)] * 2048
    synth_c = [(0, 524288, 32)] * 2048
    stress = [(i * 12345 - 1000000, 1000000 - i * 12345, 833 + (i % 3 == 2))
              for i in range(200)]
    recovery = [(-65536, 8388607, 32)] * 2048
    rows += synth_a + synth_b + synth_c + stress + recovery
    assert len(rows) == 14241
    write(HERE / "catalogue.mem", "".join(
        f"{left & 0xffffff:06x}{right & 0xffffff:06x}{delta:04x}\n"
        for left, right, delta in rows))
    snapshots = [[a for _, a, _ in real[:2048]],
                 [a for _, a, _ in real[2048:4096]],
                 [a for a, _, _ in synth_a], [a for a, _, _ in synth_c],
                 [a for a, _, _ in recovery]]
    bins = []
    for samples in snapshots:
        assert len(samples) == 2048
        for x in range(512):
            values = samples[4*x:4*x+4]
            lo, hi = min(values) >> 16, max(values) >> 16
            bins.append(((lo & 255) << 8) | (hi & 255))
    assert bins[:512] != bins[512:1024], "TEAR_NEGATIVE_MUST_BE_DISTINGUISHABLE"
    write(HERE / "golden.mem", "".join(f"{v:04x}\n" for v in bins))
    identity = {
        "historical_source": source, "reference_path": str(reference),
        "reference_sha256": sha(reference), "normal_b64_sha256": sha(raw_dir / "normal_capture.b64"),
        "manifest_sha256": sha(raw_dir / "raw_manifest.json"),
        "source_kind": "HISTORICAL_RTL_A_CAPTURE_NOT_PRO_NOT_BOARD",
        "source_seq": "adoption_ordinal_minus_one_not_request_id",
        "time_origin_ns": str(stamps[0]), "time_last_ns": str(stamps[-1]),
        "relative_timing": "exact Decimal delta / 25ns; first load uses fixture origin",
        "delta_counts": {str(v): deltas.count(Decimal(v)) for v in (833, 834)},
        "real_left_right_different": sum(a != b for _, a, b in real),
        "catalogue_ranges_exclusive": {"historical_real": [0,5849], "synthetic_A": [5849,7897],
            "synthetic_B": [7897,9945], "synthetic_C": [9945,11993],
            "synthetic_pixel_pause": [11993,12193], "synthetic_recovery": [12193,14241]},
        "golden": "signed24 min/max over four, then arithmetic shift16; five snapshots",
        "catalogue_sha256": sha(HERE / "catalogue.mem"), "golden_sha256": sha(HERE / "golden.mem"),
        "board_release_allowed": False,
    }
    write(HERE / "INPUT_IDENTITY.json", json.dumps(identity, indent=2) + "\n")
    print(json.dumps(identity, indent=2))


if __name__ == "__main__":
    main()
