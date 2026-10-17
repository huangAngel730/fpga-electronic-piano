"""Small independently known arithmetic/schema boundary assertions."""
import unittest

from b2_check import check, mix_signed24


class BackendCheckerTests(unittest.TestCase):
    def test_signed_mixer_limits(self):
        self.assertEqual(mix_signed24([8388607, 0, 0, 0]), (8388607, False))
        self.assertEqual(mix_signed24([-8388608, 0, 0, 0]), (-8388608, False))
        self.assertEqual(mix_signed24([8388607, 1, 0, 0]), (8388607, True))
        self.assertEqual(mix_signed24([-8388608, -1, 0, 0]), (-8388608, True))

    def test_growth_and_cancellation(self):
        for n in (4, 8, 16, 32):
            self.assertEqual(mix_signed24([8388607, -8388607] * (n // 2)), (0, False))
            self.assertEqual(mix_signed24([8388607] * n), (8388607, True))

    def test_no_bool_or_out_of_range(self):
        for voices in ([True, 0, 0, 0], [8388608, 0, 0, 0], [-8388609, 0, 0, 0], [0] * 3):
            with self.assertRaisesRegex(ValueError, "MIX_INPUT_RANGE"):
                mix_signed24(voices)

    def test_unknown_and_extra_columns_reject(self):
        for raw in (b"B2 4 1 0\nR 0 extra\n", b"B2 4 1 0\nR 0\nBOGUS 1\n"):
            with self.assertRaisesRegex(ValueError, "ROW_SCHEMA"):
                check(raw)

    def test_missing_reset_rejects(self):
        with self.assertRaisesRegex(ValueError, "MISSING_INITIAL_RESET"):
            check(b"B2 4 1 0\nA 1 0\n")

    def test_empty_or_missing_end_rejects(self):
        for raw in (b"", b"B2 4 1 0\nR 0\n"):
            with self.assertRaises(ValueError):
                check(raw)


if __name__ == "__main__":
    unittest.main()
