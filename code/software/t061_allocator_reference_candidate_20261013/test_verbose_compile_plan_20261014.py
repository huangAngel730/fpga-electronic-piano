"""Software-only checks for the verbose compile plan; no HDL tool starts."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import a_verbose_compile_diagnostic as worker
import a_verbose_compile_plan as planner


ROOT = Path(__file__).resolve().parents[3]


class VerboseCompilePlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            dir=ROOT / "code/output", prefix="n32_verbose_plan_")
        self.root = Path(self.temporary.name)
        self.base = self.root / "base"
        self.base_capsule = self.base / "capsule"
        self.base_capsule.mkdir(parents=True)
        self.suite = self.root / "suite"
        (self.suite / "bin").mkdir(parents=True)
        (self.suite / "lib").mkdir(parents=True)
        self.compiler = self.suite / "bin/iverilog.exe"
        self.compiler.write_bytes(b"fixture only; never executed")
        self.dll = self.suite / "lib/runtime.dll"
        self.dll.write_bytes(b"fixture dll")
        self.members = {}
        for index, relative in enumerate(planner.COPIED_MEMBERS):
            path = self.base_capsule / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative in (planner.BASE_WORKER, planner.RUNNER,
                            planner.RUNNER_TAIL, planner.WINDOWS_JOB,
                            planner.SUPERVISOR):
                path.write_bytes((ROOT / relative).read_bytes())
            else:
                path.write_bytes((relative + f":{index}\n").encode())
            self.members[relative] = {
                **planner.identity(path), "source_provenance": str(path)
            }
        sources = [str((self.base_capsule / item).resolve())
                   for item in (planner.OLD_ALLOCATOR,
                                planner.N4_CANDIDATE, planner.N4_TB)]
        self.base_plan = {
            "schema": "T061_N32_A_REVIEWED_PLAN_V1",
            "hostname": socket.gethostname(),
            "repo": str(ROOT),
            "capsule_root": str(self.base_capsule),
            "capsule_files": self.members,
            "tools": {"python": sys.executable,
                      "compile": str(self.compiler)},
            "tool_files": {
                str(Path(sys.executable).resolve()):
                    planner.identity(Path(sys.executable).resolve()),
                str(self.compiler): planner.identity(self.compiler),
                str(self.dll): planner.identity(self.dll),
            },
            "environment": {"PATH": str(self.suite / "bin")},
            "steps": [{
                "label": "N4_none_compile", "kind": "compile",
                "argv": [str(self.compiler), "-g2012", "-s", "tb_allocator",
                         "-o", "sim.vvp", *sources],
            }],
        }
        self.base_plan_path = self.base / "plan.json"
        self.base_plan_path.write_text(json.dumps(self.base_plan),
                                       encoding="utf-8")
        self.prepared = self.root / "prepared"
        self.actual = self.root / "actual"
        self.calls = []

    def tearDown(self):
        self.temporary.cleanup()

    def build(self):
        return planner.build(
            self.base_plan_path,
            planner.identity(self.base_plan_path)["sha256"],
            self.prepared,
            self.actual,
            ROOT,
        )

    def test_only_compiler_delta_is_one_verbose_token(self):
        result = self.build()
        plan = json.loads((self.prepared / "plan.json").read_text())
        self.assertEqual(result["status"],
                         "PREPARED_VERBOSE_COMPILE_ONLY_NOT_RUN")
        self.assertEqual(plan["steps"][0]["argv"],
                         [plan["non_verbose_argv"][0], "-v",
                          *plan["non_verbose_argv"][1:]])
        self.assertEqual(plan["delta"], {
            "added_tokens": ["-v"], "removed_tokens": []})
        self.assertEqual(plan["simulate_calls"], 0)
        self.assertEqual(plan["EDA_calls"], 0)
        self.assertFalse(self.actual.exists())

    def test_three_n4_source_bytes_are_unchanged(self):
        self.build()
        plan = json.loads((self.prepared / "plan.json").read_text())
        for relative in (planner.OLD_ALLOCATOR, planner.N4_CANDIDATE,
                         planner.N4_TB):
            self.assertEqual(
                plan["N4_sources"][relative],
                {key: self.members[relative][key]
                 for key in ("bytes", "sha256")})

    def test_child_helper_loader_ignores_shadow_module(self):
        self.build()
        plan = json.loads((self.prepared / "plan.json").read_text())
        poison = types.SimpleNamespace(marker="UNVERIFIED_SHADOW")
        with patch.dict(sys.modules, {"runner_tail_20261013": poison}):
            loaded = worker.load_verified_runner_tail(
                plan, self.prepared / "capsule")
        self.assertIsNot(loaded, poison)
        self.assertTrue(callable(loaded._run_process))

    def test_wrong_base_plan_sha_fails_before_output(self):
        with self.assertRaisesRegex(ValueError, "BASE_PLAN_SHA"):
            planner.build(self.base_plan_path, "0" * 64, self.prepared,
                          self.actual, ROOT)
        self.assertFalse(self.prepared.exists())

    def test_existing_verbose_flag_is_rejected(self):
        self.assertRaisesRegex(
            ValueError, "BASE_ALREADY_VERBOSE", planner.insert_verbose,
            ["iverilog.exe", "-v", "-o", "a.vvp", "a.sv"])

    def run_worker(self, mutate=None, exit_code=0):
        self.build()
        config_path = self.prepared / "verbose_compile_config.json"
        config = json.loads(config_path.read_text())
        if mutate:
            mutate(config)
            config_path.write_text(json.dumps(config), encoding="utf-8")
        config_sha = planner.identity(config_path)["sha256"]
        frozen_worker = self.prepared / "capsule" / planner.WORKER

        def fake_run(output, label, argv, cwd, cap, budget):
            self.calls.append((argv, cap))
            (cwd / "sim.vvp").write_bytes(b"not executed by this test")
            return {"exit_code": exit_code, "timed_out": False,
                    "launch_error": None}

        def write_json(path, value):
            path.write_text(json.dumps(value), encoding="utf-8")

        helper = types.SimpleNamespace(
            _run_process=fake_run,
            write_json=write_json,
            finalize_receipt=lambda path, receipt, budget: receipt,
        )
        with patch.object(worker, "__file__", str(frozen_worker)), \
                patch.object(worker, "load_verified_runner_tail",
                             return_value=helper):
            return worker.execute(config_path, config_sha)

    def test_fake_execution_is_one_verbose_compile_and_no_simulation(self):
        result = self.run_worker()
        self.assertEqual(result["status"],
                         "VERBOSE_COMPILE_ONLY_PASS_NOT_SIMULATED")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0].count("-v"), 1)
        self.assertEqual(self.calls[0][1], 90)
        self.assertEqual(result["simulate_calls"], 0)

    def test_extra_flag_is_rejected_before_fake_compile(self):
        def mutate(config):
            config["step"]["argv"].insert(2, "-Wall")

        with self.assertRaisesRegex(ValueError, "STEP_BINDING"):
            self.run_worker(mutate)
        self.assertEqual(self.calls, [])

    def test_nonzero_compile_fails_closed_without_retry(self):
        result = self.run_worker(exit_code=1)
        self.assertEqual(result["status"], "FAIL_PARTIAL")
        self.assertIn("COMPILE_FAILED", result["failure"])
        self.assertEqual(result["automatic_retries"], 0)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
