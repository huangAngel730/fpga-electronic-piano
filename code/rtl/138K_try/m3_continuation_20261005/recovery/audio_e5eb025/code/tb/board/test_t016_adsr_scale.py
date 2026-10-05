"""Negative checks against the independently generated Gowin PnR reports.

Run after run_t016_adsr_scale.ps1; no repository RTL is changed.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_t016_adsr_scale import parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = ROOT / "code/output/t016_adsr_scale/voice_4/impl/pnr"


class ProbeReportTests(unittest.TestCase):
    def setUp(self):
        if not (ORIGINAL / "adsr_probe_4_tr_content.html").exists():
            self.skipTest("Build the independent 1/4 ADSR probe first")
        self.tmp = tempfile.TemporaryDirectory(prefix="adsr_scale_gate_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dest = self.root / "voice_4/impl/pnr"
        self.dest.mkdir(parents=True)
        for suffix in ("_tr_content.html", ".rpt.txt"):
            shutil.copyfile(ORIGINAL / ("adsr_probe_4" + suffix),
                            self.dest / ("adsr_probe_4" + suffix))

    def edit(self, suffix, before, after):
        path = self.dest / ("adsr_probe_4" + suffix)
        data = path.read_text(encoding="utf-8")
        self.assertIn(before, data)
        path.write_text(data.replace(before, after, 1), encoding="utf-8")

    def test_real_report_has_four_ram_and_dsp_loads(self):
        actual = parse(self.root, 4)
        self.assertEqual(actual["resource"]["BSRAM"], 4)
        self.assertEqual(actual["resource"]["DSP"], 20)

    def test_missing_clock_is_rejected(self):
        self.edit("_tr_content.html", "sys_clk", "missing_clk")
        with self.assertRaises(ValueError):
            parse(self.root, 4)

    def test_missing_resource_is_rejected(self):
        self.edit(".rpt.txt", "  BSRAM", "  NOTRAM")
        with self.assertRaises(ValueError):
            parse(self.root, 4)

    def test_negative_slack_is_rejected(self):
        self.edit("_tr_content.html", "<td>0.973</td>", "<td>-0.001</td>")
        with self.assertRaises(ValueError):
            parse(self.root, 4)

    def test_wrong_part_is_rejected_for_comparison(self):
        self.edit(".rpt.txt", "GW5AT-LV60PG484AC1/I0", "OTHER-PART")
        self.assertEqual(parse(self.root, 4)["part"], "OTHER-PART")


if __name__ == "__main__":
    unittest.main()
