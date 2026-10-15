"""M1 R02 incremental SOFTWARE fixtures; no HDL or real evidence is created."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import unittest
from unittest.mock import patch
import zipfile

import audit_receipt
import receipt_check as core
import test_real_contract
import test_receipt_check


CASES = {
    "RCP01": "Error: synthetic compile issue",
    "RCP02": "# ** Error: synthetic run error",
    "RCP03": "Errors: 01",
    "RCP04": "# Assertion failed: synthetic",
}


class HelperIncrementTests(unittest.TestCase):
    def setUp(self):
        self.f = test_receipt_check.ReceiptCheckTests("test_valid_synthetic_receipt_is_accepted")
        self.f.setUp()
        self.addCleanup(self.f.tearDown)

    def cli(self, *extra):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(core, "R04_ARCHIVE_SHA256", self.f.archive_sha), \
                patch.object(core, "R04_MANIFEST_SHA256", self.f.manifest_sha), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            code = core.main(self.f._main_args() + list(extra))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_duplicate_exit_key_cannot_hide_failure(self):
        raw = self.f.status.read_text(encoding="utf-8")
        self.f.status.write_text(raw.replace('"exit_code": 0',
                                           '"exit_code": 7, "exit_code": 0', 1), encoding="utf-8")
        with self.assertRaisesRegex(core.ReceiptFormatError, "duplicate JSON key: exit_code"):
            self.f._check()
        code, stdout, stderr = self.cli()
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("duplicate JSON key", stderr)

    def test_duplicate_snapshot_members_rejected(self):
        raw = self.f.before.read_text(encoding="utf-8")
        self.f.before.write_text(raw.replace('"members": {', '"members": {}, "members": {', 1),
                                 encoding="utf-8")
        with self.assertRaisesRegex(core.ReceiptFormatError, "duplicate JSON key: members"):
            self.f._check()

    def test_duplicate_archive_manifest_rejected_after_hash_binding(self):
        raw = json.dumps(self.f.manifest).replace('"members": {',
                                                 '"members": {}, "members": {', 1).encode()
        with zipfile.ZipFile(self.f.package, "w") as archive:
            archive.writestr("MANIFEST.json", raw)
        with self.assertRaisesRegex(core.ReceiptFormatError, "duplicate JSON key: members"):
            core.check_receipt(
                package_path=self.f.package, vlog_log_path=self.f.vlog,
                vsim_log_path=self.f.vsim, run_status_path=self.f.status,
                inputs_before_path=self.f.before, inputs_after_path=self.f.after,
                expected_archive_sha256=hashlib.sha256(self.f.package.read_bytes()).hexdigest(),
                expected_manifest_sha256=hashlib.sha256(raw).hexdigest())

    def test_existing_output_never_prints_accepted_true(self):
        target = self.f.root / "result.json"
        target.write_text("KEEP ORIGINAL", encoding="utf-8")
        code, stdout, stderr = self.cli("--json-out", str(target))
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("already exists", stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "KEEP ORIGINAL")

    def test_unwritable_output_never_prints_success(self):
        parent = self.f.root / "occupied"
        parent.write_text("KEEP ORIGINAL", encoding="utf-8")
        code, stdout, stderr = self.cli("--json-out", str(parent / "report.json"))
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("cannot create output", stderr)
        self.assertEqual(parent.read_text(encoding="utf-8"), "KEEP ORIGINAL")

    def test_normal_cli_success_is_log_consistency_only(self):
        code, stdout, stderr = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        self.assertTrue(result["accepted"])
        self.assertFalse(result["real_execution_validated"])
        self.assertEqual(result["per_request_deadline"], "UNKNOWN")

    def test_nonfinite_json_rejected(self):
        self.f.status.write_text('{"value":NaN}', encoding="utf-8")
        with self.assertRaisesRegex(core.ReceiptFormatError, "nonfinite JSON"):
            self.f._check()


def helper_error(tool, position, diagnostic):
    def test(self):
        path = getattr(self.f, tool)
        marker = core.R04_PASS_MARKER
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            text += "# " + marker + "\n"
        replacement = diagnostic + "\n# " + marker if position == "before" else (
            "# " + marker + "\n" + diagnostic)
        path.write_text(text.replace("# " + marker, replacement), encoding="utf-8")
        result = self.f._check()
        checks = {item.name: item.passed for item in result.checks}
        self.assertFalse(result.accepted)
        self.assertFalse(checks["logs_no_error_or_failure"])
        self.assertTrue(checks["vlog_compile_success_marker"])
        self.assertTrue(checks["vsim_required_pass_marker"])
        self.assertTrue(checks["vlog_exit_zero"])
        self.assertTrue(checks["vsim_exit_zero"])
    return test


def zero_count(token):
    def test(self):
        # Original Errors: 0 remains present, exactly as in M1 RCP-03.
        with self.f.vlog.open("a", encoding="utf-8") as stream:
            stream.write("Errors: " + token + ", Warnings: 0\n")
        self.assertTrue(self.f._check().accepted)
    return test


class StreamIncrementTests(unittest.TestCase):
    def setUp(self):
        self.f = test_real_contract.OriginalContractTests(
            "test_complete_synthetic_record_is_rejected")
        self.f.setUp()
        self.addCleanup(self.f.tearDown)

    def direct_audit(self):
        with patch.object(audit_receipt, "R04_ARCHIVE_SHA256", self.f.fixture.archive_sha), \
                patch.object(audit_receipt, "R04_MANIFEST_SHA256", self.f.fixture.manifest_sha):
            return audit_receipt.audit(self.f.root, self.f.record_path,
                                       self.f.confirmation_path, self.f.sha(self.f.confirmation_path))

    def test_duplicate_raw_record_key_rejected(self):
        self.f.run_audit()
        raw = self.f.record_path.read_text(encoding="utf-8").replace(
            '"total_elapsed_seconds": 4', '"total_elapsed_seconds": 99, "total_elapsed_seconds": 4')
        self.f.record_path.write_text(raw, encoding="utf-8")
        with self.assertRaisesRegex(core.ReceiptFormatError, "duplicate JSON key: total_elapsed_seconds"):
            self.direct_audit()

    def test_duplicate_confirmation_key_rejected_even_with_matching_hash(self):
        self.f.run_audit()
        raw = self.f.confirmation_path.read_text(encoding="utf-8").replace(
            '"total_budget_seconds": 9', '"total_budget_seconds": 1, "total_budget_seconds": 9')
        self.f.confirmation_path.write_text(raw, encoding="utf-8")
        with self.assertRaisesRegex(core.ReceiptFormatError, "duplicate JSON key: total_budget_seconds"):
            self.direct_audit()

    def test_separate_stream_cannot_manufacture_exact_pass(self):
        for kind, text in (("stdout", "# PASS M2_M1TD_"),
                           ("stderr", "REAL_CHAIN_BOARD_FUNCTIONAL_ONLY\n")):
            descriptor = self.f.record["steps"]["vsim"][kind]
            path = self.f.root / descriptor["path"]
            path.write_text(text, encoding="utf-8")
            descriptor["sha256"] = self.f.sha(path)
        result = self.f.run_audit()
        self.assertIn("VSIM_EXACT_PASS_MISSING", result["reasons"])
        self.assertFalse(result["real_execution_validated"])


def stream_error(tool, kind, position, diagnostic):
    def test(self):
        descriptor = self.f.record["steps"][tool][kind]
        path = self.f.root / descriptor["path"]
        text = path.read_text(encoding="utf-8")
        marker = "# " + core.R04_PASS_MARKER
        if marker not in text:
            text += marker + "\n"
        replacement = diagnostic + "\n" + marker if position == "before" else (
            marker + "\n" + diagnostic)
        path.write_text(text.replace(marker, replacement), encoding="utf-8")
        descriptor["sha256"] = self.f.sha(path)
        result = self.f.run_audit()
        self.assertIn(f"{tool.upper()}_{kind.upper()}_DIAGNOSTIC", result["reasons"])
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["real_execution_validated"])
        self.assertEqual(result["per_request_deadline"], "UNKNOWN")
    return test


def stream_zero(tool, kind):
    def test(self):
        descriptor = self.f.record["steps"][tool][kind]
        path = self.f.root / descriptor["path"]
        path.write_text(path.read_text(encoding="utf-8") + "Errors: 000\n", encoding="utf-8")
        descriptor["sha256"] = self.f.sha(path)
        # This is still a declared synthetic fixture, never a real run PASS.
        self.assertEqual(self.f.run_audit()["reasons"], ["SYNTHETIC_OR_UNDECLARED_EVIDENCE"])
    return test


for step in ("vlog", "vsim"):
    for location in ("before", "after"):
        for label, message in CASES.items():
            setattr(HelperIncrementTests, f"test_{label}_{step}_{location}",
                    helper_error(step, location, message))
for index, zeros in enumerate(("0", "00", "000", "0" * 5000)):
    setattr(HelperIncrementTests, f"test_zero_integer_{index}", zero_count(zeros))
for step in ("vlib", "vlog", "vsim"):
    for stream in ("stdout", "stderr"):
        setattr(StreamIncrementTests, f"test_zero_{step}_{stream}", stream_zero(step, stream))
        for location in ("before", "after"):
            for label, message in CASES.items():
                setattr(StreamIncrementTests, f"test_{label}_{step}_{stream}_{location}",
                        stream_error(step, stream, location, message))


if __name__ == "__main__":
    unittest.main(verbosity=2)
