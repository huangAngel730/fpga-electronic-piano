"""Failures must be propagated even if a subscript prints a PASS line."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_audio_delivery import accept_result


class AudioGateExitTests(unittest.TestCase):
    def test_real_exit_and_coverage_marker(self):
        self.assertTrue(accept_result(0, "T010 review: 6/6 scenarios pass", r"T010 review: 6/6 scenarios pass"))

    def test_failure_exit_must_not_pass(self):
        self.assertFalse(accept_result(1, "PASS T010 review: 6/6 scenarios pass", r"T010 review: 6/6 scenarios pass"))

    def test_missing_sample_coverage_must_not_pass(self):
        self.assertFalse(accept_result(0, "All repository checks passed.", r"T010 review: 6/6 scenarios pass"))

    def test_partial_t010_rejected(self):
        self.assertFalse(accept_result(0, "T010 review: 3/6 scenarios pass", r"T010 review: 6/6 scenarios pass"))

    def test_truncated_audio_comparison_rejected(self):
        self.assertFalse(accept_result(0, "PASS mixer: 30 stereo frames", r"PASS mixer: 3008 stereo frames"))


if __name__ == "__main__":
    unittest.main()
