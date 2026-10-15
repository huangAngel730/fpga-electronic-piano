"""Independent literal, boundary, and malformed-input tests for T057 wire."""
import unittest

from wire import crc, decode_frame, decode_records, encode_frame


class WireTests(unittest.TestCase):
    def test_crc_known_vector(self):
        self.assertEqual(crc(b'123456789'), 0x29b1)
        self.assertEqual(crc(b''), 0xffff)
        self.assertEqual(crc(b'\x00'), 0xe1f0)

    def test_literal_frame_and_little_endian_fields(self):
        # Literal STATUS header, body CRC checked by separate polynomial division.
        raw = bytes.fromhex('a55a010534127856bc9a0000')
        # Check body/header literal independently; CRC uses a separate polynomial long division.
        check = polynomial_crc(raw[2:])
        full = raw + check.to_bytes(2, 'little')
        self.assertEqual(encode_frame(5, 0x1234, 0x5678, 0x9abc), full)
        self.assertEqual(decode_frame(full), {'version': 1, 'command': 5, 'session': 0x1234,
                                            'seq': 0x5678, 'offset': 0x9abc,
                                            'payload': b'', 'crc_ok': True})

    def test_invalid_crc_is_decoded_not_accepted(self):
        raw = bytearray(encode_frame(2, 7, 1, payload=b'abc'))
        raw[-1] ^= 0x80
        decoded = decode_frame(bytes(raw))
        self.assertFalse(decoded['crc_ok'])
        self.assertEqual(decoded['payload'], b'abc')

    def test_nonstandard_command_version_and_zero_session_preserved(self):
        decoded = decode_frame(encode_frame(255, 0, 65535, 65535, b'\x00', 2))
        self.assertEqual((decoded['version'], decoded['command'], decoded['session']), (2, 255, 0))
        self.assertTrue(decoded['crc_ok'])

    def test_all_payload_lengths(self):
        for size in range(129):
            payload = bytes(range(size))
            raw = encode_frame(0x80, 65535, size, size, payload)
            self.assertEqual(decode_frame(raw)['payload'], payload)
            self.assertEqual(int.from_bytes(raw[-2:], 'little'), polynomial_crc(raw[2:-2]))

    def test_structural_rejections(self):
        raw = encode_frame(1, 1, 0, payload=b'abc')
        malformed = [b'', raw[:13], raw[:-1], raw + b'\x00', raw + raw,
                     b'\x00' + raw[1:], bytearray(raw), None]
        overlong = bytes.fromhex('a55a01010100000000008100') + b'x' * 129 + b'\x00\x00'
        malformed.append(overlong)
        for bad in malformed:
            with self.subTest(raw=bad), self.assertRaises(ValueError):
                decode_frame(bad)

    def test_encoder_argument_rejections(self):
        base = {'command': 1, 'session': 1, 'seq': 0}
        for field, value in (('command', True), ('command', 256), ('command', -1),
                             ('session', 65536), ('session', 1.0), ('seq', -1),
                             ('offset', 65536), ('version', 256),
                             ('payload', b'x' * 129), ('payload', bytearray())):
            args = {**base, field: value}
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                encode_frame(**args)
        for bad in (bytearray(), '', None):
            with self.assertRaises(ValueError):
                crc(bad)

    def test_literal_records(self):
        raw = bytes.fromhex('0000000000023c64c05d000001023c40')
        self.assertEqual(decode_records(raw), [
            {'tick': 0, 'type': 'note_on', 'channel': 2, 'note': 60, 'velocity': 100},
            {'tick': 24000, 'type': 'note_off', 'channel': 2, 'note': 60, 'velocity': 64}])
        self.assertEqual(len(decode_records(bytes.fromhex('ffffffff010f7f7f') * 512)), 512)
        self.assertEqual(decode_records(bytes.fromhex('0000000001000000'))[0]['velocity'], 0)

    def test_record_bad_capacity_and_fields(self):
        for raw in (b'', b'x', b'x' * 4097, b'\x00' * 4104, bytearray(8)):
            with self.assertRaises(ValueError):
                decode_records(raw)
        base = bytes.fromhex('0000000000023c64')
        for index, value in ((4, 2), (5, 16), (6, 128), (7, 128), (7, 0)):
            bad = bytearray(base)
            bad[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                decode_records(bytes(bad))
        with self.assertRaisesRegex(ValueError, 'TICK_ORDER'):
            decode_records(bytes.fromhex('0100000000023c640000000001023c00'))


def polynomial_crc(raw):
    """Separate polynomial long-division oracle, not production CRC stepping."""
    remainder = 0xffff
    for byte in raw:
        remainder = (remainder << 8) ^ (byte << 16)
        for bit in range(23, 15, -1):
            if remainder & (1 << bit):
                remainder ^= 0x11021 << (bit - 16)
    return remainder


if __name__ == '__main__':
    unittest.main()
