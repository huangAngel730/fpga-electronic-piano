"""Software-only rejection checks for a FULL capture reuse successor."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/"code/software/t061_n32_stress_plan_candidate_20261013"))
import full_reuse_guard as guard


class ReuseGuardTests(unittest.TestCase):
    def arguments(self):
        sources = {guard.SOFTWARE + "check_full_v6.py": {"sha256": guard.OLD_CHECKER_SHA},
                   "assets/plan_v6.jsonl": {"sha256": "plan"},
                   "assets/expected_v6.jsonl": {"sha256": "math"}}
        tools = {"tool": {"sha256": "tool"}}
        plan = {"profile": "full-v6", "tool_files": tools}
        receipt = {"status": "FAIL_PARTIAL", "exit_code": 1,
                   "failure": "ValueError:C_STEP_FAILED:mutations", "inputs_after": sources,
                   "tools_after": tools, "steps": [{"name": name, "exit_code": int(name == "mutations"),
                      "failure": None, "timeout": False} for name in ("compile", "simulate", "check", "mutations")]}
        normal = {"status": "N32_C_STRESS_PASS_T061_PARTIAL", "complete_C_capture": True,
                  "single_continuous_full_C_run": True, "capture_composition": False,
                  "independent_clocked_math": {"lifecycle": {"retirements": 4}}}
        return [plan, receipt, normal, {"status": "REJECT", "reason": ""},
                sources, copy.deepcopy(sources), tools]

    def test_known_failure_only_is_qualified(self):
        self.assertEqual(guard.qualify(*self.arguments())["execution_mode"], "RTL_REUSED_NO_NEW_SIMULATION")

    def test_suffix_capture_is_rejected(self):
        arguments = self.arguments(); arguments[0]["profile"] = "suffix-v6"
        with self.assertRaisesRegex(ValueError, "C_FULL_REUSE_FRESH_FULL_ORIGIN_REQUIRED"):
            guard.qualify(*arguments)

    def test_failed_or_timed_out_simulation_is_rejected(self):
        for field, value in (("exit_code", 1), ("timeout", True)):
            arguments = self.arguments(); arguments[1]["steps"][1][field] = value
            with self.assertRaisesRegex(ValueError, "C_FULL_REUSE_COMPLETED_SIM_AND_CHECK_REQUIRED"):
                guard.qualify(*arguments)

    def test_re_signed_full_plan_or_expected_is_rejected(self):
        for name in ("assets/plan_v6.jsonl", "assets/expected_v6.jsonl"):
            arguments = self.arguments(); arguments[5][name] = {"sha256": "changed"}
            with self.assertRaisesRegex(ValueError, "C_FULL_REUSE_INPUT_DRIFT"):
                guard.qualify(*arguments)

    def test_arbitrary_checker_failure_is_rejected(self):
        arguments = self.arguments(); arguments[3]["reason"] = "other"
        with self.assertRaisesRegex(ValueError, "C_FULL_REUSE_KNOWN_STOPITERATION_ONLY"):
            guard.qualify(*arguments)

    def test_model_change_and_new_model_are_rejected(self):
        arguments = self.arguments(); arguments[5]["math_model.py"] = {"sha256": "new"}
        with self.assertRaisesRegex(ValueError, "C_FULL_REUSE_INPUT_DRIFT"):
            guard.qualify(*arguments)

    def test_normal_function_change_is_rejected(self):
        original = "def check(): return 1\ndef input_identity(): pass\ndef main(): pass\n"
        guard.unchanged_normal_functions(original, original)
        with self.assertRaisesRegex(ValueError, "C_FULL_REUSE_NORMAL_CHECKER_CHANGED"):
            guard.unchanged_normal_functions(original, original.replace("return 1", "return 2"))


if __name__ == "__main__":
    unittest.main()
