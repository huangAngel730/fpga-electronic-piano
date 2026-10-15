"""Offline contract tests: literals plus original-codec interoperability."""
import copy
import importlib.util
from pathlib import Path
import struct
import unittest

from offline_readback import crc_ccitt_false, decode_records, decode_upload, verify_roundtrip

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('original_t057_test_codec', ROOT / 'code/software/score_transfer_v1/score_transfer.py')
CODEC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CODEC)


def document():
    return {'schema': 1, 'sample_hz': 48000, 'score_id': 0x12345678, 'events': [
        {'tick': 0, 'type': 'note_on', 'channel': 2, 'note': 60, 'velocity': 100},
        {'tick': 24000, 'type': 'note_off', 'channel': 2, 'note': 60, 'velocity': 64}]}


def frames(records=None, count=2, total=16, score_crc=None, sample=48000, session=7):
    if records is None:
        records = bytes.fromhex('0000000000023c64c05d000001023c40')
    if score_crc is None:
        score_crc = CODEC.crc(records)
    return [CODEC.frame(1, session, 0, payload=struct.pack('<IHHHI', 0x12345678, count, total, score_crc, sample)),
            CODEC.frame(2, session, 1, 0, records), CODEC.frame(3, session, 2)]


class OfflineReadbackTests(unittest.TestCase):
    def test_crc_golden_and_literal_records(self):
        self.assertEqual(crc_ccitt_false(b'123456789'), 0x29b1)
        self.assertEqual(crc_ccitt_false(b''), 0xffff)
        raw = bytes.fromhex('0000000000023c64c05d000001023c40')
        self.assertEqual(decode_records(raw), document()['events'])
        sid, rebuilt, session = decode_upload(b''.join(frames()))
        self.assertEqual((sid, rebuilt, session), (0x12345678, raw, 7))

    def test_original_encoder_and_unaligned_chunks(self):
        doc = document()
        sid, records = CODEC.encode_score(doc)
        self.assertEqual(records.hex(), '0000000000023c64c05d000001023c40')
        for chunk in (1, 3, 7, 8, 13, 128):
            with self.subTest(chunk=chunk):
                report = verify_roundtrip(doc, records, b''.join(CODEC.upload_frames(sid, records, 65535, chunk)))
                self.assertEqual(report['events_compared'], 2)
                self.assertFalse(report['hardware_pass_claim'])

    def test_zero_velocity_is_canonical_note_off(self):
        doc = document()
        doc['events'][1].update(type='note_on', velocity=0)
        sid, records = CODEC.encode_score(doc)
        self.assertEqual(records[12], 1)
        self.assertEqual(decode_records(records)[1]['type'], 'note_off')
        verify_roundtrip(doc, records, b''.join(CODEC.upload_frames(sid, records, 1)))

    def test_capacity_512_and_u32_boundary(self):
        raw = bytes.fromhex('ffffffff010f7f7f') * 512
        self.assertEqual(len(decode_records(raw)), 512)
        sid, rebuilt, session = decode_upload(b''.join(CODEC.upload_frames(0xffffffff, raw, 1)))
        self.assertEqual((sid, rebuilt, session), (0xffffffff, raw, 1))
        for bad in (b'', b'\x00', raw + raw[:8], bytearray(raw)):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                decode_records(bad)

    def test_record_legality_and_order(self):
        base = bytearray(bytes.fromhex('0000000000023c64c05d000001023c40'))
        for index, value in ((4, 2), (5, 16), (6, 128), (7, 128), (7, 0)):
            bad = base.copy()
            bad[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                decode_records(bytes(bad))
        base[:4] = (24001).to_bytes(4, 'little')
        with self.assertRaisesRegex(ValueError, 'TICK_ORDER'):
            decode_records(bytes(base))

    def test_frame_structure_failures(self):
        raw = b''.join(frames())
        cases = [b'', raw[:-1], raw + b'x', b'x' + raw, raw[1:]]
        for index in (0, 2, 3, 4, 10, 12, 26):
            altered = bytearray(raw)
            altered[index] ^= 1
            cases.append(bytes(altered))
        cases.append(CODEC.frame(1, 7, 0, payload=b'x', version=2))
        # Header declares 129 bytes despite a physically short buffer.
        cases.append(b'\xa5\x5a' + bytes.fromhex('01010700000000008100') + b'\x00\x00')
        for bad in cases:
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                decode_upload(bad)

    def test_upload_transaction_failures_with_valid_frame_crc(self):
        a, b, c = frames()
        raw = bytes.fromhex('0000000000023c64c05d000001023c40')
        cases = [b + c, a + c, a + b, a + b + c + c, a + b + b + c,
                 a + CODEC.frame(2, 8, 1, 0, raw) + c,
                 a + CODEC.frame(2, 7, 2, 0, raw) + c,
                 a + CODEC.frame(2, 7, 1, 1, raw) + c,
                 a + CODEC.frame(2, 7, 1, 0, b'') + c,
                 a + CODEC.frame(3, 7, 1, 1),
                 a + b + CODEC.frame(3, 7, 2, 0, b'x'),
                 a + CODEC.frame(5, 7, 1),
                 a + CODEC.frame(2, 7, 1, 0, raw + raw[:1]) + c]
        for kwargs in ({'count': 0}, {'count': 513}, {'total': 15}, {'sample': 44100},
                       {'score_crc': 0}, {'session': 0}):
            cases.append(b''.join(frames(**kwargs)))
        for bad in cases:
            with self.subTest(raw=bad.hex()), self.assertRaises(ValueError):
                decode_upload(bad)

    def test_uploaded_illegal_record_rejected_after_valid_crcs(self):
        bad = bytes.fromhex('0000000000023c00c05d000001023c40')
        with self.assertRaisesRegex(ValueError, 'ZERO_NOTE_ON'):
            decode_upload(b''.join(frames(records=bad)))

    def test_json_strict_schema_and_types(self):
        doc = document()
        records = bytes.fromhex('0000000000023c64c05d000001023c40')
        raw = b''.join(frames())
        bad_docs = []
        for key, value in (('schema', True), ('schema', 2), ('sample_hz', 48000.0),
                           ('sample_hz', 44100), ('score_id', True), ('score_id', -1),
                           ('score_id', 0x100000000), ('events', []), ('events', tuple(doc['events']))):
            bad = copy.deepcopy(doc)
            bad[key] = value
            bad_docs.append(bad)
        bad = copy.deepcopy(doc)
        bad['extra'] = 1
        bad_docs.append(bad)
        for key, value in (('tick', True), ('tick', -1), ('tick', 0x100000000),
                           ('channel', 16), ('note', 128), ('velocity', 128),
                           ('type', 'program_change'), ('velocity', 1.0)):
            bad = copy.deepcopy(doc)
            bad['events'][0][key] = value
            bad_docs.append(bad)
        for bad in bad_docs:
            with self.subTest(document=bad), self.assertRaises(ValueError):
                verify_roundtrip(bad, records, raw)

    def test_readback_mismatch_rejection(self):
        doc = document()
        records = bytes.fromhex('0000000000023c64c05d000001023c40')
        altered = bytearray(records)
        altered[7] = 99
        with self.assertRaisesRegex(ValueError, 'READBACK_RECORD_MISMATCH'):
            verify_roundtrip(doc, bytes(altered), b''.join(frames()))
        with self.assertRaisesRegex(ValueError, 'READBACK_UPLOAD_MISMATCH'):
            verify_roundtrip(doc, records, b''.join(frames(records=bytes(altered))))
        upload = b''.join(CODEC.upload_frames(42, records, 7))
        with self.assertRaisesRegex(ValueError, 'SCORE_ID_MISMATCH'):
            verify_roundtrip(doc, records, upload)


if __name__ == '__main__':
    unittest.main()
