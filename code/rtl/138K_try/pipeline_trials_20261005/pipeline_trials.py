"""One-stage payload buffer and deeper lookahead pipeline, isolated 138K only."""
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
assert HERE == Path('E:/FPGA/GAOYUNFPGA/138K_try/pipeline_trials_20261005')
PREVIOUS = ROOT / 'optimization_followup_20261005'
LABELS = ['C_payload_buffer', 'D_rotation_pipeline']


def imported(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


shared = imported('pipeline_shared', PREVIOUS / 'experiment.py')
assessor = imported('pipeline_assessor', PREVIOUS / 'assess.py')
shared.HERE = assessor.HERE = HERE


def protected():
    result = shared.protected_hashes()
    result.update({str(p): shared.sha(p.read_bytes()) for p in PREVIOUS.rglob('*') if p.is_file()})
    return result


def protect(check=False):
    before = HERE / 'preservation_before.json'
    if not check:
        assert not before.exists(), 'Preserve old receipt'
        shared.write_json(before, protected())
        return
    frozen = json.loads(before.read_text(encoding='utf-8'))
    actual = protected()
    changes = [p for p in set(frozen) | set(actual) if frozen.get(p) != actual.get(p)]
    shared.write_json(HERE / 'preservation_verification.json', {
        'time': datetime.now().astimezone().isoformat(), 'files': len(frozen),
        'changed_added_removed': changes, 'passed': not changes})
    assert not changes, changes
    print('Protected both older experiment trees and successful +.025 baseline:', len(frozen), 'files PASS', flush=True)


def extra_negative(label):
    out = shared.OUT / 'functional'
    env = dict(os.environ)
    env['PATH'] = str(shared.CAD / 'bin') + ';' + env['PATH']
    env['TMP'] = env['TEMP'] = str(out / 'tmp')
    source = (shared.OUT / 'sources/midi_event_parser.sv').read_text(encoding='utf-8')
    mutants = [('stale_payload', 'previous_value : old_first_index', 'prepared_value0 : old_first_index')]
    if label.startswith('D_'):
        mutants.append(('wrong_next_rr', "selected_index+5'd1 : round_robin_index", "selected_index+5'd2 : round_robin_index"))
    record = json.loads((out / 'functional_review.json').read_text(encoding='utf-8'))
    for name, before, after in mutants:
        assert source.count(before) == 1, name
        bad = out / (name + '.sv')
        bad.write_text(source.replace(before, after, 1), encoding='utf-8')
        image = out / (name + '.vvp')
        compiler = [shared.CAD / 'bin/iverilog.exe', '-B', shared.CAD / 'lib/ivl', '-g2012',
                    '-s', 'tb_m2_parser_miter', '-o', image, shared.OUT / 'sources/audio_defs_pkg.sv',
                    bad, out / 'reference.sv', out / 'tb.sv']
        for suffix, cmd, good in [('_compile', compiler, True), ('', [shared.CAD / 'bin/vvp.exe', image], False)]:
            log = out / (name + suffix + '.log')
            with log.open('wb') as stream:
                process = subprocess.run([str(x) for x in cmd], cwd=out, env=env,
                                         stdout=stream, stderr=subprocess.STDOUT, timeout=240)
            text = log.read_text(encoding='utf-8', errors='replace')
            assert (process.returncode == 0) == good, name + suffix
            if not good:
                assert ('full parser' in text or 'lookahead rotation state mismatch' in text), text
            record['runs'][name + suffix] = {'command': [str(x) for x in cmd], 'exit': process.returncode,
                                            'expected_success': good, 'log_SHA256': shared.sha(log.read_bytes())}
            print(name + suffix, 'exit', process.returncode, text[-350:], flush=True)
    record['coverage'] += '; complete FIFO/parser/pending-value/accepted-value state; cached payload freshness each cycle'
    if label.startswith('D_'):
        record['coverage'] += '; lookahead bitmap equality each cycle; wrong-next-RR compiled mutant rejected'
    shared.write_json(out / 'functional_review.json', record)


def run(label, physical=True):
    assert label in LABELS
    shared.LABEL = label
    shared.OUT = HERE / label
    shared.SCOPE = HERE / 'candidates' / label
    shared.REPO = HERE / 'fixtures' / label[0]
    manifest = {'frozen_parser_SHA': shared.sha((shared.BASE / 'sources/midi_event_parser.sv').read_bytes()),
                'candidate_SHA': shared.sha((shared.SCOPE / 'midi_event_parser.sv').read_bytes()),
                'origin': 'Original de68038 public behavior, isolated prepared-selector prototype with new payload buffer',
                'physical_trial_limit': 1, 'physical_timeout_s': 1800,
                'public_latency_intended_unchanged': True, 'buffer_stages': 1 if label.startswith('C_') else 2}
    assert not (shared.SCOPE / 'manifest.json').exists()
    shared.write_json(shared.SCOPE / 'manifest.json', manifest)
    shared.prepare()
    shared.functional()
    extra_negative(label)
    if physical:
        shared.build()


def collect():
    baseline = assessor.report(shared.BASE)
    results = []
    pending = []
    for label in LABELS:
        receipt = HERE / label / 'build_receipt.json'
        if not receipt.exists():
            pending.append({'label': label, 'state': 'not_built'})
            continue
        state = json.loads(receipt.read_text(encoding='utf-8'))['state']
        if state != 'finished':
            pending.append({'label': label, 'state': state})
            continue
        results.append(assessor.evaluate(label))
    shared.write_json(HERE / 'results.json', {'baseline': baseline, 'results': results, 'pending': pending})
    if pending:
        print('Not yet assessed; no PASS inferred:', pending, flush=True)
    for result in results:
        print(result['label'], 'GATE', result['offline_report_gate_passed'], 'ERRORS', result['errors'],
              'PATHS', result['global_worst_paths'], result['recovery_removal_worst_paths'],
              'RESOURCES', result['resources'], flush=True)


if __name__ == '__main__':
    action = sys.argv[1:]
    if action == ['init']:
        protect()
    elif len(action) == 2 and action[0] == 'run':
        protect(check=True)
        try:
            run(action[1])
        finally:
            protect(check=True)
    elif len(action) == 2 and action[0] == 'prepare-functional':
        protect(check=True)
        try:
            run(action[1], physical=False)
        finally:
            protect(check=True)
    elif len(action) == 2 and action[0] == 'build':
        assert action[1] in LABELS
        shared.LABEL = action[1]
        shared.OUT = HERE / action[1]
        protect(check=True)
        try:
            shared.build()
        finally:
            protect(check=True)
    elif action == ['collect']:
        collect()
        protect(check=True)
    elif action == ['selftest']:
        suite = unittest.TestLoader().loadTestsFromTestCase(assessor.FullReportTests)
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(assessor.BaselineTests))
        with (HERE / 'report_selftest.log').open('w', encoding='utf-8') as stream:
            outcome = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        print('Report checker tests:', outcome.testsRun, 'PASS' if outcome.wasSuccessful() else 'FAIL')
        assert outcome.wasSuccessful()
    else:
        raise ValueError('Choose init, run LABEL, collect, selftest')
