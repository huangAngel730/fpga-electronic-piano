"""One observation-layer counterexample plus exact-budget/byte-snapshot assertions."""
import argparse
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner_tail_20261013 as runner  # noqa: E402
import delivery_tail_20261013 as delivery  # noqa: E402
import supervisor_20261013 as supervisor  # noqa: E402

EVIDENCE = None


def command(output):
    fake = ("import json,pathlib;"
            f"p=pathlib.Path({str(output)!r});p.mkdir();"
            "(p/'receipt.json').write_text(json.dumps({'status':'PASS','exit_code':0}),encoding='utf8')")
    return [sys.executable, "-I", "-S", "-B", "-c", fake]


class ObservationGuardTest(unittest.TestCase):
    def test_observation_commit_budget_and_snapshot(self):
        case = EVIDENCE / "stale_observation"
        child = case / "child"
        source = EVIDENCE / "frozen_probe.txt"
        source.write_bytes(b"frozen-source")
        snapshot = {str(source.resolve()): runner.identity(source)}
        now = [0.0]
        budget = runner.Budget(300, clock=lambda: now[0])
        original_finalize = runner.finalize_receipt

        def finalizer(path, receipt, unused_budget):
            now[0] = 299.0

            def writer(target, value, exclusive=True):
                if not exclusive:
                    raise OSError("INJECTED_OBSERVATION_CORRECTION_WRITE_DENIED")
                runner.write_json(target, value)
                now[0] = 301.0

            return original_finalize(path, receipt, budget, writer=writer)

        with patch.object(runner, "Budget", return_value=budget), \
                patch.object(runner, "finalize_receipt", side_effect=finalizer):
            result = supervisor.observe_run(case / "supervisor", command(child),
                                            delivery.ROOT, child / "receipt.json", snapshot)
        self.assertEqual(result["exit_code"], 1)
        observed = case / "supervisor/observation.json"
        self.assertEqual(runner.load_json(observed)["exit_code"], 0)
        self.assertFalse((observed.parent / "completion.json").exists())
        with self.assertRaisesRegex(ValueError, "SUPERVISOR_COMPLETION_MISSING"):
            supervisor.require_supervisor(child, observed, command(child), snapshot,
                                          expected_cwd=delivery.ROOT)

        # Same new software case: bind exact limits and retain the verified bytes.
        good_child = EVIDENCE / "good_child"
        good_parent = EVIDENCE / "good_parent"
        good = supervisor.observe_run(good_parent, command(good_child), delivery.ROOT,
                                      good_child / "receipt.json", snapshot)
        self.assertEqual(good["exit_code"], 0)
        for kwargs in ({"expected_total": 299}, {"expected_step": 89}):
            with self.assertRaisesRegex(ValueError, "SUPERVISOR_EXACT_BUDGET"):
                supervisor.require_supervisor(good_child, good_parent / "observation.json",
                                              command(good_child), snapshot, **kwargs)
        bundle = supervisor.require_supervisor(good_child, good_parent / "observation.json",
                                                command(good_child), snapshot)
        source.write_bytes(b"changed-after-validation")
        self.assertEqual(bundle["files"][str(source.resolve())], b"frozen-source")
        runner.write_json(EVIDENCE / "rejection.json", {
            "status": "SOFTWARE_OBSERVATION_GUARD_PASS", "stale_observation_exit": 0,
            "actual_return_exit": result["exit_code"], "completion_created": False,
            "missing_commit_diagnostic": "SUPERVISOR_COMPLETION_MISSING",
            "wider_300_than_299_and_90_than_89": "SUPERVISOR_EXACT_BUDGET",
            "verified_source_bytes_preserved": True, "old_tests": "REUSED_NOT_RERUN",
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    EVIDENCE = args.evidence_dir.resolve()
    runner.require(not EVIDENCE.exists(), "EVIDENCE_OUTPUT_EXISTS")
    EVIDENCE.mkdir(parents=True)
    unittest.main(argv=[sys.argv[0], *remaining])
