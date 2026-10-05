"""Portable negative-report tests for the isolated T034 output-path checker."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_t034_output_paths import verify_paths  # noqa: E402

PORTS = ("i2s_bclk", "i2s_lrck", "i2s_din")


def fixture():
    clock = 'create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]'
    commands = [f'report_timing -{kind} -to [get_ports {{{port}}}] -max_paths 1'
                for port in PORTS for kind in ("setup", "hold")]
    sdc = clock + "\n" + "\n".join(commands)
    prefix = '<a name="STA_Tool_Run_Summary"></a>'
    for name in ("Numbers of Setup Violated Endpoints", "Numbers of Hold Violated Endpoints"):
        prefix += f'<tr><td>{name}</td><td>0</td></tr>'
    prefix += ('<a name="Clock_Report"></a><tr><td>1</td><td>sys_clk</td>'
               '<td>Base</td><td>20.000</td><td>50.000</td></tr>'
               '<a name="SDC_Report"></a>')
    for command in (clock, *commands):
        prefix += f'<tr><td>TC</td><td>Actived</td><td>{command}</td></tr>'
    for kind in ("setup", "hold"):
        for number, port in enumerate(PORTS, start=1):
            prefix += (f'<a name="{kind.capitalize()}_Slack_Table{number}"></a>'
                       f'<tr><td>1</td><td>4.663</td><td>u_i2s_tx/sample_q/Q</td>'
                       f'<td>{port}_obuf/O</td></tr>')
    for kind in ("Recovery", "Removal"):
        prefix += (f'<a name="{kind}_Slack_Table"></a>'
                   f'<tr><td>1</td><td>0.100</td><td>reset/Q</td><td>stage/CLEAR</td></tr>')
    pins = '7. Pinout by Port Name\n'
    cst = ''
    for port, ball in zip(PORTS, ('Y17', 'AB17', 'AA16')):
        pins += (f'{port} | - | {ball}/7 | Y | out | site | cfg | LVCMOS33 | 8 | NONE |'
                 ' OFF | OFF | OFF | SLOW | OFF | OFF | OFF | 3.3 | MEDIUM\n')
        cst += (f'IO_LOC "{port}" {ball};\n'
                f'IO_PORT "{port}" IO_TYPE=LVCMOS33 PULL_MODE=NONE BANK_VCCIO=3.3;\n')
    pins += '8. All Package Pins\n'
    return prefix, pins, commands, sdc, cst


class OutputPathReportTests(unittest.TestCase):
    def setUp(self):
        self.timing, self.pins, self.commands, self.sdc, self.cst = fixture()

    def test_six_paths(self):
        result = verify_paths(self.timing, self.pins, self.commands, self.sdc, self.cst)
        self.assertEqual(set(result), set(PORTS))
        self.assertEqual(result["i2s_bclk"]["setup"]["to"], "i2s_bclk_obuf/O")

    def test_missing_physical_output_path(self):
        mutant = self.timing.replace("i2s_bclk_obuf/O</td>", "wrong_obuf/O</td>")
        with self.assertRaisesRegex(ValueError, "Missing or ambiguous output path"):
            verify_paths(mutant, self.pins, self.commands, self.sdc, self.cst)

    def test_negative_output_slack(self):
        mutant = self.timing.replace("<td>4.663</td>", "<td>-0.100</td>", 1)
        with self.assertRaisesRegex(ValueError, "Negative i2s_bclk setup"):
            verify_paths(mutant, self.pins, self.commands, self.sdc, self.cst)

    def test_inactive_or_removed_constraint(self):
        mutant = self.timing.replace('<td>Actived</td>', '<td>Inactive</td>', 1)
        with self.assertRaisesRegex(ValueError, "SDC mismatch"):
            verify_paths(mutant, self.pins, self.commands, self.sdc, self.cst)

    def test_negative_recovery_rejected(self):
        mutant = self.timing.replace(
            '<a name="Recovery_Slack_Table"></a><tr><td>1</td><td>0.100</td>',
            '<a name="Recovery_Slack_Table"></a><tr><td>1</td><td>-0.100</td>')
        with self.assertRaisesRegex(ValueError, "negative Recovery slack"):
            verify_paths(mutant, self.pins, self.commands, self.sdc, self.cst)

    def test_pin_cst_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "Probe pinout differs from formal CST"):
            verify_paths(self.timing, self.pins, self.commands, self.sdc,
                         self.cst.replace('Y17', 'R17'))

    def test_missing_report_command(self):
        mutant = self.timing.replace(
            '<td>report_timing -hold -to [get_ports {i2s_din}] -max_paths 1</td>',
            '<td>report_timing -hold -to [get_ports {i2s_fake}] -max_paths 1</td>')
        with self.assertRaisesRegex(ValueError, "SDC mismatch"):
            verify_paths(mutant, self.pins, self.commands, self.sdc, self.cst)


if __name__ == "__main__":
    unittest.main()
