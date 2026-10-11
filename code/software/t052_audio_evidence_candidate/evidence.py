"""Read-only, offline PCM WAV observations; never certify hardware polyphony."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "code/model"
REFERENCE_SHA = {
    "analysis.py": "be2220f70cbfa0d9b7e0b77e0889286f9f6e418ba0aca6ed7330524257b2d32c",
    "audio_defs.py": "126ab1cff4e95cac7379aa03758a931bb9dd5fa01fc330700938086a18351348",
}
MAX_BYTES = 8 * 1024 * 1024


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def dump(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n", encoding="utf-8", newline="\n")


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("CONFIG_DUPLICATE_KEY:" + key)
        result[key] = value
    return result


def load_json(raw: bytes) -> object:
    def invalid(value: str) -> None:
        raise ValueError("CONFIG_NONFINITE:" + value)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid)


def number(value: object, name: str, low: float, high: float) -> float:
    if (type(value) not in (int, float) or not low <= value <= high
            or not math.isfinite(value)):
        raise ValueError("CONFIG_NUMBER:" + name)
    return float(value)


def config_check(obj: object) -> dict:
    keys = {"schema", "sample_rate_hz", "start_frame", "frames", "targets_hz",
            "frequency_tolerance_hz", "min_tone_dbfs", "silence_rms_dbfs",
            "max_abs_dc", "max_rail_fraction", "provenance"}
    if type(obj) is not dict or set(obj) != keys:
        raise ValueError("CONFIG_KEYS")
    for name in ("schema", "sample_rate_hz", "start_frame", "frames"):
        if type(obj[name]) is not int:
            raise ValueError("CONFIG_INTEGER:" + name)
    if obj["schema"] != 1 or not 8000 <= obj["sample_rate_hz"] <= 192000:
        raise ValueError("CONFIG_SCHEMA_RATE")
    n = obj["frames"]
    if n < 4096 or n > 262144 or n & (n - 1) or obj["start_frame"] < 0:
        raise ValueError("CONFIG_SEGMENT")
    targets = obj["targets_hz"]
    if type(targets) is not list or not 1 <= len(targets) <= 32:
        raise ValueError("CONFIG_TARGETS")
    rate = obj["sample_rate_hz"]
    width = rate / n
    frequencies = [number(f, "target_hz", 4 * width, rate / 2 - 4 * width)
                   for f in targets]
    tolerance = number(obj["frequency_tolerance_hz"], "tolerance", 0.01, 50)
    ordered = sorted(frequencies)
    if any(b - a < max(8 * width, 4 * tolerance)
           for a, b in zip(ordered, ordered[1:])):
        raise ValueError("CONFIG_UNRESOLVED_TARGETS")
    number(obj["min_tone_dbfs"], "min_tone_dbfs", -100, -1)
    number(obj["silence_rms_dbfs"], "silence_rms_dbfs", -120, -1)
    number(obj["max_abs_dc"], "max_abs_dc", 0, 0.5)
    number(obj["max_rail_fraction"], "max_rail_fraction", 0, 1)
    provenance = obj["provenance"]
    if (type(provenance) is not dict or set(provenance) != {"kind", "label"}
            or provenance["kind"] not in
            ("synthetic", "rtl_derived", "physical_recording", "unknown")
            or type(provenance["label"]) is not str
            or not 1 <= len(provenance["label"]) <= 256):
        raise ValueError("CONFIG_PROVENANCE")
    return obj


def read_pcm(raw: bytes) -> tuple[dict, list[list[int]]]:
    """Strict little-endian RIFF PCM1; do not silently accept truncated WAVs."""
    if len(raw) > MAX_BYTES or len(raw) < 44:
        raise ValueError("WAV_SIZE")
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("WAV_RIFF")
    if struct.unpack_from("<I", raw, 4)[0] + 8 != len(raw):
        raise ValueError("WAV_RIFF_LENGTH")
    offset, fmt, data = 12, None, None
    while offset < len(raw):
        if len(raw) - offset < 8:
            raise ValueError("WAV_CHUNK_HEADER")
        tag, size = struct.unpack_from("<4sI", raw, offset)
        begin = offset + 8
        end = begin + size
        next_offset = end + (size & 1)
        if next_offset > len(raw):
            raise ValueError("WAV_CHUNK_LENGTH")
        if tag == b"fmt ":
            if fmt is not None or data is not None or size not in (16, 18):
                raise ValueError("WAV_FMT")
            fmt = struct.unpack_from("<HHIIHH", raw, begin)
            if size == 18 and raw[begin + 16:end] != b"\x00\x00":
                raise ValueError("WAV_FMT_EXTENSION")
        elif tag == b"data":
            if fmt is None or data is not None:
                raise ValueError("WAV_DATA")
            data = raw[begin:end]
        offset = next_offset
    if fmt is None or data is None:
        raise ValueError("WAV_MISSING_CHUNK")
    encoding, channels, rate, byte_rate, align, bits = fmt
    if encoding != 1 or channels not in (1, 2) or bits not in (16, 24, 32):
        raise ValueError("WAV_PCM_FORMAT")
    if not 8000 <= rate <= 192000:
        raise ValueError("WAV_RATE")
    width = bits // 8
    if align != channels * width or byte_rate != rate * align:
        raise ValueError("WAV_ALIGNMENT")
    if not data or len(data) % align:
        raise ValueError("WAV_DATA_ALIGNMENT")
    values = [[] for _ in range(channels)]
    for index in range(0, len(data), width):
        channel = (index // width) % channels
        values[channel].append(int.from_bytes(data[index:index + width],
                                              "little", signed=True))
    return dict(format="PCM1", sample_rate_hz=rate, channels=channels,
                bits=bits, total_frames=len(data) // align), values


def reference():
    """Reuse the existing periodic Hann and direct DFT without editing M1 code."""
    for name, expected in REFERENCE_SHA.items():
        if sha((MODEL / name).read_bytes()) != expected:
            raise ValueError("REFERENCE_IDENTITY:" + name)
    name = "_t052_readonly_analysis"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, MODEL / "analysis.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        sys.path.insert(0, str(MODEL))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
    return sys.modules[name]


def fft(values: list[float]) -> list[complex]:
    """Iterative radix-2 FFT; amplitudes are checked against the existing DFT."""
    n = len(values)
    if n < 2 or n & (n - 1):
        raise ValueError("FFT_LENGTH")
    out = [complex(v) for v in values]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            out[i], out[j] = out[j], out[i]
    length = 2
    while length <= n:
        step = complex(math.cos(-2 * math.pi / length),
                       math.sin(-2 * math.pi / length))
        for start in range(0, n, length):
            factor = 1 + 0j
            for pos in range(start, start + length // 2):
                a, b = out[pos], out[pos + length // 2] * factor
                out[pos], out[pos + length // 2] = a + b, a - b
                factor *= step
        length <<= 1
    return out[:n // 2 + 1]


def db(value: float) -> float | None:
    return 20 * math.log10(value) if value > 0 else None


def channel_analyze(samples: list[int], bits: int, cfg: dict) -> tuple[dict, list]:
    rate, n = cfg["sample_rate_hz"], cfg["frames"]
    scale = 1 << (bits - 1)
    normalized = [s / scale for s in samples]
    mean = math.fsum(normalized) / n
    rms = math.sqrt(math.fsum(s * s for s in normalized) / n)
    ac = [s - mean for s in normalized]
    ac_rms = math.sqrt(math.fsum(s * s for s in ac) / n)
    rails = sum(s in (-scale, scale - 1) for s in samples)
    ref = reference()
    window = ref.hann_window(n)
    gain = math.fsum(window)
    spectral = fft([s * w for s, w in zip(ac, window)])
    magnitudes = [abs(v) for v in spectral]
    amplitudes = [value * (1 if k in (0, n // 2) else 2) / gain
                  for k, value in enumerate(magnitudes)]
    tones = []
    for target in cfg["targets_hz"]:
        guard = cfg["frequency_tolerance_hz"] + 2 * rate / n
        lo = max(1, math.floor((target - guard) * n / rate))
        hi = min(n // 2 - 1, math.ceil((target + guard) * n / rate))
        k = max(range(lo, hi + 1), key=lambda index: magnitudes[index])
        logs = [math.log(max(magnitudes[i], 1e-300))
                for i in (k - 1, k, k + 1)]
        denominator = logs[0] - 2 * logs[1] + logs[2]
        shift = 0.5 * (logs[0] - logs[2]) / denominator if denominator else 0.0
        shift = max(-0.5, min(0.5, shift))
        estimated = (k + shift) * rate / n
        amplitude = 2 * abs(ref.dft_at(ac, estimated, rate, window)) / gain
        level = db(amplitude)
        present = (level is not None and level >= cfg["min_tone_dbfs"]
                   and abs(estimated - target) <= cfg["frequency_tolerance_hz"])
        tones.append(dict(target_hz=target, estimated_peak_hz=estimated,
                          error_hz=estimated - target, amplitude_dbfs=level,
                          criteria_met=present))
    reasons = []
    if ac_rms < 10 ** (cfg["silence_rms_dbfs"] / 20):
        reasons.append("SILENT_OR_DC_ONLY")
    if abs(mean) > cfg["max_abs_dc"]:
        reasons.append("DC_LIMIT")
    if rails / n > cfg["max_rail_fraction"]:
        reasons.append("DIGITAL_RAIL_LIMIT")
    if not all(tone["criteria_met"] for tone in tones):
        reasons.append("TARGET_TONE_LIMIT")
    result = dict(rms_dbfs=db(rms), ac_rms_dbfs=db(ac_rms), dc=mean,
                  peak_abs=max(abs(s) for s in normalized), digital_rail_hits=rails,
                  digital_rail_fraction=rails / n, targets=tones,
                  criteria_met=not reasons, reasons=reasons)
    return result, amplitudes


def analyze(raw: bytes, config_raw: bytes) -> tuple[dict, list]:
    cfg = config_check(load_json(config_raw))
    info, channels = read_pcm(raw)
    if info["sample_rate_hz"] != cfg["sample_rate_hz"]:
        raise ValueError("WAV_CONFIG_RATE_MISMATCH")
    start, n = cfg["start_frame"], cfg["frames"]
    if start + n > info["total_frames"]:
        raise ValueError("WAV_SHORT_SEGMENT")
    results, spectra = [], []
    for channel, samples in enumerate(channels):
        result, spectrum = channel_analyze(samples[start:start + n], info["bits"], cfg)
        results.append(dict(channel=channel, **result))
        spectra.append(spectrum)
    matched = all(channel["criteria_met"] for channel in results)
    report = dict(schema=1, status=("SPECTRAL_CRITERIA_MATCH_PARTIAL" if matched
                                   else "SPECTRAL_CRITERIA_REJECTED"),
                  criteria_met=matched, input_wav_sha256=sha(raw),
                  config_sha256=sha(config_raw), wav=info, config=cfg,
                  selected_segment=dict(start_frame=start, frames=n,
                                        seconds=n / info["sample_rate_hz"]),
                  channel_policy="all_channels_independently", channels=results,
                  provenance_verified=False, independent_voice_count_proven=False,
                  t052_complete=False, physical_validation=False,
                  limitations=["Only configured spectral criteria, not waveform equivalence",
                               "Peaks can be harmonics; not independent oscillator proof",
                               "Provenance is caller-declared, not authenticated",
                               "Digital rail hits cannot detect all analog clipping",
                               "Only the explicit segment is analyzed; no latency/STA proof"])
    return report, spectra


def spectrum_svg(report: dict, spectra: list) -> str:
    """Self-contained, code-native plot with peak-preserving display decimation."""
    n, rate = report["config"]["frames"], report["wav"]["sample_rate_hz"]
    maximum = min(rate / 2, max(report["config"]["targets_hz"]) * 1.25 + 100)
    last = min(n // 2, math.ceil(maximum * n / rate))
    elements = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="480" '
                'viewBox="0 0 1000 480">', '<rect width="1000" height="480" fill="white"/>',
                '<text x="60" y="24" font-size="16">Offline WAV spectrum: '
                'not hardware polyphony certification</text>']
    for level in range(-120, 1, 20):
        y = 420 - (level + 120) / 120 * 360
        elements.append(f'<path d="M60 {y:.2f} H960" stroke="#ddd"/>')
        elements.append(f'<text x="8" y="{y + 4:.2f}" font-size="12">{level}</text>')
    for target in report["config"]["targets_hz"]:
        x = 60 + target / maximum * 900
        elements.append(f'<path d="M{x:.2f} 60 V420" stroke="#aaa" '
                        'stroke-dasharray="4 4"/>')
    for channel, amplitudes in enumerate(spectra):
        points = []
        stride = max(1, math.ceil((last + 1) / 1200))
        for begin in range(0, last + 1, stride):
            k = max(range(begin, min(begin + stride, last + 1)),
                    key=lambda index: amplitudes[index])
            raw_level = db(amplitudes[k])
            level = max(-120, min(0, raw_level if raw_level is not None else -120))
            x = 60 + (k * rate / n) / maximum * 900
            y = 420 - (level + 120) / 120 * 360
            points.append(f"{x:.2f},{y:.2f}")
        color = ("#1765c0", "#c05020")[channel]
        elements.append(f'<polyline points="{" ".join(points)}" fill="none" '
                        f'stroke="{color}" stroke-width="1"/>')
        elements.append(f'<text x="{650 + channel * 150}" y="46" fill="{color}" '
                        f'font-size="12">channel {channel}</text>')
    elements += [f'<text x="60" y="455" font-size="12">0 to {maximum:.1f} Hz; '
                 'Hann-windowed peak amplitude dBFS; display floor -120 dBFS</text>',
                 '</svg>']
    return "\n".join(elements) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("REFUSE_EXISTING_OUTPUT")
        if args.wav.stat().st_size > MAX_BYTES or args.config.stat().st_size > 65536:
            raise ValueError("INPUT_SIZE_LIMIT")
        raw, cfg_raw = args.wav.read_bytes(), args.config.read_bytes()
        report, spectra = analyze(raw, cfg_raw)
        args.output.mkdir(parents=True, exist_ok=False)
        dump(args.output / "analysis.json", report)
        (args.output / "spectrum.svg").write_text(spectrum_svg(report, spectra),
                                                encoding="utf-8", newline="\n")
        (args.output / "input_config.json").write_bytes(cfg_raw)
        code = 0 if report["criteria_met"] else 2
        sources = {str(path.relative_to(ROOT)).replace("\\", "/"): sha(path.read_bytes())
                   for path in (Path(__file__), MODEL / "analysis.py", MODEL / "audio_defs.py")}
        artifacts = {path.name: dict(bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
                     for path in sorted(args.output.iterdir()) if path.is_file()}
        if args.wav.read_bytes() != raw or args.config.read_bytes() != cfg_raw:
            raise ValueError("INPUT_CHANGED_DURING_ANALYSIS")
        dump(args.output / "receipt.json", dict(status=report["status"], exit_code=code,
             command=sys.argv, input_wav=str(args.wav.resolve()), input_bytes=len(raw),
             input_wav_sha256=sha(raw), config_sha256=sha(cfg_raw), sources=sources,
             artifacts=artifacts, physical_validation=False, t052_complete=False))
        print(json.dumps(dict(status=report["status"], exit_code=code,
                              output=str(args.output.resolve()))))
        return code
    except (ValueError, OSError, ImportError, UnicodeError, struct.error,
            OverflowError, RecursionError) as error:
        print(json.dumps(dict(status="INPUT_OR_EXECUTION_REJECTED", error=str(error),
                              error_type=type(error).__name__,
                              diagnostic=("INPUT_NOT_FOUND" if isinstance(error, FileNotFoundError)
                                          else "INVALID_INPUT_OR_EXECUTION"))),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
