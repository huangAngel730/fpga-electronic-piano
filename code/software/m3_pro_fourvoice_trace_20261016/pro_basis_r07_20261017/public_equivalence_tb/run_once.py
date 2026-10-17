"""Frozen pure-software group runner, shared read-only by R7-D."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time


def ident(path):
    p = Path(path).resolve()
    raw = p.read_bytes()
    return {'path': str(p), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    spec_path, expected_sha, output = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    assert ident(spec_path)['sha256'] == expected_sha, 'RUN_SPEC_SHA'
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    assert spec['HDL_EDA_hardware_calls'] == 0 and spec['limit_s'] <= 90
    assert ident(sys.executable) == spec['python'], 'PYTHON_CHANGED'
    assert all(ident(i['path']) == i for i in spec['frozen_inputs']), 'FROZEN_INPUT_CHANGED'
    remaining = (datetime(2026, 10, 17, 14, 55, tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds()
    assert remaining > 0, 'TASK_DEADLINE'
    output.mkdir(exist_ok=False, parents=True)
    for i, item in enumerate(spec['frozen_inputs']):
        if item['path'] in spec['snapshot_paths']:
            folder = output / 'frozen'
            folder.mkdir(exist_ok=True)
            (folder / f'{i:03}_{Path(item["path"]).name}').write_bytes(Path(item['path']).read_bytes())
    limit = min(spec['limit_s'], remaining)
    argv = [sys.executable, '-B', '-X', 'utf8', spec['selftest'], str(output / 'products')]
    launch = {'spec': ident(spec_path), 'argv': argv, 'cwd': spec['cwd'],
              'machine': platform.node(), 'start_utc': datetime.now(timezone.utc).isoformat(),
              'limit_s': limit, 'python': ident(sys.executable), 'python_version': sys.version,
              'loaded_python_dependencies': [ident(module.__file__) for module in list(sys.modules.values())
                                             if getattr(module, '__file__', None) and Path(module.__file__).is_file()]}
    write(output / 'LAUNCH.json', launch)
    start = time.monotonic()
    with (output / 'stdout.bin').open('xb') as stdout, (output / 'stderr.bin').open('xb') as stderr:
        child = subprocess.Popen(argv, cwd=spec['cwd'], stdout=stdout, stderr=stderr)
        write(output / 'CONSUMED.json', {'pid': child.pid, 'package': spec['package'],
              'group': spec.get('group', 'INITIAL_01'), 'created_utc': datetime.now(timezone.utc).isoformat()})
        try:
            code = child.wait(timeout=limit)
            timeout = False
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            code, timeout = 124, True
    stable = all(ident(i['path']) == i for i in spec['frozen_inputs'])
    receipt = {**launch, 'pid': child.pid, 'exit_code': code if stable else 65,
               'child_exit_code': code, 'timeout': timeout, 'input_identity_stable': stable,
               'seconds': time.monotonic() - start, 'end_utc': datetime.now(timezone.utc).isoformat(),
               'stdout': ident(output / 'stdout.bin'), 'stderr': ident(output / 'stderr.bin'),
               'products': [ident(p) for p in sorted((output / 'products').rglob('*')) if p.is_file()],
               'HDL_EDA_hardware_calls': 0, 'board_release_allowed': False}
    write(output / 'RECEIPT.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('exit_code', 'seconds', 'input_identity_stable')}))
    return receipt['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
