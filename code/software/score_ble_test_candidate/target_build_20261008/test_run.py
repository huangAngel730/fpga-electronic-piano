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
        identities, errors = RUN.frozen_sources("c3_header_fix_20261009")
        self.assertEqual(len(identities), 10)
        self.assertEqual(errors, [])
        self.assertTrue(identities[RUN.MAIN_SOURCE]["include_only_proof"]["passed"])

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
                "--downloads", str(out / "missing_downloads"), "--source-profile", "c3_header_fix_20261009"]
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
                "--downloads", str(out / "missing_downloads"), "--source-profile", "c3_header_fix_20261009"]
        with patch.object(sys, "argv", args):
            self.assertEqual(RUN.main(), 2)
        receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
        self.assertFalse(receipt["target_build_passed"])
        self.assertNotIn("apk_build", [step["label"] for step in receipt["steps"]])

    def identity_with_inputs(self, overrides, profile):
        # Inject bytes only at the read boundary; never mutate actual frozen sources.
        actual_reader = Path.read_bytes

        def reader(path):
            for relative, data in overrides.items():
                if path == RUN.ROOT / relative:
                    return data
            return actual_reader(path)

        with patch.object(Path, "read_bytes", reader):
            return RUN.frozen_sources(profile)

    def test_old_profile_accepts_only_old_main(self):
        new = (RUN.ROOT / RUN.MAIN_SOURCE).read_bytes().replace(b"\r\n", b"\n")
        old = new.replace(b'#include "host/util/util.h"\n', b"", 1)
        _, errors = self.identity_with_inputs({RUN.MAIN_SOURCE: old}, "d040")
        self.assertEqual(errors, [])
        _, errors = self.identity_with_inputs({RUN.MAIN_SOURCE: new}, "d040")
        self.assertIn("FROZEN_SOURCE_IDENTITY: " + RUN.MAIN_SOURCE, errors)

    def test_new_profile_rejects_old_main(self):
        new = (RUN.ROOT / RUN.MAIN_SOURCE).read_bytes().replace(b"\r\n", b"\n")
        old = new.replace(b'#include "host/util/util.h"\n', b"", 1)
        _, errors = self.identity_with_inputs({RUN.MAIN_SOURCE: old}, "c3_header_fix_20261009")
        self.assertIn("FROZEN_SOURCE_IDENTITY: " + RUN.MAIN_SOURCE, errors)
        self.assertIn("HEADER_INCLUDE_ONLY: " + RUN.MAIN_SOURCE, errors)

    def test_new_profile_rejects_additional_or_business_changes(self):
        new = (RUN.ROOT / RUN.MAIN_SOURCE).read_bytes().replace(b"\r\n", b"\n")
        for data in (new + b"\n", new + b"/* extra */\n",
                     new.replace(b"ble_hs_util_ensure_addr(0)", b"ble_hs_util_ensure_addr(1)"),
                     new.replace(b'#include "host/util/util.h"\n',
                                 b'#include "host/util/util.h"\n' * 2)):
            with self.subTest(case=RUN.hashlib.sha256(data).hexdigest()):
                _, errors = self.identity_with_inputs({RUN.MAIN_SOURCE: data}, "c3_header_fix_20261009")
                self.assertIn("FROZEN_SOURCE_IDENTITY: " + RUN.MAIN_SOURCE, errors)
                self.assertIn("HEADER_INCLUDE_ONLY: " + RUN.MAIN_SOURCE, errors)

    def test_new_profile_rejects_relocated_include(self):
        new = (RUN.ROOT / RUN.MAIN_SOURCE).read_bytes().replace(b"\r\n", b"\n")
        added = b'#include "host/util/util.h"\n'
        moved = added + new.replace(added, b"", 1)
        identities, errors = self.identity_with_inputs({RUN.MAIN_SOURCE: moved}, "c3_header_fix_20261009")
        self.assertFalse(identities[RUN.MAIN_SOURCE]["include_only_proof"]["immediate_after_host_header"])
        self.assertIn("HEADER_INCLUDE_ONLY: " + RUN.MAIN_SOURCE, errors)

    def test_each_of_other_nine_sources_is_checked(self):
        expected, _ = RUN.source_profile("c3_header_fix_20261009")
        for relative in expected:
            if relative == RUN.MAIN_SOURCE:
                continue
            with self.subTest(source=relative):
                _, errors = self.identity_with_inputs(
                    {relative: (RUN.ROOT / relative).read_bytes() + b"\n"}, "c3_header_fix_20261009")
                self.assertIn("FROZEN_SOURCE_IDENTITY: " + relative, errors)

    def test_wrong_profile_expected_sha_is_rejected(self):
        actual_loads = json.loads

        def loader(text, *args, **kwargs):
            value = actual_loads(text, *args, **kwargs)
            if value.get("name") == "c3_header_fix_20261009":
                value["new_main_lf_sha256"] = "0" * 64
            return value

        with patch.object(RUN.json, "loads", loader):
            with self.assertRaisesRegex(ValueError, "HEADER_PROFILE_IDENTITY"):
                RUN.frozen_sources("c3_header_fix_20261009")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_SOURCE_PROFILE"):
            RUN.frozen_sources("accept_current_sources")


if __name__ == "__main__":
    unittest.main(verbosity=2)
