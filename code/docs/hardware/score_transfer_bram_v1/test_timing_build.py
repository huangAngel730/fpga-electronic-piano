"""Execution-policy tests use mocks, not Gowin or FPGA hardware."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import timing_build


class ExecutePolicyTest(unittest.TestCase):
    def run_policy(self, limit, timeout=False):
        with tempfile.TemporaryDirectory(prefix='score_pnr_policy_') as temp:
            out = Path(temp)
            process = Mock(pid=4321, returncode=0)
            if timeout:
                process.wait.side_effect = [subprocess.TimeoutExpired('mock', limit), 1]
                process.returncode = 1
            with patch.object(timing_build.subprocess, 'Popen', return_value=process), \
                    patch.object(timing_build.subprocess, 'run') as kill:
                result = timing_build.execute(out, 'pnr', out/'pnr.tcl', limit)
                journal = json.loads((out/'pnr_process.json').read_text(encoding='utf-8'))
            return result, journal, process, kill

    def test_unlimited_has_no_automatic_kill(self):
        result, journal, process, kill = self.run_policy(None)
        process.wait.assert_called_once_with(timeout=None)
        kill.assert_not_called()
        self.assertIsNone(result['timeout'])
        self.assertFalse(result['timed_out'])
        self.assertTrue(journal['unlimited'])
        self.assertEqual(journal['pid'], 4321)

    def test_bounded_default_is_preserved(self):
        result, journal, process, kill = self.run_policy(900)
        process.wait.assert_called_once_with(timeout=900)
        kill.assert_not_called()
        self.assertEqual(result['timeout'], 900)
        self.assertFalse(journal['unlimited'])

    def test_bounded_timeout_kills_only_owned_tree(self):
        result, _, process, kill = self.run_policy(900, timeout=True)
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['exit_code'], 1)
        self.assertEqual(process.wait.call_count, 2)
        kill.assert_called_once_with(['taskkill', '/PID', '4321', '/T', '/F'],
                                    capture_output=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
