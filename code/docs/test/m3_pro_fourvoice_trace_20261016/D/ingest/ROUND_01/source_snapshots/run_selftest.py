"""One bounded D3 validation round; retain every CLI input and double stream."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
SOURCE = Path(__file__).with_name('ingest.py')
OUT = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/D/ingest/ROUND_01'


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def row(kind, cycle, epoch=0, **fields):
    return {'kind': kind, 'cycle': cycle, 'epoch': epoch, **fields}


def normal():
    return [row('RESET', 0), row('PA', 0, rst_n=0, stable=0, pa_en=0),
            row('PA', 1, rst_n=1, stable=0, pa_en=0),
            row('PA', 5, rst_n=1, stable=1, pa_en=1), row('FRAME', 10, frame_id=0),
            row('REQUEST', 10, req_id=7, lane_mask=15), row('ACCEPT', 11, req_id=7),
            *[row('LANE_TICK', 12 + lane, req_id=7, lane=lane) for lane in range(4)],
            row('RETURN', 45, req_id=7, left=8388607, right=-8388608),
            row('FRAME', 843, frame_id=1), row('CONSUME', 843, req_id=7, frame_id=1),
            row('FRAME', 1677, frame_id=2), row('RESET', 1700, epoch=1),
            row('PA', 1700, epoch=1, rst_n=0, stable=0, pa_en=0),
            row('END', 1701, epoch=1)]


def case(name, rows, provenance='SYNTHETIC_FIXTURE', mutation=None):
    folder = OUT / name
    folder.mkdir()
    (folder / 'source.txt').write_text('SYNTHETIC interface fixture, no Pro RTL\n', encoding='utf-8')
    (folder / 'rom.txt').write_text('SYNTHETIC no oscillator ROM or M1 golden\n', encoding='utf-8')
    write(folder / 'contract.json', {'schema': 'M3_PRO_OBSERVER_REQUIREMENTS_V1',
          'package': 'FPG676', 'clock_hz': 40000000,
          'sampling_phase': 'SYS_EDGE_ORDERED_EVENTS_V1', 'pa_active': 1, 'identity_only': True})
    write(folder / 'calendar.json', {'schema': 'M3_PRO_INTAKE_CALENDAR_V1',
          'provenance': provenance, 'requests': [{'epoch': 0, 'req_id': 7, 'cycle': 10, 'lane_mask': 15}]})
    (folder / 'trace.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    artifacts = []
    for role, file in [('source', 'source.txt'), ('rom', 'rom.txt'), ('contract', 'contract.json'),
                       ('calendar', 'calendar.json'), ('trace', 'trace.jsonl')]:
        item = identity(folder / file)
        artifacts.append({'role': role, 'path': file, 'bytes': item['bytes'], 'sha256': item['sha256']})
    manifest = {'schema': 'M3_PRO_INTAKE_V1', 'provenance': provenance, 'clock_hz': 40000000,
                'sampling_phase': 'SYS_EDGE_ORDERED_EVENTS_V1', 'package': 'FPG676', 'artifacts': artifacts}
    if mutation:
        mutation(manifest)
    write(folder / 'manifest.json', manifest)
    return folder


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    write(OUT / 'ROUND_STARTED.json', {'utc': datetime.now(timezone.utc).isoformat(), 'round': 1,
          'consumes': 'D shared round 6 allocated to coordinator D3', 'source': identity(SOURCE),
          'runner': identity(Path(__file__)), 'python': identity(Path(sys.executable)),
          'machine': platform.node(), 'cwd': str(ROOT), 'group_timeout_seconds': 90})
    cases = [('positive', normal(), None, None),
             ('bad_sha', normal(), 'ARTIFACT_SHA_trace', lambda m: m['artifacts'][-1].update(sha256='0' * 64))]
    missing = normal()
    del missing[11]['right']
    cases.append(('missing_pcm', missing, 'ROW_FIELDS_OR_AFTER_END', None))
    duplicate = normal()
    duplicate.insert(14, row('FRAME', 843, frame_id=1))
    cases.append(('duplicate_frame', duplicate, 'DUPLICATE_FRAME', None))
    wrong_epoch = normal()
    wrong_epoch[11]['epoch'] = 1
    cases.append(('old_epoch', wrong_epoch, 'OLD_OR_MISSING_EPOCH', None))
    canceled = normal()
    canceled.insert(12, row('CANCEL', 46, req_id=7))
    cases.append(('consume_after_cancel', canceled, 'CONSUME_CANCELED_OR_UNRETURNED', None))
    missing_lane = normal()
    missing_lane.pop(10)
    cases.append(('missing_fourth_lane', missing_lane, 'RETURN_STATE_OR_MISSING_LANE', None))
    duplicate_lane = normal()
    duplicate_lane[10]['lane'] = 2
    cases.append(('duplicate_lane', duplicate_lane, 'WRONG_OR_DUPLICATE_LANE', None))
    late = normal()
    late.pop(11)
    cases.append(('deadline', late, 'MISSED_NEXT_FRAME_DEADLINE', None))
    at_boundary = normal()
    at_boundary[11]['cycle'] = 843
    cases.append(('return_on_deadline', at_boundary, 'RETURN_NOT_STRICTLY_BEFORE_FRAME', None))
    lost_consume = normal()[:13] + [row('RESET', 844, epoch=1), row('END', 845, epoch=1)]
    cases.append(('reset_after_missed_consume', lost_consume, 'RESET_UNCONSUMED_DUE_FRAME', None))
    bad_pa = normal()
    bad_pa[2]['pa_en'] = 1
    cases.append(('unstable_pa', bad_pa, 'PA_POLARITY_OR_UNSTABLE', None))
    polarity = normal()
    polarity[3]['pa_en'] = 0
    cases.append(('wrong_pa_polarity', polarity, 'PA_POLARITY_OR_UNSTABLE', None))
    unfinished = normal()
    unfinished = unfinished[:12] + [row('END', 46)]
    cases.append(('unfinished', unfinished, 'UNFINISHED_TRANSACTION', None))
    for role, mutate in [('missing_artifact', lambda m: m['artifacts'].pop(1)),
                         ('path_escape', lambda m: m['artifacts'][0].update(path='../source.txt'))]:
        cases.append((role, normal(), 'ARTIFACT_ROLES_MISSING' if role == 'missing_artifact' else 'ARTIFACT_PATH_OR_MISSING', mutate))
    results = []
    for name, rows, expected_failure, mutation in cases:
        if time.monotonic() - start >= 85:
            break
        folder = case(name, rows, mutation=mutation)
        manifest = folder / 'manifest.json'
        argv = [sys.executable, '-X', 'utf8', str(SOURCE), str(manifest), '--sha256', identity(manifest)['sha256']]
        begun = time.monotonic()
        begun_utc = datetime.now(timezone.utc).isoformat()
        error = None
        try:
            process = subprocess.run(argv, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
                                     timeout=min(5, max(0.1, 85 - (time.monotonic() - start))), check=False)
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
        except (subprocess.TimeoutExpired, OSError) as exc:
            stdout, stderr = getattr(exc, 'stdout', None) or b'', getattr(exc, 'stderr', None) or b''
            code, error = None, repr(exc)
        (folder / 'stdout.txt').write_bytes(stdout)
        (folder / 'stderr.txt').write_bytes(stderr)
        raw = stderr if expected_failure else stdout
        try:
            actual = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            actual = {'first_failure': 'UNPARSEABLE_CLI_RESULT'}
        passed = code == (1 if expected_failure else 0) and error is None
        if expected_failure:
            passed = passed and expected_failure in actual.get('first_failure', '')
        else:
            passed = passed and actual.get('status') == 'INTAKE_FIXTURE_PASS' and actual.get('consumed') == 1 and actual.get('frame_gaps') == [833, 834]
        result = {'case': name, 'argv': argv, 'cwd': str(ROOT), 'start_utc': begun_utc,
                  'end_utc': datetime.now(timezone.utc).isoformat(), 'elapsed_seconds': time.monotonic() - begun,
                  'exit_code': code, 'error': error, 'expected_failure': expected_failure,
                  'actual': actual, 'test_pass': bool(passed), 'files': [identity(p) for p in sorted(folder.iterdir())]}
        write(folder / 'COMMAND_RECEIPT.json', result)
        results.append(result)
        if error is not None:
            break
    summary = {'status': 'PASS' if len(results) == len(cases) and all(r['test_pass'] for r in results) else 'FAIL',
               'rounds_consumed': 1, 'validation_seconds': time.monotonic() - start, 'level': 'L1',
               'board_release_allowed': False, 'real_trace_status': 'PENDING_PRO_SOURCE_OR_TRACE',
               'source': identity(SOURCE), 'runner': identity(Path(__file__)), 'results': results}
    write(OUT / 'RESULT.json', summary)
    print(json.dumps({'status': summary['status'], 'cases': len(results), 'seconds': summary['validation_seconds'],
                      'failed': [r['case'] for r in results if not r['test_pass']]}))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
