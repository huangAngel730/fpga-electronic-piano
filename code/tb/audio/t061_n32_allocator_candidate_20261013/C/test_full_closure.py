"""New software tests only: FULL identity, policy and immutable HDL."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/"code/software/t061_n32_stress_plan_candidate_20261013"))
import check_full_v6 as checker
from generate_v6 import build_v6_operations


class FullClosureTests(unittest.TestCase):
    def pair(self):
        body = [{"case_id": "C%02d_TEST" % i, "op": "tick"} for i in range(10)]
        return ([{"segment": "FULL"}, *body, {"record": "END"}],
                [{"segment": "FULL"}, {"record": "END"}])

    def test_full_exact_pair_identity(self):
        plan, expected = self.pair()
        with patch.object(checker, "generate", return_value=(plan, expected)) as generate:
            checker.input_identity(plan, expected)
            generate.assert_called_once_with("FULL")

    def test_short_suffix_rejected_before_capture(self):
        plan, expected = self.pair()
        plan[0]["segment"] = "SHORT_SUFFIX"
        with self.assertRaisesRegex(ValueError, "C_FULL_SEGMENT_REQUIRED"):
            checker.check(b"", plan, expected)

    def test_suffix_expected_rejected(self):
        plan, expected = self.pair()
        expected[0]["segment"] = "SHORT_SUFFIX"
        with self.assertRaisesRegex(ValueError, "C_FULL_SEGMENT_REQUIRED"):
            checker.input_identity(plan, expected)

    def test_missing_case_rejected(self):
        plan, expected = self.pair()
        del plan[-2]
        with self.assertRaisesRegex(ValueError, "C_FULL_CASE_SET"):
            checker.input_identity(plan, expected)

    def test_resigned_changed_plan_rejected(self):
        plan, expected = self.pair()
        changed = copy.deepcopy(plan)
        changed[1]["op"] = "reset"
        with patch.object(checker, "generate", return_value=(plan, expected)):
            with self.assertRaisesRegex(ValueError, "C_FULL_INPUT_IDENTITY"):
                checker.input_identity(changed, expected)

    def test_resigned_changed_expected_rejected(self):
        plan, expected = self.pair()
        changed = copy.deepcopy(expected)
        changed[0]["other"] = 1
        with patch.object(checker, "generate", return_value=(plan, expected)):
            with self.assertRaisesRegex(ValueError, "C_FULL_INPUT_IDENTITY"):
                checker.input_identity(plan, changed)

    def test_full_real_release_and_drain_boundaries(self):
        operations = build_v6_operations("FULL")
        self.assertEqual({op["case_id"].split("_")[0] for op in operations},
                         {"C%02d" % i for i in range(10)})
        self.assertEqual(sum(op["op"] == "sample" and
                             0x400000 <= op["result_id"] < 0x400000 + 4800 for op in operations), 4800)
        for i, op in enumerate(operations):
            if op["op"] == "set_result_ready" and op["value"] == 0:
                self.assertEqual(operations[i-1]["op"], "wait_idle")
            if op["case_id"] == "C09_EXACT_FULLSCALE_NOT_CLIPPED" and op["op"] == "reset":
                self.assertEqual(operations[i-1], {"case_id": "C08_HIGH_DENSITY", "op": "wait_idle"})


if __name__ == "__main__":
    unittest.main()
