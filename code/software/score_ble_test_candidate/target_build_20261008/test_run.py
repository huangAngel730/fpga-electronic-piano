"""Runner isolation/version tests only; not a firmware or APK test."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("target_run", Path(__file__).with_name("run.py"))
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


class TargetRunnerTests(unittest.TestCase):
    def test_real_configuration_and_frozen_identity(self):
        self.assertEqual(RUN.check_configs(), [])
        identities, errors = RUN.frozen_sources()
        self.assertEqual(len(identities), 10)
        self.assertEqual(errors, [])

    def test_version_rejection(self):
        for wrong, pattern in [("Gradle 8.10", r"Gradle 8\.9\b"),
                               ('java version "11.0.2"', r'version "17\.'),
                               ("gcc 13.2.0", r"14\.2\.0")]:
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, "VERSION_MISMATCH"):
                RUN.require_match(wrong, pattern, "tool")

    def test_command_success_real_python(self):
        temp = tempfile.mkdtemp(prefix="m3_t059_target_unit_", dir=RUN.ROOT / "code/output")
        commands = RUN.Commands(Path(temp), dict(RUN.os.environ), 30)
        self.assertEqual(commands.run("ok", [sys.executable, "-c", "print('ok')"]), "ok")
        self.assertEqual(commands.steps[0]["exit_code"], 0)
        self.assertEqual(len(commands.steps[0]["stdout_sha256"]), 64)

    def test_nonzero_and_timeout_are_failures(self):
        for expression, timeout in [("raise SystemExit(7)", 5), ("import time; time.sleep(20)", 0.2)]:
            temp = tempfile.mkdtemp(prefix="m3_t059_target_unit_", dir=RUN.ROOT / "code/output")
            commands = RUN.Commands(Path(temp), dict(RUN.os.environ), 30)
            with self.assertRaisesRegex(ValueError, "COMMAND_FAIL"):
                commands.run("bad", [sys.executable, "-c", expression], limit=timeout)
            self.assertTrue(commands.steps[0]["exit_code"] != 0)

    def test_missing_environment_cannot_call_target_compiler(self):
        # Output is inside the real allowed prefix but uses impossible explicit tool roots.
        out = RUN.ROOT / "code/output" / ("m3_t059_target_unittest_" + uuid.uuid4().hex[:10])
        args = ["run.py", "c3", "--output", str(out), "--idf-root", str(out / "missing_sdk"),
                "--downloads", str(out / "missing_downloads")]
        with patch.object(sys, "argv", args):
            self.assertEqual(RUN.main(), 2)
        receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
        self.assertFalse(receipt["target_build_passed"])
        self.assertFalse(receipt["complete_t059_passed"])
        self.assertFalse(receipt["device_operations"])
        self.assertNotIn("c3_build", [step["label"] for step in receipt["steps"]])

    def test_missing_apk_environment_cannot_be_pass(self):
        out = RUN.ROOT / "code/output" / ("m3_t059_target_unittest_" + uuid.uuid4().hex[:10])
        args = ["run.py", "apk", "--output", str(out), "--java17", str(out / "missing_jdk"),
                "--downloads", str(out / "missing_downloads")]
        with patch.object(sys, "argv", args):
            self.assertEqual(RUN.main(), 2)
        receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
        self.assertFalse(receipt["target_build_passed"])
        self.assertNotIn("apk_build", [step["label"] for step in receipt["steps"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
