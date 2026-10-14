"""One B-001 software regression; only temporary copies are changed."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import a_harness as harness
import a_bootstrap


class FrozenCapsuleGuard(unittest.TestCase):
    def test_live_change_and_restore_cannot_change_execution_sources(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output", prefix="n32_capsule_guard_") as temporary:
            live = Path(temporary) / "live"
            here = live / harness.HERE.relative_to(harness.ROOT)
            helpers = live / harness.HELPERS.relative_to(harness.ROOT)
            original = live / harness.ORIGINAL.relative_to(harness.ROOT)
            candidate = live / harness.CANDIDATE.relative_to(harness.ROOT)
            originals = {}
            sources = [*harness.HERE.glob("*.py"), harness.HERE / "README_A.md",
                       harness.ORIGINAL, harness.CANDIDATE]
            sources += [harness.HELPERS / name for name in
                        ("runner.py", "runner_tail_20261013.py", "windows_job.py", "supervisor_20261013.py")]
            for source in sources:
                target = live / source.relative_to(harness.ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                raw = source.read_bytes()
                target.write_bytes(raw)
                originals[target] = raw
            output = live / "code/output/prepared"
            execution = live / "code/output/actual"
            python = str(Path(sys.executable).resolve())
            suite = Path(temporary) / "unused_suite"
            (suite / "lib").mkdir(parents=True)
            (suite / "environment.bat").write_text("SOFTWARE_FAKE_ONLY\n", encoding="ascii")
            inventory = ({name: python for name in ("python", "compile", "simulate")},
                         {python: harness.identity(python),
                          str(suite / "environment.bat"): harness.identity(suite / "environment.bat")})
            with patch.multiple(harness, ROOT=live, HERE=here, HELPERS=helpers,
                                ORIGINAL=original, CANDIDATE=candidate), \
                    patch.object(harness, "tool_inventory", return_value=inventory):
                plan = harness.prepare(output, execution, suite)
                plan_path = output / "plan.json"
                plan_sha = harness.identity(plan_path)["sha256"]
                capsule = Path(plan["capsule_root"])
                before = {relative: (capsule / relative).read_bytes()
                          for relative in plan["capsule_files"]}
                command_before = [step["argv"][:] for step in plan["steps"]]
                changed = [original, here / "a_harness.py", here / "reference.py",
                           here / "vectors.py", helpers / "runner.py",
                           helpers / "runner_tail_20261013.py", helpers / "windows_job.py"]
                try:
                    for path in changed:
                        path.write_bytes(originals[path] + b"\nTEMPORARY_LIVE_TAMPER\n")
                    harness.verify(plan_path)
                    checked = a_bootstrap.bootstrap(plan_path, plan_sha, invoke=False)
                    self.assertEqual(checked["worker"], str(capsule / plan["worker"]))
                    self.assertEqual(plan["launch"]["cwd"], str(capsule))
                    argv = plan["launch"]["argv_prefix"] + [plan_sha, "--import-verify"]
                    child = subprocess.Popen(argv, cwd=plan["launch"]["cwd"],
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        stdout, stderr = child.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.communicate()
                        self.fail("SOFTWARE_IMPORT_PROBE_TIMEOUT")
                    self.assertEqual(child.returncode, 0, stderr.decode("utf-8", errors="replace"))
                    report = json.loads(stdout)
                    self.assertEqual(report["status"], "SOFTWARE_IMPORT_VERIFY_PASS")
                    self.assertEqual(set(report["imports"]),
                                     {"worker", "reference", "vectors", "runner_tail_20261013",
                                      "runner", "windows_job"})
                    for item in report["imports"].values():
                        path = Path(item["path"])
                        self.assertTrue(path.is_relative_to(capsule))
                        expected = plan["capsule_files"][path.relative_to(capsule).as_posix()]
                        self.assertEqual({key: item[key] for key in ("bytes", "sha256")},
                                         {key: expected[key] for key in ("bytes", "sha256")})
                    print(json.dumps({"scope": "SOFTWARE_ONLY_FRESH_IMPORT_DURING_LIVE_TAMPER",
                                      "pid": child.pid, "exit_code": child.returncode,
                                      "argv": argv, "cwd": plan["launch"]["cwd"],
                                      "stdout": stdout.decode("utf-8"),
                                      "stderr": stderr.decode("utf-8"),
                                      "HDL_calls": 0}, sort_keys=True))
                    self.assertEqual(before, {relative: (capsule / relative).read_bytes()
                                              for relative in plan["capsule_files"]})
                    self.assertEqual(command_before, [step["argv"] for step in plan["steps"]])
                    for step in plan["steps"]:
                        if step["kind"] == "compile":
                            self.assertTrue(Path(step["argv"][-3]).is_relative_to(capsule))
                            self.assertTrue(Path(step["argv"][-2]).is_relative_to(capsule))
                            self.assertTrue(Path(step["argv"][-1]).is_relative_to(capsule))
                        elif step["kind"] == "check":
                            self.assertTrue(Path(step["argv"][6]).is_relative_to(capsule))
                finally:
                    for path in changed:
                        path.write_bytes(originals[path])
                harness.verify(plan_path)
                self.assertFalse(execution.exists())


if __name__ == "__main__":
    unittest.main()
