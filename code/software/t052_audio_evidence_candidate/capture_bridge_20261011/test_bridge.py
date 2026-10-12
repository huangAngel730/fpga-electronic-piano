"""New bridge-only synthetic tests; never imports signed WAV/math tools."""

import copy
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("bridge", Path(__file__).with_name("bridge.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def fixture(count=3):
    ids = [i % 256 for i in range(count)]
    requests = "".join(f"REQ {i} 04b17e4d 00000000 00000000 ffffffff 15\n"
                       for i in ids).encode()
    capture = "".join(f"ID={i} PCM v0=-32768 v1=-1 v2=0 v3=32767 ACT=4 CLIP=1\n"
                      for i in ids).encode()
    return capture, requests


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.cap, self.req = fixture()
        self.config = b.config_for(self.cap, self.req, 3, "SYNTHETIC_SOFTWARE_TEST")

    def bad_cap(self, old, new, diagnostic):
        with self.assertRaisesRegex(ValueError, diagnostic):
            b.parse_rows(self.cap.replace(old, new, 1), self.req, 3)

    def bad_req(self, old, new, diagnostic):
        with self.assertRaisesRegex(ValueError, diagnostic):
            b.parse_rows(self.cap, self.req.replace(old, new, 1), 3)

    def test_signed_extremes_and_full_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cap").write_bytes(self.cap)
            (root / "req").write_bytes(self.req)
            b.dump(root / "config", self.config)
            result = b.export(root / "cap", root / "req", root / "config", root / "out")
            self.assertEqual(result["lane_samples"], 12)
            for key in b.FALSE_CLAIMS:
                self.assertIs(result[key], False)
            self.assertEqual(len(list((root / "out").glob("*.wav"))), 4)
            mapping = (root / "out/sample_mapping.jsonl").read_text().splitlines()
            self.assertEqual(len(mapping), 3)
            self.assertEqual(b.load_json(mapping[-1])["wav_file_byte_offset"], 48)
            for lane, expected in enumerate((-32768, -1, 0, 32767)):
                raw = (root / "out" / ("lane" + str(lane) + ".wav")).read_bytes()
                for line in mapping:
                    offset = b.load_json(line)["wav_file_byte_offset"]
                    self.assertEqual(struct.unpack_from("<h", raw, offset)[0], expected)

    def test_ids_wrap_and_repeat(self):
        cap, req = fixture(258)
        self.assertEqual(len(b.parse_rows(cap, req, 258)), 258)
        self.assertEqual(len(b.parse_rows(self.cap + self.cap, self.req + self.req, 6)), 6)

    def test_unknown_capture_tag(self):
        self.bad_cap(b"PCM", b"OTHER", "CAPTURE_SCHEMA")

    def test_unknown_request_tag(self):
        self.bad_req(b"REQ", b"UNKNOWN", "REQUEST_SCHEMA")

    def test_extra_column(self):
        self.bad_cap(b"CLIP=1", b"CLIP=1 X=0", "CAPTURE_SCHEMA")

    def test_missing_column(self):
        self.bad_req(b" ffffffff", b"", "REQUEST_SCHEMA")

    def test_mask_out_of_range(self):
        self.bad_req(b" 15\n", b" 17\n", "MASK_RANGE")

    def test_mask_negative(self):
        self.bad_req(b" 15\n", b" -1\n", "REQUEST_SCHEMA")

    def test_act_mismatch(self):
        self.bad_cap(b"ACT=4", b"ACT=3", "ACT_MASK")

    def test_act_out_of_range(self):
        self.bad_cap(b"ACT=4", b"ACT=7", "ACT_MASK")

    def test_id_mismatch(self):
        self.bad_cap(b"ID=0", b"ID=9", "PAIRED_ID")

    def test_id_out_of_range(self):
        self.bad_cap(b"ID=0", b"ID=256", "ID_RANGE")

    def test_clip_not_binary(self):
        self.bad_cap(b"CLIP=1", b"CLIP=2", "CAPTURE_SCHEMA")

    def test_clip_provenance_not_math(self):
        self.assertEqual(b.parse_rows(self.cap.replace(b"CLIP=1", b"CLIP=0"),
                                     self.req, 3)[0]["clip_provenance_only"], 0)

    def test_positive_overflow(self):
        self.bad_cap(b"32767", b"32768", "PCM16_RANGE")

    def test_negative_overflow(self):
        self.bad_cap(b"-32768", b"-32769", "PCM16_RANGE")

    def test_unknown_bits(self):
        self.bad_req(b"04b17e4d", b"xxxxxxxx", "REQUEST_SCHEMA")

    def test_fcw_too_wide(self):
        self.bad_req(b"ffffffff", b"1ffffffff", "REQUEST_SCHEMA")

    def test_truncated_pair(self):
        with self.assertRaisesRegex(ValueError, "ROW_COUNT"):
            b.parse_rows(b"\n".join(self.cap.splitlines()[:2]),
                         b"\n".join(self.req.splitlines()[:2]), 3)

    def test_extra_unknown_tail(self):
        with self.assertRaisesRegex(ValueError, "ROW_COUNT"):
            b.parse_rows(self.cap, self.req + b"UNKNOWN 0\n", 3)

    def test_blank_line(self):
        self.bad_cap(b"ID=0 PCM v0=-32768 v1=-1 v2=0 v3=32767 ACT=4 CLIP=1",
                     b"", "CAPTURE_SCHEMA")

    def test_non_ascii(self):
        self.bad_cap(b"PCM", b"\xff", "ASCII_INPUT")

    def test_duplicate_json(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            b.load_json('{"a":1,"a":2}')

    def test_nan(self):
        with self.assertRaisesRegex(ValueError, "NONFINITE_JSON"):
            b.load_json('{"a":NaN}')

    def test_config_refusals(self):
        for key, value, diagnostic in [
                ("expected_rows", True, "EXPECTED_ROWS"),
                ("wav_rate_hz", 47984.644914, "WAV_INTEGER_RATE"),
                ("wav_rate_hz", True, "WAV_INTEGER_RATE"),
                ("rate_mode", "physical_time", "PHYSICAL_TIME_MAPPING_BLOCKED"),
                ("rate_rationale", "", "RATE_RATIONALE"),
                ("profile", "physical_recording", "PROFILE"),
                ("capture_sha256", "", "INPUT_SHA_SCHEMA")]:
            with self.subTest(key=key, value=value):
                config = copy.deepcopy(self.config)
                config[key] = value
                with self.assertRaisesRegex(ValueError, diagnostic):
                    b.validate_config(config)

    def test_frozen_profile_repin_rejected(self):
        config = dict(self.config, profile=b.PROFILE, expected_rows=4137)
        with self.assertRaisesRegex(ValueError, "FROZEN_INPUT_SHA"):
            b.validate_config(config)
        config.update(capture_sha256=b.CAP_SHA, request_sha256=b.REQ_SHA,
                      expected_rows=4096)
        with self.assertRaisesRegex(ValueError, "FROZEN_ROW_COUNT"):
            b.validate_config(config)

    def test_output_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS"):
                b.export(root / "missing", root / "missing", root / "missing", root)

    def test_input_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cap").write_bytes(self.cap + b"x")
            (root / "req").write_bytes(self.req)
            b.dump(root / "config", self.config)
            with self.assertRaisesRegex(ValueError, "CAPTURE_SHA"):
                b.export(root / "cap", root / "req", root / "config", root / "out")
            self.assertFalse((root / "out").exists())

    def test_frequency_label(self):
        self.assertAlmostEqual(0x04B17E4D * 48000 / (1 << 32), 880.0000213086605)

    def test_all_sixteen_masks(self):
        for mask in range(16):
            with self.subTest(mask=mask):
                rows = b.parse_rows(self.cap.replace(b"ACT=4", (
                    "ACT=" + str(mask.bit_count())).encode()),
                    self.req.replace(b" 15\n", (" " + str(mask) + "\n").encode()), 3)
                self.assertEqual(rows[0]["mask"], mask)

    def test_request_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cap").write_bytes(self.cap)
            (root / "req").write_bytes(self.req + b"x")
            b.dump(root / "config", self.config)
            with self.assertRaisesRegex(ValueError, "REQUEST_SHA"):
                b.export(root / "cap", root / "req", root / "config", root / "out")
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
