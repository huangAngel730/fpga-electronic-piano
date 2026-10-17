"""Preserve four new B0 CLI fixtures, raw streams, reports and exact exits.

The fixture factory is this batch's test helper; unittest mains are not run.
All PCM values here are synthetic software products, including the deliberately
relabelled REAL admission-negative. No item is evidence of a real DUT capture.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOCS = REPO / 'code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016/B0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if DOCS.resolve() not in output.parents:
        raise ValueError('OUTPUT_MUST_BE_NEW_CHILD_OF_B0')
    output.mkdir(parents=True, exist_ok=False)
    from test_capture_compare import make_fixture, save_fixture
    from capture_compare import read_json
    cases = [('synthetic_fourvoice', 0, 'SYNTHETIC_FIXTURE_PASS'),
             ('left_one_lsb', 1, 'PCM_MISMATCH'),
             ('identity_before_pcm', 2, 'CONTRACT_REJECTED'),
             ('relabelled_real_admission_negative', 3, 'PENDING_REAL_CAPTURE')]
    receipt = {'schema': 'M1_PRO_B0_RAW_CLI_QUALIFICATION_V1',
               'scope': 'SYNTHETIC_SOFTWARE_FIXTURES_ONLY',
               'REAL_RESULT': 'PENDING_REAL_CAPTURE',
               'board_release_allowed': False, 'cases': []}
    for name, wanted_exit, wanted_status in cases:
        folder = output / name
        folder.mkdir(exist_ok=False)
        manifest_path = make_fixture(folder)
        manifest = read_json(manifest_path)
        calendar = read_json(folder / 'calendar.json')
        public = read_json(folder / 'public_pcm.json')
        if name == 'left_one_lsb':
            public['rows'][0]['left'] += 1
        elif name == 'identity_before_pcm':
            # The later identity fault must reject before the earlier PCM fault.
            public['rows'][0]['left'] += 1
            active = next(x for x in public['rows'][-1]['identities'] if x['source'] is not None)
            active['source'] = (active['source'] + 1) % 16
        elif name == 'relabelled_real_admission_negative':
            manifest['mode'] = 'REAL'
            calendar.update(origin='M3_INDEPENDENT_APPLIED_CALENDAR', producer='M3')
            public.update(origin='REAL_DUT_PUBLIC_CAPTURE', producer='DUT_PUBLIC_CAPTURE')
        save_fixture(folder, manifest, calendar, public)
        command = [sys.executable, '-B', '-X', 'utf8', str(HERE / 'capture_compare.py'),
                   '--manifest', str(manifest_path), '--out', str(folder / 'REPORT.json')]
        start = time.time()
        with (folder / 'stdout.bin').open('xb') as out, (folder / 'stderr.bin').open('xb') as err:
            result = subprocess.run(command, cwd=REPO, stdout=out, stderr=err, timeout=30)
        report = read_json(folder / 'REPORT.json')
        expectation = result.returncode == wanted_exit and report['status'] == wanted_status
        if name == 'relabelled_real_admission_negative':
            expectation &= bool(report['missing_real_requirements']) and not report['rtl_or_board_pass']
        row = {'name': name, 'argv': command, 'cwd': str(REPO),
               'exit_code': result.returncode, 'expected_exit_code': wanted_exit,
               'status': report['status'], 'expected_status': wanted_status,
               'elapsed_seconds': time.time() - start,
               'expectation_matched': expectation,
               'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                         for p in sorted(folder.iterdir()) if p.is_file()}}
        receipt['cases'].append(row)
        if not expectation:
            break
    receipt['all_expectations_matched'] = len(receipt['cases']) == len(cases) and all(
        row['expectation_matched'] for row in receipt['cases'])
    write(output / 'QUALIFICATION_RECEIPT.json', receipt)
    print(json.dumps({'all_expectations_matched': receipt['all_expectations_matched'],
                      'expected_exits': [row['expected_exit_code'] for row in receipt['cases']],
                      'actual_exits': [row['exit_code'] for row in receipt['cases']],
                      'REAL_RESULT': receipt['REAL_RESULT']}))
    return 0 if receipt['all_expectations_matched'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
