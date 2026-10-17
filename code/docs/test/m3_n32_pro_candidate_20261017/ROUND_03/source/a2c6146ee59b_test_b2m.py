"""Synthetic software tests and readonly N4 capture checks; no HDL execution."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import b2m_check as m
from dds_model import PianoDDS
from envelope_model import Envelope, voice_pcm


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (Path(os.environ["B2M_FIXTURE_ROOT"]) / "N4_R1.capture").read_bytes()

    def test_original_and_nonmutation(self):
        before = bytes(self.raw)
        result = m.check(self.raw)
        self.assertEqual(result["counts"]["published_pcm_checked"], 21)
        self.assertFalse(result["task_complete"])
        self.assertFalse(result["LFO_nonrollback_proved"])
        self.assertFalse(result["lane_math_fields_observed"])
        self.assertEqual(before, self.raw)

    def test_pcm_1lsb_rejects(self):
        with self.assertRaisesRegex(ValueError, "B2M_PCM"):
            m.Mathematics.compare_pcm(dict(cycle=1, left=2, right=1), 1)

    def test_asymmetric_pcm_rejects(self):
        with self.assertRaisesRegex(ValueError, "B2M_PCM"):
            m.Mathematics.compare_pcm(dict(cycle=1, left=1, right=0), 1)

    def test_floor_negative(self):
        self.assertEqual(voice_pcm(-1, 1), -256)
        self.assertEqual(voice_pcm(-32768, 32767), -8388352)

    def test_positive_gain(self):
        self.assertEqual(voice_pcm(32767, 32767), 8388096)
        self.assertEqual(voice_pcm(32767, 0), 0)

    def test_envelope_advance_rollback_is_detected(self):
        edge = Envelope.edge
        def bad(env, *args, **kwargs):
            return edge(env, *args, **dict(kwargs, tick=False))
        with patch.object(Envelope, "edge", bad), self.assertRaisesRegex(ValueError, "B2M_PCM"):
            m.check(self.raw)

    def test_wrong_wave_rom_is_detected(self):
        original = m.signed
        def bad(value, width):
            return original(value, width) + 16
        with patch.object(m, "signed", bad), self.assertRaisesRegex(ValueError, "B2M_PCM"):
            m.check(self.raw)

    def test_wrong_gain_is_detected(self):
        with patch.object(m, "voice_pcm", lambda w, e: 0), self.assertRaisesRegex(ValueError, "B2M_PCM"):
            m.check(self.raw)

    def test_wrong_dds_is_detected(self):
        edge = PianoDDS.edge
        def bad(osc, fcw, *args, **kwargs):
            return edge(osc, 0 if kwargs.get("tick") else fcw, *args, **kwargs)
        with patch.object(PianoDDS, "edge", bad), self.assertRaisesRegex(ValueError, "B2M_PCM"):
            m.check(self.raw)

    def test_missing_end_is_rejected(self):
        lines = [x for x in self.raw.splitlines() if not x.startswith(b"END ")]
        with self.assertRaises(ValueError):
            m.check(b"\n".join(lines) + b"\n")

    def test_zero_response_rejected(self):
        raw = self.raw.replace(b"B2K 4 1", b"B2K 4 0", 1)
        with self.assertRaisesRegex(ValueError, "CLOCK_PARAMETERS"):
            m.check(raw)

    def test_whole_domain_reset_clears_math(self):
        model = m.Mathematics(4, 1)
        model.env[0].level = 0x100000
        model.dds[0].phase = 123
        model.lfo[0] = 456
        model.reset(17)
        self.assertEqual(model.env[0].level, 0)
        self.assertEqual(model.dds[0].phase, 0)
        self.assertEqual(model.lfo[0], 0)
        self.assertEqual(model.env[0].cycle, 17)


if __name__ == "__main__":
    unittest.main()
