"""Real timestamp analysis guard tests; no modelled timing substituted."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code/scripts"))
from check_t031_digital_latency import analyze


class AnalysisGuards(unittest.TestCase):
    def setUp(self):
        self.source = ROOT / "code/output/t031_digital_latency_20261002/latency.csv"
        self.accepted = analyze(self.source)
        with self.source.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            self.columns = reader.fieldnames
            self.rows = list(reader)

    def reject(self, mutation):
        rows = [dict(row) for row in self.rows]
        mutation(rows)
        with tempfile.TemporaryDirectory(prefix="t031_analysis_guard_") as folder:
            target = Path(folder) / "bad.csv"
            with target.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.columns)
                writer.writeheader();writer.writerows(rows)
            with self.assertRaises(ValueError):
                analyze(target)

    def test_actual_complete_capture(self):
        self.assertEqual(self.accepted["trial_count"], 11)
        self.assertFalse(self.accepted["physical_analog_latency_proven"])
        self.assertFalse(self.accepted["T031_closed"])

    def test_no_target_difference(self):
        self.reject(lambda rows: rows[0].update(reference_right_pcm16=rows[0]["dut_right_pcm16"]))

    def test_word_before_causal_event(self):
        self.reject(lambda rows: rows[0].update(right_word_complete_cycle=rows[0]["event_accept_cycle"]))

    def test_weakened_transport_input(self):
        self.reject(lambda rows: rows[0].update(final_byte_rx_cycle=str(int(rows[0]["start_cycle"]) + 100)))

    def test_truncated_suite(self):
        self.reject(lambda rows: rows.pop())

    def test_over_limit_serial_word(self):
        self.reject(lambda rows: rows[0].update(right_word_complete_cycle=str(int(rows[0]["start_cycle"]) + 500001)))


if __name__ == "__main__":
    unittest.main()
