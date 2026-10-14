"""New diagnostic-worker guards only; no external or HDL process is invoked."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import a_compile_diagnostic as diagnostic


ROOT = Path(__file__).resolve().parents[3]
WORKER = "code/software/t061_allocator_reference_candidate_20261013/a_compile_diagnostic.py"


class DiagnosticGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            dir=ROOT / "code/output", prefix="n32_diagnostic_guards_")
        self.root = Path(self.temporary.name)
        self.capsule = self.root / "capsule"
        self.worker = self.capsule / WORKER
        self.worker.parent.mkdir(parents=True)
        self.worker.write_bytes(b"# isolated software fixture, not a tool\n")
        self.suite = self.root / "suite"
        for name in ("bin", "lib"):
            (self.suite / name).mkdir(parents=True)
        self.compiler = self.suite / "bin/iverilog.exe"
        self.compiler.write_bytes(b"not executable; never started")
        self.dll = self.suite / "lib/runtime.dll"
        self.dll.write_bytes(b"software-only DLL identity fixture")
        self.output = self.root / "actual"
        self.plan_path = self.root / "plan.json"
        self.config_path = self.root / "config.json"
        self.plan = {
            "capsule_root": str(self.capsule),
            "tools": {"compile": str(self.compiler), "python": sys.executable},
            "capsule_files": {WORKER: diagnostic.identity(self.worker)},
            "tool_files": {str(p): diagnostic.identity(p)
                           for p in (self.compiler, self.dll)},
            "environment": {},
            "steps": [{"argv": [str(self.compiler)], "kind": "compile"}],
        }
        self.config = {
            "schema": "T061_N32_A_COMPILE_DIAGNOSTIC_V1",
            "hostname": socket.gethostname(), "plan_path": str(self.plan_path),
            "execution_output": str(self.output), "environment": {},
            "total_seconds": 300, "step_seconds": 90, "calls": 1,
            "simulate_calls": 0,
            "step": {"argv": [str(self.compiler)], "kind": "compile",
                     "timeout_seconds": 90, "calls": 1,
                     "label": "software_fake_compile", "cwd": str(self.output / "work")},
        }
        self.calls = []

    def tearDown(self):
        self.temporary.cleanup()

    def freeze(self):
        self.plan_path.write_text(json.dumps(self.plan), encoding="utf-8")
        self.config["plan"] = diagnostic.identity(self.plan_path)
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        return diagnostic.identity(self.config_path)["sha256"]

    def run_worker(self, callback=None, child_exit=0):
        config_sha = self.freeze()

        def fake_run(output, label, argv, cwd, cap, budget):
            self.calls.append((argv, cap))
            (cwd / "sim.vvp").write_bytes(b"software placeholder, not simulated")
            if callback:
                callback()
            return {"exit_code": child_exit, "timed_out": False, "launch_error": None}

        def write_json(path, value):
            path.write_text(json.dumps(value), encoding="utf-8")

        helper = types.SimpleNamespace(
            _run_process=fake_run, write_json=write_json,
            finalize_receipt=lambda path, receipt, budget: receipt)
        with patch.object(diagnostic, "__file__", str(self.worker)), \
                patch.dict(sys.modules, {"runner_tail_20261013": helper}):
            return diagnostic.execute(self.config_path, config_sha)

    def test_one_read_binds_hash_and_parsed_json(self):
        raw = b'{"marker":"reviewed"}'
        expected = {"bytes": len(raw),
                    "sha256": diagnostic.hashlib.sha256(raw).hexdigest()}
        with patch.object(Path, "read_bytes", side_effect=[raw, b'{"marker":"changed"}']) as read:
            parsed, observed = diagnostic.load_bound_json(
                self.config_path, expected, diagnostic.DiagnosticBudget(), "SHA")
        self.assertEqual(parsed, {"marker": "reviewed"})
        self.assertEqual(observed, expected)
        self.assertEqual(read.call_count, 1)

    def test_new_unbound_dll_rejected_by_real_validator(self):
        (self.suite / "bin/new.dll").write_bytes(b"new")
        with self.assertRaisesRegex(ValueError, "SUITE_DLL_MEMBERS"):
            diagnostic.validate_inputs(self.plan, diagnostic.DiagnosticBudget())

    def test_missing_bound_dll_rejected_by_real_validator(self):
        self.dll.unlink()
        with self.assertRaisesRegex(ValueError, "SUITE_DLL_MEMBERS"):
            diagnostic.validate_inputs(self.plan, diagnostic.DiagnosticBudget())

    def test_omitted_dll_binding_rejected_before_compile(self):
        del self.plan["tool_files"][str(self.dll)]
        with self.assertRaisesRegex(ValueError, "SUITE_DLL_MEMBERS"):
            self.run_worker()
        self.assertEqual(self.calls, [])

    def test_python_identity_rejected_before_compile(self):
        self.plan["tools"]["python"] = str(self.root / "other_python.exe")
        with self.assertRaisesRegex(ValueError, "PYTHON_IDENTITY"):
            self.run_worker()
        self.assertEqual(self.calls, [])

    def test_source_drift_rejected_before_compile(self):
        self.worker.write_bytes(b"changed fixture")
        with self.assertRaisesRegex(ValueError, "SOURCE_DRIFT"):
            self.run_worker()
        self.assertEqual(self.calls, [])

    def test_preverification_time_consumes_worker_budget(self):
        clock = iter((0, 301))
        budget = diagnostic.DiagnosticBudget(clock=lambda: next(clock))
        with patch.object(diagnostic, "DiagnosticBudget", return_value=budget):
            with self.assertRaisesRegex(ValueError, "TOTAL_BUDGET_EXHAUSTED"):
                self.run_worker()
        self.assertEqual(self.calls, [])

    def test_tool_loop_budget_checks_before_and_after_hash(self):
        budget = diagnostic.DiagnosticBudget(clock=lambda: 0)
        original = diagnostic.identity

        def slow_hash(path):
            result = original(path)
            if Path(path) == self.compiler:
                budget.clock = lambda: 301
            return result

        with patch.object(diagnostic, "identity", side_effect=slow_hash):
            with self.assertRaisesRegex(ValueError, "TOTAL_BUDGET_EXHAUSTED"):
                diagnostic.validate_inputs(self.plan, budget)

    def test_insufficient_full_compile_cap_does_not_launch(self):
        budget = diagnostic.DiagnosticBudget(clock=lambda: 0)
        budget.started = -220
        with patch.object(diagnostic, "DiagnosticBudget", return_value=budget):
            result = self.run_worker()
        self.assertEqual(result["status"], "FAIL_PARTIAL")
        self.assertIn("INSUFFICIENT_COMPILE_BUDGET", result["failure"])
        self.assertEqual(self.calls, [])

    def test_post_members_added_forces_failure(self):
        result = self.run_worker(lambda: (self.capsule / "new.py").write_bytes(b"new"))
        self.assertEqual(result["status"], "FAIL_PARTIAL")
        self.assertIn("CAPSULE_MEMBERS:AFTER", result["failure"])
        self.assertEqual(len(self.calls), 1)

    def test_post_dll_added_forces_failure(self):
        result = self.run_worker(lambda: (self.suite / "lib/new.dll").write_bytes(b"new"))
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("SUITE_DLL_MEMBERS", result["failure"])

    def test_post_config_mutation_forces_failure(self):
        result = self.run_worker(lambda: self.config_path.write_bytes(b"{}"))
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("CONFIG_AFTER_DRIFT", result["failure"])

    def test_post_plan_mutation_forces_failure(self):
        result = self.run_worker(lambda: self.plan_path.write_bytes(b"{}"))
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("PLAN_AFTER_DRIFT", result["failure"])

    def test_original_failure_not_erased_by_post_failure(self):
        result = self.run_worker(
            lambda: (self.capsule / "new.py").write_bytes(b"new"), child_exit=1)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("COMPILE_FAILED", result["failure"])
        self.assertIn("CAPSULE_MEMBERS:AFTER", result["failure"])

    def test_unchanged_software_chain_preserves_pass(self):
        result = self.run_worker()
        self.assertEqual(result["status"], "COMPILE_ONLY_PASS_NOT_SIMULATED")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["plan_after"], self.config["plan"])


if __name__ == "__main__":
    unittest.main()
