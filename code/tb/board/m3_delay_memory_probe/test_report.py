"""I report validator synthetic negative fixtures, not synthesis evidence."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "code/scripts"))
spec = importlib.util.spec_from_file_location("i_probe", ROOT / "code/scripts/run_m3_delay_memory_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

HTML = """<h1><a name="about">Synthesis</a></h1><table>
<tr><td>Part Number</td><td>GW5AT-LV60PG484AC1/I0</td></tr>
<tr><td>Device Version</td><td>B</td></tr><tr><td>Tool Version</td><td>test only</td></tr></table>
<h2><a name="usage">Usage</a></h2><table>
<tr><td>DSP</td><td></td></tr><tr><td>MULTALU27X18</td><td>3</td></tr>
<tr><td>RAM16SDP1</td><td>64</td></tr></table>
<h2><a name="utilization">Utilization</a></h2><table>
<tr><td>Logic</td><td>740(287 LUT, 69 ALU, 64 RAM16) / 59904</td></tr>
<tr><td>Register</td><td>103 / 60780</td></tr><tr><td>BSRAM</td><td>2 / 118</td></tr></table>
<h2><a name="clock">Clock</a></h2><table><tr><td>1</td><td>sys_clk</td><td>Base</td>
<td>20.000</td><td>50.000</td></tr></table>"""


class ReportTests(unittest.TestCase):
    def review(self, text):
        with tempfile.TemporaryDirectory(prefix="i_report_") as folder:
            path = Path(folder) / "report.html"
            path.write_text(text, encoding="utf-8")
            return probe.review_report(path)

    def test_positive_and_unknown(self):
        result = self.review(HTML)
        self.assertTrue(result["contract_passed"])
        self.assertEqual(result["resources"]["Logic"]["used"], 740)
        self.assertEqual(result["resources"]["DSP"], "unknown")
        self.assertEqual(result["dsp_primitive_units"], 3)
        self.assertEqual(result["resources"]["RAM16"]["used"], 64)

    def test_clock10_rejected(self):
        self.assertFalse(self.review(HTML.replace("20.000", "10.000").replace("50.000", "100.000"))["contract_passed"])

    def test_missing_clock(self):
        self.assertFalse(self.review(HTML.replace("sys_clk", "other_clk"))["contract_passed"])

    def test_wrong_part(self):
        self.assertFalse(self.review(HTML.replace("GW5AT-LV60PG484AC1/I0", "wrong"))["contract_passed"])

    def test_wrong_revision(self):
        self.assertFalse(self.review(HTML.replace("<td>B</td>", "<td>A</td>"))["contract_passed"])

    def test_missing_bram(self):
        self.assertFalse(self.review(HTML.replace("<td>BSRAM</td>", "<td>other</td>"))["contract_passed"])

    def test_over_capacity(self):
        self.assertFalse(self.review(HTML.replace("740(", "60000("))["contract_passed"])

    def test_malformed_number(self):
        with self.assertRaises(ValueError):
            self.review(HTML.replace("740(", "X("))

    def test_duplicate_resource(self):
        with self.assertRaises(ValueError):
            self.review(HTML.replace("<tr><td>Register</td>", "<tr><td>Logic</td><td>1 / 2</td></tr><tr><td>Register</td>"))

    def test_missing_ram_stays_unknown(self):
        self.assertEqual(self.review(HTML.replace("RAM16SDP1", "absent"))["resources"]["RAM16"], "unknown")

    def test_native_correction_tool_required(self):
        probe.validate_correction_tool(Path("GowinSynthesis.exe"))
        for tool in (None, Path("gw_sh.exe")):
            with self.assertRaises(ValueError):
                probe.validate_correction_tool(tool)

    def test_failed_first_depth_stops(self):
        for status in ("contract_report_failed", "synthesis_failed", "missing_report_failed"):
            self.assertTrue(probe.stop_after_case(dict(synthesis_executed=True, status=status)))
        self.assertFalse(probe.stop_after_case(dict(synthesis_executed=True, status="synthesis_completed")))
        self.assertFalse(probe.stop_after_case(dict(synthesis_executed=False, status="prepared_not_run")))


if __name__ == "__main__":
    unittest.main()
