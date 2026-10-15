"""New recovery/authority boundary tests only; old 32/13 suites are reused."""
import hashlib
import json
from pathlib import Path
import unittest

import importlib.util

spec = importlib.util.spec_from_file_location("freeze_audit", Path(__file__).with_name("freeze_audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class RecoveryTests(unittest.TestCase):
    def test_known_sha(self):
        self.assertEqual(audit.identity(b"")["sha256"], "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_duplicate_recorded_mapping_is_not_double_edit(self):
        operations = [{"old": '"C:/original/a.mem"', "new": '"rom/a.mem"'}] * 2
        raw, receipt = audit.inverse_paths(b'x="rom/a.mem"; y="rom/a.mem";', operations)
        self.assertEqual(raw, b'x="C:/original/a.mem"; y="C:/original/a.mem";')
        self.assertEqual([x["replacements"] for x in receipt], [2, 0])

    def test_inverse_does_not_change_semantic_bytes(self):
        raw, _ = audit.inverse_paths(b'base_s2<=base_s1; "rom/a.mem"\r\n', [{"old": '"C:/a.mem"', "new": '"rom/a.mem"'}])
        self.assertEqual(raw, b'base_s2<=base_s1; "C:/a.mem"\r\n')

    def test_missing_literal_cannot_invent_bytes(self):
        raw, receipt = audit.inverse_paths(b"original-no-path", [{"old": "old", "new": "absent"}])
        self.assertEqual(raw, b"original-no-path")
        self.assertEqual(receipt[0]["replacements"], 0)

    def test_wrong_reconstruction_fails_identity_comparison(self):
        raw, _ = audit.inverse_paths(b'"rom/a.mem"', [{"old": '"C:/wrong.mem"', "new": '"rom/a.mem"'}])
        self.assertNotEqual(audit.identity(raw), audit.identity(b'"C:/correct.mem"'))

    def test_windows_receipt_path_normalized(self):
        self.assertEqual(audit.safe_relative("inputs\\sources\\pitch.sv"), "inputs/sources/pitch.sv")

    def test_unsafe_receipt_names_rejected(self):
        for name in ("../bad", "inputs/../../bad", "C:/outside", "/inputs/a", "other/a"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                audit.safe_relative(name)

    def test_fresh_output_only(self):
        with self.assertRaises(ValueError):
            audit.audit(audit.DOC / "input_audit_r01")

    def test_out_of_scope_rejected_before_read(self):
        with self.assertRaises(ValueError):
            audit.audit(audit.DOC.parent / "not_authorized")

    def test_84_independently_manifest_bound_bytes(self):
        base = audit.DOC / "input_audit_r01"
        result = json.loads((base / "AUDIT.json").read_bytes())
        self.assertEqual((result["input_expected_count"], result["matched_count"], result["missing"]), (84, 84, []))
        self.assertEqual(len({r["path"] for r in result["matched"]}), 84)
        for item in result["matched"]:
            raw = (base / "derived_original_bytes" / item["path"]).read_bytes()
            self.assertEqual(audit.identity(raw), item["expected"])
            self.assertEqual(audit.identity(raw), item["actual"])

    def test_tool_launcher_matches_signed_run_receipt(self):
        import zipfile
        with zipfile.ZipFile(audit.PHYSICAL) as z:
            original = json.loads(z.read("RUN_RECEIPT.json"))
        expected = [v for k, v in original["input_before"].items() if k.endswith("gw_sh.exe")]
        self.assertEqual(len(expected), 1)
        self.assertEqual(audit.identity(audit.TOOL_CANDIDATES[0].read_bytes()), expected[0])

    def test_not_consumed_not_sta_pass(self):
        result = json.loads((audit.DOC / "input_audit_r01/AUDIT.json").read_bytes())
        self.assertEqual(result["status"], "BLOCKED_INPUT")
        self.assertEqual(result["physical_allowance"]["tool_starts"], 0)
        self.assertFalse(result["physical_allowance"]["consumed"])
        self.assertFalse(result["board_release_allowed"])
        self.assertEqual(result["physical_archive_netlists"], [])
        self.assertEqual(result["absolute_literal_unavailable_count"], 40)

    def test_refined_counts_do_not_claim_all_paths_active(self):
        result = json.loads((audit.DOC / "input_audit_verify_r02/AUDIT.json").read_bytes())
        self.assertEqual(result["unique_absolute_literal_count"], 9)
        self.assertEqual(result["literal_occurrences_in_gprj_sources"], 38)
        self.assertEqual(result["literal_occurrences_in_non_gprj_sources"], 2)
        self.assertEqual(result["gprj_file_count"], 69)
        self.assertTrue(result["compiled_is_not_proof_of_elaboration"])
        self.assertTrue(result["physical_allowance"]["historical_netlist_absence_alone_does_not_forbid_new_same_source_build"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
