"""Guard the T009 PnR gate against synthetic false-positive reports."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_t009_fusion_report import verify


class ReportGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        cls.example_timing = (root / "code/output/t009_fusion/impl/pnr/adsr_probe_tr_content.html")
        cls.example_usage = (root / "code/output/t009_fusion/impl/pnr/adsr_probe.rpt.txt")

    def test_missing_report_rejected(self):
        failures, _ = verify("", "")
        self.assertTrue(failures)

    def test_timing_requirements_enforced(self):
        # Use real report when available; standalone unit tests remain clean
        # and skip comparison before the optional Gowin flow is run.
        if not self.example_timing.exists():
            self.skipTest("optional standalone PnR output absent")
        timing = self.example_timing.read_text(encoding="utf-8")
        usage = self.example_usage.read_text(encoding="utf-8")
        self.assertEqual(verify(timing, usage)[0], [])
        bad = timing.replace("<td class=\"label\">Numbers of Setup Violated Endpoints</td>\n<td>0</td>", "<td class=\"label\">Numbers of Setup Violated Endpoints</td>\n<td>1</td>", 1)
        self.assertTrue(verify(bad, usage)[0])
        self.assertTrue(verify(timing, usage.replace("<Part Number>: GW5AT", "<Part Number>: GW0AT"))[0])


if __name__ == "__main__":
    unittest.main()
