"""Probe report checker rejects damaged timing/part/resource evidence."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_t024_voice_datapath import report

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "code/output/t024_voice_datapath/lanes_4/impl/pnr"


class ReportTests(unittest.TestCase):
    def setUp(self):
        if not (REPORT / "voice_datapath_probe_4.rpt.txt").exists():
            self.skipTest("Run standalone Gowin probe first")
        self.tmp = tempfile.TemporaryDirectory(prefix="t024_report_")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.dest = self.base / "lanes_4/impl/pnr"
        self.dest.mkdir(parents=True)
        for suffix in (".rpt.txt", "_tr_content.html"):
            shutil.copyfile(REPORT / ("voice_datapath_probe_4" + suffix),
                            self.dest / ("voice_datapath_probe_4" + suffix))

    def mutate(self, suffix, old, new):
        path = self.dest / ("voice_datapath_probe_4" + suffix)
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_real_report_has_eight_roms_and_dsp(self):
        data = report(self.base, 4)
        self.assertEqual(data["resources"]["BSRAM"], 8)
        self.assertEqual(data["resources"]["DSP"], 24)

    def test_wrong_part_rejected(self):
        self.mutate(".rpt.txt", "GW5AT-LV60PG484AC1/I0", "WRONG")
        with self.assertRaises(ValueError):
            report(self.base, 4)

    def test_missing_bram_usage_rejected(self):
        self.mutate(".rpt.txt", "  BSRAM", "  REMOVED")
        with self.assertRaises(ValueError):
            report(self.base, 4)

    def test_negative_setup_rejected(self):
        path = self.dest / "voice_datapath_probe_4_tr_content.html"
        text = path.read_text(encoding="utf-8")
        prefix, marker, section = text.partition('name="Setup_Slack_Table"')
        self.assertTrue(marker)
        self.assertIn("<td>0.963</td>", section)
        section = section.replace("<td>0.963</td>", "<td>-0.001</td>", 1)
        path.write_text(prefix + marker + section, encoding="utf-8")
        with self.assertRaises(ValueError):
            report(self.base, 4)

    def test_missing_clock_rejected(self):
        self.mutate("_tr_content.html", "sys_clk", "missing_clk")
        with self.assertRaises(ValueError):
            report(self.base, 4)


if __name__ == "__main__":
    unittest.main()
