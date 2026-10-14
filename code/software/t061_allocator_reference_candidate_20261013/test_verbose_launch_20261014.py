"""Software-only parent admission/watchdog tests; no HDL tool is invoked."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import a_verbose_launch as launcher


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HELPER_SOURCE = ROOT / "code/software/t052_runner_acceptance_candidate_20261012"
RELATIVE_ROOT = "code/software/t061_allocator_reference_candidate_20261013"


class VerboseLaunchTests(unittest.TestCase):
    def make(self, root):
        capsule = root / "capsule"
        local = capsule / RELATIVE_ROOT
        local.mkdir(parents=True)
        members = {}
        for name in ("a_verbose_compile_diagnostic.py", "a_verbose_launch.py",
                     "a_compile_diagnostic.py"):
            target = local / name
            target.write_bytes((HERE / name).read_bytes())
            members[f"{RELATIVE_ROOT}/{name}"] = {
                **launcher.identity(target.read_bytes()),
                "source_provenance": str(HERE / name),
            }
        helpers = capsule / "code/software/t052_runner_acceptance_candidate_20261012"
        helpers.mkdir(parents=True)
        for name in launcher.HELPERS:
            target = helpers / name
            target.write_bytes((HELPER_SOURCE / name).read_bytes())
            members[f"code/software/t052_runner_acceptance_candidate_20261012/{name}"] = {
                **launcher.identity(target.read_bytes()),
                "source_provenance": str(HELPER_SOURCE / name),
            }
        python = str(Path(sys.executable).resolve())
        plan = {
            "capsule_root": str(capsule),
            "worker": f"{RELATIVE_ROOT}/a_verbose_compile_diagnostic.py",
            "launcher": f"{RELATIVE_ROOT}/a_verbose_launch.py",
            "base_worker": f"{RELATIVE_ROOT}/a_compile_diagnostic.py",
            "runner_tail": (
                "code/software/t052_runner_acceptance_candidate_20261012/"
                "runner_tail_20261013.py"),
            "capsule_files": members,
            "tools": {"python": python},
            "tool_files": {python: launcher.identity(Path(python).read_bytes())},
        }
        plan_path = root / "plan.json"
        plan_path.write_bytes(launcher.encoded(plan))
        config = {
            "plan": launcher.identity(plan_path.read_bytes()),
            "execution_output": str(root / "actual"),
        }
        config_path = root / "config.json"
        config_path.write_bytes(launcher.encoded(config))
        manifest_path = root / "launch.json"
        command_path = root / "launch_command.json"
        launcher.prepare(plan_path, config_path, manifest_path, command_path)
        return (json.loads(manifest_path.read_bytes()), manifest_path,
                json.loads(command_path.read_bytes()))

    @staticmethod
    def actual(manifest, sha):
        return {
            "pid": 123,
            "orig_argv": manifest["parent_argv_prefix"] + [sha],
            "argv": [manifest["launcher"]["path"], "execute"],
            "cwd": manifest["cwd"],
            "python_path": manifest["python"]["path"],
            "python": {key: manifest["python"][key]
                       for key in ("bytes", "sha256")},
            "flags": {key: 1 for key in
                      ("isolated", "no_site", "no_user_site",
                       "dont_write_bytecode", "utf8_mode")},
            "xoptions": {"utf8": True},
        }

    def test_prepare_pins_raw_entries_and_worker_has_no_old_subcommand(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temp:
            manifest, path, command = self.make(Path(temp))
            self.assertEqual(manifest["worker_argv"][1:7],
                             ["-I", "-S", "-B", "-X", "utf8", "-c"])
            self.assertNotIn("execute", manifest["worker_argv"])
            self.assertEqual(manifest["worker_argv"][-4:-2],
                             ["--config", manifest["config"]["path"]])
            self.assertEqual(command["status"], "PREPARED_NOT_RUN")
            self.assertEqual(command["cwd"], manifest["cwd"])
            self.assertEqual(command["argv"],
                             manifest["parent_argv_prefix"]
                             + [launcher.identity(path.read_bytes())["sha256"]])

    def test_tampered_base_is_rejected_before_helper_execution(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temp:
            manifest, path, _ = self.make(Path(temp))
            sha = launcher.identity(path.read_bytes())["sha256"]
            base_path = Path(manifest["capsule"]) / (
                f"{RELATIVE_ROOT}/a_compile_diagnostic.py")
            base_path.write_bytes(b"UNAUTHENTICATED")
            with patch.object(launcher, "__file__", manifest["launcher"]["path"]), \
                    patch.object(launcher, "collect_parent_identity",
                                 return_value=self.actual(manifest, sha)), \
                    patch.object(launcher, "load_parent_helpers") as loading:
                with self.assertRaisesRegex(AssertionError,
                                            "PARENT_SOURCE_SHA"):
                    launcher.execute(path, sha)
                loading.assert_not_called()

    def test_parent_budget_is_anchored_before_admission(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temp:
            manifest, path, _ = self.make(Path(temp))
            sha = launcher.identity(path.read_bytes())["sha256"]
            observed = {}

            class Budget:
                def __init__(self, seconds):
                    self.started = -1.0

            fake = SimpleNamespace(runner=SimpleNamespace(
                Budget=Budget,
                identity=lambda source: launcher.identity(Path(source).read_bytes()),
                _run_process=lambda *args: None,
            ))

            def observe(output, argv, cwd, receipt, sources, **limits):
                observed.update(output=output, argv=argv, cwd=cwd,
                                receipt=receipt, limits=limits,
                                started=fake.runner.Budget(300).started)
                return {"status": "SOFTWARE_WIRING_ONLY", "exit_code": 0,
                        "failure": None, "elapsed_seconds": 0.0}

            fake.observe_run = observe
            with patch.object(launcher, "__file__", manifest["launcher"]["path"]), \
                    patch.object(launcher.time, "monotonic", return_value=1234.0), \
                    patch.object(launcher, "collect_parent_identity",
                                 return_value=self.actual(manifest, sha)), \
                    patch.object(launcher, "load_parent_helpers",
                                 return_value=fake):
                result = launcher.execute(path, sha)
            self.assertEqual(result["status"], "SOFTWARE_WIRING_ONLY")
            self.assertEqual(observed["started"], 1234.0)
            self.assertEqual(observed["limits"], {
                "total_seconds": 300, "step_seconds": 300})
            self.assertEqual(observed["argv"], manifest["worker_argv"])

    def test_pinned_wrong_sha_cannot_execute_marker_script(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "code/output") as temp:
            root = Path(temp)
            marker = root / "marker.txt"
            script = root / "must_not_run.py"
            script.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('RAN', encoding='ascii')\n",
                encoding="ascii")
            child = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                 launcher.PINNED_EXEC, str(script), "0" * 64],
                capture_output=True, timeout=15)
            self.assertNotEqual(child.returncode, 0)
            self.assertFalse(marker.exists())
            self.assertIn(b"FROZEN_SCRIPT_SHA", child.stderr)


if __name__ == "__main__":
    unittest.main()
