"""New controller fault checks with stub subprocesses, never Gowin EDA."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import patch

import run_138k_polyphony_synthesis_once as runner

REPORT = "impl/gwsynthesis/b2l_resource_probe_syn_rsc.xml"
SUCCESS = (
    "from pathlib import Path; "
    f"p=Path('{REPORT}'); p.parent.mkdir(parents=True); "
    "p.write_text('<row name=\"b2l_resource_probe\" T_Logic=\"7\" "
    "T_Register=\"11\" T_Bsram=\"2\"/>'); "
    "Path('impl/gwsynthesis/probe.vg').write_text('module probe; endmodule'); "
)


class ControllerTests(unittest.TestCase):
    project: Path
    output: Path

    def attempt(self, name, code, timeout=10):
        return runner._execute_one(self.project, self.output / name,
            authorized=True, stub_command=[sys.executable, "-B", "-c", code],
            timeout_seconds=timeout)

    def test_locked_cli_never_creates_attempt(self):
        dest = self.output / "cli_locked"
        process = subprocess.run([sys.executable, "-B", str(Path(runner.__file__)),
            "--project", str(self.project), "--output", str(dest), "--execute"],
            capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 1)
        self.assertIn(b"SYNTHESIS_NOT_AUTHORIZED", process.stdout)
        self.assertFalse(dest.exists())

    def test_private_default_is_locked(self):
        with self.assertRaisesRegex(ValueError, "SYNTHESIS_NOT_AUTHORIZED"):
            runner._execute_one(self.project, self.output / "default_locked")

    def test_result_scope_cannot_escape(self):
        with self.assertRaisesRegex(ValueError, "OUTPUT_OUTSIDE"):
            runner.plan(self.project, runner.prepared.ROOT / "outside_output")

    def test_success_is_stub_only_and_unknown_not_zero(self):
        r = self.attempt("success", SUCCESS)
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(r["status"], "STUB_SYNTHESIS_CONTROLLER_PASS")
        self.assertTrue(r["stub_test"])
        self.assertTrue(r["frozen_project_unchanged"])
        self.assertFalse(r["resource_admission"])
        self.assertIsNone(r["resource_report"]["hierarchy"][0]["resources"]["DSP"])
        self.assertEqual(r["tool_runs"], 1)
        runtime = r["runtime_inputs"]
        self.assertEqual(runtime["original_gprj_sha256"], runtime["runtime_gprj_sha256"])

    def test_pass_text_with_nonzero_exit_rejected(self):
        r = self.attempt("nonzero", SUCCESS + "import sys; print('PASS'); sys.exit(7)")
        self.assertEqual(r["exit_code"], 1)
        self.assertEqual(r["diagnostic"], "TOOL_NONZERO_NO_RETRY")
        self.assertEqual(r["tool_runs"], 1)

    def test_zero_exit_without_report_rejected(self):
        r = self.attempt("missing", "print('PASS')")
        self.assertEqual(r["exit_code"], 1)
        self.assertIn("REPORT_REQUIRED", r["diagnostic"])

    def test_malformed_report_rejected_with_receipt(self):
        r = self.attempt("malformed", SUCCESS + "p.write_text('<broken')")
        self.assertEqual(r["exit_code"], 1)
        self.assertTrue((self.output / "malformed/receipt.json").is_file())

    def test_missing_netlist_rejected(self):
        r = self.attempt("no_netlist", SUCCESS +
            "Path('impl/gwsynthesis/probe.vg').unlink()")
        self.assertEqual(r["diagnostic"], "FRESH_NETLIST_REQUIRED")

    def test_invalid_bound_rejected_without_attempt(self):
        for value in (True, 0, 901):
            with self.assertRaisesRegex(ValueError, "INVALID_TIMEOUT_BOUND"):
                runner._execute_one(self.project, self.output / "bad_bound",
                                    authorized=True, timeout_seconds=value)
        self.assertFalse((self.output / "bad_bound").exists())

    def test_preflight_time_counts_without_starting_tool(self):
        record = runner.prepared.verify(self.project)
        with patch.object(runner, "plan", return_value={"synthetic_budget_test": True}), \
             patch.object(runner.prepared, "verify", return_value=record), \
             patch.object(runner.time, "monotonic", side_effect=[0, 5, 6]):
            r = self.attempt("budget_exhausted", SUCCESS, timeout=2)
        self.assertEqual(r["diagnostic"], "TIMEOUT_BEFORE_TOOL")
        self.assertEqual(r["tool_runs"], 0)

    def test_pnr_bitstream_rejected(self):
        r = self.attempt("bitstream", SUCCESS + "Path('forbidden.fs').write_bytes(b'x')")
        self.assertEqual(r["diagnostic"], "UNEXPECTED_PNR_BITSTREAM")
        self.assertEqual(r["exit_code"], 1)

    def test_ambiguous_reports_rejected(self):
        r = self.attempt("ambiguous", SUCCESS +
            "Path('impl/gwsynthesis/n32_r1_resource_syn_rsc.xml').write_text(p.read_text())")
        self.assertIn("EXACTLY_ONE", r["diagnostic"])

    def test_existing_result_not_overwritten(self):
        target = self.output / "existing"
        target.mkdir()
        marker = target / "keep.txt"
        marker.write_bytes(b"KEEP")
        with self.assertRaisesRegex(ValueError, "REFUSE_EXISTING_ATTEMPT"):
            runner._execute_one(self.project, target, authorized=True,
                                stub_command=[sys.executable, "-c", SUCCESS])
        self.assertEqual(marker.read_bytes(), b"KEEP")

    def test_input_identity_failure_is_fail_closed(self):
        record = runner.prepared.verify(self.project)
        with patch.object(runner, "plan", return_value={"synthetic_test": True}), \
             patch.object(runner.prepared, "verify", side_effect=[
                 record, ValueError("SYNTHETIC_SOURCE_DRIFT"),
                 ValueError("SYNTHETIC_SOURCE_DRIFT")]):
            r = self.attempt("identity_drift", SUCCESS)
        self.assertEqual(r["exit_code"], 1)
        self.assertFalse(r["frozen_project_unchanged"])

    def test_timeout_kills_owned_child_no_retry(self):
        code = ("import subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                "print('CHILD_PID='+str(p.pid),flush=True); time.sleep(30)")
        record = runner.prepared.verify(self.project)
        # Isolate process-timeout semantics from the separately tested real preflight.
        with patch.object(runner, "plan", return_value={"synthetic_timeout_test": True}), \
             patch.object(runner.prepared, "verify", return_value=record):
            r = self.attempt("timeout", code, timeout=2)
        self.assertTrue(r["timed_out"])
        self.assertEqual(r["tool_runs"], 1)
        self.assertEqual(r["exit_code"], 1)
        text = (self.output / "timeout/stdout.bin").read_text("utf-8")
        found = re.search(r"CHILD_PID=(\d+)", text)
        self.assertIsNotNone(found)
        if os.name == "nt":
            pid = int(found.group(1))
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.restype = ctypes.c_void_p
            handle = kernel.OpenProcess(0x1000, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                try:
                    self.assertTrue(kernel.GetExitCodeProcess(ctypes.c_void_p(handle),
                                                            ctypes.byref(exit_code)))
                    self.assertNotEqual(exit_code.value, 259)
                finally:
                    kernel.CloseHandle(ctypes.c_void_p(handle))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--project", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    args.output = args.output.resolve()
    root = (runner.prepared.ROOT / "code/output").resolve()
    if args.output == root or not args.output.is_relative_to(root):
        raise ValueError("TEST_OUTPUT_SCOPE")
    args.output.mkdir(parents=True, exist_ok=False)
    ControllerTests.project, ControllerTests.output = args.project.resolve(), args.output
    before = runner.prepared.verify(ControllerTests.project)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ControllerTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = runner.prepared.verify(ControllerTests.project)
    summary = dict(tests_run=result.testsRun, failures=len(result.failures),
                   errors=len(result.errors), skipped=len(result.skipped),
                   frozen_receipt_unchanged=before == after,
                   stub_processes_only=True, actual_Gowin_runs=0,
                   physical_resources="UNKNOWN", STA="NOT_RUN")
    summary["exit_code"] = 0 if result.wasSuccessful() and before == after else 1
    runner.write_new(args.output / "test_receipt.json", summary)
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
