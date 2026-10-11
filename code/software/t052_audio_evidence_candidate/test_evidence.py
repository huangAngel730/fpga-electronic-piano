"""Synthetic-only tests. No simulated/recorded hardware results are claimed."""

import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import evidence as tool


HERE = Path(__file__).resolve().parent


def config() -> dict:
    return tool.load_json((HERE / "example_synthetic_config.json").read_bytes())


def encode_pcm(channels: list[list[int]], bits: int = 16, rate: int = 48000) -> bytes:
    width = bits // 8
    payload = b"".join(value.to_bytes(width, "little", signed=True)
                       for row in zip(*channels) for value in row)
    fmt = struct.pack("<HHIIHH", 1, len(channels), rate, rate * len(channels) * width,
                      len(channels) * width, bits)
    body = (b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt
            + b"data" + struct.pack("<I", len(payload)) + payload)
    if len(payload) & 1:
        body += b"\x00"
    return b"RIFF" + struct.pack("<I", len(body)) + body


def synthesis(frequencies=None, bits=16, frames=8192, rate=48000, dc=0.0) -> list[int]:
    frequencies = config()["targets_hz"] if frequencies is None else frequencies
    scale = (1 << (bits - 1)) - 1
    return [round(scale * (dc + sum(0.12 * math.sin(2 * math.pi * f * i / rate + 0.3)
                                   for f in frequencies))) for i in range(frames)]


def observed(channels, bits=16, cfg=None, rate=48000):
    return tool.analyze(encode_pcm(channels, bits, rate),
                        json.dumps(config() if cfg is None else cfg).encode())[0]


class EvidenceTests(unittest.TestCase):
    def test_positive_four_tones(self):
        result = observed([synthesis()])
        self.assertTrue(result["criteria_met"])
        self.assertFalse(result["independent_voice_count_proven"])
        self.assertFalse(result["physical_validation"])
        self.assertFalse(result["t052_complete"])
        self.assertTrue(all(abs(t["error_hz"]) < 0.15
                            for t in result["channels"][0]["targets"]))

    def test_24bit_negative_and_positive_decode(self):
        _, channels = tool.read_pcm(encode_pcm([[-8388608, -1, 0, 8388607]], 24))
        self.assertEqual(channels, [[-8388608, -1, 0, 8388607]])
        self.assertTrue(observed([synthesis(bits=24)], 24)["criteria_met"])

    def test_32bit_stereo(self):
        samples = synthesis(bits=32)
        result = observed([samples, [-s for s in samples]], 32)
        self.assertTrue(result["criteria_met"])
        self.assertEqual(len(result["channels"]), 2)

    def test_missing_tone_rejects(self):
        result = observed([synthesis([263, 431, 659])])
        self.assertFalse(result["criteria_met"])
        self.assertIn("TARGET_TONE_LIMIT", result["channels"][0]["reasons"])

    def test_wrong_frequency_rejects(self):
        self.assertFalse(observed([synthesis([263, 431, 659, 1012])])["criteria_met"])

    def test_silence_rejects(self):
        result = observed([[0] * 8192])
        self.assertIsNone(result["channels"][0]["ac_rms_dbfs"])
        self.assertIn("SILENT_OR_DC_ONLY", result["channels"][0]["reasons"])

    def test_right_channel_not_hidden(self):
        result = observed([synthesis(), [0] * 8192])
        self.assertFalse(result["criteria_met"])
        self.assertTrue(result["channels"][0]["criteria_met"])
        self.assertFalse(result["channels"][1]["criteria_met"])

    def test_dc_limit(self):
        result = observed([synthesis(dc=0.1)])
        self.assertIn("DC_LIMIT", result["channels"][0]["reasons"])

    def test_positive_and_negative_digital_rails(self):
        samples = synthesis()
        samples[3], samples[5] = -32768, 32767
        result = observed([samples])
        self.assertEqual(result["channels"][0]["digital_rail_hits"], 2)
        self.assertIn("DIGITAL_RAIL_LIMIT", result["channels"][0]["reasons"])

    def test_dc_only_is_not_sound(self):
        result = observed([[5000] * 8192])
        self.assertIn("SILENT_OR_DC_ONLY", result["channels"][0]["reasons"])

    def test_physical_label_is_not_certification(self):
        cfg = config()
        cfg["provenance"]["kind"] = "physical_recording"
        result = observed([synthesis()], cfg=cfg)
        self.assertTrue(result["criteria_met"])
        self.assertFalse(result["provenance_verified"])
        self.assertFalse(result["physical_validation"])

    def test_harmonic_peaks_not_voice_proof(self):
        cfg = config()
        cfg["targets_hz"] = [440, 880, 1760, 3520]
        result = observed([synthesis(cfg["targets_hz"])], cfg=cfg)
        self.assertTrue(result["criteria_met"])
        self.assertFalse(result["independent_voice_count_proven"])

    def test_segment_is_explicit(self):
        cfg = config()
        cfg["start_frame"] = 8192
        samples = [0] * 8192 + synthesis()
        result = observed([samples], cfg=cfg)
        self.assertTrue(result["criteria_met"])
        self.assertEqual(result["selected_segment"]["start_frame"], 8192)
        self.assertFalse(observed([samples])["criteria_met"])

    def test_short_segment_rejects(self):
        with self.assertRaisesRegex(ValueError, "WAV_SHORT_SEGMENT"):
            observed([synthesis(frames=4096)])

    def test_rate_mismatch(self):
        with self.assertRaisesRegex(ValueError, "WAV_CONFIG_RATE_MISMATCH"):
            observed([synthesis(rate=44100)], rate=44100)

    def test_bad_wav_lengths(self):
        raw = encode_pcm([synthesis()])
        for invalid in (b"", raw[:-1], raw + b"junk"):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                tool.read_pcm(invalid)

    def test_float_format_rejects(self):
        raw = bytearray(encode_pcm([synthesis()]))
        struct.pack_into("<H", raw, 20, 3)
        with self.assertRaisesRegex(ValueError, "WAV_PCM_FORMAT"):
            tool.read_pcm(raw)

    def test_bad_alignment(self):
        raw = bytearray(encode_pcm([synthesis()]))
        struct.pack_into("<H", raw, 32, 4)
        with self.assertRaisesRegex(ValueError, "WAV_ALIGNMENT"):
            tool.read_pcm(raw)

    def test_duplicate_data(self):
        raw = bytearray(encode_pcm([synthesis()]))
        raw.extend(b"data\x00\x00\x00\x00")
        struct.pack_into("<I", raw, 4, len(raw) - 8)
        with self.assertRaisesRegex(ValueError, "WAV_DATA"):
            tool.read_pcm(raw)

    def test_unknown_metadata_chunk_allowed(self):
        raw = bytearray(encode_pcm([synthesis()]))
        raw.extend(b"JUNK\x03\x00\x00\x00abc\x00")
        struct.pack_into("<I", raw, 4, len(raw) - 8)
        info, _ = tool.read_pcm(raw)
        self.assertEqual(info["total_frames"], 8192)

    def test_boolean_nonfinite_and_extra_config(self):
        for key, value in (("schema", True), ("frames", 8192.0),
                           ("min_tone_dbfs", float("nan")), ("max_abs_dc", True),
                           ("extra", 1)):
            cfg = config()
            cfg[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                tool.config_check(cfg)
        for raw in (b'{"schema":1,"schema":1}', b'{"v":NaN}'):
            with self.assertRaises(ValueError):
                tool.load_json(raw)

    def test_unresolved_frequencies(self):
        for targets in ([440, 440], [440, 441], [], [0], [24000]):
            cfg = config()
            cfg["targets_hz"] = targets
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                tool.config_check(cfg)

    def test_fft_vs_independent_direct_dft(self):
        samples = [math.sin(i * 0.11) + 0.3 * math.cos(i * 0.3) for i in range(128)]
        values = tool.fft(samples)
        for k in (0, 1, 7, 32, 64):
            direct = sum(s * complex(math.cos(-2 * math.pi * k * i / 128),
                                     math.sin(-2 * math.pi * k * i / 128))
                         for i, s in enumerate(samples))
            self.assertLess(abs(values[k] - direct), 1e-10)
        with self.assertRaisesRegex(ValueError, "FFT_LENGTH"):
            tool.fft([1, 2, 3])

    def test_amplitude_calibration(self):
        cfg = config()
        cfg["targets_hz"] = [468.75]  # exactly FFT bin 80
        result = observed([synthesis(cfg["targets_hz"])], cfg=cfg)
        level = result["channels"][0]["targets"][0]["amplitude_dbfs"]
        self.assertAlmostEqual(level, 20 * math.log10(0.12), places=2)

    def test_reference_identity_refused(self):
        with patch.dict(tool.REFERENCE_SHA, {"analysis.py": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "REFERENCE_IDENTITY"):
                tool.reference()

    def test_32_targets_are_only_software_capacity(self):
        cfg = config()
        cfg["targets_hz"] = [200 + i * 100 for i in range(32)]
        scale = 32767
        # Leave amplitude headroom above -40 dBFS; exact threshold tests are separate.
        samples = [round(scale * sum(0.0125 * math.sin(2 * math.pi * f * i / 48000)
                                     for f in cfg["targets_hz"])) for i in range(8192)]
        report, spectra = tool.analyze(encode_pcm([samples]), json.dumps(cfg).encode())
        self.assertTrue(report["criteria_met"])
        self.assertFalse(report["independent_voice_count_proven"])
        svg = ET.fromstring(tool.spectrum_svg(report, spectra))
        self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")

    def test_huge_integer_is_config_error(self):
        cfg = config()
        cfg["min_tone_dbfs"] = 10 ** 400
        with self.assertRaisesRegex(ValueError, "CONFIG_NUMBER"):
            tool.config_check(cfg)

    def test_input_changed_never_writes_success_receipt(self):
        with tempfile.TemporaryDirectory(prefix="t052_changed_") as directory:
            root = Path(directory)
            wav, cfg, out = root / "in.wav", root / "cfg.json", root / "out"
            wav.write_bytes(encode_pcm([synthesis()]))
            cfg.write_text(json.dumps(config()), encoding="utf-8")
            original = tool.analyze

            def changed(raw, config_raw):
                result = original(raw, config_raw)
                wav.write_bytes(b"changed private test input")
                return result

            argv = ["evidence.py", "--wav", str(wav), "--config", str(cfg),
                    "--output", str(out)]
            with patch.object(sys, "argv", argv), patch.object(tool, "analyze", changed):
                self.assertEqual(tool.main(), 1)
            self.assertFalse((out / "receipt.json").exists())

    def test_cli_fail_closed_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="t052_audio_test_") as directory:
            root = Path(directory)
            wav, cfg, out = root / "input.wav", root / "config.json", root / "out"
            wav.write_bytes(encode_pcm([synthesis()]))
            cfg.write_text(json.dumps(config()), encoding="utf-8")
            command = [sys.executable, "-B", str(HERE / "evidence.py"),
                       "--wav", str(wav), "--config", str(cfg), "--output", str(out)]
            first = subprocess.run(command, capture_output=True, timeout=30)
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["exit_code"], 0)
            self.assertEqual(receipt["input_wav_sha256"], tool.sha(wav.read_bytes()))
            snapshot = {p.name: p.read_bytes() for p in out.iterdir()}
            self.assertEqual(subprocess.run(command, capture_output=True,
                                            timeout=30).returncode, 1)
            self.assertEqual(snapshot, {p.name: p.read_bytes() for p in out.iterdir()})
            wav.unlink()  # only this test's private synthetic temporary input
            command[-1] = str(root / "missing_out")
            self.assertEqual(subprocess.run(command, capture_output=True,
                                            timeout=30).returncode, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    success = result.wasSuccessful() and not result.skipped
    if args.receipt:
        tool.dump(args.receipt, dict(status="SOFTWARE_TESTS_PASS" if success else "FAIL",
             tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
             skipped=len(result.skipped), exit_code=0 if success else 1,
             input_kind="synthetic_only", physical_validation=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
