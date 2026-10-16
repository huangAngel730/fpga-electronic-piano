"""Bounded software-only delta, original stdout/stderr and source hashes retained."""
import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from analyze_existing import ROOT, identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not args.run_id.isalnum():
        raise ValueError('RUN_ID_MUST_BE_ALNUM')
    out = ROOT / 'code/docs/test/m3_r05_functional_integration_20261015/chat8_20261016' / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    src = Path(__file__).parent
    source_before = [identity(p) for p in sorted(src.glob('*.py'))]
    commands = [
        ('synthetic_tests', [sys.executable, '-B', '-X', 'utf8', str(src / 'test_analysis.py')]),
        ('actual_input_delta', [sys.executable, '-B', '-X', 'utf8', str(src / 'analyze_existing.py'),
                                '--out', str(out / 'ANALYSIS.json')]),
    ]
    calls = []
    start = time.monotonic()
    for name, command in commands:
        remaining = 180 - (time.monotonic() - start)
        if remaining <= 0:
            raise TimeoutError('SOFTWARE_TOTAL_BUDGET')
        begin = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(command, cwd=ROOT, capture_output=True,
                                  timeout=min(90, remaining), check=False)
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = exc.stdout or b'', exc.stderr or b'', None
            timed_out = True
        stdout_path, stderr_path = out / (name + '.stdout.log'), out / (name + '.stderr.log')
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        calls.append({'argv': command, 'cwd': str(ROOT), 'exit_code': code,
                      'timeout': timed_out, 'elapsed_s': time.monotonic() - begin,
                      'stdout': identity(stdout_path), 'stderr': identity(stderr_path)})
        if timed_out or code != 0:
            break
    source_after = [identity(p) for p in sorted(src.glob('*.py'))]
    passed = len(calls) == 2 and all(c['exit_code'] == 0 for c in calls) and source_before == source_after
    result = {'status': 'SOFTWARE_DELTA_COMPLETE_MATH_PARTIAL' if passed else 'SOFTWARE_DELTA_FAILED',
              'machine': platform.node(), 'python': identity(Path(sys.executable)),
              'source_before': source_before, 'source_after': source_after,
              'calls': calls, 'software_subprocess_calls': len(calls),
              'ModelSim_calls': 0, 'Gowin_calls': 0, 'old_C_tests_rerun': 0,
              'board_release_allowed': False, 'wall_s': time.monotonic() - start}
    (out / 'RUN_RECEIPT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result['status'])
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
