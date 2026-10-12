"""Only new scope identity/refusal tests, not old audio or capture replay."""

import copy
from pathlib import Path
import tempfile
import unittest

import scope_bundle as scope


class ScopeBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="t060_scope_tests_")
        cls.bundle = Path(cls.temp.name) / "bundle"
        scope.prepare(scope.ROOT, cls.bundle)
        cls.original = scope.load((cls.bundle / "scope.json").read_bytes())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def reject(self, edit, diagnostic):
        bad = copy.deepcopy(self.original)
        edit(bad)
        with self.assertRaisesRegex(ValueError, diagnostic):
            scope.validate_summary(bad, self.original)

    def test_portable_positive(self):
        self.assertEqual(scope.verify(self.bundle)["exit_code"], 0)
        self.assertEqual(len(self.original["ROM_identity"]), 7)
        self.assertEqual(len(self.original["dependency_identity"]), 13)

    def test_wrong_input_sha(self):
        self.reject(lambda s: s["input_identity"]["audio_observation.jsonl"].update(sha256="0" * 64),
                    "SCOPE_INPUT_IDENTITY")

    def test_wrong_ROM_sha(self):
        self.reject(lambda s: next(iter(s["ROM_identity"].values())).update(sha256="0" * 64),
                    "SCOPE_ROM_IDENTITY")

    def test_wrong_dependency_sha(self):
        self.reject(lambda s: next(iter(s["dependency_identity"].values())).update(sha256="0" * 64),
                    "SCOPE_DEPENDENCY_IDENTITY")

    def test_missing_ROM(self):
        self.reject(lambda s: s["ROM_identity"].pop(next(iter(s["ROM_identity"]))),
                    "SCOPE_ROM_IDENTITY")

    def test_missing_dependency(self):
        self.reject(lambda s: s["dependency_identity"].pop(next(iter(s["dependency_identity"]))),
                    "SCOPE_DEPENDENCY_IDENTITY")

    def test_wrong_source_sha(self):
        self.reject(lambda s: next(iter(s["frozen_source_identity"].values())).update(sha256="0" * 64),
                    "SCOPE_SOURCE_IDENTITY")

    def test_re_signed_bad_authority(self):
        with tempfile.TemporaryDirectory(prefix="t060_bad_receipt_") as tmp:
            folder = Path(tmp)
            (folder / "authority").mkdir()
            for p in (self.bundle / "authority").iterdir():
                raw = p.read_bytes() + (b" " if p.name == "counter_review.json" else b"")
                (folder / "authority" / p.name).write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "SCOPE_RECEIPT_SHA:counter_review"):
                scope.read_authority(folder)

    def test_missing_actual_receipt(self):
        with tempfile.TemporaryDirectory(prefix="t060_missing_receipt_") as tmp:
            folder = Path(tmp)
            (folder / "authority").mkdir()
            for p in (self.bundle / "authority").iterdir():
                if p.name != "router_receipt.json":
                    (folder / "authority" / p.name).write_bytes(p.read_bytes())
            with self.assertRaisesRegex(ValueError, "SCOPE_RECEIPT_SET"):
                scope.read_authority(folder)

    def test_missing_receipt_claim(self):
        self.reject(lambda s: s["reused_receipts"].pop("router_receipt.json"), "SCOPE_RECEIPT_IDENTITY")

    def test_widen_window(self):
        self.reject(lambda s: s["EXCLUDED_METADATA_EXPECTATION"].update(cycle_window=[1744211, 1745045]),
                    "SCOPE_EXCLUSION_WIDENED")

    def test_all_flags_excluded(self):
        self.reject(lambda s: s["EXCLUDED_METADATA_EXPECTATION"].update(all_fixture_flags=True),
                    "SCOPE_EXCLUSION_WIDENED")

    def test_extra_excluded_point(self):
        self.reject(lambda s: s["EXCLUDED_METADATA_EXPECTATION"]["fixture_points"].append(
            copy.deepcopy(s["EXCLUDED_METADATA_EXPECTATION"]["fixture_points"][0])),
                    "SCOPE_EXCLUSION_WIDENED")

    def test_wrong_point(self):
        self.reject(lambda s: s["EXCLUDED_METADATA_EXPECTATION"]["fixture_points"][0].update(cycle=1744210),
                    "SCOPE_EXCLUSION_WIDENED")

    def test_flag_bool_not_integer(self):
        self.reject(lambda s: s["EXCLUDED_METADATA_EXPECTATION"]["fixture_points"][0].update(observed_flag=True),
                    "SCOPE_EXCLUSION_WIDENED")

    def test_excluded_not_zero_or_pass(self):
        for value in (0, "PASS"):
            self.reject(lambda s: s["EXCLUDED_METADATA_EXPECTATION"]["END"][0].update(expected=value),
                        "SCOPE_EXCLUSION_WIDENED")

    def test_no_PCM_exclusion(self):
        self.reject(lambda s: s["EXCLUDED_METADATA_EXPECTATION"]["fixture_points"][0].update(
            PCM_math_and_timing_excluded=True), "SCOPE_EXCLUSION_WIDENED")

    def test_no_complete(self):
        for key in ("t060_complete", "t061_complete"):
            self.reject(lambda s: s.update({key: True}), "SCOPE_FALSE_COMPLETE")

    def test_no_false_STA(self):
        self.reject(lambda s: s.update(physical_STA_passed=True), "SCOPE_FALSE_STA")

    def test_false_is_not_zero(self):
        self.reject(lambda s: s.update(physical_STA_passed=0), "SCOPE_FALSE_STA")

    def test_no_false_physical(self):
        self.reject(lambda s: s.update(physical_validation=True), "SCOPE_FALSE_PHYSICAL")

    def test_no_RTL_permission(self):
        self.reject(lambda s: s.update(new_RTL_execution_authorized=True), "SCOPE_FALSE_RTL_PERMISSION")

    def test_no_gap_waiver(self):
        self.reject(lambda s: s.update(UNCOVERED=[]), "SCOPE_FUNCTIONAL_GAP_WAIVED")

    def test_no_strict_check_removed(self):
        self.reject(lambda s: s.update(mandatory_strict_checks=[]), "SCOPE_STRICT_CHECKS_REMOVED")

    def test_old_exit3_retained(self):
        self.reject(lambda s: s["old_entry"].update(exit_code=0), "SCOPE_OLD_PARTIAL_CHANGED")

    def test_no_new_math_claim(self):
        self.reject(lambda s: s["REUSED"]["router_and_audio_math"].update(new_execution=True),
                    "SCOPE_FALSE_REPLAY_CLAIM")

    def test_unknown_summary_field(self):
        self.reject(lambda s: s.update(STA="PASS"), "SCOPE_SUMMARY_SCHEMA_OR_BOUNDARY")

    def test_duplicate_and_nonfinite_json(self):
        for raw, diagnostic in ((b'{"x":1,"x":2}', "SCOPE_DUPLICATE_KEY"),
                                (b'{"x":NaN}', "SCOPE_NONFINITE")):
            with self.assertRaisesRegex(ValueError, diagnostic):
                scope.load(raw)

    def test_refuse_existing_output(self):
        with self.assertRaisesRegex(ValueError, "SCOPE_OUTPUT_EXISTS"):
            scope.prepare(scope.ROOT, self.bundle)


if __name__ == "__main__":
    unittest.main()
