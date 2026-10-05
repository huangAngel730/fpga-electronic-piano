"""Synthetic corruption tests; fixtures are not physical timing evidence."""
import copy
from html import escape
import unittest
from collect_sta_results import analyze, FROZEN_CLOCKS

SDC = '\n'.join([
    'create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]',
    'set_clock_uncertainty -hold 0.550 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]',
    'set_false_path -from [get_ports {sys_rst_n}]',
])
USAGE = '''<Tool Version>: V1.9.11.03 Education
<Part Number>: GW5AT-LV60PG484AC1/I0
<Device>: GW5AT-60
<Device Version>: B
<Created Time>: synthetic fixture, NOT actual build
 Logic | 19534/59904
 Register | 8674/60780
 DSP | 46/118
 BSRAM | 20/118
'''


def fixture():
    rows = {
        'STA_Tool_Run_Summary': [[k, v] for k, v in [
            ('Numbers of Paths Analyzed', '100'), ('Numbers of Endpoints Analyzed', '50'),
            ('Numbers of Setup Violated Endpoints', '0'), ('Numbers of Hold Violated Endpoints', '0')]],
        'Clock_Report': [[str(i), c, 'Base', f'{p:.3f}', f'{f:.3f}']
                         for i, (c, (p, f)) in enumerate(FROZEN_CLOCKS.items(), 1)],
        'Max_Frequency_Report': [[str(i), c, f'{f:.3f}(MHz)', f'{f + 5:.3f}(MHz)']
                                 for i, (c, (p, f)) in enumerate(FROZEN_CLOCKS.items(), 1)],
        'Total_Negative_Slack_Report': [[c, k, '0.000', '0'] for c in FROZEN_CLOCKS for k in ['Setup', 'Hold']],
        'SDC_Report': [['TYPE', 'Actived', line] for line in SDC.splitlines()],
    }
    for kind in ['Setup', 'Hold', 'Recovery', 'Removal']:
        rows[kind + '_Slack_Table'] = [[str(i), '0.100', 'source/Q', 'sink/D', c + ':[R]', c + ':[R]']
                                       for i, c in enumerate(FROZEN_CLOCKS, 1)]
    return rows


def html(rows, implicit=False):
    end = '' if implicit else '</td>'
    return ''.join('<a name="' + section + '"></a><table>' + ''.join(
        '<tr>' + ''.join('<td>' + escape(cell) + end for cell in row) + '</tr>' for row in records
    ) + '</table>' for section, records in rows.items())


class CollectorTests(unittest.TestCase):
    def evaluate(self, rows=None, usage=USAGE, implicit=False):
        return analyze(html(rows or fixture(), implicit), usage, FROZEN_CLOCKS, True, SDC)

    def assert_rejected(self, rows, fragment, usage=USAGE):
        self.assertTrue(any(fragment in error for error in self.evaluate(rows, usage)['errors']))

    def test_positive(self):
        self.assertEqual(self.evaluate()['errors'], [])

    def test_implicit_cell_closing(self):
        self.assertEqual(self.evaluate(implicit=True)['errors'], [])

    def test_negative_hold_even_with_zero_tns(self):
        rows = fixture(); rows['Hold_Slack_Table'][0][1] = '-0.001'
        self.assert_rejected(rows, 'negative')

    def test_negative_cross_clock_path(self):
        rows = fixture(); rows['Setup_Slack_Table'].append(['99', '-1.000', 'a/Q', 'b/D', 'sys_clk:[R]', 'video_pixel:[R]'])
        self.assert_rejected(rows, 'negative global/cross-clock')

    def test_nonfinite_slack(self):
        rows = fixture(); rows['Hold_Slack_Table'][0][1] = 'nan'
        self.assert_rejected(rows, 'invalid global')

    def test_missing_recovery(self):
        rows = fixture(); del rows['Recovery_Slack_Table']
        self.assert_rejected(rows, 'missing asynchronous')

    def test_negative_removal(self):
        rows = fixture(); rows['Removal_Slack_Table'][0][1] = '-0.020'
        self.assert_rejected(rows, 'negative Removal')

    def test_missing_clock(self):
        rows = fixture(); rows['Clock_Report'].pop()
        self.assert_rejected(rows, 'missing/duplicate clock')

    def test_duplicate_clock(self):
        rows = fixture(); rows['Clock_Report'].append(copy.deepcopy(rows['Clock_Report'][0]))
        self.assert_rejected(rows, 'missing/duplicate clock')

    def test_wrong_period(self):
        rows = fixture(); rows['Clock_Report'][0][3] = '25.000'
        self.assert_rejected(rows, 'clock period')

    def test_low_fmax(self):
        rows = fixture(); rows['Max_Frequency_Report'][0][3] = '49.000(MHz)'
        self.assert_rejected(rows, 'Fmax below')

    def test_nonzero_tns(self):
        rows = fixture(); rows['Total_Negative_Slack_Report'][0][2] = '-0.001'
        self.assert_rejected(rows, 'nonzero TNS')

    def test_missing_tns(self):
        rows = fixture(); rows['Total_Negative_Slack_Report'].pop()
        self.assert_rejected(rows, 'missing/invalid TNS')

    def test_old_hold_uncertainty(self):
        rows = fixture(); rows['SDC_Report'][1][2] = rows['SDC_Report'][1][2].replace('0.550', '0.500')
        self.assert_rejected(rows, '0.550 not active')

    def test_inactive_constraint(self):
        rows = fixture(); rows['SDC_Report'][0][1] = 'Invalid'
        self.assert_rejected(rows, 'missing/inactive')

    def test_unexpected_broad_cut(self):
        rows = fixture(); rows['SDC_Report'].append(['TYPE', 'Actived', 'set_clock_groups -asynchronous -group A -group B'])
        self.assert_rejected(rows, 'unexpected timing exception')

    def test_empty_analyzed_paths(self):
        rows = fixture(); rows['STA_Tool_Run_Summary'][0][1] = '0'
        self.assert_rejected(rows, 'missing/empty analyzed')

    def test_missing_resources(self):
        self.assert_rejected(fixture(), 'missing/duplicate resource: BSRAM', USAGE.replace(' BSRAM | 20/118', ''))

    def test_missing_metadata(self):
        self.assert_rejected(fixture(), 'missing tool/target metadata', '')

    def test_probe_missing_async_is_not_full_pass(self):
        rows = fixture(); del rows['Recovery_Slack_Table']; del rows['Removal_Slack_Table']
        self.assertTrue(self.evaluate(rows)['errors'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
