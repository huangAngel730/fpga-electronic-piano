from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from receipt_check import R04_PASS_MARKER, check_receipt, main


class ReceiptCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.manifest = {
            "status": "PORTABLE_MODELSIM_INPUT_PREPARED_NOT_EXECUTED",
            "members": {
                "inputs/compile.f": {"bytes": 3, "sha256": "a" * 64},
                "inputs/tb.sv": {"bytes": 4, "sha256": "b" * 64},
            },
        }
        manifest_bytes = json.dumps(self.manifest, separators=(",", ":")).encode()
        self.manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        self.package = self.root / "r04.zip"
        with zipfile.ZipFile(self.package, "w") as archive:
            archive.writestr("MANIFEST.json", manifest_bytes)
        self.archive_sha = hashlib.sha256(self.package.read_bytes()).hexdigest()
        self.vlog = self.root / "vlog.log"
        self.vsim = self.root / "vsim.log"
        self.status = self.root / "status.json"
        self.before = self.root / "before.json"
        self.after = self.root / "after.json"
        self._write_valid()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _identity(self) -> dict[str, object]:
        return {
            "source_archive_sha256": self.archive_sha,
            "manifest_sha256": self.manifest_sha,
            "members": self.manifest["members"],
        }

    def _write_valid(self) -> None:
        self.vlog.write_text("ModelSim vlog\nErrors: 0, Warnings: 1\n", encoding="utf-8")
        self.vsim.write_text(f"# END REAL_M1\n# {R04_PASS_MARKER}\n", encoding="utf-8")
        self.status.write_text(
            json.dumps(
                {
                    "vlog": {"exit_code": 0, "timed_out": False},
                    "vsim": {"exit_code": 0, "timed_out": False},
                }
            ),
            encoding="utf-8",
        )
        identity = json.dumps(self._identity())
        self.before.write_text(identity, encoding="utf-8")
        self.after.write_text(identity, encoding="utf-8")

    def _check(self):
        return check_receipt(
            package_path=self.package,
            vlog_log_path=self.vlog,
            vsim_log_path=self.vsim,
            run_status_path=self.status,
            inputs_before_path=self.before,
            inputs_after_path=self.after,
            expected_archive_sha256=self.archive_sha,
            expected_manifest_sha256=self.manifest_sha,
        )

    def _main_args(self) -> list[str]:
        return [
            "--package",
            str(self.package),
            "--vlog-log",
            str(self.vlog),
            "--vsim-log",
            str(self.vsim),
            "--run-status",
            str(self.status),
            "--inputs-before",
            str(self.before),
            "--inputs-after",
            str(self.after),
        ]

    def test_valid_synthetic_receipt_is_accepted(self) -> None:
        self.assertTrue(self._check().accepted)

    def test_missing_pass_marker_is_rejected(self) -> None:
        self.vsim.write_text("# END REAL_M1\n", encoding="utf-8")
        result = self._check()
        self.assertFalse(result.accepted)
        self.assertFalse(
            next(x for x in result.checks if x.name == "vsim_required_pass_marker").passed
        )

    def test_fatal_after_pass_marker_is_rejected(self) -> None:
        self.vsim.write_text(
            f"# {R04_PASS_MARKER}\n# ** Fatal: late failure\n",
            encoding="utf-8",
        )
        result = self._check()
        self.assertFalse(result.accepted)
        self.assertFalse(
            next(x for x in result.checks if x.name == "logs_no_fatal_or_timeout").passed
        )

    def test_nonzero_vlog_exit_is_rejected(self) -> None:
        data = json.loads(self.status.read_text(encoding="utf-8"))
        data["vlog"]["exit_code"] = 2
        self.status.write_text(json.dumps(data), encoding="utf-8")
        self.assertFalse(self._check().accepted)

    def test_nonzero_vsim_exit_is_rejected(self) -> None:
        data = json.loads(self.status.read_text(encoding="utf-8"))
        data["vsim"]["exit_code"] = 1
        self.status.write_text(json.dumps(data), encoding="utf-8")
        self.assertFalse(self._check().accepted)

    def test_timeout_flag_is_rejected(self) -> None:
        data = json.loads(self.status.read_text(encoding="utf-8"))
        data["vsim"]["timed_out"] = True
        self.status.write_text(json.dumps(data), encoding="utf-8")
        self.assertFalse(self._check().accepted)

    def test_missing_compile_success_marker_is_rejected(self) -> None:
        self.vlog.write_text("ModelSim vlog completed\n", encoding="utf-8")
        self.assertFalse(self._check().accepted)

    def test_changed_input_after_run_is_rejected(self) -> None:
        identity = self._identity()
        identity["members"]["inputs/tb.sv"]["sha256"] = "c" * 64
        self.after.write_text(json.dumps(identity), encoding="utf-8")
        result = self._check()
        self.assertFalse(result.accepted)
        self.assertFalse(
            next(x for x in result.checks if x.name == "after_input_identity").passed
        )

    def test_cli_returns_zero_for_pass(self) -> None:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main_with_test_identity(
                self._main_args(), self.archive_sha, self.manifest_sha
            )
        self.assertEqual(code, 0)

    def test_cli_returns_one_for_rejection(self) -> None:
        self.vsim.write_text("# no required marker\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main_with_test_identity(
                self._main_args(), self.archive_sha, self.manifest_sha
            )
        self.assertEqual(code, 1)

    def test_cli_returns_two_for_malformed_status(self) -> None:
        self.status.write_text("{}", encoding="utf-8")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main_with_test_identity(
                self._main_args(), self.archive_sha, self.manifest_sha
            )
        self.assertEqual(code, 2)


def main_with_test_identity(
    argv: list[str], archive_sha: str, manifest_sha: str
) -> int:
    """Exercise CLI status handling while keeping production constants pinned."""

    from unittest.mock import patch

    with patch("receipt_check.R04_ARCHIVE_SHA256", archive_sha), patch(
        "receipt_check.R04_MANIFEST_SHA256", manifest_sha
    ):
        return main(argv)


if __name__ == "__main__":
    unittest.main()
