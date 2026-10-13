"""One new regression: JSON body without the commit's final LF is not complete."""
import argparse
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner_tail_20261013 as runner  # noqa: E402
import supervisor_20261013 as supervisor  # noqa: E402
import delivery_tail_20261013 as delivery  # noqa: E402

EVIDENCE = None


class CompletionEncodingTest(unittest.TestCase):
    def test_json_body_without_lf_then_error_is_rejected(self):
        child = EVIDENCE / "child"
        parent = EVIDENCE / "supervisor"
        probe = EVIDENCE / "probe.txt"
        probe.write_bytes(b"completion-encoding-probe")
        snapshot = {str(probe.resolve()): runner.identity(probe)}
        fake = ("import pathlib,json;"
                f"p=pathlib.Path({str(child)!r});p.mkdir();"
                "(p/'receipt.json').write_text(json.dumps({'status':'PASS','exit_code':0}),encoding='utf8')")
        argv = [sys.executable, "-I", "-S", "-B", "-c", fake]
        original_write = runner.write_json
        injected = []

        def writer(path, value, exclusive=True):
            if Path(path).name == "completion.json":
                with Path(path).open("xb") as stream:
                    stream.write(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))
                injected.append(str(path))
                raise OSError("INJECTED_ERROR_BEFORE_COMPLETION_FINAL_LF")
            original_write(path, value, exclusive=exclusive)

        with patch.object(runner, "write_json", side_effect=writer):
            result = supervisor.observe_run(parent, argv, EVIDENCE,
                                            child / "receipt.json", snapshot)
        self.assertEqual(len(injected), 1)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("COMPLETION_WRITE", result["failure"])
        raw = (parent / "completion.json").read_bytes()
        self.assertEqual(json.loads(raw)["schema"], "T052_OBSERVATION_COMPLETION_V1")
        self.assertFalse(raw.endswith(b"\n"))
        with self.assertRaisesRegex(ValueError, "SUPERVISOR_COMPLETION_ENCODING"):
            supervisor.require_supervisor(child, parent / "observation.json", argv,
                                          snapshot, expected_cwd=EVIDENCE)
        target = delivery.DOC / "REJECTED_NO_LF_COMMIT_MUST_NOT_EXIST_20261013"
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(ValueError, "SUPERVISOR_COMPLETION_ENCODING"):
            delivery.seal(child, target, parent / "observation.json")
        self.assertFalse(target.exists())
        runner.write_json(EVIDENCE / "result.json", {
            "status": "SOFTWARE_INCOMPLETE_COMMIT_REJECTED", "returned_exit_code": 1,
            "injected": "complete JSON body, missing LF, write OSError",
            "require_and_seal_diagnostic": "SUPERVISOR_COMPLETION_ENCODING",
            "target_created": False, "old_tests": "REUSED_NOT_RERUN",
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    EVIDENCE = args.evidence_dir.resolve()
    runner.require(not EVIDENCE.exists(), "EVIDENCE_OUTPUT_EXISTS")
    EVIDENCE.mkdir(parents=True)
    unittest.main(argv=[sys.argv[0], *remaining])
