"""Small scope projection negatives, not capture2/old 56-case replay."""

import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads((scope.REVIEW / "ACCEPTANCE_SCOPE.json").read_text(encoding="utf-8"))

    def test_null_preserved(self):
        result = scope.project(self.original)
        self.assertEqual(len(result["END_metadata"]), 3)
        self.assertTrue(all(e["expected"] is None for e in result["END_metadata"]))
        self.assertFalse(result["t060_complete"])

    def test_no_widening(self):
        bad = copy.deepcopy(self.original)
        bad["exact_fixture_metadata_expectation_exclusions"][0]["cycle"] -= 1
        with self.assertRaisesRegex(ValueError, "T060_SCOPE_FLAG_POINTS"):
            scope.project(bad)

    def test_no_zero_golden(self):
        bad = copy.deepcopy(self.original)
        bad["END_metadata_expectation_exclusions"][0]["independently_expected"] = 0
        with self.assertRaisesRegex(ValueError, "T060_SCOPE_END_EXCLUSIONS"):
            scope.project(bad)

    def test_no_boolean_flag(self):
        bad = copy.deepcopy(self.original)
        bad["exact_fixture_metadata_expectation_exclusions"][0]["observed_flag"] = True
        with self.assertRaisesRegex(ValueError, "T060_SCOPE_FLAG_TYPE"):
            scope.project(bad)

    def test_no_complete(self):
        bad = copy.deepcopy(self.original)
        bad["t060_complete"] = True
        with self.assertRaisesRegex(ValueError, "T060_SCOPE_BOUNDARY"):
            scope.project(bad)


if __name__ == "__main__":
    unittest.main()
