"""One new case: complete commit persisted despite a failed write acknowledgement."""
import argparse
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner_tail_20261013 as runner  # noqa: E402
import supervisor_20261013 as supervisor  # noqa: E402

EVIDENCE = None


class CompletionAckTest(unittest.TestCase):
    def test_complete_write_then_error_is_consistent_commit(self):
        child = EVIDENCE / "child"
        parent = EVIDENCE / "supervisor"
        probe = EVIDENCE / "probe.txt"
        probe.write_bytes(b"completion-ack-probe")
        snapshot = {str(probe.resolve()): runner.identity(probe)}
        fake = ("import pathlib,json;"
                f"p=pathlib.Path({str(child)!r});p.mkdir();"
                "(p/'receipt.json').write_text(json.dumps({'status':'PASS','exit_code':0}),encoding='utf8')")
        argv = [sys.executable, "-I", "-S", "-B", "-c", fake]
        original_write = runner.write_json
        injected = []

        def writer(path, value, exclusive=True):
            original_write(path, value, exclusive=exclusive)
            if Path(path).name == "completion.json":
                injected.append(str(path))
                raise OSError("INJECTED_ERROR_AFTER_COMPLETE_COMMIT_WRITE")

        with patch.object(runner, "write_json", side_effect=writer):
            result = supervisor.observe_run(parent, argv, EVIDENCE,
                                            child / "receipt.json", snapshot)
        self.assertEqual(len(injected), 1)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["status"], "OBSERVED_ZERO_EXIT")
        self.assertIsNone(result["failure"])
        verified = supervisor.require_supervisor(
            child, parent / "observation.json", argv, snapshot, expected_cwd=EVIDENCE)
        self.assertEqual(verified["record"], result)
        self.assertEqual(verified["files"][str((parent / "completion.json").resolve())],
                         (parent / "completion.json").read_bytes())
        runner.write_json(EVIDENCE / "result.json", {
            "status": "SOFTWARE_COMPLETE_WRITE_ACK_FAILURE_CONSISTENT",
            "injected": "completion complete write then OSError",
            "returned_exit_code": 0, "verified_completion": True,
            "old_tests": "REUSED_NOT_RERUN",
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    EVIDENCE = args.evidence_dir.resolve()
    runner.require(not EVIDENCE.exists(), "EVIDENCE_OUTPUT_EXISTS")
    EVIDENCE.mkdir(parents=True)
    unittest.main(argv=[sys.argv[0], *remaining])
