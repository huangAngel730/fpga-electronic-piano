"""Summarize the already captured Pro software executions without rerunning."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
MODEL = REPO / 'code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016'
PRODUCTION = MODEL.relative_to(REPO).as_posix() + '/capture_compare.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    runs = {}
    for name in ('A1_TEST_R01', 'A1_GENERATE_R01', 'B0_TEST_R01', 'B0_CLI_R01',
                 'B0_TEST_R02_AFTER_SPECIFIC_FIX', 'B0_FIX_ONLY_ADDED_CASE_R02B'):
        path = HERE / 'RUNS' / name / 'RECEIPT.json'
        row = read(path)
        if row['exit_code'] or row['timeout'] or not row['source_unchanged']:
            raise ValueError('CAPTURED_COMMAND_NOT_SUCCESSFUL:' + name)
        for stream, facts in row['streams'].items():
            raw = path.parent / stream
            if raw.stat().st_size != facts['bytes'] or sha(raw) != facts['sha256']:
                raise ValueError('RAW_STREAM_CHANGED:' + name + '/' + stream)
        runs[name] = {'receipt': path.relative_to(HERE).as_posix(),
                      'receipt_sha256': sha(path), 'argv': row['argv'],
                      'cwd': row['cwd'], 'exit_code': row['exit_code'],
                      'duration_seconds': row['elapsed_seconds'],
                      'python': row['python'], 'streams': row['streams'],
                      'source_sha256': {key.replace('\\', '/'): value
                                        for key, value in row['source_before_sha256'].items()}}
    production_sha = sha(MODEL / 'capture_compare.py')
    for name in ('B0_TEST_R02_AFTER_SPECIFIC_FIX', 'B0_FIX_ONLY_ADDED_CASE_R02B'):
        if runs[name]['source_sha256'][PRODUCTION] != production_sha:
            raise ValueError('FINAL_PRODUCTION_NOT_TESTED:' + name)
    fixture_qualification = read(HERE / 'B0/cli_R01/QUALIFICATION_RECEIPT.json')
    if not fixture_qualification['all_expectations_matched']:
        raise ValueError('CLI_QUALIFICATION_DID_NOT_MATCH')
    a1 = read(HERE / 'A1/generated_R01/QUALIFICATION_SYNTHETIC.json')
    result = {
        'schema': 'M1_PRO_17_OFFLINE_DELIVERY_RECEIPT_V1',
        'status': 'OFFLINE_SOFTWARE_PREPARATION_COMPLETE_REAL_AND_PUBLICATION_PENDING',
        'basis_local_head': '228879b6713188d71e1e97ae1170eaa53c523168',
        'last_successful_origin_develop': '8b129dee4248e055d97d2910675f1c4b23473c96',
        'remote_latest_verified': False,
        'authorization_task_sha256': sha(HERE / 'TASK_RECEIVED.md'),
        'actual_level': 'L0_SOURCE_AND_SYNTHETIC_SOFTWARE_PREPARATION',
        'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False,
        'A0': {'files': 73, 'archive_members': 32, 'frozen_dependencies': 7,
               'source_manifest_sha256': sha(HERE / 'A0/SOURCE_FREEZE.json'),
               'original_outer_raw_streams_saved': False,
               'limitation': 'Original A0 tool transcript and structured child Git receipts preserved; final independent static SHA verification has separate raw streams.'},
        'A1': {'new_test_methods_passed': 14, 'scenes': 5,
               'rows_per_scene': 256, 'total_synthetic_rows': 1280,
               'qualification_sha256': sha(HERE / 'A1/generated_R01/QUALIFICATION_SYNTHETIC.json'),
               'true_clip_rows': a1['observed_true_clip_rows'],
               'sum_of_effected_solos_is_chord_golden': False,
               'counterexample': a1['final_solo_sum_counterexample']},
        'B0': {'final_production_sha256': production_sha,
               'final_test_file_sha256': sha(MODEL / 'test_capture_compare.py'),
               'initial_new_methods_passed': 30,
               'specific_fix_round': {'first_command_methods_passed': 32,
                                      'subsequently_added_method_passed': 1,
                                      'single_final_33_method_suite_run_claimed': False,
                                      'same_final_production_sha_on_both_commands': True},
               'pre_fix_cli_expected_and_actual_exits': [0, 1, 2, 3],
               'pre_fix_cli_results_are_not_relabelled_as_final_source_reruns': True,
               'profile': 'R06_SETTLED_SIMULTANEOUS_LANE_TICKS_V1',
               'real_admission': 'ALWAYS_PENDING_WITH_CURRENT_PRO_GAPS',
               'tolerance_pcm_lsb': 0},
        'executions': runs,
        'self_review': {'A1': 'Read-only review found no blocker in new adapter and required parent generator context',
                        'B0_first_finding': 'Static review: missing public PCM returned pending before validating supplied calendar identities/counts; original 30 tests had not covered it',
                        'B0_minimal_fix': 'Reconstruct supplied calendar and check each available count component before pending return; no arithmetic rewrite',
                        'B0_followup': 'Read-only review confirmed that specific blocker closed',
                        'runtime_failure_fabricated': False},
        'source_and_artifacts': {p.relative_to(REPO).as_posix():
                                {'bytes': p.stat().st_size, 'sha256': sha(p)}
                                for p in sorted(MODEL.glob('*.py'))},
        'publication': {'status': 'BLOCKED_GIT_FETCH', 'staged': False,
                        'committed': False, 'pushed': False,
                        'exact_tree_nine_gate_executed': False,
                        'reason': 'Cannot synchronize current develop; preserve local originals and require fresh sync/scoped staging/cached check/exact-tree gate before publishing',
                        'network_global_config_changed': False,
                        'certificate_verification_disabled': False,
                        'attempts': ['default proxy connect failed; root tool transcript retained',
                                     'process-only direct Schannel SEC_E_NO_CREDENTIALS; SESSION raw streams',
                                     'process-only direct OpenSSL credential-helper signal-pipe failure; SESSION raw streams']},
        'no_new_execution': ['old signed software test suites', 'old303 replay',
                             'ModelSim', 'Gowin', 'PnR', 'STA', 'bitstream', 'board'],
        'missing_real_inputs': ['same-version Pro part/top/PLL/reset/source+ROM role mapping',
                                'M3 original driver/full trace/observer source chain',
                                'independent applications/slot/epoch/all lane_tick/cancel/FX config acceptances',
                                'asynchronous RESET_EDGES', 'same-run public PCM/ID/clip',
                                'tool/argv/raw streams/exit/quota/continuity provenance'],
        'notification': '待用户转发，尚未送达',
        'next_action': 'Software preparation is sealed; real comparison waits for required Pro/M3 originals and a trusted supported contract',
    }
    with (HERE / 'FINAL_RECEIPT.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'A1_new_tests': 14,
                      'B0_final_production_tests': '32+1', 'REAL_RESULT': result['REAL_RESULT'],
                      'committed': False, 'pushed': False}))


if __name__ == '__main__':
    main()
