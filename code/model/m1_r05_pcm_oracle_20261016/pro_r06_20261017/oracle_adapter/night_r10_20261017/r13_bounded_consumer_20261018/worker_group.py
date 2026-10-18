"""Fixed one-worker candidate. No import of candidate math before admission."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def verified_buffer(root, desc, max_bytes=1 << 20):
    path = (root / desc['path']).resolve()
    if not path.is_relative_to(root) or desc['bytes'] > max_bytes:
        raise ValueError('FROZEN_PATH_OR_SIZE')
    with path.open('rb') as file:
        raw = file.read(max_bytes + 1)
    if len(raw) != desc['bytes'] or hashlib.sha256(raw).hexdigest() != desc['sha256']:
        raise ValueError('FROZEN_SOURCE_DRIFT:' + desc['path'])
    return raw


def import_buffer(root, desc, name):
    if name in sys.modules:
        raise ValueError('MODULE_IDENTITY_COLLISION:' + name)
    raw = verified_buffer(root, desc)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(root / desc['path'])
    sys.modules[name] = module
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module


def admit(package, group):
    auth = package.get('authorization', {})
    if (package.get('schema') != 'M1_R13_FROZEN_EXECUTION_V1'
            or auth.get('approved') is not True or auth.get('owner') != 'M2'
            or auth.get('target_software') is not True or group not in auth.get('groups', [])
            or not auth.get('permission_id')):
        raise ValueError('RUN_GO_NOT_GRANTED')
    if not auth['not_before_unix_ns'] <= time.time_ns() < auth['deadline_unix_ns']:
        raise ValueError('RUN_GO_WINDOW_CLOSED')
    if group == 'FIX01' and not all(auth.get('repair', {}).get(k) for k in
            ('original_failure_sha256', 'located_cause', 'changed_source_sha256', 'exact_regression_scope')):
        raise ValueError('UNIQUE_REPAIR_PRECONDITIONS_MISSING')
    required = {'04_CAPACITY_SCHEDULE_R13.json', '05_CAPACITY_LIMITS_AND_MEASUREMENT_R13.json',
                '06_CASE_MATRIX_R13.json', '08_TIME_AND_STOP_R13.json',
                '09_BUDGET_AND_NATIVE_CALL_REQUEST_R13.json'}
    if {Path(x['path']).name for x in package['controls']} != required:
        raise ValueError('FIVE_R13_CONTROLS_REQUIRED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--package-sha256', required=True)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--group', required=True, choices=('SW01', 'CAP01', 'FIX01'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--start-ns', required=True, type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    with args.package.open('rb') as file:
        raw = file.read((1 << 20) + 1)
    if len(raw) > 1 << 20 or hashlib.sha256(raw).hexdigest() != args.package_sha256:
        raise ValueError('PACKAGE_IDENTITY')
    package = json.loads(raw)
    admit(package, args.group)
    # Fixed names and fixed import order; no runtime-supplied handler or argv.
    bindings = json.loads(verified_buffer(root, package['source_bindings']))
    files = {Path(row['path']).stem: row for row in bindings['files']}
    names = ('identity_guard', 'stream_io', 'lifecycle_store', 'results_stream', 'history_join',
             'clocked_math_stream', 'independent_plan', 'fixture_recipe', 'test_new_seams',
             'run_stream_math', 'measure_group')
    if not set(names) <= files.keys():
        raise ValueError('SOURCE_CLOSURE_INCOMPLETE')
    for name in names:
        import_buffer(root, files[name], name)
    guard = sys.modules['identity_guard']
    held = []
    try:
        for desc in bindings['dependencies'] + package['controls']:
            stream = guard.LockedInput(root, desc, 'dependency', lambda: None)
            held.append(stream)
            stream.verify()
        stop_ns = args.start_ns + package['time']['cooperative_stop_ns'][args.group]

        def tick():
            if time.monotonic_ns() >= stop_ns or (args.output / 'STOP').exists():
                raise ValueError('GROUP_COOPERATIVE_STOP')
        evaluate = sys.modules['run_stream_math'].evaluate
        if args.group == 'CAP01':
            # Full fixture generation/transport cannot be silently moved before
            # the clock. R13 static scope leaves the producer-geometry binding
            # unresolved; a precise source successor is required to wire it.
            raise ValueError('CAPACITY_GENERATOR_BINDING_PENDING')
        if args.group in ('CAP01', 'FIX01'):
            job = json.loads(verified_buffer(root, package['jobs'][args.group]))
            result = evaluate(job, root, args.output / 'math', bindings, tick)
        else:
            matrix = sys.modules['test_new_seams'].freeze_matrix(
                root / package['case_matrix']['path'], package['case_matrix']['sha256'])
            jobs = package.get('case_jobs', {})
            if set(jobs) != {case['id'] for case in matrix}:
                raise ValueError('INDEPENDENT_FIXTURE_SET_NOT_FROZEN')
            group_budget = sys.modules['results_stream'].Budget(args.output,
                total_cap=256 << 20, output_cap=256 << 20, scratch_cap=128 << 20)
            audit = sys.modules['results_stream'].Audit(args.output, group_budget)

            def handler(case):
                try:
                    if case['id'] == 'N41':
                        case_root = args.output / case['id']
                        case_root.mkdir()
                        tiny = sys.modules['results_stream'].Budget(case_root, output_cap=(8 << 20) + 64)
                        tiny.reserve_output(65)
                        value = dict(status='UNEXPECTED_ACCEPT', code=None)
                    elif case['id'] == 'N42':
                        sys.modules['measure_group'].validate_recorded_samples([
                            dict(time_ns=0, peak_working_set=1),
                            dict(time_ns=101000000, peak_working_set=None)])
                        value = dict(status='UNEXPECTED_ACCEPT', code=None)
                    else:
                        job = json.loads(verified_buffer(root, jobs[case['id']]))
                        value = evaluate(job, root, args.output / case['id'], bindings, tick, group_budget)
                except (ValueError, OSError, KeyError, TypeError) as error:
                    code = getattr(error, 'code', str(error).split(':')[0])
                    status = getattr(error, 'status', 'RESOURCE_LIMIT' if case['id'] in ('N41', 'N42') else 'CONTRACT_REJECTED')
                    value = dict(status=status, code=code, first_difference=None)
                return {**value, 'target_invocations': 1}
            try:
                result = sys.modules['test_new_seams'].run_cases(matrix,
                    {case['id']: handler for case in matrix}, audit, tick)
            finally:
                audit.close()
        for stream in held:
            stream.verify()
        tick()
        raw_result = json.dumps(result, separators=(',', ':'), allow_nan=False).encode()
        if len(raw_result) > 1 << 20:
            raise ValueError('WORKER_SUMMARY_LIMIT')
        (args.output / 'WORKER_RESULT.json').write_bytes(raw_result + b'\n')
        return 0 if result['status'] in ('SOFTWARE_MATCH_STREAM_COMPLETE', 'SOFTWARE_CASES_MATCHED') else 1
    finally:
        for stream in held:
            stream.close()


if __name__ == '__main__':
    raise SystemExit(main())
