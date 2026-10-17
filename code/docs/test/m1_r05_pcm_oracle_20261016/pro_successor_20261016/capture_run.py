"""Capture a new Pro successor Python command without overwriting prior runs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
MODEL = REPO / 'code/model/m1_r05_pcm_oracle_20261016'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def source_hashes():
    files = sorted(MODEL.glob('*.py')) + sorted((MODEL / 'frozen').rglob('*'))
    files += sorted((MODEL / 'pro_successor_20261016').glob('*.py'))
    files += [MODEL / 'DEPENDENCIES.json', HERE / 'TASK_RECEIVED.md', Path(__file__)]
    return {str(p.relative_to(REPO)): sha(p) for p in files if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not argv or Path(argv[0]).resolve() != Path(sys.executable).resolve():
        raise ValueError('THIS_RUNNER_ACCEPTS_THIS_PYTHON_EXECUTABLE_ONLY')
    if not 1 <= args.timeout <= 120 or not args.label.replace('_', '').isalnum():
        raise ValueError('LABEL_OR_BOUND')
    dest = HERE / 'RUNS' / args.label
    dest.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    started = time.time()
    timeout = False
    with (dest / 'stdout.bin').open('xb') as out, (dest / 'stderr.bin').open('xb') as err:
        process = subprocess.Popen(argv, cwd=REPO, stdout=out, stderr=err)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timeout = True
            process.kill()
            code = process.wait()
    after = {name: sha(REPO / name) if (REPO / name).is_file() else None
             for name in before}
    receipt = {
        'schema': 'M1_PRO_PYTHON_RAW_COMMAND_RECEIPT_V1',
        'argv': argv, 'cwd': str(REPO), 'started_epoch': started,
        'elapsed_seconds': time.time() - started, 'exit_code': code,
        'timeout': timeout, 'outer_bound_seconds': args.timeout,
        'python': {'path': sys.executable, 'version': sys.version,
                   'sha256': sha(Path(sys.executable))},
        'machine': platform.node(), 'platform': platform.platform(),
        'source_before_sha256': before, 'source_after_sha256': after,
        'source_unchanged': before == after,
        'source_scope': 'Files present before this command; independently added files are not imports of the running command',
        'streams': {name: {'bytes': (dest / name).stat().st_size,
                            'sha256': sha(dest / name)}
                    for name in ('stdout.bin', 'stderr.bin')},
        'scope': 'NEW_PRO_SOFTWARE_COMMAND_ONLY_NO_HDL_EDA_OR_BOARD',
        'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False,
    }
    write(dest / 'RECEIPT.json', receipt)
    print(json.dumps({key: receipt[key] for key in (
        'argv', 'exit_code', 'timeout', 'elapsed_seconds', 'source_unchanged')},
        ensure_ascii=False))
    for name in ('stdout.bin', 'stderr.bin'):
        print(name + ':\n' + (dest / name).read_bytes().decode('utf-8', errors='replace')[-9000:])
    return code if code else int(not receipt['source_unchanged'])


if __name__ == '__main__':
    raise SystemExit(main())
