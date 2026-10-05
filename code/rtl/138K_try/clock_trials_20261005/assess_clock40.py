"""Strict new-clock-profile STA gate; no report editing or hidden false paths."""
import json
from pathlib import Path
import re
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clock_trial as trial

checks = trial.imported('independent_clock40_report_checks', trial.ROOT / 'reproduction_20261005/full_report_checks.py')
checks.FROZEN_CLOCKS = {'sys_clk': (25.0, 40.0), 'video_pixel': (40.0, 25.0), 'video_serial': (8.0, 125.0)}
legacy = trial.imported('independent_clock40_legacy_assess', trial.ROOT / 'optimization_followup_20261005/assess.py')
EXPECTED_ROUTE = 1


def read(path):
    return path.read_text(encoding='utf-8')


def profile(timing, usage, sdc, pin_report, command, cfg):
    base_pnr = trial.BASE / 'impl/pnr'
    expected_command = read(base_pnr / 'cmd.do')
    assert EXPECTED_ROUTE in (1, 2)
    if EXPECTED_ROUTE == 2:
        assert expected_command.count('-route_option 1') == 1
        expected_command = expected_command.replace('-route_option 1', '-route_option 2')
    result = checks.check(timing, usage, sdc, pin_report,
                          checks.pins(read(base_pnr / (trial.STEM + '.pin.html'))),
                          'GW5AST-LV138PG484AC1/I0', 'C', command, expected_command,
                          cfg, (base_pnr / 'device.cfg').read_bytes())
    result['explicit_physical_route_option'] = EXPECTED_ROUTE
    rows = checks.parsed(timing)
    clocks = [row for section, row in rows if section == 'Clock_Report' and len(row) >= 5 and row[0].isdigit()]
    refs = [row for row in clocks if row[1] == 'ref_clk']
    if len(refs) != 1 or float(refs[0][3]) != 20 or float(refs[0][4]) != 50:
        result['errors'].append('physical 50MHz oscillator reference missing/mismatched')
    if len(clocks) != 4 or {row[1] for row in clocks} != set(checks.FROZEN_CLOCKS) | {'ref_clk'}:
        result['errors'].append('unexpected/missing actual clock net/domain')
    result['reference_clock'] = refs[0] if refs else None
    for row in clocks:
        if len(row) < 10 or float(row[5]) != 0 or float(row[6]) != float(row[3]) / 2:
            result['errors'].append('PLL/reference static waveform differs from approved plan: ' + row[1])
    # Preserve exact seven CDC cuts,10ns payload bound,1ns/.55ns uncertainties,
    # output delays and timing reports. Only actual-clock declarations change.
    original = read(trial.BASE / 'constraints/audio_visual_hold055.sdc')
    commands = lambda text: {checks.normalize(line) for line in text.splitlines()
                             if line.strip() and not line.lstrip().startswith('#') and
                             not line.startswith(('create_clock ', 'create_generated_clock '))}
    if commands(sdc) != commands(original):
        result['errors'].append('non-clock SDC changed from +.039 baseline')
    expected_clock_lines = {
        'create_clock -name ref_clk -period 20.000 [get_ports {sys_clk}]',
        'create_generated_clock -name sys_clk -source [get_ports {sys_clk}] -master_clock ref_clk -multiply_by 4 -divide_by 5 [get_pins {u_visual/u_video_pll/PLLA_inst/CLKOUT2}]',
        'create_generated_clock -name video_pixel -source [get_ports {sys_clk}] -master_clock ref_clk -multiply_by 1 -divide_by 2 [get_pins {u_visual/u_video_pll/PLLA_inst/CLKOUT1}]',
        'create_generated_clock -name video_serial -source [get_ports {sys_clk}] -master_clock ref_clk -multiply_by 5 -divide_by 2 [get_pins {u_visual/u_video_pll/PLLA_inst/CLKOUT0}]'}
    actual_lines = {checks.normalize(line) for line in sdc.splitlines() if line.startswith(('create_clock ', 'create_generated_clock '))}
    if actual_lines != expected_clock_lines:
        result['errors'].append('SDC not exact approved physical PLL clock plan')
    for index, suffix in [(0, 'A'), (1, 'B')]:
        cell = f'u_visual/u_serial_reset/sync_chain_{index}_s0'
        observed = {row[5] for _, row in rows if len(row) == 7 and row[6] in [cell + '/CLK', cell + '/Q']}
        if observed != {f'R44C168[1][{suffix}]'}:
            result['errors'].append('fixed serial reset location changed: ' + cell)
    # Any extra TNS domain must be accounted for, including empty ref_clk rows.
    tns_headers = [row for section, row in rows if section == 'Total_Negative_Slack_Report'
                   and row and row[0] == 'Clock Name']
    if tns_headers != [['Clock Name', 'Analysis Type', 'Endpoints TNS', 'Number of Endpoints']]:
        result['errors'].append('missing/duplicate/unrecognized TNS table header')
    for section, row in rows:
        if section == 'Total_Negative_Slack_Report' and len(row) >= 4:
            if row[0] == 'Clock Name':
                continue
            if row[0] not in set(checks.FROZEN_CLOCKS) | {'ref_clk'}:
                result['errors'].append('unreviewed TNS clock: ' + str(row))
            elif float(row[2]) != 0 or int(row[3]) != 0:
                result['errors'].append('any-domain nonzero TNS/endpoints: ' + str(row))
    result['offline_report_gate_passed'] = not result['errors']
    result['engineering_setup_margin_0p5ns_passed'] = result['offline_report_gate_passed'] and result['global_worst_paths']['Setup']['slack_ns'] >= .5
    result['hardware_acceptance'] = False
    return result


def collect():
    folder = trial.OUT
    pnr = folder / 'impl/pnr'
    receipt = json.loads(read(folder / 'build_receipt.json'))
    assert receipt['state'] == 'finished' and receipt['exit_code'] == 0, 'No successful full tool completion'
    timing = read(pnr / (trial.STEM + '_tr_content.html'))
    usage = read(pnr / (trial.STEM + '.rpt.txt'))
    sdc = read(folder / 'constraints/audio_visual_hold055.sdc')
    pin_report = read(pnr / (trial.STEM + '.pin.html'))
    command = read(pnr / 'cmd.do')
    cfg = (pnr / 'device.cfg').read_bytes()
    result = profile(timing, usage, sdc, pin_report, command, cfg)
    manifest = json.loads(read(folder / 'input_manifest.json'))
    changed = []
    for record in manifest['inputs']:
        original = (trial.BASE / record['path']).read_bytes()
        actual = (folder / record['path']).read_bytes()
        assert record['baseline_SHA256'] == trial.sha(original)
        assert record['candidate_SHA256'] == trial.sha(actual)
        if actual.replace(folder.as_posix().encode(), trial.BASE.as_posix().encode()) != original:
            changed.append(record['path'])
    assert len(manifest['inputs']) == 56 and set(changed) == trial.ALLOWED
    assert (folder / 'constraints/audio_visual.cst').read_bytes() == (trial.BASE / 'constraints/audio_visual.cst').read_bytes()
    normalized_tcl = (folder / 'run.tcl').read_bytes().replace(folder.as_posix().encode(), trial.BASE.as_posix().encode())
    if EXPECTED_ROUTE == 2:
        assert normalized_tcl.count(b'set_option -route_option 2') == 1
        normalized_tcl = normalized_tcl.replace(b'set_option -route_option 2', b'set_option -route_option 1')
    assert normalized_tcl == (trial.BASE / 'run.tcl').read_bytes()
    log = folder / 'build.log'
    assert receipt['build_log_SHA256'] == trial.sha(log.read_bytes())
    for marker in ['GowinSynthesis finish', 'Placement and routing completed', 'Timing analysis completed', 'Bitstream generation completed']:
        assert marker in read(log), marker
    functional = json.loads(read(folder / 'functional/functional_review.json'))
    assert functional['passed']
    evidence = Path(functional['actual_evidence_directory'])
    evidence.relative_to(folder)
    for name, run in functional['runs'].items():
        assert trial.sha((evidence / (name + '.log')).read_bytes()) == run['log_SHA256']
        assert (run['exit'] == 0) == run['expected_success']
    for name, digest in functional['RTL_SHA256'].items():
        assert trial.sha((folder / 'sources' / name).read_bytes()) == digest
    result.update({'label': folder.name, 'receipt': receipt, 'input_changes': sorted(changed),
                   'functional_passed_with_explicit_DVI_boundary_stub': True,
                   'programmed': False, 'formal_repo_written': False,
                   'actual_result_level': 'isolated simulation/synthesis/PnR/STA, not L6',
                   'artifact_SHA256': {p.relative_to(folder).as_posix(): trial.sha(p.read_bytes())
                                       for p in list(pnr.glob('*.html')) + [pnr / (trial.STEM + '.rpt.txt'), pnr / 'cmd.do', pnr / 'device.cfg', log]}})
    # Report guard negative tests use the actual full report, never edit it.
    negative = {}
    bad_profile = dict(checks.FROZEN_CLOCKS)
    checks.FROZEN_CLOCKS['sys_clk'] = (20.0, 50.0)
    rejected = profile(timing, usage, sdc, pin_report, command, cfg)
    checks.FROZEN_CLOCKS = bad_profile
    negative['pretend_50MHz_not_actual_40MHz_rejected'] = 'clock period/frequency mismatch: sys_clk' in rejected['errors']
    relaxed = sdc.replace('set_clock_uncertainty -hold  0.550', 'set_clock_uncertainty -hold  0.100')
    negative['hold_uncertainty_relaxation_rejected'] = 'non-clock SDC changed from +.039 baseline' in profile(timing, usage, relaxed, pin_report, command, cfg)['errors']
    wrong = sdc.replace('-multiply_by 4 -divide_by 5', '-multiply_by 1 -divide_by 2')
    negative['wrong_PLL_generated_ratio_rejected'] = 'SDC not exact approved physical PLL clock plan' in profile(timing, usage, wrong, pin_report, command, cfg)['errors']
    assert all(negative.values()), negative
    target = 'results.json' if EXPECTED_ROUTE == 1 else 'H_results.json'
    trial.write_json(trial.HERE / target, {'baseline': legacy.report(trial.BASE), 'candidate': result,
                     'clock_profile_guard_negative_tests': negative})
    trial.protect()
    print('GATE', result['offline_report_gate_passed'], 'ERRORS', result['errors'],
          'PATHS', result['global_worst_paths'], result['recovery_removal_worst_paths'],
          'CLOCKS', result['clocks'], 'RESOURCES', result['resources'], flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        suite = unittest.TestLoader().loadTestsFromTestCase(legacy.FullReportTests)
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(legacy.BaselineTests))
        with (trial.HERE / 'report_selftest.log').open('w', encoding='utf-8') as stream:
            outcome = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        assert outcome.wasSuccessful()
        print('Legacy strict report guards', outcome.testsRun, 'PASS')
    elif sys.argv[1:] == ['collect']:
        collect()
    elif sys.argv[1:] == ['collect-H']:
        trial.OUT = trial.HERE / 'H_pll_core40_route2'
        EXPECTED_ROUTE = 2
        collect()
    else:
        raise ValueError('Choose selftest or collect')
