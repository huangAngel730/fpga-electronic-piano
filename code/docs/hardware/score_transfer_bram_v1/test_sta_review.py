"""Small synthetic negative tests of the new report gate, no tool execution."""
import copy
import unittest

from sta_review import timing_facts, virtual_port_coverage


def fixture():
    return [
        ('STA_Tool_Run_Summary', ['Numbers of Setup Violated Endpoints', '0']),
        ('STA_Tool_Run_Summary', ['Numbers of Hold Violated Endpoints', '0']),
        ('STA_Tool_Run_Summary', ['Numbers of Paths Analyzed', '100']),
        ('STA_Tool_Run_Summary', ['Numbers of Endpoints Analyzed', '10']),
        ('Clock_Report', ['1', 'sys_clk', 'Base', '25.000', '40.000']),
        ('Setup_Slack_Table', ['1', '1.2', 'q/Q', 'd/D']),
        ('Hold_Slack_Table', ['1', '0.1', 'q/Q', 'd/D']),
        ('Total_Negative_Slack_Report', ['sys_clk', 'Setup', '0', '0']),
        ('Total_Negative_Slack_Report', ['sys_clk', 'Hold', '0', '0']),
        ('MIN_PULSE_WIDTH_TABLE', ['1', '1.0', '', '', '', '', '']),
    ]


class GateTests(unittest.TestCase):
    def test_positive_schema(self):
        self.assertEqual(timing_facts(fixture())['errors'], [])

    def test_negative_and_nonfinite_slacks(self):
        for kind in ('Setup', 'Hold', 'Recovery', 'Removal'):
            for value in ('-0.001', 'nan', 'inf'):
                rows = copy.deepcopy(fixture())
                rows.append((kind+'_Slack_Table', ['2', value, 'q/Q', 'd/D']))
                self.assertIn('NEGATIVE_OR_NONFINITE:'+kind,
                              timing_facts(rows)['errors'])

    def test_global_violation(self):
        rows = fixture()
        rows[0][1][1] = '1'
        self.assertTrue(timing_facts(rows)['errors'])

    def test_tns_violation(self):
        rows = fixture()
        rows[7][1][2] = '-1.0'
        self.assertIn('NONZERO_TNS_OR_ENDPOINTS', timing_facts(rows)['errors'])

    def test_missing_analysis(self):
        self.assertTrue(timing_facts(fixture()[1:])['errors'])

    def test_frequency_lowered(self):
        rows = fixture()
        rows[4][1][3:] = ['30.000', '33.333']
        self.assertIn('CLOCK_CONTRACT', timing_facts(rows)['errors'])

    def test_false_path(self):
        rows = fixture()+[('SDC_Report', ['1', 'Actived', 'set_false_path -from [all_inputs]'])]
        self.assertIn('UNAUTHORIZED_EXCEPTION', timing_facts(rows)['errors'])

    def test_unconstrained_path(self):
        rows = fixture()+[('Unconstrained_Paths_Report', ['1', 'a', 'b'])]
        self.assertIn('UNCONSTRAINED_PATH_ROW', timing_facts(rows)['errors'])

    def test_engineering_margin(self):
        for slack, passed in (('0.499', False), ('0.500', True), ('1.000', True)):
            rows = fixture()
            rows[5][1][1] = slack
            self.assertEqual('SETUP_ENGINEERING_MARGIN' not in
                             timing_facts(rows, minimum_setup=0.5)['errors'], passed)

    def test_virtual_pin_coverage_rejects_absent_or_wrong_direction(self):
        for rows in ([], [('Pinout_by_Port_Name', ['clk','-','X','N','out'])]):
            self.assertIn('clk', virtual_port_coverage(rows)['missing_or_wrong'])
        self.assertEqual(virtual_port_coverage([])['expected_ports'], 131)

    def test_virtual_pin_coverage_rejects_unexpected_port(self):
        rows=[('Pinout_by_Port_Name', ['surprise','-','X','N','in'])]
        self.assertEqual(virtual_port_coverage(rows)['unexpected'], ['surprise'])


if __name__ == '__main__':
    unittest.main()
