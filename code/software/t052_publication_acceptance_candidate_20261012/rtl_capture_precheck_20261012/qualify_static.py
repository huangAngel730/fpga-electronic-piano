"""Bounded software-only qualification for the T052 control preparation."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST = ROOT / ('code/docs/test/t052_publication_acceptance_20261012/'
                   'CONTROL_PREPARATION_20261012/source_manifest.json')


def identity(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def dump(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def inputs():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    paths = [MANIFEST, *(ROOT / path for path in manifest['tracked_files'])]
    paths.extend((ROOT / manifest['plan_path'],
                  ROOT / manifest['raw_archive']['path'],
                  ROOT / manifest['readonly_archive']['path']))
    return {path.relative_to(ROOT).as_posix(): identity(path) for path in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'code/output') or output.exists():
        raise SystemExit('OUTPUT_SCOPE_OR_EXISTS')
    output.mkdir(parents=True)
    started = time.monotonic()
    before = inputs()
    steps = []
    failure = None
    base = [sys.executable, '-I', '-B', '-X', 'utf8']

    def step(label, argv):
        remaining = 300 - (time.monotonic() - started)
        if remaining <= 0:
            raise RuntimeError('TOTAL_BUDGET')
        begin = time.monotonic()
        result = subprocess.run(base + [str(item) for item in argv], cwd=ROOT,
                                capture_output=True, timeout=min(90, remaining))
        stdout = output / (label + '.stdout.txt')
        stderr = output / (label + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        record = {
            'label': label,
            'argv': base + [str(item) for item in argv],
            'exit_code': result.returncode,
            'expected_exit': 0,
            'elapsed_seconds': time.monotonic() - begin,
            'stdout': identity(stdout),
            'stderr': identity(stderr),
        }
        dump(output / (label + '.receipt.json'), record)
        steps.append(record)
        if result.returncode != 0:
            raise RuntimeError('STEP_FAILED:' + label)

    try:
        step('unit_tests', [HERE / 'test_precheck.py', '-v'])
        step('static_precheck', [HERE / 'precheck.py', 'static',
                                 '--manifest', MANIFEST])
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as error:
        failure = str(error)
    after = inputs()
    if before != after:
        failure = (failure + '; ' if failure else '') + 'INPUT_DRIFT'
    elapsed = time.monotonic() - started
    if elapsed >= 300:
        failure = (failure + '; ' if failure else '') + 'TOTAL_BUDGET'
    receipt = {
        'status': 'STATIC_PREPARATION_QUALIFIED' if failure is None else 'FAIL_PARTIAL',
        'exit_code': int(failure is not None),
        'failure': failure,
        'host': socket.gethostname(),
        'inputs_before': before,
        'inputs_after': after,
        'steps': steps,
        'python': {'path': sys.executable, 'version': sys.version,
                   **identity(Path(sys.executable))},
        'elapsed_seconds': elapsed,
        'total_limit_seconds': 300,
        'step_limit_seconds': 90,
        'RTL_runs': 0,
        'EDA_runs': 0,
        'T052_complete': False,
        'notice': '待用户转发，尚未送达',
    }
    dump(output / 'receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'exit_code': receipt['exit_code'],
                      'elapsed_seconds': elapsed}, sort_keys=True))
    return receipt['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
