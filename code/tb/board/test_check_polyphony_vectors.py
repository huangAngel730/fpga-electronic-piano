"""Independent acceptance tests for the T010 vector preflight."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from check_polyphony_vectors import VectorError, check_vector, main


class VectorPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "polyphony.txt"

    def put(self, *rows):
        self.path.write_text("# T010 integration\n" + "\n".join(rows) + "\n",
                             encoding="utf-8")

    def test_four_voices_and_signed_pcm(self):
        self.put("0 000000 0 1 0 0 0 0",
                 "1 ffffff -1 1 1 1 1 0",
                 "2 7fffff 8388607 1 1 1 1 1")
        self.assertEqual(check_vector(self.path), (3, 4, 2))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.path)]), 0)

    def test_three_voice_vector_fails_process_exit(self):
        self.put("0 000001 1 1 1 1 0 0")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(self.path)]), 1)

    def test_four_silent_voices_are_not_audible_coverage(self):
        self.put("0 000000 0 1 1 1 1 0")
        with self.assertRaisesRegex(VectorError, "nonzero_four_voice_frames=0"):
            check_vector(self.path)

    def test_mismatched_pcm_encoding_rejected(self):
        self.put("0 ffffff 1 1 1 1 1 0")
        with self.assertRaisesRegex(VectorError, "decimal/hex mismatch"):
            check_vector(self.path)

    def test_frame_gap_rejected(self):
        self.put("0 000001 1 1 1 1 1 0",
                 "2 000001 1 1 1 1 1 0")
        with self.assertRaisesRegex(VectorError, "expected 1"):
            check_vector(self.path)

    def test_clipping_flag_requires_saturation(self):
        self.put("0 000001 1 1 1 1 1 1")
        with self.assertRaisesRegex(VectorError, "clipping flag"):
            check_vector(self.path)


if __name__ == "__main__":
    unittest.main()
