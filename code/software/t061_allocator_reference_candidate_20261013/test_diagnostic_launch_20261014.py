"""New diagnostic parent wiring only; no HDL or old supervisor test group."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import a_diagnostic_launch as launcher

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class DiagnosticLaunchTests(unittest.TestCase):
    def make(self, root):
        capsule = root / "capsule"
        target = capsule / "code/software/t061_allocator_reference_candidate_20261013"
        target.mkdir(parents=True)
        for name in ("a_compile_diagnostic.py", "a_diagnostic_launch.py"):
            (target / name).write_bytes((HERE / name).read_bytes())
        helpers = capsule / "code/software/t052_runner_acceptance_candidate_20261012"
        helpers.mkdir(parents=True)
        for name in ("runner.py", "runner_tail_20261013.py", "windows_job.py", "supervisor_20261013.py"):
            (helpers / name).write_bytes((ROOT / "code/software/t052_runner_acceptance_candidate_20261012" / name).read_bytes())
        python = str(Path(sys.executable).resolve())
        plan = {"capsule_root": str(capsule), "tools": {"python": python},
                "tool_files": {python: launcher.identity(Path(python).read_bytes())}}
        plan_path, config_path, manifest_path = root / "plan.json", root / "config.json", root / "launch.json"
        plan_path.write_bytes(launcher.encoded(plan))
        config_path.write_bytes(launcher.encoded({"plan": launcher.identity(plan_path.read_bytes()),
                                                 "execution_output": str(root / "actual")}))
        launcher.prepare(plan_path, config_path, manifest_path)
        return json.loads(manifest_path.read_bytes()), manifest_path

    def test_unique_pinned_command_cwd_and_total_watchdog_wiring(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temporary:
            manifest, path = self.make(Path(temporary))
            self.assertEqual(manifest["worker_argv"][1:7], ["-I", "-S", "-B", "-X", "utf8", "-c"])
            self.assertEqual(manifest["worker_argv"][-1], manifest["config"]["sha256"])
            observed = {}

            class OriginalBudget:
                def __init__(self, seconds):
                    self.started = -1

            fake = SimpleNamespace(runner=SimpleNamespace(
                Budget=OriginalBudget, identity=lambda p: launcher.identity(Path(p).read_bytes()),
                _run_process=lambda *args: None))

            def observe(output, argv, cwd, receipt, sources, **limits):
                observed.update(output=output, argv=argv, cwd=cwd, receipt=receipt, limits=limits)
                self.assertEqual(fake.runner.Budget(300).started, 1234.0)
                self.assertEqual(sources[str(path)], launcher.identity(path.read_bytes()))
                self.assertEqual(sources[manifest["python"]["path"]], actual["python"])
                return {"status": "SOFTWARE_WIRING_ONLY", "exit_code": 0,
                        "failure": None, "elapsed_seconds": 0.0}

            fake.observe_run = observe
            sha = launcher.identity(path.read_bytes())["sha256"]
            actual = self.actual(manifest, sha)
            with patch.object(launcher, "__file__", manifest["launcher"]["path"]), \
                    patch.object(launcher.time, "monotonic", return_value=1234.0), \
                    patch.object(launcher, "collect_parent_identity", return_value=actual), \
                    patch.object(launcher, "load_parent_helpers", return_value=fake), \
                    patch.object(launcher.sys, "path", sys.path.copy()):
                result = launcher.execute(path, sha)
            self.assertEqual(result["status"], "SOFTWARE_WIRING_ONLY")
            self.assertEqual(observed["cwd"], Path(manifest["capsule"]))
            self.assertEqual(observed["limits"], {"total_seconds": 300, "step_seconds": 300})
            self.assertEqual(observed["argv"], manifest["worker_argv"])

    def test_python_drift_after_initial_parent_check_never_starts_worker(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temporary:
            manifest, path = self.make(Path(temporary))
            sha = launcher.identity(path.read_bytes())["sha256"]
            helpers = Path(manifest["capsule"]) / "code/software/t052_runner_acceptance_candidate_20261012"
            supervisor = launcher.load_parent_helpers(
                launcher.read_parent_helpers(manifest, helpers), helpers)
            original = supervisor.runner.identity
            python_path = Path(manifest["python"]["path"]).resolve()
            calls = 0

            def drift_on_executable_before(source):
                nonlocal calls
                if Path(source).resolve() == python_path:
                    calls += 1
                    if calls >= 2:
                        return {"bytes": 1, "sha256": "0" * 64}
                return original(source)

            with patch.object(launcher, "__file__", manifest["launcher"]["path"]), \
                    patch.object(launcher, "collect_parent_identity", return_value=self.actual(manifest, sha)), \
                    patch.object(launcher, "load_parent_helpers", return_value=supervisor), \
                    patch.object(supervisor.runner, "identity", side_effect=drift_on_executable_before), \
                    patch.object(supervisor.runner, "_run_process") as worker:
                result = launcher.execute(path, sha)
                worker.assert_not_called()
            self.assertEqual(result["exit_code"], 1)
            self.assertIn("CHILD_PYTHON_SHA", result["failure"])

    def actual(self, manifest, sha):
        return {"pid": 123, "orig_argv": manifest["parent_argv_prefix"] + [sha],
                "argv": [manifest["launcher"]["path"], "execute"],
                "cwd": manifest["cwd"], "python_path": manifest["python"]["path"],
                "python": {key: manifest["python"][key] for key in ("bytes", "sha256")},
                "flags": {key: 1 for key in
                          ("isolated", "no_site", "no_user_site", "dont_write_bytecode", "utf8_mode")},
                "xoptions": {"utf8": True}}

    def test_wrong_cwd_missing_flag_and_argv_offset_rejected_before_worker(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temporary:
            manifest, path = self.make(Path(temporary))
            sha = launcher.identity(path.read_bytes())["sha256"]
            for defect, diagnostic in (("cwd", "PARENT_ACTUAL_CWD"),
                                       ("flag", "PARENT_FLAGS"), ("argv", "PARENT_ARGV")):
                with self.subTest(defect=defect):
                    actual = self.actual(manifest, sha)
                    if defect == "cwd":
                        actual["cwd"] = str(Path(temporary))
                    elif defect == "flag":
                        actual["flags"]["no_site"] = 0
                    else:
                        actual["orig_argv"][-1] = "0" * 64
                    with patch.object(launcher, "collect_parent_identity", return_value=actual), \
                            patch.object(launcher, "load_parent_helpers") as loading:
                        with self.assertRaisesRegex(AssertionError, diagnostic):
                            launcher.execute(path, sha)
                        loading.assert_not_called()
                    Path(manifest["parent_entry"]).unlink()

    def test_unlisted_pyc_rejected_before_helper_loading(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temporary:
            manifest, path = self.make(Path(temporary))
            helpers = Path(manifest["capsule"]) / "code/software/t052_runner_acceptance_candidate_20261012"
            cache = helpers / "__pycache__"
            cache.mkdir()
            (cache / "runner.cpython-312.pyc").write_bytes(b"UNLISTED_POISON")
            with self.assertRaisesRegex(AssertionError, "PARENT_HELPER_MEMBERS"):
                launcher.read_parent_helpers(manifest, helpers)

    def test_hash_then_poison_loads_verified_raw_not_disk(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temporary:
            manifest, path = self.make(Path(temporary))
            program = r'''
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import a_diagnostic_launch as source
manifest=json.loads(Path(sys.argv[2]).read_bytes())
helpers=Path(manifest['capsule'])/'code/software/t052_runner_acceptance_candidate_20261012'
raws=source.read_parent_helpers(manifest,helpers)
for p in raws: p.write_text("raise RuntimeError('POISON_EXECUTED')\n",encoding='ascii')
supervisor=source.load_parent_helpers(raws,helpers)
assert supervisor._identity(b'probe')['sha256']==hashlib.sha256(b'probe').hexdigest()
print('VERIFIED_RAW_HELPER_LOAD_PASS')
'''
            child = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                                    program, str(HERE), str(path)],
                                   capture_output=True, timeout=15)
            self.assertEqual(child.returncode, 0, child.stderr.decode("utf-8", errors="replace"))
            self.assertIn(b"VERIFIED_RAW_HELPER_LOAD_PASS", child.stdout)

    def test_pinned_raw_mismatch_never_executes_poison_script(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temporary:
            path = Path(temporary) / "poison.py"
            path.write_text("print('UNREVIEWED_CODE_EXECUTED')\n", encoding="ascii")
            child = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                                    launcher.PINNED_EXEC, str(path), "0" * 64],
                                   capture_output=True, timeout=15)
            self.assertNotEqual(child.returncode, 0)
            self.assertNotIn(b"UNREVIEWED_CODE_EXECUTED", child.stdout)
            self.assertIn(b"FROZEN_SCRIPT_SHA", child.stderr)


if __name__ == "__main__":
    unittest.main()
