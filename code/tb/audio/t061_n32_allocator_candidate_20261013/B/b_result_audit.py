"""Audit the split N32-B execution without rerunning RTL or the checker."""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def audit(base, continuation):
    base = Path(base).resolve()
    continuation = Path(continuation).resolve()
    base_receipt = load(base / 'receipt.json')
    final = load(continuation / 'receipt.json')
    capture = base / 'normal_long_simulate.stdout.bin'
    report = load(continuation / 'work/normal_long/report.json')
    require(base_receipt['failure'] ==
            'RunnerFailure:STEP_TIMEOUT_OR_LAUNCH:normal_long_check',
            'BASE_FAILURE_SCOPE')
    require(base_receipt['steps'][1]['exit_code'] == 0 and
            not base_receipt['steps'][1]['timed_out'], 'BASE_SIM_NOT_PASS')
    require(digest(capture) == base_receipt['steps'][1]['stdout'],
            'CAPTURE_SHA')
    require(final['status'] ==
            'N32_B_R1_EVENT_AUDIO_AND_MUTANTS_PASS_T061_PARTIAL' and
            final['exit_code'] == 0 and final['failure'] is None,
            'CONTINUATION_NOT_PASS')
    require(final['source_before'] == final['source_after'], 'SOURCE_DRIFT')
    require(len(final['steps']) == 10 and all(not row['timed_out']
            and row['launch_error'] is None for row in final['steps']),
            'CONTINUATION_STEP_STATE')
    require(report['status'] == 'N32_B_R1_EVENT_AUDIO_PASS_T061_PARTIAL',
            'NORMAL_REPORT_STATUS')
    require(report['capture_sha256'] == digest(capture)['sha256'],
            'NORMAL_REPORT_CAPTURE_SHA')
    require(report['deadline_misses'] == 0 and
            report['max_request_to_result_cycles'] <= 833,
            'DEADLINE_RESULT')
    require(report['hold_edges'] > 0 and report['cancelled_requests'] > 0 and
            report['clipped_results'] > 0 and report['unclipped_results'] > 0,
            'NORMAL_COVERAGE')
    require(report['independently_traced_contributing_slots'] == 32 and
            report['lifecycle']['retirements'] >= 32,
            'N32_LIFECYCLE_COVERAGE')
    expected = {'wrong_id': 'RESULT_ID_LEDGER',
                'wrong_pcm': 'RESULT_PCM_LEDGER',
                'wrong_clipped': 'RESULT_CLIPPED_LEDGER'}
    for name, reason in expected.items():
        item = load(continuation / ('work/' + name + '/report.json'))
        require(item == {'status': 'REJECT', 'reason': reason},
                'MUTANT_RESULT:' + name)
    return {
        'schema': 'T061_N32_B_RESULT_AUDIT_V1', 'status': 'PASS',
        'base_receipt': digest(base / 'receipt.json'),
        'capture': digest(capture),
        'continuation_receipt': digest(continuation / 'receipt.json'),
        'normal_report': digest(continuation / 'work/normal_long/report.json'),
        'deadline_misses': report['deadline_misses'],
        'latency_cycles': [report['min_request_to_result_cycles'],
                           report['max_request_to_result_cycles']],
        'published_results': report['published_results'],
        'hold_edges': report['hold_edges'],
        'cancelled_requests': report['cancelled_requests'],
        'retirements': report['lifecycle']['retirements'],
        'contributing_slots': report['independently_traced_contributing_slots'],
        'mutants': expected, 'T061_complete': False,
        'physical_STA': 'NOT_RUN',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--continuation', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.base, args.continuation)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8', newline='\n')
    print(json.dumps(result, sort_keys=True))
