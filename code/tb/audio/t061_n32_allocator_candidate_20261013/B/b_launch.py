"""Pinned B parent watchdog. Run only from the prepared source snapshot."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time


def identity(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def launch(plan_path, expected_sha):
    started = time.monotonic()
    plan_path = Path(plan_path).resolve()
    raw = plan_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha, 'PLAN_SHA'
    plan = json.loads(raw)
    snapshot = Path(plan['prepared']) / 'snapshot'
    sources = {str(plan_path): identity(plan_path)}
    for row in plan['inputs']:
        path = (snapshot / row['snapshot']).resolve()
        assert path.is_relative_to(snapshot.resolve()), 'SOURCE_ESCAPE'
        expected = {key: row[key] for key in ('bytes', 'sha256')}
        assert identity(path) == expected, 'SOURCE_SHA'
        sources[str(path)] = expected
    own = snapshot / 'code/tb/audio/t061_n32_allocator_candidate_20261013/B/b_launch.py'
    assert Path(__file__).resolve() == own.resolve(), 'LAUNCH_FROM_SNAPSHOT_ONLY'
    assert Path.cwd().resolve() == snapshot.resolve(), 'LAUNCH_CWD'
    assert sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
    python = plan['tools']['python']
    assert Path(sys.executable).resolve() == Path(python).resolve(), 'PYTHON_PATH'
    assert identity(python) == plan['tool_files'][python], 'PYTHON_SHA'
    sources[python] = identity(python)
    helpers = snapshot / 'code/software/t052_runner_acceptance_candidate_20261012'
    for name in ('runner', 'runner_tail_20261013', 'windows_job', 'supervisor_20261013'):
        path = helpers / (name + '.py')
        assert str(path.resolve()) in sources, 'UNBOUND_HELPER'
    sys.path.insert(0, str(helpers))
    spec = importlib.util.spec_from_file_location('b_frozen_supervisor',
                                                 helpers / 'supervisor_20261013.py')
    supervisor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(supervisor)
    class ParentBudget:
        def __init__(self, seconds):
            assert type(seconds) in (int, float) and 0 < seconds <= 345600
            self.seconds = float(seconds)
            self.started = started

        def elapsed(self):
            return time.monotonic() - self.started

        def remaining(self, cap):
            left = self.seconds - self.elapsed()
            assert left > 0 and type(cap) in (int, float) and cap > 0
            return min(float(cap), left)

    supervisor.runner.Budget = ParentBudget
    gate = plan['dependency_gate']
    argv = plan['execution_argv_prefix'] + [
        '--plan', str(plan_path), '--reviewed-plan-sha', expected_sha,
        '--a-receipt-sha', gate['a_receipt_sha256'],
        '--a-allocator-sha', gate['a_allocator_sha256'],
        '--a-review-key', gate['a_result_review_key']]
    output = Path(plan['execution_output'])
    assert not output.exists() and not Path(str(output) + '_parent').exists(), 'OUTPUT_EXISTS'
    return supervisor.observe_run(str(output) + '_parent', argv, snapshot,
        output / 'receipt.json', sources, total_seconds=plan['total_seconds'],
        step_seconds=plan['total_seconds'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--plan-sha', required=True)
    args = parser.parse_args()
    result = launch(args.plan, args.plan_sha)
    print(json.dumps({key: result[key] for key in
        ('status', 'exit_code', 'failure', 'elapsed_seconds')}))
    raise SystemExit(result['exit_code'])
