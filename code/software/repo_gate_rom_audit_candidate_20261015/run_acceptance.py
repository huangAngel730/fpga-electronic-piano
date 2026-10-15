"""Capture isolated software tests and immutable input/tool evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def identity(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != ROOT / 'code/output' or not output.name.startswith('repo_gate_rom_audit_'):
        parser.error('require fresh task output under code/output')
    output.mkdir(exist_ok=False)
    expected_path = args.expected.resolve()
    before = {}
    try:
        frozen = json.loads(expected_path.read_text(encoding='utf-8'))
        paths = {str(p): p for p in HERE.glob('*.py')}
        paths[str(expected_path)] = expected_path
        paths[str(Path(sys.executable))] = Path(sys.executable)
        for key in frozen['files']:
            paths[str(ROOT / key)] = ROOT / key
        for key in frozen['tools']:
            path = Path(frozen['tool_root']) / key
            paths[str(path)] = path
        for key, path in sorted(paths.items()):
            before[key] = identity(path)
        for group, base in (('files', ROOT), ('tools', Path(frozen['tool_root']))):
            for relative, expected_sha in frozen[group].items():
                if before[str(base / relative)]['sha256'] != expected_sha:
                    raise ValueError(f'INDEPENDENT_FROZEN_IDENTITY_DRIFT: {relative}')
    except Exception as error:
        (output / 'stdout.log').write_bytes(b'')
        (output / 'stderr.log').write_text(traceback.format_exc(), encoding='utf-8')
        receipt = {'schema': 1, 'scope': 'ROM_GATE_SOFTWARE_SELFTEST',
                   'status': 'PREFLIGHT_REJECT', 'passed': False, 'exit_code': 2,
                   'error': type(error).__name__ + ':' + str(error),
                   'before_partial': before, 'inputs_complete': False, 'tool_calls': 0,
                   'logs': {p.name: identity(p) for p in output.glob('*.log')}}
        (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'passed': False, 'exit_code': 2, 'receipt': str(output / 'receipt.json')}))
        return 2
    argv = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c',
            'import sys,unittest;sys.path.insert(0,sys.argv[1]);'
            's=unittest.defaultTestLoader.discover(sys.argv[1],pattern="test_*.py");'
            'r=unittest.TextTestRunner(verbosity=2).run(s);'
            'raise SystemExit(not r.wasSuccessful())', str(HERE)]
    started = time.monotonic()
    code, timed_out = None, False
    try:
        with (output / 'stdout.log').open('wb') as stdout, (output / 'stderr.log').open('wb') as stderr:
            env = dict(os.environ, ROM_GATE_EXPECTED=str(expected_path))
            result = subprocess.run(argv, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=90, check=False)
            code = result.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
    after = {key: identity(p) for key, p in sorted(paths.items())}
    receipt = {'schema': 1, 'scope': 'ROM_GATE_SOFTWARE_SELFTEST',
               'argv': argv, 'cwd': str(ROOT), 'exit_code': code,
               'timeout': timed_out, 'bound_seconds': 90,
               'seconds': time.monotonic() - started,
               'before': before, 'after': after,
               'passed': code == 0 and not timed_out and before == after,
               'eda_calls': 0, 'hardware_calls': 0,
               'external_review_messages': 0}
    receipt['logs'] = {p.name: identity(p) for p in output.glob('*.log')}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': receipt['passed'], 'exit_code': code,
                      'receipt': str(output / 'receipt.json')}))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
