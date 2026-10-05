"""Strict gate against a predeclared physical profile, not CLI success alone."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / 'reproduction_20261005'
sys.path.insert(0, str(OLD))
from full_report_checks import check, normalized_options, pins, parsed
from experiment import BASE, PROFILES, RESET_LABEL, RESET_LABELS, expected_cst

STEM = 'audio_visual_coexistence_top'


def expected_command(label):
    place, route = PROFILES[label]
    original = (BASE / 'impl/pnr/cmd.do').read_text(encoding='utf-8')
    assert original.count('-place_option 0') == original.count('-route_option 0') == 1
    return original.replace('-place_option 0', f'-place_option {place}').replace(
        '-route_option 0', f'-route_option {route}')


def evaluate(folder, command_profile):
    pnr = folder / 'impl/pnr'
    receipt = json.loads((folder / 'build_receipt.json').read_text(encoding='utf-8'))
    manifest = json.loads((folder / 'input_manifest.json').read_text(encoding='utf-8'))
    errors = []
    for item in manifest['inputs']:
        actual = (folder / item['path']).read_bytes()
        frozen = (BASE / item['path']).read_bytes()
        if item['path'] == 'constraints\\audio_visual.cst' or item['path'] == 'constraints/audio_visual.cst':
            frozen = expected_cst(folder.name, frozen)
        if hashlib.sha256(actual).hexdigest() != item['candidate_SHA256']:
            errors.append('input hash mismatch: ' + item['path'])
        if actual.replace(folder.as_posix().encode(), BASE.as_posix().encode()) != frozen:
            errors.append('non-path input change: ' + item['path'])
    paths = [pnr / (STEM + '_tr_content.html'), pnr / (STEM + '.rpt.txt'),
             pnr / (STEM + '.pin.html'), pnr / 'cmd.do', pnr / 'device.cfg', folder / 'build.log']
    if receipt['state'] != 'finished' or any(not p.is_file() for p in paths):
        return {'label': folder.name, 'state': receipt['state'], 'receipt': receipt,
                'offline_report_gate_passed': False, 'errors': errors + ['incomplete run/reports']}
    read = lambda p: p.read_text(encoding='utf-8')
    result = check(read(paths[0]), read(paths[1]), read(folder / 'constraints/audio_visual_hold055.sdc'),
                   read(paths[2]), pins(read(BASE / 'impl/pnr' / (STEM + '.pin.html'))),
                   'GW5AST-LV138PG484AC1/I0', 'C', read(paths[3]), command_profile,
                   paths[4].read_bytes(), (BASE / 'impl/pnr/device.cfg').read_bytes())
    actual_options = normalized_options(read(paths[3]))
    baseline_options = normalized_options(read(BASE / 'impl/pnr/cmd.do'))
    result['actual_option_difference_vs_baseline'] = {
        'added': [o for o in actual_options if o not in baseline_options],
        'removed': [o for o in baseline_options if o not in actual_options]}
    log = read(folder / 'build.log')
    rows = parsed(read(paths[0]))
    fixed = {}
    for index, suffix in [(0, 'A'), (1, 'B')]:
        cell = f'u_visual/u_serial_reset/sync_chain_{index}_s0'
        wanted = f'R44C168[1][{suffix}]' if folder.name in RESET_LABELS else f'R49C101[1][{suffix}]'
        observed = sorted({r[5] for section, r in rows if len(r) == 7
                           and r[6] in [cell + '/CLK', cell + '/Q']})
        fixed[cell] = {'expected': wanted, 'observed': observed}
        if observed != [wanted]:
            errors.append('serial reset fixed location missing/mismatched: ' + cell)
    result['serial_reset_fixed_location_readback'] = fixed
    result['OSER_reset_recovery_net_delays_ns'] = [
        {'node': r[6], 'location': r[5], 'delay_ns': float(r[1])}
        for section, r in rows if section == 'Recovery_Analysis' and len(r) == 7
        and r[2] == 'tNET' and 'u_OSER10' in r[6] and r[6].endswith('/RESET')]
    if receipt['exit_code'] != 0:
        errors.append('CLI exit not zero')
    for marker in ['GowinSynthesis finish', 'Placement and routing completed',
                   'Timing analysis completed', 'Bitstream generation completed']:
        if marker not in log:
            errors.append('missing completion: ' + marker)
    if hashlib.sha256(paths[-1].read_bytes()).hexdigest() != receipt['build_log_SHA256']:
        errors.append('log receipt hash mismatch')
    result['errors'].extend(errors)
    result['offline_report_gate_passed'] = not result['errors']
    result['engineering_margin_0p5ns_passed'] = result['offline_report_gate_passed'] and min(
        p['slack_ns'] for p in result['global_worst_paths'].values()) >= 0.5
    result.update({'label': folder.name, 'state': receipt['state'], 'receipt': receipt,
                   'input_count': len(manifest['inputs']), 'SDC_unchanged': True,
                   'CST_unchanged': folder.name not in RESET_LABELS,
                   'physical_profile': manifest['changes'],
                   'profile_basis': 'Declared before run; exact options checked, no blanket exceptions',
                   'artifact_SHA256': {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in paths}, 'programmed': False})
    return result


def collect():
    old = json.loads((OLD / 'full_run_results.json').read_text(encoding='utf-8'))
    baseline = next(r for r in old['results'] if r['label'] == BASE.name)
    results = []
    for label in PROFILES:
        folder = HERE / label
        if (folder / 'build_receipt.json').exists():
            result = evaluate(folder, expected_command(label))
            results.append(result)
            print(label, 'GATE', result['offline_report_gate_passed'],
                  result.get('global_worst_paths'), result.get('recovery_removal_worst_paths'), flush=True)
    report = {'time': datetime.now().astimezone().isoformat(), 'baseline': baseline,
              'results': results, 'original_repo_written': False, 'programmed': False}
    (HERE / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


class ProfileTests(unittest.TestCase):
    def test_only_two_declared_options_change(self):
        old = normalized_options((BASE / 'impl/pnr/cmd.do').read_text(encoding='utf-8'))
        for label, (place, route) in PROFILES.items():
            new = normalized_options(expected_command(label))
            if label == RESET_LABEL:
                self.assertEqual(old, new)
                continue
            self.assertEqual([o for o in old if o not in new],
                             ([ '-place_option 0'] if place else []) + (['-route_option 0'] if route else []))
            self.assertEqual([o for o in new if o not in old],
                             ([f'-place_option {place}'] if place else []) + ([f'-route_option {route}'] if route else []))
            self.assertIn('-correct_hold 1', new)

    def test_reset_cst_change_is_exactly_two_existing_locations(self):
        old = (BASE / 'constraints/audio_visual.cst').read_bytes()
        new = expected_cst(RESET_LABEL, old)
        changed = [(a, b) for a, b in zip(old.splitlines(), new.splitlines()) if a != b]
        self.assertEqual(len(changed), 2)
        self.assertTrue(all(a.startswith(b'INS_LOC "u_visual/u_serial_reset/') for a, b in changed))
        for suffix in ['A', 'B']:
            new = new.replace(f'R44C168[1][{suffix}]'.encode(), f'R49C101[1][{suffix}]'.encode())
        self.assertEqual(new, old)

    def test_profile_does_not_allow_arbitrary_options(self):
        # In-memory parser negative fixture, not a new physical run.
        from full_report_checks import check
        pnr = BASE / 'impl/pnr'
        read = lambda p: p.read_text(encoding='utf-8')
        profile = expected_command('C_reset_route1')
        arguments = dict(timing=read(pnr / (STEM + '_tr_content.html')),
                         usage=read(pnr / (STEM + '.rpt.txt')),
                         sdc=read(BASE / 'constraints/audio_visual_hold055.sdc'),
                         pin_report=read(pnr / (STEM + '.pin.html')),
                         expected_pins=pins(read(pnr / (STEM + '.pin.html'))),
                         expected_pn='GW5AST-LV138PG484AC1/I0', expected_version='C',
                         original_command=profile)
        for modified in [profile.replace('-correct_hold 1', '-correct_hold 0'),
                         profile.replace('-route_option 1', '-route_option 2')]:
            self.assertIn('non-path PnR options changed', check(command=modified, **arguments)['errors'])

    def test_actual_negative_baseline_cannot_become_pass(self):
        # Baseline fixture is genuinely failed, even when CLI exit=0.
        pnr = BASE / 'impl/pnr'
        read = lambda p: p.read_text(encoding='utf-8')
        result = check(read(pnr / (STEM + '_tr_content.html')), read(pnr / (STEM + '.rpt.txt')),
                       read(BASE / 'constraints/audio_visual_hold055.sdc'),
                       read(pnr / (STEM + '.pin.html')), pins(read(pnr / (STEM + '.pin.html'))),
                       'GW5AST-LV138PG484AC1/I0', 'C')
        self.assertFalse(result['offline_report_gate_passed'])
        self.assertEqual(result['global_worst_paths']['Setup']['slack_ns'], -1.356)
        self.assertEqual(result['global_worst_paths']['Hold']['slack_ns'], -0.348)


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        suite = unittest.TestLoader().loadTestsFromTestCase(ProfileTests)
        # Reuse all 21 original fail-closed checker tests without writing old evidence.
        from test_full_report_checks import FullReportTests
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FullReportTests))
        with (HERE / 'report_selftest.log').open('w', encoding='utf-8') as log:
            outcome = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        print('Report selftests:', outcome.testsRun, 'PASS' if outcome.wasSuccessful() else 'FAIL')
        raise SystemExit(0 if outcome.wasSuccessful() else 1)
    collect()
