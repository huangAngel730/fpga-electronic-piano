"""Synthetic software fixtures only; no real run or permission is created."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_receipt
import test_receipt_check as legacy_cases


class OriginalContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy_cases.ReceiptCheckTests("test_valid_synthetic_receipt_is_accepted")
        self.fixture.setUp()
        self.root = self.fixture.root
        self.record_path = self.root / "SYNTHETIC_record.json"
        self.confirmation_path = self.root / "SYNTHETIC_confirmation.json"
        self.record = {
            "schema": "r04_original_receipt_v1", "evidence_kind": "SYNTHETIC",
            "machine": "SYNTHETIC_MACHINE", "source_archive_sha256": self.fixture.archive_sha,
            "package": "r04.zip", "inputs_before": "before.json", "inputs_after": "after.json",
            "total_elapsed_seconds": 4, "steps": {},
        }
        self.confirmation = {
            "schema": "r04_m2_confirmation_v1", "reference": "SYNTHETIC_NOT_AN_APPROVAL",
            "machine": "SYNTHETIC_MACHINE", "source_archive_sha256": self.fixture.archive_sha,
            "total_budget_seconds": 9, "steps": {},
        }
        for name in ("vlib", "vlog", "vsim"):
            output = "" if name == "vlib" else (
                "Errors: 0\n" if name == "vlog" else f"# {audit_receipt.R04_PASS_MARKER}\n"
            )
            for kind, content in (("stdout", output), ("stderr", "")):
                (self.root / f"{name}.{kind}.txt").write_text(content, encoding="utf-8")
            step = {
                "command": [f"SYNTHETIC_{name}.exe", "synthetic_argument"],
                "cwd": "C:/SYNTHETIC/inputs", "elapsed_seconds": 1,
                "exit_code": 0, "timed_out": False,
                "tool": {"path": f"C:/SYNTHETIC/{name}.exe", "sha256": "a" * 64,
                         "version": "SYNTHETIC_NOT_A_TOOL",
                         "dependencies": [{"path": "SYNTHETIC_DLL", "sha256": "b" * 64}]},
            }
            for kind in ("stdout", "stderr"):
                stream = self.root / f"{name}.{kind}.txt"
                step[kind] = {"path": stream.name, "sha256": self.sha(stream)}
            self.record["steps"][name] = step
            self.confirmation["steps"][name] = {
                key: copy.deepcopy(step[key]) for key in ("command", "cwd", "tool")
            } | {"budget_seconds": 3}

    def tearDown(self):
        self.fixture.tearDown()

    @staticmethod
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def run_audit(self):
        self.record_path.write_text(json.dumps(self.record), encoding="utf-8")
        self.confirmation_path.write_text(json.dumps(self.confirmation), encoding="utf-8")
        with patch.object(audit_receipt, "R04_ARCHIVE_SHA256", self.fixture.archive_sha), \
                patch.object(audit_receipt, "R04_MANIFEST_SHA256", self.fixture.manifest_sha):
            return audit_receipt.audit(
                self.root, self.record_path, self.confirmation_path,
                self.sha(self.confirmation_path),
            )

    def test_complete_synthetic_record_is_rejected(self):
        result = self.run_audit()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["reasons"], ["SYNTHETIC_OR_UNDECLARED_EVIDENCE"])
        self.assertFalse(result["real_execution_validated"])
        self.assertEqual(result["per_request_deadline"], "UNKNOWN")

    def test_all_six_streams_reject_error(self):
        for name in ("vlib", "vlog", "vsim"):
            for kind in ("stdout", "stderr"):
                with self.subTest(name=name, stream=kind):
                    descriptor = self.record["steps"][name][kind]
                    path = self.root / descriptor["path"]
                    old = path.read_bytes()
                    path.write_bytes(old + b"# Error: diagnostic\n")
                    descriptor["sha256"] = self.sha(path)
                    self.assertIn(f"{name.upper()}_{kind.upper()}_DIAGNOSTIC",
                                  self.run_audit()["reasons"])
                    path.write_bytes(old)
                    descriptor["sha256"] = self.sha(path)

    def test_stream_bytes_tamper_is_rejected(self):
        (self.root / "vlib.stderr.txt").write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stream SHA mismatch"):
            self.run_audit()

    def test_missing_vlib_is_invalid(self):
        del self.record["steps"]["vlib"]
        with self.assertRaisesRegex(ValueError, "vlib/vlog/vsim"):
            self.run_audit()

    def test_missing_stream_is_invalid(self):
        (self.root / "vsim.stderr.txt").unlink()
        with self.assertRaisesRegex(ValueError, "missing original file"):
            self.run_audit()

    def test_missing_dependency_is_invalid(self):
        self.record["steps"]["vlog"]["tool"]["dependencies"] = []
        with self.assertRaisesRegex(ValueError, "runtime dependencies"):
            self.run_audit()

    def test_wrong_command_cwd_tool_or_machine_is_rejected(self):
        for field in ("command", "cwd", "tool"):
            with self.subTest(field=field):
                original = copy.deepcopy(self.confirmation["steps"]["vsim"][field])
                self.confirmation["steps"]["vsim"][field] = "DIFFERENT"
                self.assertIn(f"VSIM_CONFIRMED_{field.upper()}_MISMATCH",
                              self.run_audit()["reasons"])
                self.confirmation["steps"]["vsim"][field] = original
        self.confirmation["machine"] = "OTHER_MACHINE"
        self.assertIn("MACHINE_IDENTITY_MISMATCH", self.run_audit()["reasons"])

    def test_total_and_step_budget_failures_are_rejected(self):
        self.record["total_elapsed_seconds"] = 10
        self.record["steps"]["vlib"]["elapsed_seconds"] = 4
        reasons = self.run_audit()["reasons"]
        self.assertIn("TOTAL_BUDGET_EXCEEDED", reasons)
        self.assertIn("VLIB_PROCESS_OR_BUDGET_FAILURE", reasons)

    def test_boolean_exit_is_invalid(self):
        self.record["steps"]["vlib"]["exit_code"] = False
        with self.assertRaisesRegex(ValueError, "malformed process result"):
            self.run_audit()

    def test_confirmation_sha_is_independently_bound(self):
        self.run_audit()
        with self.assertRaisesRegex(ValueError, "confirmation SHA mismatch"):
            audit_receipt.audit(self.root, self.record_path, self.confirmation_path, "0" * 64)

    def test_path_escape_is_invalid(self):
        self.record["package"] = "../OUTSIDE.zip"
        with self.assertRaisesRegex(ValueError, "escapes its root"):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
