"""Independent synthetic SMF contract tests; no serial, network or RTL calls."""
from __future__ import annotations

import hashlib
import struct
import unittest

from midi_fixtures import (
    basic, capacity, end, event, expected_event, meta, note_off, note_on, smf,
    tempo,
)
from midi_import import MidiImportError, convert_midi


class MidiImportTests(unittest.TestCase):
    def reject(self, raw):
        with self.assertRaises(MidiImportError):
            convert_midi(raw)

    def test_basic_type0_exact_document(self):
        raw = basic(release_velocity=37)
        document, provenance = convert_midi(raw, 0x12345678)
        self.assertEqual(document, {
            "schema": 1, "sample_hz": 48000, "score_id": 0x12345678,
            "events": [expected_event(0, "note_on", velocity=100),
                       expected_event(24000, "note_off", velocity=37)],
        })
        self.assertEqual(provenance["input"], {
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        self.assertEqual(provenance["event_origins"][1]["midi_tick"], 480)
        self.assertEqual(provenance["event_origins"][1]["track"], 0)

    def test_type1_tempo_and_multitrack_stable_order(self):
        raw = smf(tempo(0, 500000) + tempo(480, 1000000) + end(480),
                  note_on(note=64, channel=2) + note_off(960, note=64, channel=2) + end(),
                  note_on(note=62, channel=1) + note_off(480, note=62, channel=1) + end())
        doc, origin = convert_midi(raw)
        self.assertEqual(doc["events"], [
            expected_event(0, "note_on", 2, 64, 100),
            expected_event(0, "note_on", 1, 62, 100),
            expected_event(24000, "note_off", 1, 62),
            expected_event(72000, "note_off", 2, 64),
        ])
        self.assertEqual([p["track"] for p in origin["event_origins"]], [1, 2, 2, 1])

    def test_running_status_zero_noteon_normalizes_off(self):
        doc, _ = convert_midi(smf(note_on() + event(480, [60, 0]) + end()))
        self.assertEqual(doc["events"][1], expected_event(24000, "note_off"))

    def test_release_velocity_and_all_channels_notes(self):
        for channel in range(16):
            for note in (0, 127):
                with self.subTest(channel=channel, note=note):
                    doc, _ = convert_midi(basic(channel=channel, note=note,
                                              release_velocity=127))
                    self.assertEqual(doc["events"][1], expected_event(
                        24000, "note_off", channel, note, 127))

    def test_same_tick_original_order_survives(self):
        doc, _ = convert_midi(smf(note_on() + note_off(0)
                                 + note_on(0) + note_off(0) + end()))
        self.assertEqual([e["type"] for e in doc["events"]],
                         ["note_on", "note_off", "note_on", "note_off"])
        self.assertEqual([e["tick"] for e in doc["events"]], [0] * 4)

    def test_nearest_sample_ties_up_not_bankers_rounding(self):
        # Default tempo gives 24000/32000 = 0.75 samples per MIDI tick.
        doc, _ = convert_midi(smf(note_on(2) + note_off(4) + end(), division=32000))
        self.assertEqual([e["tick"] for e in doc["events"]], [2, 5])

    def test_exact_accumulation_across_many_tempo_changes(self):
        body = note_on()
        # Each one-tick segment is fractional. Round only final absolute time.
        body += tempo(1, 500001) + tempo(1, 500002) + tempo(1, 500003)
        body += note_off(1) + end()
        doc, origin = convert_midi(smf(body, division=7))
        numerator = (500000 + 500001 + 500002 + 500003) * 48000
        denominator = 7000000
        expected = (numerator + denominator // 2) // denominator
        self.assertEqual(doc["events"][1]["tick"], expected)
        self.assertEqual(origin["event_origins"][1]["exact_sample_numerator"], numerator)

    def test_tempo_before_first_note_and_annotations(self):
        body = meta(0, 0, b"\x00\x01") + meta(0, 3, b"synthetic")
        body += meta(0, 0x58, b"\x04\x02\x18\x08")
        body += meta(0, 0x59, b"\xff\x01")
        body += tempo(0, 1000000) + note_on(480) + note_off(480) + end()
        doc, origin = convert_midi(smf(body))
        self.assertEqual([e["tick"] for e in doc["events"]], [48000, 96000])
        self.assertEqual(len(origin["annotations_not_encoded"]), 4)

    def test_identical_duplicate_tempo_allowed(self):
        raw = smf(tempo(0, 500000) + tempo(0, 500000) + note_on() + note_off() + end())
        self.assertEqual(convert_midi(raw)[0]["events"][1]["tick"], 24000)

    def test_capacity_exact_512_and_overflow_513(self):
        self.assertEqual(len(convert_midi(capacity(512))[0]["events"]), 512)
        self.reject(capacity(513))

    def test_invalid_input_and_score_id(self):
        for raw in (None, "MThd", bytearray(basic())):
            self.reject(raw)
        for score_id in (-1, 0x100000000, True, 1.0, "1"):
            with self.subTest(score_id=score_id), self.assertRaises(MidiImportError):
                convert_midi(basic(), score_id)

    def test_header_format_timebase_and_track_count(self):
        good = basic()
        for raw in (b"", good[1:], b"RIFF" + good[4:],
                    good[:7] + b"\x07" + good[8:],
                    smf(note_on() + note_off() + end(), midi_format=2),
                    smf(note_on() + note_off() + end(), division=0),
                    smf(note_on() + note_off() + end(), division=0xE728),
                    smf(end(), end(), midi_format=0), smf()):
            with self.subTest(raw=raw[:16]):
                self.reject(raw)

    def test_every_truncated_prefix_and_trailing_bytes(self):
        raw = basic()
        for count in range(len(raw)):
            with self.subTest(count=count):
                self.reject(raw[:count])
        self.reject(raw + b"\x00")
        self.reject(raw[:14] + b"JUNK" + raw[18:])

    def test_invalid_vlq_running_status_data(self):
        for body in (b"\x81\x80\x80\x80\x00" + note_on(),
                     event(0, [60, 100]) + end(),
                     event(0, [0x90, 128, 100]) + end(),
                     event(0, [0x90, 60, 255]) + end(),
                     note_on() + meta(1, 1, b"x") + event(1, [60, 0]) + end(),
                     b"\x00\xff\x01\x80\x80\x80\x80\x00" + end()):
            with self.subTest(body=body):
                self.reject(smf(body))

    def test_end_of_track_contract(self):
        for body in (note_on() + note_off(),
                     note_on() + note_off() + meta(0, 0x2F, b"x"),
                     note_on() + note_off() + end() + b"\x00",
                     end()):
            with self.subTest(body=body):
                self.reject(smf(body))

    def test_tempo_zero_length_and_nonconductor_rejected(self):
        for raw in (smf(tempo(0, 0) + note_on() + note_off() + end()),
                    smf(meta(0, 0x51, b"\x01\x02") + end()),
                    smf(tempo(0, 500000) + tempo(0, 500001)
                        + note_on() + note_off() + end()),
                    smf(end(), tempo(0, 500000) + note_on() + note_off() + end())):
            self.reject(raw)

    def test_unsupported_channel_system_and_meta_events(self):
        for payload in ([0xB0, 64, 127], [0xC0, 1], [0xD0, 1],
                        [0xA0, 60, 10], [0xE0, 0, 64], [0xF0, 0],
                        [0xF7, 0], [0xF1, 0], [0xF8], [0xFE]):
            with self.subTest(payload=payload):
                self.reject(smf(event(0, payload) + end()))
        for kind in (0x20, 0x21, 0x54, 0x7F, 0x10):
            with self.subTest(meta_type=kind):
                self.reject(smf(meta(0, kind, b"\x00") + end()))

    def test_invalid_annotation_shapes(self):
        for data in (meta(1, 0, b"\x00\x01"), meta(0, 0, b"\x00"),
                     meta(0, 0x58, b"\x00\x02\x18\x08"),
                     meta(0, 0x58, b"\x04\x08\x18\x08"),
                     meta(0, 0x59, b"\x08\x00"),
                     meta(0, 0x59, b"\x00\x02")):
            self.reject(smf(data + note_on() + note_off() + end()))

    def test_note_lifetime_identity_rejections(self):
        for raw in (smf(note_off() + end()), smf(note_on() + end()),
                    smf(note_on() + note_on() + note_off() + end()),
                    smf(note_on() + note_off() + end(), note_on() + note_off() + end()),
                    smf(note_on() + end(), note_off() + end())):
            self.reject(raw)

    def test_note_identity_may_repeat_on_separate_tracks_sequentially(self):
        raw = smf(note_on() + note_off(480) + end(),
                  note_on(960) + note_off(480) + end())
        self.assertEqual([e["tick"] for e in convert_midi(raw)[0]["events"]],
                         [0, 24000, 48000, 72000])

    def test_absolute_midi_and_sample_u32_limits(self):
        body = note_on() + b"".join(meta(0x0FFFFFFF, 1) for _ in range(17))
        self.reject(smf(body + note_off(0) + end(), division=32767))
        # Valid MIDI tick, but 48 kHz sample timestamp is larger than u32.
        self.reject(smf(note_on() + note_off(0x0FFFFFFF) + end(), division=1))

    def test_resource_limits(self):
        self.reject(b"\x00" * (16 * 1024 * 1024 + 1))
        self.reject(smf(*(end() for _ in range(257)), midi_format=1))
        self.reject(smf(meta(0, 1, b"x" * 65537) + end()))
        self.reject(smf(meta(0, 1) * 100001 + note_on() + note_off() + end()))

    def test_original_encoder_record_bytes_independently_expected(self):
        from midi_import import load_encoder
        doc, _ = convert_midi(basic(release_velocity=37), 123)
        sid, records = load_encoder().encode_score(doc)
        self.assertEqual(sid, 123)
        self.assertEqual(records, b"\x00\x00\x00\x00\x00\x00\x3c\x64"
                         + b"\xc0\x5d\x00\x00\x01\x00\x3c\x25")


if __name__ == "__main__":
    unittest.main(verbosity=2)
