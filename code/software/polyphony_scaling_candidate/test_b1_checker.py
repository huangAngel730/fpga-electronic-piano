"""Small checker unit tests; the runner separately replays actual RTL captures."""
import unittest

from b1_check import CW, MASK, operation, replay, unpack
from protocol_oracle import Tag


class B1CheckerTests(unittest.TestCase):
    def test_full_width_identity_for_all_N(self):
        for sw in (2, 3, 4, 5):
            slot = (1 << sw) - 1
            tag = (0xffffffff << (sw + 40)) | (15 << (sw + 36)) | (14 << (sw + 32)) | (0xffffffff << sw) | slot
            self.assertEqual(unpack(tag, sw), Tag(slot, 15, 14, 0xffffffff, 0xffffffff))

    def test_fixture_high_context_is_not_truncated(self):
        context = 1 << (CW - 1)
        result = operation(context, 0, 0, 0, False)
        self.assertEqual(result >> 32, (MASK ^ context) >> 32)
        self.assertEqual(result & 0xffffffff, 0xffffffff ^ 0x5a36c17e)

    def test_pedal_and_flag_independent_bits(self):
        first = operation(0, 0, 0, 0, False)
        self.assertEqual(first ^ operation(0, 0, 0, 0, True), 1 << 31)
        self.assertEqual(first ^ operation(0, 0, 0, 2, False), 2 << 20)

    def test_no_header_rejected(self):
        with self.assertRaisesRegex(ValueError, "HEADER_MISSING"):
            replay(b"B1_END 10 0\n")

    def test_unsupported_profile_rejected(self):
        with self.assertRaisesRegex(ValueError, "PROFILE"):
            replay(b"B1_HEADER 3 1 0\n")

    def test_missing_data_or_unknown_tag_rejected(self):
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_CAPTURE"):
            replay(b"B1_HEADER 4 1 0\n")
        with self.assertRaisesRegex(ValueError, "EVENT_SCHEMA"):
            replay(b"B1_HEADER 4 1 0\nB1 1 FAKE\n")


if __name__ == "__main__":
    unittest.main()
