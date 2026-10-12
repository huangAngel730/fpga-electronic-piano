"""300s NEW software qualification only; read-only versions/help, no HDL."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from controlled_runner import Budget, dump, identity, load, step  # noqa: E402
from prepare import ROOT, TB_REL, dependencies  # noqa: E402


def run(out, suite):
    budget = Budget(300)
    out = out.resolve()
    if out.exists() or not out.is_relative_to(ROOT / 'code/output'):
        raise ValueError('FOLLOWUP_OUTPUT_SCOPE_OR_EXISTS')
    out.mkdir(parents=True)
    paths, _ = dependencies()
    paths += [p for p in (ROOT / TB_REL).glob('*') if p.is_file()]
    before = {p.relative_to(ROOT).as_posix(): identity(p) for p in paths}
    steps, failure = [], None
    python = [sys.executable, '-I', '-S', '-B', '-X', 'utf8']
    try:
        steps.append(step(out, 'new_tests', python + [str(HERE / 'test_followup.py'),
            '--evidence-dir', str(out / 'software_suffix'), '-v'], out, budget, 90))
        steps.append(step(out, 'new_package', python + [str(HERE / 'prepare_followup.py'),
            '--output', str(out / 'prepared'), '--suite', str(suite)], out, budget, 90))
        portable = out / 'prepared/portable'
        software = portable / HERE.relative_to(ROOT)
        config = portable / 'CONTROLLED_CONFIG_NOT_AUTHORIZED.json'
        steps.append(step(out, 'default_execution_locked', python + [str(software / 'controlled_runner.py'),
            '--config', str(config), '--output', str(out / 'locked_preflight')], out, budget, 90))
        locked = load(out / 'locked_preflight/receipt.json')
        if locked['status'] != 'PRECHECK_ONLY_EXECUTION_LOCKED' or locked['steps'] or locked['execution_authorized']:
            raise ValueError('FOLLOWUP_DEFAULT_NOT_LOCKED')
        steps.append(step(out, 'isolated_recovery', python + [str(software / 'check_minclosure.py'),
            '--capture', str(out / 'software_suffix/B_suffix_software.jsonl'),
            '--plan', str(portable / 'plan_B.json'), '--software-fixture'], out, budget, 90))
        steps.append(step(out, 'isolated_dirty_reset_refusal', python + [str(software / 'check_minclosure.py'),
            '--capture', str(out / 'software_suffix/B_dirty_reset_complete.jsonl'),
            '--plan', str(portable / 'plan_B.json'), '--software-fixture'], out, budget, 90,
            expected=1, diagnostic='MINCLOSURE_ADVANCE_NONROLLBACK_MATH'))
        steps.append(step(out, 'refuse_repeat_output', python + [str(software / 'controlled_runner.py'),
            '--config', str(config), '--output', str(out / 'locked_preflight')], out, budget, 90,
            expected=1, diagnostic='RUNNER_OUTPUT_EXISTS_OR_NESTED'))
        budget.limit(90)
    except Exception as error:
        failure = str(error)
    after = {p.relative_to(ROOT).as_posix(): identity(p) for p in paths}
    if before != after:
        failure = (failure or '') + '; SOURCE_DRIFT'
    if budget.elapsed() >= 300:
        failure = (failure or '') + '; TOTAL_TIMEOUT'
    receipt = dict(status='NEW_C_FOLLOWUP_SOFTWARE_PASS' if not failure else 'FAIL_PARTIAL',
        exit_code=int(failure is not None), failure=failure, sources_before=before, sources_after=after,
        steps=steps, total_limit_seconds=300, step_limit_seconds=90, elapsed_seconds=budget.elapsed(),
        evidence_origin='SYNTHETIC_SOFTWARE_TEST', old_22_tests='NOT_RERUN; V0295 REUSED',
        A_long_software='NOT_RERUN; V0295 REUSED', execution_authorized=False,
        RTL_compilations=0, RTL_runs=0, EDA_runs=0, physical_verified=False, t060_complete=False)
    dump(out / 'receipt.json', receipt)
    print(receipt['status'] + ': ' + str(failure))
    return receipt['exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suite', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.suite))
