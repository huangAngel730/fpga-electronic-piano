"""Bound repository publication gate to unchanged candidate bytes and raw logs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
COORD = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator'
OUT = COORD / 'PUBLICATION_GATE'


def identity(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def snapshot():
    tracked = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
    paths = {x.decode('utf-8') for x in tracked.split(b'\0') if x}
    planned = json.loads((COORD / 'PUBLICATION_FILES.json').read_text(encoding='utf-8'))
    paths.update(planned['paths'])
    return {p: identity(ROOT / p) for p in sorted(paths) if (ROOT / p).is_file()}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    before = snapshot()
    save(OUT / 'INPUTS_BEFORE.json', before)
    shell = Path('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
    script = Path(__file__).with_name('publication_gate.ps1')
    argv = [str(shell), '-NoProfile', '-File', str(script)]
    started = datetime.now(timezone.utc).isoformat()
    timer = time.monotonic()
    process = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    error = None
    try:
        stdout, stderr = process.communicate(timeout=900)
    except subprocess.TimeoutExpired:
        error = 'GATE_TIMEOUT_900S'
        cleanup = subprocess.run(['C:/Windows/System32/taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                                 stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=15)
        (OUT / 'cleanup.stdout.bin').write_bytes(cleanup.stdout)
        (OUT / 'cleanup.stderr.bin').write_bytes(cleanup.stderr)
        stdout, stderr = process.communicate(timeout=15)
    (OUT / 'stdout.bin').write_bytes(stdout)
    (OUT / 'stderr.bin').write_bytes(stderr)
    readable = stdout.decode('utf-8', errors='replace')
    (OUT / 'stdout.txt').write_text(readable, encoding='utf-8', newline='\n')
    after = snapshot()
    save(OUT / 'INPUTS_AFTER.json', after)
    pass_lines = re.findall(r'^\s*\[PASS\].*$', readable, re.MULTILINE)
    fail_lines = re.findall(r'^\s*\[FAIL\].*$', readable, re.MULTILINE)
    passed = (process.returncode == 0 and error is None and len(pass_lines) == 9
              and not fail_lines and 'All repository checks passed.' in readable and before == after)
    receipt = {'status': 'PASS' if passed else 'FAIL', 'argv': argv, 'cwd': str(ROOT),
               'machine': platform.node(), 'start_utc': started, 'end_utc': datetime.now(timezone.utc).isoformat(),
               'seconds': time.monotonic() - timer, 'exit_code': process.returncode, 'error': error,
               'pass_count': len(pass_lines), 'pass_lines': pass_lines, 'fail_lines': fail_lines,
               'candidate_input_count': len(before), 'input_bytes_unchanged': before == after,
               'input_manifest_before': identity(OUT / 'INPUTS_BEFORE.json'),
               'input_manifest_after': identity(OUT / 'INPUTS_AFTER.json'),
               'shell': {'path': str(shell), **identity(shell)},
               'python': {'path': sys.executable, **identity(Path(sys.executable))},
               'wrapper': {'path': str(script), **identity(script)},
               'raw_stdout': identity(OUT / 'stdout.bin'), 'raw_stderr': identity(OUT / 'stderr.bin'),
               'environment_keys': sorted(os.environ), 'scope': 'repository publication gate; no new Pro DUT or EDA evidence',
               'new_functional_rounds': 0, 'board_release_allowed': False}
    save(OUT / 'GATE_RECEIPT.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('status', 'seconds', 'exit_code', 'pass_count', 'input_bytes_unchanged')}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
