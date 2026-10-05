"""Self-check extensions using explicitly corrupted copies, not fabricated EDA evidence."""
from pathlib import Path
import re
import unittest

from full_report_checks import check, extensions, normalized_options, pins, expected_138k_electrical_pins

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / 'M2_DVI_V0171_originals_20261005/originals/V0171'
PNR = ORIGINAL / 'impl/pnr'
STEM = 'audio_visual_coexistence_top'


class FullReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timing = (PNR / (STEM + '_tr_content.html')).read_text(encoding='utf-8')
        cls.usage = (PNR / (STEM + '.rpt.txt')).read_text(encoding='utf-8')
        cls.pin_report = (PNR / (STEM + '.pin.html')).read_text(encoding='utf-8')
        cls.expected_pins = pins(cls.pin_report)
        cls.sdc = (ORIGINAL / 'constraints/audio_visual_hold055.sdc').read_text(encoding='utf-8')
        cls.command = (PNR / 'cmd.do').read_text(encoding='utf-8')
        cls.device_cfg = (PNR / 'device.cfg').read_bytes()

    def run_check(self, **changes):
        arguments = dict(timing=self.timing, usage=self.usage, sdc=self.sdc,
                         pin_report=self.pin_report, expected_pins=self.expected_pins,
                         expected_pn='GW5AT-LV60PG484AC1/I0', expected_version='B',
                         command=self.command, original_command=self.command,
                         device_cfg=self.device_cfg, original_device_cfg=self.device_cfg)
        arguments.update(changes)
        return check(**arguments)

    def test_original_pass_is_not_hardware_or_margin_acceptance(self):
        result = self.run_check()
        self.assertEqual(result['errors'], [])
        self.assertTrue(result['offline_report_gate_passed'])
        self.assertFalse(result['hardware_acceptance'])
        self.assertFalse(result['engineering_margin_0p5ns_passed'])
        self.assertEqual(result['min_pulse_width_slack_ns'], 2.327)
        self.assertEqual(len(result['CDC_second_stage_slacks']), 14)

    def test_negative_pulse_rejected(self):
        self.assertIn('<td>2.327</td>', self.timing)
        result = self.run_check(timing=self.timing.replace('<td>2.327</td>', '<td>-0.001</td>'))
        self.assertIn('missing/nonfinite/negative minimum pulse width evidence', result['errors'])

    def test_nonfinite_pulse_rejected(self):
        result = self.run_check(timing=self.timing.replace('<td>2.327</td>', '<td>NaN</td>'))
        self.assertIn('missing/nonfinite/negative minimum pulse width evidence', result['errors'])

    def test_missing_pulse_section_rejected(self):
        self.assertIn('name="MIN_PULSE_WIDTH_TABLE"', self.timing)
        text = self.timing.replace('name="MIN_PULSE_WIDTH_TABLE"', 'name="MISSING_PULSE"')
        self.assertIn('missing/nonfinite/negative minimum pulse width evidence', self.run_check(timing=text)['errors'])

    def test_nan_recovery_rejected(self):
        self.assertIn('<td>1.113</td>', self.timing)
        text = self.timing.replace('<td>1.113</td>', '<td>NaN</td>')
        self.assertIn('missing/nonfinite/negative Recovery', self.run_check(timing=text)['errors'])

    def test_cdc_second_stage_wrong_endpoint_rejected(self):
        old = 'u_visual/u_event_bridge/ack_sync_s0/D'
        self.assertIn(old, self.timing)
        result = self.run_check(timing=self.timing.replace(old, old + '_wrong'))
        self.assertTrue(any('CDC second stage' in error for error in result['errors']))

    def test_cdc_payload_table_missing_rejected(self):
        old = 'name="Setup_Slack_Table1"'
        self.assertIn(old, self.timing)
        result = self.run_check(timing=self.timing.replace(old, 'name="MISSING_PAYLOAD_TABLE"'))
        self.assertTrue(any('CDC payload' in error for error in result['errors']))

    def test_changed_pin_bank_rejected(self):
        self.assertIn('AA13/9', self.pin_report)
        result = self.run_check(pin_report=self.pin_report.replace('AA13/9', 'AA13/5'))
        self.assertIn('pin electrical/location mismatch: sys_rst_n', result['errors'])

    def test_changed_pnr_hold_correction_rejected(self):
        result = self.run_check(command=self.command.replace('-correct_hold 1', '-correct_hold 0'))
        self.assertIn('non-path PnR options changed', result['errors'])

    def test_option_path_changes_allowed(self):
        self.assertEqual(normalized_options(self.command), normalized_options(
            self.command.replace('D:\\17\\project_17', 'E:\\isolated')))

    def test_changed_device_options_rejected(self):
        result = self.run_check(device_cfg=self.device_cfg.replace(b'set compress = false', b'set compress = true'))
        self.assertIn('device programming/options configuration changed', result['errors'])

    def test_changed_resource_footprint_rejected(self):
        usage, count = re.subn(r'(BSRAM\s*\|\s*)20/', r'\g<1>21/', self.usage)
        self.assertEqual(count, 1)
        self.assertIn('frozen DSP/BSRAM footprint changed', self.run_check(usage=usage)['errors'])

    def test_wrong_target_rejected(self):
        self.assertIn('target part/version mismatch', self.run_check(expected_version='C')['errors'])

    def test_disabled_architecture_extra_recorded(self):
        result = self.run_check(command=self.command + '-enable_dsrm 0\n',
                                allowed_extra_options=('-enable_dsrm 0',))
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['PnR_option_differences']['added'], ['-enable_dsrm 0'])

    def test_enabled_architecture_extra_rejected(self):
        result = self.run_check(command=self.command + '-enable_dsrm 1\n',
                                allowed_extra_options=('-enable_dsrm 0',))
        self.assertIn('non-path PnR options changed', result['errors'])

    def test_unreviewed_port_has_no_guessed_bank(self):
        with self.assertRaises(ValueError):
            expected_138k_electrical_pins({**self.expected_pins, 'extra_port': self.expected_pins['sys_clk']})

    def test_138k_profile_keeps_balls_and_only_three_input_standards_change(self):
        profile = expected_138k_electrical_pins(self.expected_pins)
        changed_io = []
        for port, row in profile.items():
            self.assertEqual(row['Loc./Bank'].split('/')[0], self.expected_pins[port]['Loc./Bank'].split('/')[0])
            if row['IO Type'] != self.expected_pins[port]['IO Type']:
                changed_io.append(port)
        self.assertEqual(set(changed_io), {'sys_rst_n', 'key_n[0]', 'key_n[1]'})

    def test_138k_actual_pin_headers_without_slew_rate(self):
        path = HERE / '138K_B_electrical_migration/impl/pnr' / (STEM + '.pin.html')
        # Parser-only fixture combining original timing and actual 138K pin
        # schema; NOT a design timing/acceptance result.
        report = path.read_text(encoding='utf-8')
        actual = pins(report)
        self.assertNotIn('Slew Rate', actual['sys_clk'])
        result = extensions(self.timing, report, expected_138k_electrical_pins(self.expected_pins))
        self.assertEqual(result['errors'], [])

    def test_missing_required_pin_column_rejected(self):
        report = self.pin_report.replace('BankVccio', 'MISSING_BANK_VOLTAGE')
        self.assertTrue(any('malformed pin report' in error for error in self.run_check(pin_report=report)['errors']))

    def test_vccx_architecture_adaptation_is_explicit(self):
        result = self.run_check(device_cfg=self.device_cfg.replace(b'set vccx = 3.3', b'set vccx = 1.8'),
                                allowed_device_cfg_changes=((b'set vccx = 3.3', b'set vccx = 1.8'),))
        self.assertEqual(result['errors'], [])
        self.assertFalse(result['device_cfg_matches_original'])
        self.assertTrue(result['device_cfg_matches_allowed_profile'])

    def test_vccx_allowance_cannot_hide_other_configuration_change(self):
        changed = self.device_cfg.replace(b'set vccx = 3.3', b'set vccx = 1.8').replace(
            b'set compress = false', b'set compress = true')
        result = self.run_check(device_cfg=changed,
                                allowed_device_cfg_changes=((b'set vccx = 3.3', b'set vccx = 1.8'),))
        self.assertIn('device programming/options configuration changed', result['errors'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
