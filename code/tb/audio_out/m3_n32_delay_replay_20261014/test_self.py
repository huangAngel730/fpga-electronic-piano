#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from check_replay import DelayReference, PCM_MAX, PCM_MIN, q15_term, sat24


class FixedPointTests(unittest.TestCase):
    def test_saturation_edges(self) -> None:
        self.assertEqual(sat24(PCM_MAX), (PCM_MAX, False))
        self.assertEqual(sat24(PCM_MAX + 1), (PCM_MAX, True))
        self.assertEqual(sat24(PCM_MIN), (PCM_MIN, False))
        self.assertEqual(sat24(PCM_MIN - 1), (PCM_MIN, True))

    def test_negative_q15_is_arithmetic_shift(self) -> None:
        self.assertEqual(q15_term(-3, 16384), -2)

    def test_bypass_does_not_advance_history(self) -> None:
        model = DelayReference()
        self.assertEqual(model.accept(123, -456, 0)["left"], 123)
        self.assertEqual(model.pointer, 0)
        self.assertEqual(model.left_history[0], 0)

    def test_enable_flushes_history(self) -> None:
        model = DelayReference()
        model.configure(True, 1, 32767, 32767, 0)
        model.accept(1000, 1000, 0)
        self.assertEqual(model.pointer, 1)
        model.configure(False, 1, 32767, 0, 0)
        self.assertEqual(model.pointer, 0)
        self.assertTrue(all(value == 0 for value in model.left_history))

    def test_delay_change_flushes_history(self) -> None:
        model = DelayReference()
        model.configure(True, 1, 32767, 32767, 0)
        model.accept(1000, 1000, 0)
        model.configure(True, 2, 32767, 32767, 0)
        self.assertEqual(model.pointer, 0)
        self.assertTrue(all(value == 0 for value in model.left_history))

    def test_gain_change_preserves_history(self) -> None:
        model = DelayReference()
        model.configure(True, 1, 32767, 32767, 0)
        model.accept(1000, 1000, 0)
        before = list(model.left_history)
        model.configure(True, 1, 12345, 23456, 1)
        self.assertEqual(model.pointer, 1)
        self.assertEqual(model.left_history, before)

    def test_delay_zero_reads_old_pointer_cell(self) -> None:
        model = DelayReference()
        model.configure(True, 0, 0, 32767, 0)
        first = model.accept(2000, 2000, 0)
        self.assertEqual(first["left"], 0)
        for _ in range(1023):
            model.accept(0, 0, 0)
        wrapped = model.accept(0, 0, 0)
        self.assertGreater(wrapped["left"], 0)

    def test_pointer_wrap(self) -> None:
        model = DelayReference()
        model.configure(True, 1023, 32767, 0, 0)
        for index in range(1025):
            model.accept(index, index, 0)
        self.assertEqual(model.pointer, 1)
        self.assertEqual(model.maximum_enabled_run, 1025)

    def test_upstream_clip_propagates_in_bypass(self) -> None:
        model = DelayReference()
        self.assertTrue(model.accept(0, 0, 1)["clip"])

    def test_result_clip_does_not_include_feedback_clip(self) -> None:
        model = DelayReference()
        model.configure(True, 1, 0, 0, 32767)
        model.left_history[1023] = PCM_MAX
        result = model.accept(PCM_MAX, PCM_MAX, 0)
        self.assertFalse(result["clip"])
        self.assertTrue(result["feedback_clip_left"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
