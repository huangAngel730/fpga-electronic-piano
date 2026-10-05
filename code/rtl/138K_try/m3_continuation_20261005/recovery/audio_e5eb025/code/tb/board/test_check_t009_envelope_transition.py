"""Tests the T009 gate itself; these do not assert that the current M1 model passes."""

import contextlib
import io
import unittest
from unittest.mock import patch

from check_t009_envelope_transition import (
    ATTACK_STEP_BOUND,
    continuity_error,
    main,
)


class GateTests(unittest.TestCase):
    def test_boundary_is_inclusive(self):
        self.assertIsNone(continuity_error(5000, 5000 + ATTACK_STEP_BOUND,
                                           ATTACK_STEP_BOUND, "attack"))

    def test_jump_exceeding_bound_fails(self):
        error = continuity_error(6533, 54, ATTACK_STEP_BOUND, "retrigger")
        self.assertIn("delta=6479", error)

    def test_invalid_q15_level_fails(self):
        self.assertIn("Q1.15", continuity_error(-1, 0, 2, "invalid"))

    def test_real_failure_returns_nonzero(self):
        with patch("check_t009_envelope_transition.evaluate",
                   return_value=(["large jump"], ["sample detail"])):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(), 1)

    def test_success_returns_zero(self):
        with patch("check_t009_envelope_transition.evaluate",
                   return_value=([], ["sample detail"])):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
