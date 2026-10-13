"""Only three new tail regressions; no frozen nine-case suite execution."""
import argparse
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner_tail_20261013 as runner  # noqa: E402
import delivery_tail_20261013 as delivery  # noqa: E402
from test_runner import fixture  # noqa: E402 -- only the fake config factory

EVIDENCE = None


class TailTests(unittest.TestCase):
    def tail_case(self, name, after_write):
        case = EVIDENCE / name
        case.mkdir()
        config = fixture(case)
        value = runner.load_json(config)
        value["total_seconds"] = 900
        runner.write_json(config, value, exclusive=False)
        clock = [0.0]
        budget = runner.Budget(900, clock=lambda: clock[0])
        original_finalize = runner.finalize_receipt
        original_writer = runner.write_json
        writes = []

        def writer(path, receipt, exclusive=True):
            original_writer(path, receipt, exclusive=exclusive)
            writes.append({"status": receipt["status"], "exit_code": receipt["exit_code"]})
            clock[0] = after_write

        def finalizer(path, receipt, actual_budget):
            clock[0] = 899.0
            return original_finalize(path, receipt, actual_budget, writer=writer)

        with patch.object(runner, "Budget", return_value=budget), \
                patch.object(runner, "finalize_receipt", side_effect=finalizer):
            result = runner.run(config, case / "out")
        persisted = runner.load_json(case / "out/receipt.json")
        self.assertEqual(result, persisted)
        runner.write_json(case / "synthetic_clock.json", {
            "kind": "SOFTWARE_SYNTHETIC_CLOCK_NOT_RTL",
            "before_final_receipt_write": 899, "after_final_receipt_write": after_write,
            "budget_seconds": 900, "writes": writes,
            "returned_exit_code": result["exit_code"],
        })
        return result, writes

    def test_final_receipt_write_crosses_budget(self):
        result, writes = self.tail_case("tail_crosses", 901.0)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["status"], "FAIL_PARTIAL")
        self.assertIn("TOTAL_BUDGET_EXHAUSTED_AFTER_RECEIPT", result["failure"])
        self.assertEqual([item["exit_code"] for item in writes], [0, 1])
        self.assertEqual(result["elapsed_seconds"], 901.0)

    def test_final_receipt_write_stays_in_budget(self):
        result, writes = self.tail_case("tail_within", 899.5)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["status"], "JOINT_COMPILE_SIMULATE_CHECK_PASS")
        self.assertEqual(len(writes), 1)

    def test_qualification_timeout_keeps_partial_and_owned_cleanup(self):
        case = EVIDENCE / "qualification_timeout"
        child = "import time,pathlib;time.sleep(1.2);pathlib.Path('orphan.txt').write_text('bad')"
        fake = (
            "import pathlib,subprocess,sys,time;"
            "print('qualification partial stdout',flush=True);"
            "print('qualification partial stderr',file=sys.stderr,flush=True);"
            "pathlib.Path('partial.fake').write_bytes(b'partial-original');"
            f"subprocess.Popen([sys.executable,'-I','-S','-B','-c',{child!r}]);"
            "time.sleep(10)"
        )
        result = delivery.qualify(
            case, command=[sys.executable, "-I", "-S", "-B", "-c", fake],
            total_seconds=5, step_seconds=0.4,
        )
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("QUALIFICATION_TIMEOUT", result["failure"])
        self.assertTrue(result["step"]["timed_out"])
        self.assertIsNotNone(result["step"]["cleanup"])
        self.assertEqual((case / "partial.fake").read_bytes(), b"partial-original")
        self.assertIn(b"qualification partial stdout", (case / "tests.stdout.bin").read_bytes())
        self.assertIn(b"qualification partial stderr", (case / "tests.stderr.bin").read_bytes())
        self.assertEqual(runner.load_json(case / "receipt.json"), result)
        time.sleep(1.4)
        self.assertFalse((case / "orphan.txt").exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    EVIDENCE = args.evidence_dir.resolve()
    if EVIDENCE.exists():
        raise ValueError("EVIDENCE_OUTPUT_EXISTS")
    EVIDENCE.mkdir(parents=True)
    unittest.main(argv=[sys.argv[0], *remaining])
