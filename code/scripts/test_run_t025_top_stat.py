"""Incremental regression for output isolation and real process timeout."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location("t025_runner", Path(__file__).with_name("run_t025_top_stat.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_fresh_outputs(self):
        with tempfile.TemporaryDirectory() as root:
            previous = runner.ROOT
            try:
                runner.ROOT = Path(root)
                first = runner.new_stage("tb_example")
                (first / "run.log").write_text("OLD PASS", encoding="utf-8")
                second = runner.new_stage("tb_example")
                self.assertNotEqual(first, second)
                self.assertFalse((second / "run.log").exists())
                with self.assertRaises(ValueError):
                    runner.new_stage("../escape")
            finally:
                runner.ROOT = previous

    def test_failure_keeps_streams(self):
        with tempfile.TemporaryDirectory() as root:
            stage = Path(root)
            code, timeout = runner.run_bounded(
                [sys.executable, "-B", "-c", "import sys; print('PARTIAL'); print('BAD',file=sys.stderr); sys.exit(7)"], stage, 10)
            self.assertEqual(code, 7)
            self.assertFalse(timeout)
            self.assertIn(b"PARTIAL", (stage / "stdout.log").read_bytes())
            self.assertIn(b"BAD", (stage / "stderr.log").read_bytes())

    def test_timeout_keeps_partial_and_kills_child(self):
        with tempfile.TemporaryDirectory() as root:
            stage = Path(root)
            child = "import time; from pathlib import Path; time.sleep(2); Path('orphan.txt').write_text('BAD')"
            code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); print('STARTED',flush=True); time.sleep(20)"
            started = time.monotonic()
            exit_code, timeout = runner.run_bounded([sys.executable, "-B", "-c", code], stage, 1)
            self.assertTrue(timeout)
            self.assertNotEqual(exit_code, 0)
            self.assertLess(time.monotonic() - started, 3)
            self.assertIn(b"STARTED", (stage / "stdout.log").read_bytes())
            time.sleep(2)
            self.assertFalse((stage / "orphan.txt").exists())

    def test_no_launch_after_budget(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(TimeoutError):
                runner.run_bounded([sys.executable, "-c", "raise SystemExit(0)"], Path(root), 0)


if __name__ == "__main__":
    unittest.main()
