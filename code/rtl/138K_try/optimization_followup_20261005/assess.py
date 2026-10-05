"""Strict full-design STA comparison with preserved success, no relaxed cuts."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'optimization_20261005/C_reset_route1'
STEM = 'audio_visual_coexistence_top'
sys.path.insert(0, str(ROOT / 'reproduction_20261005'))
from full_report_checks import check, normalized_options, pins, parsed
from test_full_report_checks import FullReportTests


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return path.read_text(encoding='utf-8')


def report(folder):
    pnr = folder / 'impl/pnr'
    baseline_pnr = BASE / 'impl/pnr'
    result = check(read(pnr / (STEM + '_tr_content.html')),
                   read(pnr / (STEM + '.rpt.txt')),
                   read(folder / 'constraints/audio_visual_hold055.sdc'),
                   read(pnr / (STEM + '.pin.html')),
                   pins(read(baseline_pnr / (STEM + '.pin.html'))),
                   'GW5AST-LV138PG484AC1/I0', 'C',
                   read(pnr / 'cmd.do'), read(baseline_pnr / 'cmd.do'),
                   (pnr / 'device.cfg').read_bytes(), (baseline_pnr / 'device.cfg').read_bytes())
    rows = parsed(read(pnr / (STEM + '_tr_content.html')))
    fixed = {}
    for index, suffix in [(0, 'A'), (1, 'B')]:
        cell = f'u_visual/u_serial_reset/sync_chain_{index}_s0'
        expected = f'R44C168[1][{suffix}]'
        observed = sorted({r[5] for section, r in rows if len(r) == 7
                           and r[6] in [cell + '/CLK', cell + '/Q']})
        fixed[cell] = {'expected': expected, 'observed': observed}
        if observed != [expected]:
            result['errors'].append('serial reset fixed location mismatch: ' + cell)
    result['serial_reset_fixed_location_readback'] = fixed
    result['offline_report_gate_passed'] = not result['errors']
    return result


def inputs(folder):
    manifest = json.loads(read(folder / 'input_manifest.json'))
    errors = []
    changed = []
    for item in manifest['inputs']:
        original = (BASE / item['path']).read_bytes()
        actual = (folder / item['path']).read_bytes()
        if sha(original) != item['baseline_SHA256'] or sha(actual) != item['candidate_SHA256']:
            errors.append('input hash mismatch: ' + item['path'])
        normalized = actual.replace(folder.as_posix().encode(), BASE.as_posix().encode())
        if normalized != original:
            changed.append(item['path'])
    if len(manifest['inputs']) != 56 or changed != ['sources/midi_event_parser.sv']:
        errors.append('input change set not exactly one parser: ' + str(changed))
    for name in ['audio_visual.cst', 'audio_visual_hold055.sdc']:
        if (folder / 'constraints' / name).read_bytes() != (BASE / 'constraints' / name).read_bytes():
            errors.append('constraint bytes changed: ' + name)
    if (folder / 'run.tcl').read_bytes().replace(folder.as_posix().encode(), BASE.as_posix().encode()) != (BASE / 'run.tcl').read_bytes():
        errors.append('build Tcl changed beyond project path')
    return errors


def evaluate(label):
    folder = HERE / label
    receipt = json.loads(read(folder / 'build_receipt.json'))
    errors = inputs(folder)
    result = report(folder)
    log = folder / 'build.log'
    if receipt['state'] != 'finished' or receipt['exit_code'] != 0:
        errors.append('build incomplete/nonzero exit')
    if sha(log.read_bytes()) != receipt['build_log_SHA256']:
        errors.append('build log hash mismatch')
    for marker in ['GowinSynthesis finish', 'Placement and routing completed',
                   'Timing analysis completed', 'Bitstream generation completed']:
        if marker not in read(log):
            errors.append('missing completion marker: ' + marker)
    functional = json.loads(read(folder / 'functional/functional_review.json'))
    if not functional['passed'] or functional['candidate_SHA256'] != sha((folder / 'sources/midi_event_parser.sv').read_bytes()):
        errors.append('functional evidence missing/mismatched')
    result['errors'].extend(errors)
    result['offline_report_gate_passed'] = not result['errors']
    result.update({'label': label, 'receipt': receipt, 'functional_passed': functional['passed'],
                   'programmed': False, 'formal_repo_written': False,
                   'engineering_margin_0p5ns_passed': result['offline_report_gate_passed'] and
                   result['global_worst_paths']['Setup']['slack_ns'] >= 0.5,
                   'artifact_SHA256': {p.relative_to(folder).as_posix(): sha(p.read_bytes())
                                       for p in list((folder / 'impl/pnr').glob('*.html')) +
                                       [folder / 'impl/pnr/cmd.do', folder / 'impl/pnr/device.cfg',
                                        folder / 'impl/pnr' / (STEM + '.rpt.txt'), log]}})
    return result


class BaselineTests(unittest.TestCase):
    def test_preserved_success_is_strict_pass(self):
        r = report(BASE)
        self.assertEqual(r['errors'], [])
        self.assertEqual(r['global_worst_paths']['Setup']['slack_ns'], 0.025)
        self.assertEqual(r['global_worst_paths']['Hold']['slack_ns'], 0.0)

    def test_options_do_not_ignore_hold_or_route_changes(self):
        a = read(BASE / 'impl/pnr/cmd.do')
        self.assertNotEqual(normalized_options(a), normalized_options(a.replace('-correct_hold 1', '-correct_hold 0')))
        self.assertNotEqual(normalized_options(a), normalized_options(a.replace('-route_option 1', '-route_option 2')))


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        suite = unittest.TestLoader().loadTestsFromTestCase(FullReportTests)
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(BaselineTests))
        with (HERE / 'report_selftest.log').open('w', encoding='utf-8') as log:
            outcome = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        print('Report checker tests', outcome.testsRun, 'PASS' if outcome.wasSuccessful() else 'FAIL')
        raise SystemExit(0 if outcome.wasSuccessful() else 1)
    baseline = report(BASE)
    labels = sys.argv[1:]
    assert labels and all((HERE / label).parent == HERE for label in labels)
    results = [evaluate(label) for label in labels]
    (HERE / 'results.json').write_text(json.dumps({'baseline': baseline, 'results': results},
                                                indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for r in results:
        print(r['label'], 'GATE', r['offline_report_gate_passed'], 'ERRORS', r['errors'],
              '\nSETUP/HOLD', r['global_worst_paths'], '\nREC/REM', r['recovery_removal_worst_paths'],
              '\nRESOURCES', r['resources'], flush=True)
