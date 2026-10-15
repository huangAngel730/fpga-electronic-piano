"""Synthetic-only regression checks for R04 diagnostic rejection.

No subprocess or simulator is invoked.  The core accepts one merged log per
tool, so each diagnostic is checked independently in the vlog and vsim input.
"""

from __future__ import annotations

import json
import unittest

import receipt_check
import test_receipt_check as legacy_tests


class DiagnosticTests(unittest.TestCase):
    """Use the old fixture by composition without rerunning its test methods."""

    def setUp(self) -> None:
        self.case = legacy_tests.ReceiptCheckTests(
            methodName="test_valid_synthetic_receipt_is_accepted"
        )
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        for path in (self.case.vlog, self.case.vsim):
            text = path.read_text(encoding="utf-8")
            path.write_text(
                "# SYNTHETIC SOFTWARE TEST; NO MODELSIM EXECUTION\n" + text,
                encoding="utf-8",
            )

    def insert_diagnostic(self, tool: str, position: str, diagnostic: str) -> None:
        path = getattr(self.case, tool)
        text = path.read_text(encoding="utf-8")
        marker = "# " + receipt_check.R04_PASS_MARKER
        if tool == "vlog":
            text += marker + "\n"
        replacement = (
            diagnostic + "\n" + marker
            if position == "before"
            else marker + "\n" + diagnostic
        )
        path.write_text(text.replace(marker, replacement), encoding="utf-8")


def diagnostic_test(tool: str, position: str, diagnostic: str):
    def test(self: DiagnosticTests) -> None:
        self.insert_diagnostic(tool, position, diagnostic)
        result = self.case._check()
        self.assertFalse(result.accepted)
        checks = {check.name: check for check in result.checks}
        self.assertFalse(checks["logs_no_error_or_failure"].passed)
        self.assertTrue(checks["vsim_required_pass_marker"].passed)
        self.assertTrue(checks["vlog_exit_zero"].passed)
        self.assertTrue(checks["vsim_exit_zero"].passed)

    return test


def zero_summary_test(tool: str):
    def test(self: DiagnosticTests) -> None:
        self.insert_diagnostic(tool, "after", "# Errors: 0, Warnings: 0")
        result = self.case._check()
        self.assertTrue(result.accepted)
        checks = {check.name: check for check in result.checks}
        self.assertTrue(checks["logs_no_error_or_failure"].passed)

    return test


def malformed_pass_test(prefix: str, suffix: str):
    def test(self: DiagnosticTests) -> None:
        self.case.vsim.write_text(
            "# SYNTHETIC SOFTWARE TEST; NO MODELSIM EXECUTION\n"
            + "# " + prefix + receipt_check.R04_PASS_MARKER + suffix + "\n",
            encoding="utf-8",
        )
        result = self.case._check()
        self.assertFalse(result.accepted)
        checks = {check.name: check for check in result.checks}
        self.assertFalse(checks["vsim_required_pass_marker"].passed)

    return test


def malformed_status_test(tool: str, field: str, value: object):
    def test(self: DiagnosticTests) -> None:
        data = json.loads(self.case.status.read_text(encoding="utf-8"))
        data[tool][field] = value
        self.case.status.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(receipt_check.ReceiptFormatError):
            self.case._check()

    return test


DIAGNOSTICS = {
    "error": "# Error: synthetic diagnostic",
    "errors_one": "# Errors: 1, Warnings: 0",
    "modelsim_error": "# ** Error: synthetic diagnostic",
    "fail": "# FAIL synthetic diagnostic",
    "failed": "# FAILED synthetic diagnostic",
    "failure": "# Failure synthetic diagnostic",
}

for tool_name in ("vlog", "vsim"):
    for position_name in ("before", "after"):
        for form_name, form_text in DIAGNOSTICS.items():
            setattr(
                DiagnosticTests,
                f"test_{tool_name}_{position_name}_pass_{form_name}_rejected",
                diagnostic_test(tool_name, position_name, form_text),
            )
    setattr(
        DiagnosticTests,
        f"test_{tool_name}_error_zero_is_diagnostic_rejected",
        diagnostic_test(tool_name, "after", "# Error: 0 synthetic diagnostic"),
    )
    setattr(
        DiagnosticTests,
        f"test_{tool_name}_errors_zero_summary_accepted",
        zero_summary_test(tool_name),
    )
    setattr(
        DiagnosticTests,
        f"test_{tool_name}_boolean_exit_code_rejected",
        malformed_status_test(tool_name, "exit_code", False),
    )
    setattr(
        DiagnosticTests,
        f"test_{tool_name}_integer_timeout_rejected",
        malformed_status_test(tool_name, "timed_out", 0),
    )

for pass_name, pass_prefix, pass_suffix in (
    ("not", "NOT ", ""),
    ("prefix", "synthetic-prefix ", ""),
    ("suffix", "", " synthetic-suffix"),
    ("both", "synthetic-prefix ", " synthetic-suffix"),
):
    setattr(
        DiagnosticTests,
        f"test_pass_marker_{pass_name}_rejected",
        malformed_pass_test(pass_prefix, pass_suffix),
    )


if __name__ == "__main__":
    unittest.main()
