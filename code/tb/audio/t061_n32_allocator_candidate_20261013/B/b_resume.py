"""Continue N32-B from one completed, identity-bound long simulation."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import b_harness as harness
from b_progress import run_cpu_guarded
from runner import identity, require, write_json


def replace_root(value, old, new):
    return str(value).replace(str(old), str(new))


def run(base_plan_path, base_receipt_path, output):
    base_plan_path = Path(base_plan_path).resolve()
    base_receipt_path = Path(base_receipt_path).resolve()
    output = Path(output).resolve()
    require(not output.exists(), 'CONTINUATION_OUTPUT_EXISTS')
    plan = json.loads(base_plan_path.read_text(encoding='utf-8'))
    receipt0 = json.loads(base_receipt_path.read_text(encoding='utf-8'))
    harness.verify(base_plan_path, verify_origins=False)
    require(receipt0['plan'] == identity(base_plan_path), 'BASE_PLAN_IDENTITY')
    require(receipt0['failure'] ==
            'RunnerFailure:STEP_TIMEOUT_OR_LAUNCH:normal_long_check',
            'BASE_FAILURE_SCOPE')
    require(len(receipt0['steps']) == 3, 'BASE_STEP_COUNT')
    compile0, simulate0, check0 = receipt0['steps']
    require(compile0['label'] == 'normal_long_compile' and
            compile0['exit_code'] == 0 and not compile0['timed_out'],
            'BASE_COMPILE_NOT_PASS')
    require(simulate0['label'] == 'normal_long_simulate' and
            simulate0['exit_code'] == 0 and not simulate0['timed_out'] and
            simulate0.get('progress_policy') ==
            'STOP_AFTER_300_SECONDS_WITHOUT_STDOUT_GROWTH',
            'BASE_SIMULATION_NOT_PASS')
    require(check0['label'] == 'normal_long_check' and check0['timed_out'],
            'BASE_CHECK_NOT_TIMEOUT')
    base_root = Path(plan['execution_output']).resolve()
    capture = base_root / 'normal_long_simulate.stdout.bin'
    require(identity(capture) == simulate0['stdout'], 'BASE_CAPTURE_IDENTITY')
    require(b'END ' in capture.read_bytes()[-4096:], 'BASE_CAPTURE_END_MISSING')

    output.mkdir(parents=True)
    budget = harness.Budget(345600)
    source_paths = [Path(__file__).resolve(), (HERE / 'b_progress.py').resolve(),
                    Path(harness.__file__).resolve(),
                    (harness.HELPERS / 'runner.py').resolve(),
                    (harness.HELPERS / 'runner_tail_20261013.py').resolve(),
                    (harness.HELPERS / 'windows_job.py').resolve(),
                    base_plan_path, base_receipt_path, capture]
    before = {str(path): identity(path) for path in source_paths}
    result = {
        'schema': 'T061_N32_B_CONTINUATION_RECEIPT_V1',
        'status': 'FAIL_PARTIAL', 'exit_code': 1, 'failure': None,
        'base_plan': identity(base_plan_path),
        'base_receipt': identity(base_receipt_path),
        'base_capture': identity(capture),
        'source_before': before, 'steps': [], 'automatic_retries': 0,
        'lower_calls': 0, 'EDA_calls': 0, 'T061_complete': False,
    }
    try:
        normal = plan['steps'][2]
        normal_work = output / 'work/normal_long'
        normal_work.mkdir(parents=True)
        argv = list(normal['argv'])
        argv[argv.index('--input') + 1] = str(capture)
        argv[argv.index('--output') + 1] = str(normal_work / 'report.json')
        step = run_cpu_guarded(output, normal['label'], argv, normal_work,
                               86400, budget)
        result['steps'].append(step)
        require(not step['timed_out'] and step['launch_error'] is None,
                'CONTINUED_NORMAL_CHECK_TIMEOUT_OR_LAUNCH')
        require(step['exit_code'] == 0, 'CONTINUED_NORMAL_CHECK_EXIT')

        for original in plan['steps'][3:]:
            case = original['label'].rsplit('_', 1)[0]
            work = output / 'work' / case
            work.mkdir(parents=True, exist_ok=True)
            argv = [replace_root(item, base_root, output)
                    for item in original['argv']]
            if original['kind'] == 'simulate':
                step = harness._run_process_with_environment(
                    output, original['label'], argv, work, 86400, budget,
                    plan['environment'])
            elif original['kind'] == 'check':
                step = run_cpu_guarded(output, original['label'], argv, work,
                                       86400, budget)
            else:
                step = harness._run_process_with_environment(
                    output, original['label'], argv, work, 300, budget,
                    plan['environment'])
            result['steps'].append(step)
            require(not step['timed_out'] and step['launch_error'] is None,
                    'CONTINUATION_STEP_TIMEOUT_OR_LAUNCH:' + original['label'])
            require(step['exit_code'] == original['expected_exit'],
                    'CONTINUATION_STEP_EXIT:' + original['label'])
            raw = ((output / (original['label'] + '.stdout.bin')).read_bytes() +
                   (output / (original['label'] + '.stderr.bin')).read_bytes())
            marker = original['marker']
            require(marker is None or marker.encode('ascii') in raw,
                    'CONTINUATION_STEP_DIAGNOSTIC:' + original['label'])

        after = {str(path): identity(path) for path in source_paths}
        require(after == before, 'CONTINUATION_SOURCE_DRIFT')
        result.update(status='N32_B_R1_EVENT_AUDIO_AND_MUTANTS_PASS_T061_PARTIAL',
                      exit_code=0, source_after=after)
    except Exception as error:
        result['failure'] = type(error).__name__ + ':' + str(error)
    return harness.finalize_receipt(output / 'receipt.json', result, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-plan', required=True, type=Path)
    parser.add_argument('--base-receipt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    final = run(args.base_plan, args.base_receipt, args.output)
    print(json.dumps({key: final.get(key) for key in
                      ('status', 'exit_code', 'failure', 'elapsed_seconds')}))
    raise SystemExit(final['exit_code'])
