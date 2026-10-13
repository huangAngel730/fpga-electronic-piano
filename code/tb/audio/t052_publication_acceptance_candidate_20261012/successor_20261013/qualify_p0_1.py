"""Capture only new P0-1 Python/static evidence in a fresh output directory."""
import argparse
import difflib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import schedule_check as audit


def dump(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    audit.need(out.is_relative_to(audit.ROOT / 'code/output') and not out.exists(),
               'OUTPUT_SCOPE_OR_EXISTS')
    out.mkdir(parents=True)
    started = time.monotonic()
    paths = sorted(HERE.glob('*.py')) + [audit.TB, audit.OBSERVER, audit.MEM, audit.PLAN,
             HERE.parent / 'tb_t052_publication_control_128.sv',
             HERE.parent / 't052_public_observer.sv']
    before = {str(path.relative_to(audit.ROOT)): audit.identity(path) for path in paths}
    argv = [sys.executable, '-I', '-B', '-X', 'utf8', str(HERE / 'test_schedule.py'), '-v']
    status, failure = 1, None
    try:
        child = subprocess.run(argv, cwd=audit.ROOT, capture_output=True, timeout=90)
        (out / 'unit.stdout.txt').write_bytes(child.stdout)
        (out / 'unit.stderr.txt').write_bytes(child.stderr)
        audit.need(child.returncode == 0, 'UNIT_EXIT:' + str(child.returncode))
        dump(out / 'source_schedule.json', audit.check())
        for label, old, new in (
                ('driver', HERE.parent / 'tb_t052_publication_control_128.sv', audit.TB),
                ('observer', HERE.parent / 't052_public_observer.sv', audit.OBSERVER)):
            diff = ''.join(difflib.unified_diff(
                old.read_text(encoding='utf-8').splitlines(True),
                new.read_text(encoding='utf-8').splitlines(True),
                fromfile=old.name, tofile=new.name))
            (out / (label + '.diff')).write_text(diff, encoding='utf-8', newline='\n')
        status = 0
    except subprocess.TimeoutExpired as error:
        (out / 'unit.stdout.txt').write_bytes(error.stdout or b'')
        (out / 'unit.stderr.txt').write_bytes(error.stderr or b'')
        failure = 'UNIT_TIMEOUT_90_SECONDS'
    except (OSError, ValueError) as error:
        failure = str(error)
    after = {str(path.relative_to(audit.ROOT)): audit.identity(path) for path in paths}
    if before != after:
        status, failure = 1, 'INPUT_DRIFT'
    if time.monotonic() - started >= 300:
        status, failure = 1, 'TOTAL_BUDGET'
    receipt = {'status': 'P0_1_STATIC_SOFTWARE_PASS' if status == 0 else 'FAIL_PARTIAL',
               'exit_code': status, 'failure': failure, 'machine': socket.gethostname(),
               'argv': argv, 'cwd': str(audit.ROOT), 'inputs_before': before,
               'inputs_after': after,
               'python': {'path': sys.executable, 'version': sys.version,
                          **audit.identity(sys.executable)},
               'artifacts': {p.name: audit.identity(p) for p in sorted(out.iterdir())},
               'elapsed_before_receipt_write_seconds': time.monotonic() - started,
               'total_limit_seconds': 300, 'step_limit_seconds': 90,
               'candidate_HDL_compiles': 0, 'candidate_RTL_runs': 0,
               'EDA_runs': 0, 'T052_complete': False}
    dump(out / 'receipt.json', receipt)
    elapsed = time.monotonic() - started
    if elapsed >= 300:
        # Final success qualification occurs after collection AND receipt write.
        status = 1
        dump(out / 'FAIL_AFTER_RECEIPT.json',
             {'status': 'FAIL_PARTIAL', 'exit_code': 1, 'failure': 'TOTAL_BUDGET',
              'elapsed_after_receipt_write_seconds': elapsed})
    print(json.dumps({'exit_code': status, 'elapsed_after_receipt_write_seconds': elapsed,
                      'output': str(out)}, sort_keys=True))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
