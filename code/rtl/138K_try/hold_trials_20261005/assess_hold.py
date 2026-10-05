"""Strict 40MHz full-design gate, plus Setup >= .5ns acceptance floor."""
import json
import math
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hold_trial as trial
sys.path.insert(0, str(trial.ROOT / 'reproduction_20261005'))
import full_report_checks as checks

PAIR = 'g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/'
EXTRA_REPORTS = ''.join(f'report_timing -{kind} -from [get_regs {{{PAIR}base_s1_18_s0}}] '
                        f'-to [get_regs {{{PAIR}base_s2_18_s0}}] -max_paths 1\n' for kind in ['setup', 'hold'])
CLOCKS = {'sys_clk': (25.0, 40.0), 'video_pixel': (40.0, 25.0), 'video_serial': (8.0, 125.0)}

def accept_user(result):
    setup = result['global_worst_paths']['Setup']['slack_ns']
    return result['offline_report_gate_passed'] and math.isfinite(setup) and setup >= .5


def read(path):
    return path.read_text(encoding='utf-8')


def expected_sdc(label):
    text = read(trial.BASE / 'constraints/audio_visual_hold055.sdc')
    if label is not None:
        text += EXTRA_REPORTS
    if label in ['K_encoded_guard065', 'L_locations_guard065']:
        assert text.count('set_clock_uncertainty -hold  0.550') == 1
        text = text.replace('set_clock_uncertainty -hold  0.550', 'set_clock_uncertainty -hold  0.650')
    return text


def profile(label, timing, usage, sdc, pin_report, command, cfg):
    pnr = trial.BASE / 'impl/pnr'
    frozen = checks.FROZEN_CLOCKS
    checks.FROZEN_CLOCKS = CLOCKS
    try:
        result = checks.check(timing, usage, sdc, pin_report,
                              checks.pins(read(pnr / (trial.STEM + '.pin.html'))),
                              'GW5AST-LV138PG484AC1/I0', 'C', command, read(pnr / 'cmd.do'),
                              cfg, (pnr / 'device.cfg').read_bytes())
    finally:
        checks.FROZEN_CLOCKS = frozen
    rows = checks.parsed(timing)
    # The read-only legacy gate requires exactly .550. L deliberately tightens
    # that requirement: replace only this obsolete diagnostic, after checking
    # the actual STA active-command list, not just the source SDC text.
    guard = .650 if label in ['K_encoded_guard065', 'L_locations_guard065'] else .550
    hold_command = (f'set_clock_uncertainty -hold {guard:.3f} '
                    '-from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]')
    active_hold = [checks.normalize(r[2]) for section, r in rows
                   if section == 'SDC_Report' and len(r) == 3 and r[1] == 'Actived'
                   and r[2].startswith('set_clock_uncertainty -hold ')]
    if active_hold != [hold_command]:
        result['errors'].append('missing/duplicate/incorrect active approved Hold uncertainty')
    elif guard == .650:
        result['errors'] = [error for error in result['errors']
                            if error != 'sys Hold uncertainty 0.550 not active']
    clocks = [r for s, r in rows if s == 'Clock_Report' and len(r) >= 10 and r[0].isdigit()]
    if len(clocks) != 4 or {r[1] for r in clocks} != set(CLOCKS) | {'ref_clk'}:
        result['errors'].append('unexpected clock reference/domain set')
    for row in clocks:
        target = (20, 50) if row[1] == 'ref_clk' else CLOCKS.get(row[1])
        if target is None or (float(row[3]), float(row[4])) != target or float(row[5]) != 0 or float(row[6]) != target[0] / 2:
            result['errors'].append('incorrect physical clock frequency/phase/waveform: ' + row[1])
    actual_commands = [checks.normalize(line) for line in sdc.splitlines()
                       if line.strip() and not line.lstrip().startswith('#')]
    expected_commands = [checks.normalize(line) for line in expected_sdc(label).splitlines()
                         if line.strip() and not line.lstrip().startswith('#')]
    if actual_commands != expected_commands:
        result['errors'].append('SDC differs from exact approved H plan plus reports/explicit stricter guard')
    locations = {'u_visual/u_serial_reset/sync_chain_0_s0': 'R44C168[1][A]',
                 'u_visual/u_serial_reset/sync_chain_1_s0': 'R44C168[1][B]'}
    if label in ['I_hold_locations', 'L_locations_guard065']:
        locations.update({PAIR + 'base_s1_18_s0': 'R83C99[1][B]',
                          PAIR + 'base_s2_18_s0': 'R87C101[0][A]'})
    readback = {}
    for cell, expected in locations.items():
        actual = sorted({r[5] for _, r in rows if len(r) == 7 and r[6] in [cell + '/CLK', cell + '/Q', cell + '/D']})
        readback[cell] = {'expected': expected, 'actual': actual}
        if actual != [expected]:
            result['errors'].append('internal FF location not evidenced: ' + cell)
    result['internal_location_readback'] = readback
    hold_rows = [r for s, r in rows if s.startswith('Hold_Slack_Table') and len(r) >= 9 and r[0].isdigit()]
    result['diagnostic_original_short_path'] = [r for r in hold_rows if r[2] == PAIR + 'base_s1_18_s0/Q' and r[3] == PAIR + 'base_s2_18_s0/D']
    for section, row in rows:
        if section == 'Total_Negative_Slack_Report' and len(row) >= 4 and row[0] != 'Clock Name':
            if row[0] not in set(CLOCKS) | {'ref_clk'} or float(row[2]) != 0 or int(row[3]) != 0:
                result['errors'].append('nonzero/unknown-domain TNS/endpoints: ' + str(row))
    result['offline_report_gate_passed'] = not result['errors']
    result['user_setup_floor_ns'] = .5
    result['user_acceptance_passed'] = accept_user(result)
    result['hardware_acceptance'] = False
    return result


def collect(label):
    out = trial.folder(label)
    manifest = trial.verify_inputs(label)
    receipt = json.loads(read(out / 'build_receipt.json'))
    assert receipt['state'] == 'finished' and receipt['exit_code'] == 0
    log = out / 'build.log'
    assert trial.sha(log.read_bytes()) == receipt['build_log_SHA256']
    for marker in ['GowinSynthesis finish', 'Placement and routing completed', 'Timing analysis completed', 'Bitstream generation completed']:
        assert marker in read(log)
    pnr = out / 'impl/pnr'
    result = profile(label, read(pnr / (trial.STEM + '_tr_content.html')), read(pnr / (trial.STEM + '.rpt.txt')),
                     read(out / 'constraints/audio_visual_hold055.sdc'), read(pnr / (trial.STEM + '.pin.html')),
                     read(pnr / 'cmd.do'), (pnr / 'device.cfg').read_bytes())
    review = json.loads(read(out / 'functional/functional_review.json'))
    evidence = Path(review['actual_evidence_directory'])
    evidence.relative_to(out)
    assert review['passed'] and review == json.loads(read(evidence / 'functional_review.json'))
    for name, record in review['runs'].items():
        assert trial.sha((evidence / (name + '.log')).read_bytes()) == record['log_SHA256']
        assert (record['exit'] == 0) == record['expected_success']
    for name, digest in review['RTL_SHA256'].items():
        assert trial.sha((out / 'sources' / name).read_bytes()) == digest
    result.update({'label': label, 'receipt': receipt, 'input_changes': manifest['changes'],
                   'functional_checks': 1855, 'DVI_boundary_stub_not_TMDS_verification': True,
                   'other_repository_files_written': False, 'programmed': False,
                   'hold_uncertainty_ns': .650 if label in ['K_encoded_guard065', 'L_locations_guard065'] else .550,
                   'artifact_SHA256': {p.relative_to(out).as_posix(): trial.sha(p.read_bytes())
                                       for p in list(pnr.glob('*.html')) + [pnr / (trial.STEM + '.rpt.txt'), pnr / 'cmd.do', pnr / 'device.cfg', log]}})
    trial.write_json(out / 'assessment.json', result)
    trial.preserve()
    print(label, 'REPORT_GATE', result['offline_report_gate_passed'], 'USER_ACCEPTANCE', result['user_acceptance_passed'],
          'ERRORS', result['errors'], 'PATHS', result['global_worst_paths'],
          'RESET', result['recovery_removal_worst_paths'], 'RESOURCE', result['resources'],
          'ORIGINAL_SHORT_PATH', result['diagnostic_original_short_path'], flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        legacy = trial.imported('moved_legacy_assess_for_selftest', trial.ROOT / 'optimization_followup_20261005/assess.py')
        suite = unittest.TestLoader().loadTestsFromTestCase(legacy.FullReportTests)
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(legacy.BaselineTests))
        with (trial.HERE / 'report_selftest.log').open('w', encoding='utf-8') as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        assert result.wasSuccessful()
        print('23 strict report tests PASS')
    else:
        collect(sys.argv[1])
