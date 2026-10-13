"""Bounded new software/prepare checks, never call HDL tools or create RTL receipts."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'code/software/t052_runner_acceptance_candidate_20261012'))
from runner_tail_20261013 import Budget, _run_process, finalize_receipt  # noqa: E402

loader = importlib.util.spec_from_file_location('oneshot', HERE / 'oneshot.py')
m = importlib.util.module_from_spec(loader)
loader.loader.exec_module(m)


def qualify(output, suite, reuse=None):
    output = output.resolve()
    m.need(output.is_relative_to(ROOT / 'code/output') and output != ROOT / 'code/output',
           'QUALIFICATION_OUTPUT_SCOPE')
    m.need(not output.exists(), 'OUTPUT_EXISTS')
    output.mkdir(parents=True)
    temp_root = output / 'software_temp'
    temp_root.mkdir()
    budget = Budget(300)
    receipt = {'status': 'FAIL_PARTIAL', 'exit_code': 1, 'failure': None,
               'evidence_kind': 'SOFTWARE_AND_STATIC_PREPARATION_ONLY',
               'steps': [], 'HDL_calls': 0, 'actual_receipts': 0,
               'old_32_tests': 'REUSED_NOT_RUN', 'T052_complete': False}
    config_path = output / 'prepared/config.json'
    runner = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(HERE / 'oneshot.py')]

    def step(label, argv, expected_exit, diagnostic=None):
        child_env = dict(os.environ, TEMP=str(temp_root), TMP=str(temp_root))
        with m.environment(child_env):
            result = _run_process(output, label, argv, ROOT, 90, budget)
        receipt['steps'].append(result)
        m.need(result['exit_code'] == expected_exit and not result['timed_out'] and
               result['launch_error'] is None, 'STEP_RESULT:' + label)
        if diagnostic:
            value = json.loads((output / (label + '.stdout.bin')).read_text(encoding='utf-8'))
            m.need(value.get('diagnostic') == diagnostic, 'DIAGNOSTIC:' + label)

    try:
        if reuse is not None:
            old = m.read(reuse / 'receipt.json')
            m.need(old['status'] == 'PREPARATION_SOFTWARE_PASS' and
                   old['exit_code'] == 0 and old['HDL_calls'] == 0, 'REUSED_NOT_PASS')
            config_path = Path(old['config']['path'])
            m.need(m.spec(config_path) == old['config'], 'REUSED_CONFIG_DRIFT')
            pin = old['config']['sha256']
            step('01_increment_static_verify', runner + ['verify', '--config', str(config_path),
                                                         '--config-sha', pin], 0)
            receipt['config'] = m.spec(config_path)
            receipt['REUSED'] = {'receipt': m.spec(reuse / 'receipt.json'),
                                 'seven_guards_and_five_steps': 'NOT_RERUN',
                                 'not_external_exit_attestation_of_old_run': True}
            receipt['artifacts'] = {p.relative_to(output).as_posix(): m.spec(p)
                                    for p in output.rglob('*') if p.is_file()}
            budget.remaining(90)
            receipt.update(status='PREPARATION_SOFTWARE_PASS', exit_code=0)
            return finalize_receipt(output / 'receipt.json', receipt, budget)
        step('01_new_guards', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                              str(HERE / 'test_oneshot.py')], 0)
        step('02_prepare', runner + ['prepare', '--output', str(config_path.parent),
                                     '--suite', str(suite)], 0)
        pin = m.identity(config_path)['sha256']
        base = ['--config', str(config_path), '--config-sha', pin]
        step('03_verify', runner + ['verify', *base], 0)
        step('04_missing_permission', runner + ['execute', *base], 1,
             'M2_EXACT_PERMISSION_REQUIRED')
        step('05_no_overwrite', runner + ['prepare', '--output', str(config_path.parent),
                                          '--suite', str(suite)], 1, 'OUTPUT_EXISTS')
        m.need(not (config_path.parent / 'consumed.json').exists() and
               not (config_path.parent / 'actual_once').exists(), 'EXECUTION_SIDE_EFFECT')
        receipt['config'] = m.spec(config_path)
        receipt['artifacts'] = {p.relative_to(output).as_posix(): m.spec(p)
                                for p in output.rglob('*') if p.is_file()}
        budget.remaining(90)
        receipt.update(status='PREPARATION_SOFTWARE_PASS', exit_code=0)
    except Exception as error:
        receipt['failure'] = type(error).__name__ + ':' + str(error)
    return finalize_receipt(output / 'receipt.json', receipt, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--reuse', type=Path)
    args = parser.parse_args()
    result = qualify(args.output, args.suite, args.reuse)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(result['exit_code'])
