"""T029 pitch-register probe guards, independent of FPGA tool availability."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import probe_t029_pitch_register as probe  # noqa: E402


class PitchRegisterProbeTests(unittest.TestCase):
    def test_candidate_is_guarded_and_contains_event_step_register(self):
        source = probe.SOURCE.read_text(encoding="utf-8")
        generated = probe.candidate(source)
        self.assertIn(".note_number (event_data.note_number)", generated)
        self.assertIn("step_q <= incoming_step;", generated)
        self.assertEqual(source.count("step_q <= incoming_step;"), 0)
        with self.assertRaisesRegex(ValueError, "Source pitch instance changed"):
            probe.candidate(source.replace(".note_number (note_q)", ".note_number (unknown)"))

    def test_trace_length_and_sample_mismatch_rejected(self):
        self.assertEqual(probe.compare_traces(["TRACE 0"], ["TRACE 0"]), 1)
        with self.assertRaisesRegex(ValueError, "length differs"):
            probe.compare_traces(["TRACE 0"], [])
        with self.assertRaisesRegex(ValueError, "differs at cycle 0"):
            probe.compare_traces(["TRACE 0"], ["TRACE 0 changed"])

    def test_fmax_or_baseline_drift_rejected(self):
        base = probe.source_fingerprints()
        original = {"timing_and_resources": {"fmax_mhz": "50.000(MHz)",
                 "resources": {"Logic": 1}},
                 "tool_and_part": {"Part Number": "fake"}, "active_sdc_commands": []}
        with self.assertRaisesRegex(ValueError, "did not improve"):
            probe.compare_baseline(base, original)
        with self.assertRaisesRegex(ValueError, "inputs differ"):
            probe.compare_baseline({"changed": "hash"}, original)


if __name__ == "__main__":
    unittest.main()
