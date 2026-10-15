#!/usr/bin/env python3
"""Unit tests for the offline R04 frame-budget analyzer."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from frame_budget_offline import CsvFormatError, analyze_csv


FIELDS = (
    "frame_index",
    "frame_cycles",
    "max_processing_cycles",
    "underrun_count",
)


class FrameBudgetOfflineTests(unittest.TestCase):
    def write_rows(self, rows: list[tuple[int, int, int, int]]) -> Path:
        temporary = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", suffix=".csv", delete=False
        )
        with temporary:
            writer = csv.writer(temporary)
            writer.writerow(FIELDS)
            writer.writerows(rows)
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return Path(temporary.name)

    def test_accepts_833_834_distribution_below_processing_deadline(self) -> None:
        path = self.write_rows(
            [(0, 833, 700, 0), (1, 834, 720, 0), (2, 833, 720, 0)]
        )
        result = analyze_csv(path)
        self.assertEqual("PASS", result["status"])
        self.assertEqual(
            {"833": 2, "834": 1},
            result["observed"]["frame_cycles_distribution"],
        )

    def test_rejects_processing_deadline_equal_to_834(self) -> None:
        path = self.write_rows([(0, 833, 833, 0), (1, 834, 834, 0)])
        result = analyze_csv(path)
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(
            any("MAX_PROCESSING_DEADLINE_FAIL" in reason for reason in result["reasons"])
        )

    def test_rejects_nonzero_underrun(self) -> None:
        path = self.write_rows([(0, 833, 700, 0), (1, 834, 700, 1)])
        result = analyze_csv(path)
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(any("UNDERRUN_NONZERO" in reason for reason in result["reasons"]))

    def test_rejects_frame_period_outside_833_834(self) -> None:
        path = self.write_rows([(0, 832, 700, 0)])
        result = analyze_csv(path)
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(
            any("FRAME_CYCLES_OUT_OF_CONTRACT" in reason for reason in result["reasons"])
        )

    def test_rejects_counter_rollback(self) -> None:
        path = self.write_rows([(0, 833, 700, 0), (1, 834, 699, 0)])
        result = analyze_csv(path)
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(
            any("MAX_PROCESSING_COUNTER_ROLLBACK" in reason for reason in result["reasons"])
        )

    def test_missing_field_is_schema_error(self) -> None:
        temporary = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", suffix=".csv", delete=False
        )
        with temporary:
            temporary.write("frame_index,frame_cycles\n0,833\n")
        path = Path(temporary.name)
        self.addCleanup(path.unlink, missing_ok=True)
        with self.assertRaises(CsvFormatError):
            analyze_csv(path)


if __name__ == "__main__":
    unittest.main()
