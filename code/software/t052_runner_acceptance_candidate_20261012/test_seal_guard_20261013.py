"""One incremental counterexample: stale PASS on disk is not a zero exit."""
import argparse
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner_tail_20261013 as runner  # noqa: E402
import delivery_tail_20261013 as delivery  # noqa: E402
import supervisor_20261013 as supervisor  # noqa: E402

EVIDENCE = None


def failing_child(output):
    output.mkdir(parents=True)
    now = [0.0]
    budget = runner.Budget(900, clock=lambda: now[0])
    now[0] = 899.0
    receipt = {"status": "SOFTWARE_TAIL_INCREMENT_PASS", "exit_code": 0, "failure": None,
               "sources_before": delivery.sources(), "sources_after": delivery.sources()}

    def writer(path, value, exclusive=True):
        if not exclusive:
            raise OSError("INJECTED_CORRECTION_WRITE_DENIED_BEFORE_OVERWRITE")
        runner.write_json(path, value)
        now[0] = 901.0

    result = runner.finalize_receipt(output / "receipt.json", receipt, budget, writer=writer)
    print(result["failure"], flush=True)
    return result["exit_code"]


class SealGuardTest(unittest.TestCase):
    def test_disk_pass_with_observed_nonzero_cannot_seal(self):
        child_output = EVIDENCE / "stale_pass_child"
        command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(Path(__file__).resolve()),
                   "--failing-child", "--output", str(child_output)]
        observation = supervisor.observe_run(
            EVIDENCE / "parent", command, delivery.ROOT, child_output / "receipt.json",
            delivery.source_snapshot(), total_seconds=30, step_seconds=10,
        )
        self.assertEqual(runner.load_json(child_output / "receipt.json")["exit_code"], 0)
        self.assertEqual(observation["step"]["exit_code"], 1)
        self.assertEqual(observation["exit_code"], 1)
        self.assertIn("SUPERVISOR_CHILD_NONZERO", observation["failure"])
        target = delivery.DOC / "REJECTED_STALE_PASS_MUST_NOT_EXIST_20261013"
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(ValueError, "SUPERVISOR_NOT_ZERO_EXIT"):
            delivery.seal(child_output, target, EVIDENCE / "parent/observation.json")
        self.assertFalse(target.exists())
        runner.write_json(EVIDENCE / "rejection.json", {
            "status": "SOFTWARE_COUNTEREXAMPLE_REJECTED",
            "disk_pass_exit": 0, "actual_child_exit": observation["step"]["exit_code"],
            "diagnostic": "SUPERVISOR_NOT_ZERO_EXIT", "seal_created": False,
            "old_nine_and_new_three": "REUSED_NOT_RERUN",
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--failing-child", action="store_true")
    parser.add_argument("--output", type=Path)
    args, remaining = parser.parse_known_args()
    if args.failing_child:
        raise SystemExit(failing_child(args.output))
    EVIDENCE = args.evidence_dir.resolve()
    runner.require(not EVIDENCE.exists(), "EVIDENCE_OUTPUT_EXISTS")
    EVIDENCE.mkdir(parents=True)
    unittest.main(argv=[sys.argv[0], *remaining])
