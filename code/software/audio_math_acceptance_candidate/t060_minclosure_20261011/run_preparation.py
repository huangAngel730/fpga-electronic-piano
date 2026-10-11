"""Bounded NEW software preparation checks only; no RTL/EDA launch path."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from prepare import ROOT, TB_REL, dependencies, dump, metadata  # noqa: E402


def run(out):
    out = out.resolve()
    if not out.is_relative_to(ROOT / 'code/output') or out.exists():
        raise ValueError('PREPARATION_OUTPUT_SCOPE_OR_EXISTS')
    out.mkdir(parents=True)
    started = time.monotonic()
    paths, _ = dependencies()
    paths += list((ROOT / TB_REL).glob('*'))
    before = {p.relative_to(ROOT).as_posix(): metadata(p.read_bytes()) for p in paths if p.is_file()}
    steps = []

    def command(label, script, args, expected=0, diagnostic=None):
        remaining = 300 - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError('PREPARATION_TOTAL_TIMEOUT')
        argv = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(script), *map(str, args)]
        begin = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=out, capture_output=True, timeout=min(90, remaining))
            stdout, stderr, code, timeout = result.stdout, result.stderr, result.returncode, False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code, timeout = error.stdout or b'', error.stderr or b'', -1, True
        (out / (label + '.stdout.txt')).write_bytes(stdout)
        (out / (label + '.stderr.txt')).write_bytes(stderr)
        steps.append(dict(label=label, argv=argv, exit_code=code, expected_exit=expected,
                          diagnostic=diagnostic, timeout=timeout, elapsed=time.monotonic() - begin,
                          stdout=metadata(stdout), stderr=metadata(stderr)))
        dump_progress = out / 'progress.json'
        dump_progress.write_text(json.dumps(steps, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(label + ': exit ' + str(code), flush=True)
        if timeout or code != expected or (diagnostic and diagnostic.encode() not in stdout + stderr):
            raise ValueError('PREPARATION_STEP_FAILED:' + label)

    status, failure = 'NEW_SOFTWARE_PREPARATION_PASS', None
    try:
        command('new_software_tests', HERE / 'test_preparation.py',
                ['-v', '--evidence-dir', out / 'software_fixtures'])
        command('static_package', HERE / 'prepare.py', ['--output', out / 'portable'])
        portable = out / 'portable'
        checker = portable / HERE.relative_to(ROOT) / 'check_minclosure.py'
        command('isolated_positive_B', checker, ['--capture', out / 'software_fixtures/normal_B.jsonl.gz',
                '--plan', portable / 'plan_B.json', '--software-fixture'])
        for name, group, diagnostic in (
            ('retirement_reuse_wrong_generation', 'A', 'MINCLOSURE_RETIRE_IDENTITY'),
            ('accepted_panic_missing_off', 'A', 'MINCLOSURE_PANIC_RELEASE'),
            ('frame_accepts_old_result', 'B', 'MINCLOSURE_CANCEL_OLD_ID'),
            ('advance_rolled_back', 'B', 'MINCLOSURE_ADVANCE_NONROLLBACK_MATH')):
            command('isolated_reject_' + name, checker,
                    ['--capture', out / ('software_fixtures/' + name + '.jsonl.gz'),
                     '--plan', portable / ('plan_' + group + '.json'), '--software-fixture'],
                    expected=1, diagnostic=diagnostic)
        command('isolated_reject_synthetic_as_RTL', checker,
                ['--capture', out / 'software_fixtures/normal_B.jsonl.gz',
                 '--plan', portable / 'plan_B.json'], expected=1, diagnostic='origin')
    except Exception as error:
        status, failure = 'NEW_SOFTWARE_PREPARATION_FAIL', str(error)
    after = {p.relative_to(ROOT).as_posix(): metadata(p.read_bytes()) for p in paths if p.is_file()}
    if before != after:
        status, failure = 'NEW_SOFTWARE_PREPARATION_FAIL', 'SOURCE_DRIFT'
    receipt = dict(status=status, exit_code=0 if failure is None else 1, failure=failure,
                   sources_before=before, sources_after=after, steps=steps,
                   total_limit_seconds=300, step_limit_seconds=90, elapsed=time.monotonic() - started,
                   evidence_origin='SYNTHETIC_SOFTWARE_TEST', RTL_compilations=0,
                   RTL_runs=0, EDA_runs=0, t060_complete=False, physical_verified=False)
    dump(out / 'receipt.json', receipt)
    print(json.dumps(dict(status=status, exit_code=receipt['exit_code'], failure=failure)))
    return receipt['exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
