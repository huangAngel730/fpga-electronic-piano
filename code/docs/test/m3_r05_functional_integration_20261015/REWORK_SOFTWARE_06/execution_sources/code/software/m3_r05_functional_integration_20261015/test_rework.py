"""A-only synthetic launch/identity tests. Never invokes ModelSim."""
import ctypes as C
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from common import DOCS, Refusal, write_new
from supervised_process import invoke
from tool_probe_policy import pin_inventory, probe_valid
import windows_job


class ProbePolicyTests(unittest.TestCase):
    def call(self, name, option):
        return {"argv": [name + ".exe", option], "exit_code": 0,
                "timeout": False, "error": None, "process_created": True,
                "log_limit_exceeded": False}

    def test_vlib_help_is_not_version(self):
        call = self.call("vlib", "-help")
        self.assertTrue(probe_valid("vlib", call, b"Usage: vlib -help\n"))
        call["argv"][1] = "-version"
        call["exit_code"] = 1
        self.assertFalse(probe_valid("vlib", call, b"Usage: vlib -help\n"))

    def test_runtime_version_wrong_or_absent_rejected(self):
        for name in ("vlog", "vsim"):
            call = self.call(name, "-version")
            self.assertTrue(probe_valid(name, call, b"ModelSim SE-64 2020.4 Compiler\n"))
            for text in (b"ModelSim SE-64 10.7", b"Usage: vlib -help", b""):
                self.assertFalse(probe_valid(name, call, text))

    def test_error_exit_timeout_unknown_creation_rejected(self):
        for field, value in (("exit_code", False), ("exit_code", 1),
                             ("timeout", True), ("error", "error"),
                             ("process_created", None), ("log_limit_exceeded", True)):
            call = self.call("vlib", "-help")
            call[field] = value
            self.assertFalse(probe_valid("vlib", call, b"Usage: vlib -help\n"))

    def test_inventory_and_metadata_drift(self):
        self.assertEqual(pin_inventory({"x": "a"}, {"x": "a"}, b'"2020.4"')[
            "vlib_runtime_version"], "NOT_EXPORTED_BY_HELP")
        for current, metadata in (({"x": "b"}, b'"2020.4"'),
                                  ({"x": "a"}, b'"10.7"')):
            with self.assertRaises(Refusal):
                pin_inventory(current, {"x": "a"}, metadata)

    def test_good_banner_with_error_and_wrong_edition(self):
        for name, option, banner in (("vlib", "-help", b"Usage: vlib -help\n"),
                                     ("vlog", "-version", b"ModelSim SE-64 2020.4 Compiler\n"),
                                     ("vsim", "-version", b"ModelSim SE-64 2020.4 Simulator\n")):
            for error in (b"Error: synthetic\n", b"Errors: 01\n", b"** Failure: synthetic\n"):
                for raw in (error + banner, banner + error):
                    self.assertFalse(probe_valid(name, self.call(name, option), raw))
        self.assertFalse(probe_valid("vlog", self.call("vlog", "-version"),
                                     b"ModelSim Intel FPGA 2020.4"))


@unittest.skipUnless(os.name == "nt", "Windows API contract")
class LaunchTests(unittest.TestCase):
    def call(self, code, *, callback=None):
        base = Path(os.environ["A_REWORK_TEST_OUTPUT"])
        folder = Path(tempfile.mkdtemp(prefix="SYNTHETIC_", dir=base))
        result = invoke([sys.executable, "-B", "-c", code], folder, folder,
                        "python", time.monotonic() + 5, step_budget=4,
                        on_created=callback)
        write_new(folder / "RECEIPT.json", result)
        return result

    def test_old_stdin_failure_and_fixed_eof(self):
        old_path = DOCS / "REWORK_20261016_R02/source_before/windows_job.py"
        spec = importlib.util.spec_from_file_location("historical_job", old_path)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        code = ("import sys;print('SYNTHETIC_STDIN',sys.stdin is not None,flush=True);"
                "raise SystemExit(7 if sys.stdin is None else (0 if sys.stdin.read()=='' else 8))")
        real_loader = C.WinDLL
        observed = []

        class ContractProxy:
            def __init__(self):
                self.real = real_loader("kernel32", use_last_error=True)

            def __getattr__(self, name):
                fn = getattr(self.real, name)
                if name != "CreateProcessW":
                    return fn
                def checked(*args):
                    # Examine exactly what our wrapper supplies, before any
                    # CRT/host transforms the child's standard handles.
                    startup = args[-2]._obj
                    observed.append(startup.stdin)
                    if not startup.stdin:
                        raise ValueError("SYNTHETIC_INVALID_STARTUP_STDIN")
                    fn.restype, fn.argtypes = checked.restype, checked.argtypes
                    return fn(*args)
                setattr(self, name, checked)
                return checked

        with patch.object(C, "WinDLL", lambda *a, **kw: ContractProxy()):
            with patch("supervised_process.JobProcess", old.JobProcess):
                before = self.call(code)
            after = self.call(code)
        self.assertIn("SYNTHETIC_INVALID_STARTUP_STDIN", before["error"])
        self.assertIsNone(observed[0])
        self.assertTrue(observed[1])
        self.assertEqual(after["exit_code"], 0)
        self.assertTrue(after["create_process_returned"])
        self.assertGreater(after["created_pid"], 0)

    def failed_api(self, name, error=5):
        real_loader = C.WinDLL

        class Proxy:
            def __init__(self):
                self.real = real_loader("kernel32", use_last_error=True)

            def __getattr__(self, key):
                if key != name:
                    return getattr(self.real, key)
                def fail(*args):
                    C.set_last_error(error)
                    return 0xFFFFFFFF if key == "ResumeThread" else 0
                return fail
        return patch.object(windows_job.C, "WinDLL", lambda *a, **kw: Proxy())

    def test_create_process_failure_precise_and_unconsumed(self):
        created = []
        with self.failed_api("CreateProcessW", 623):
            result = self.call("print('MUST_NOT_EXECUTE')", callback=created.append)
        self.assertFalse(result["process_created"])
        self.assertTrue(result["create_process_attempted"])
        self.assertFalse(result["create_process_returned"])
        self.assertEqual(result["winerror"], 623)
        self.assertEqual(result["launch_stage_failed"], "CREATE_PROCESS_SUSPENDED")
        self.assertEqual(created, [])

    def test_assignment_failure_created_consumed_before_resume(self):
        created = []
        with self.failed_api("AssignProcessToJobObject"):
            result = self.call("print('MUST_NOT_EXECUTE')", callback=created.append)
        self.assertTrue(result["process_created"])
        self.assertTrue(result["create_process_returned"])
        self.assertEqual(result["launch_stage_failed"], "ASSIGN_TO_JOB")
        self.assertEqual(len(created), 1)
        self.assertEqual(result["stdout"]["bytes"], 0)

    def test_resume_failure_created_consumed(self):
        created = []
        with self.failed_api("ResumeThread"):
            result = self.call("print('MUST_NOT_EXECUTE')", callback=created.append)
        self.assertTrue(result["process_created"])
        self.assertEqual(result["launch_stage_failed"], "RESUME_THREAD")
        self.assertEqual(len(created), 1)
        self.assertEqual(result["stdout"]["bytes"], 0)

    def test_callback_failure_does_not_start_code(self):
        def reject(pid):
            raise FileExistsError("SYNTHETIC_DUPLICATE_CONSUMPTION")
        result = self.call("print('MUST_NOT_EXECUTE')", callback=reject)
        self.assertTrue(result["process_created"])
        self.assertEqual(result["launch_stage_failed"], "CREATION_CALLBACK")
        self.assertEqual(result["stdout"]["bytes"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
