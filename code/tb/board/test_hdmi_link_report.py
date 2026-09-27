"""Regression tests for fail-closed Gowin HDMI timing report validation."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_hdmi_link_report import analyze, analyze_pins


def fixture(setup_count="0", recovery="0.4"):
    def section(name, rows):
        return ('<a name="' + name + '"></a><table>' + ''.join(
            '<tr>' + ''.join('<td>' + str(c) for c in row) + '</tr>'
            for row in rows) + '</table>')
    # Missing td closing tags deliberately matches Gowin's Clock Report HTML.
    text = section("STA_Tool_Run_Summary", [
        ["Numbers of Setup Violated Endpoints", setup_count],
        ["Numbers of Hold Violated Endpoints", "0"],
        ["Numbers of Paths Analyzed", "520"],
        ["Numbers of Endpoints Analyzed", "380"]])
    text += section("Clock_Report", [
        [1, "sys_clk", "Base", "20.000", "50.000"],
        [2, "video_serial", "Generated", "8.000", "125.000"],
        [3, "video_pixel", "Generated", "40.000", "25.000"]])
    for kind in ("Setup", "Hold", "Recovery", "Removal"):
        text += section(kind + "_Slack_Table", [
            [1, recovery if kind == "Recovery" else "0.5", "source/Q", "sink/D"]])
    return text


class TimingReportTests(unittest.TestCase):
    def test_valid_report_with_implicit_cell_end(self):
        self.assertEqual(analyze(fixture())["errors"], [])

    def test_global_count_cannot_be_hidden_by_zero_tns(self):
        result = analyze(fixture(setup_count="4"))
        self.assertTrue(any("Violated Endpoints: 4" in e for e in result["errors"]))

    def test_recovery_failure_is_not_ignored(self):
        self.assertTrue(any("Recovery" in e for e in analyze(fixture(recovery="-0.152"))["errors"]))

    def test_missing_removal_is_failure(self):
        text = fixture().replace('name="Removal_Slack_Table"', 'name="missing"')
        self.assertTrue(any("Missing path" in e for e in analyze(text)["errors"]))

    def test_wrong_clock_is_failure(self):
        self.assertTrue(analyze(fixture().replace("125.000", "200.000"))["errors"])

    def test_empty_report_is_failure(self):
        self.assertTrue(analyze("")["errors"])


class PinoutReportTests(unittest.TestCase):
    def setUp(self):
        self.prefix = "7. Pinout by Port Name\n"
        self.suffix = "\n8. All Package Pins"
        self.rows = [
            ["sys_clk", "-", "V22/7", "Y", "in", "", "", "LVCMOS33", "", "NONE"],
            ["sys_rst_n", "-", "AA13/9", "Y", "in", "", "", "LVCMOS15", "", "UP"],
            ["tmds_clk_p", "tmds_clk_n", "G15,G16/4", "Y", "out", "", "", "LVDS25", "", "NONE"],
            ["tmds_data_p[0]", "tmds_data_n[0]", "J14,H14/4", "Y", "out", "", "", "LVDS25", "", "NONE"],
            ["tmds_data_p[1]", "tmds_data_n[1]", "J15,H15/4", "Y", "out", "", "", "LVDS25", "", "NONE"],
            ["tmds_data_p[2]", "tmds_data_n[2]", "K17,J17/5", "Y", "out", "", "", "LVDS25", "", "NONE"],
            ["pa_en", "-", "AB16/7", "Y", "out", "", "", "LVCMOS33", "", "NONE"],
        ]
        for row in self.rows:
            row.extend(["0"] * 7)
            row.append("1.5" if row[0] == "sys_rst_n" else "3.3")

    def rendered(self):
        return self.prefix + "\n".join("|".join(r) for r in self.rows) + self.suffix

    def test_real_pin_table_geometry(self):
        pins, errors = analyze_pins(self.rendered())
        self.assertFalse(errors)
        self.assertEqual(len(pins), 7)

    def test_wrong_ball_fails(self):
        self.rows[2][2] = "G15,G17/4"
        self.assertTrue(analyze_pins(self.rendered())[1])

    def test_wrong_voltage_fails(self):
        self.rows[0][17] = "1.5"
        self.assertTrue(analyze_pins(self.rendered())[1])

    def test_missing_pin_fails(self):
        self.rows.pop(0)
        self.assertTrue(analyze_pins(self.rendered())[1])

if __name__ == "__main__":
    unittest.main()
