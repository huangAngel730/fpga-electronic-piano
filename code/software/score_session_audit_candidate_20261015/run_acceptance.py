"""Task-local software checks and evidence seal; no old专项, device or Git calls."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REFERENCES = [ROOT / 'code/software/score_transfer_v1/score_transfer.py',
              ROOT / 'code/docs/hardware/score_transfer_v1/PROTOCOL.md',
              ROOT / 'code/rtl/input/score_transfer_bram_candidate/score_transfer_bram_candidate.sv']


def ident(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def snapshot(paths):
    return {str(path): ident(path.read_bytes()) for path in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    sources = sorted(path for path in HERE.iterdir() if path.is_file()) + REFERENCES
    prefix = Path(sys.base_prefix)
    runtime = sorted(set([Path(sys.executable).resolve(), *prefix.glob('*.dll'),
                         *prefix.glob('*.zip'), *prefix.glob('DLLs/*.dll'), *prefix.glob('DLLs/*.pyd'),
                         *(path for path in (prefix / 'Lib').rglob('*.py') if 'site-packages' not in path.parts)]))
    receipt = {'status': 'FAIL', 'machine': platform.node(), 'python_version': sys.version,
               'steps': [], 'scope': 'OFFLINE_SOFTWARE_FIXTURES_ONLY', 'hardware_pass_claim': False,
               'rtl_calls': 0, 'device_calls': 0, 'git_writes': 0, 'external_review_messages': 0,
               'single_step_limit_seconds': 90, 'total_limit_seconds': 300,
               'sources_before': snapshot(sources), 'runtime_before': snapshot(runtime)}
    save(out / 'plan.json', {'steps': ['unit_tests', 'success_trace', 'recovery_trace', 'wrong_ack_reject'],
                           'expected_exits': [0, 0, 0, 1], 'single_step_seconds': 90,
                           'total_seconds': 300, 'retries': 0,
                           'source_sha': receipt['sources_before'], 'runtime_sha': receipt['runtime_before']})

    def step(label, argv, expected):
        remaining = 300 - (time.monotonic() - start)
        if remaining <= 0:
            raise TimeoutError('outer deadline')
        item = {'label': label, 'argv': argv, 'cwd': str(ROOT), 'expected_exit': expected,
                'timeout_seconds': min(90, remaining), 'timed_out': False}
        then = time.monotonic()
        try:
            completed = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=item['timeout_seconds'])
            stdout, stderr = completed.stdout, completed.stderr
            item['exit_code'] = completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr = exc.stdout or b'', exc.stderr or b''
            item.update(timed_out=True, exit_code=None)
        item['elapsed_seconds'] = time.monotonic() - then
        for stream, data in (('stdout', stdout), ('stderr', stderr)):
            with (out / f'{label}.{stream}.bin').open('xb') as handle:
                handle.write(data)
            item[stream] = ident(data)
        receipt['steps'].append(item)
        save(out / f'{label}.receipt.json', item)
        if item['timed_out'] or item['exit_code'] != expected:
            raise ValueError(label + ': unexpected exit or timeout')

    try:
        for path in sources:
            if path.suffix == '.py':
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        py = [str(Path(sys.executable).resolve()), '-I', '-S', '-B', '-X', 'utf8']
        test_code = ('import sys,unittest,json;sys.path.insert(0,sys.argv[1]);'
                     's=unittest.defaultTestLoader.discover(sys.argv[1],pattern="test_*.py");'
                     'r=unittest.TextTestRunner(verbosity=2).run(s);'
                     'print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped))));'
                     'raise SystemExit(not r.wasSuccessful())')
        step('unit_tests', py + ['-c', test_code, str(HERE)], 0)
        receipt['unit_test_summary'] = json.loads((out / 'unit_tests.stdout.bin').read_bytes().splitlines()[-1])
        sys.path.insert(0, str(HERE))
        from session_fixtures import build_success, build_recovery
        from wire import decode_frame, encode_frame
        good, recovery = build_success(), build_recovery()
        save(out / 'success.json', good)
        save(out / 'recovery.json', recovery)
        bad = copy.deepcopy(good)
        item = bad['attempts'][0]
        decoded = decode_frame(bytes.fromhex(item['response_hex']))
        item['response_hex'] = encode_frame(decoded['command'], decoded['session'] ^ 1,
                                            decoded['seq'], decoded['offset'], decoded['payload']).hex()
        save(out / 'wrong_ack.json', bad)
        bootstrap = ('import sys,runpy;sys.path.insert(0,sys.argv[1]);'
                     'p=sys.argv[1]+"/session_audit.py";sys.argv=[p,*sys.argv[2:]];runpy.run_path(p,run_name="__main__")')
        cli = py + ['-c', bootstrap, str(HERE)]
        for label, trace, expected in (('success_trace', 'success', 0), ('recovery_trace', 'recovery', 0), ('wrong_ack_reject', 'wrong_ack', 1)):
            step(label, cli + ['--trace', str(out / (trace + '.json')), '--output', str(out / label)], expected)
        rejection = json.loads((out / 'wrong_ack_reject/receipt.json').read_bytes())
        if 'RESPONSE_IDENTITY' not in rejection.get('error', '') or 'audit' in rejection:
            raise ValueError('wrong ACK did not produce designated identity rejection')
        receipt['status'] = 'OFFLINE_SESSION_TOOL_SOFTWARE_PASS'
    except Exception as exc:
        receipt['failure'] = f'{type(exc).__name__}: {exc}'
    receipt['sources_after'], receipt['runtime_after'] = snapshot(sources), snapshot(runtime)
    if receipt['sources_after'] != receipt['sources_before'] or receipt['runtime_after'] != receipt['runtime_before']:
        receipt.update(status='FAIL', failure='source/runtime drift')
    receipt['elapsed_seconds'] = time.monotonic() - start
    save(out / 'receipt.json', receipt)
    source_dir = out / 'source_snapshot'
    for path in sources:
        destination = source_dir / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        if ident(raw) != receipt['sources_after'][str(path)]:
            raise ValueError('source changed before seal')
        with destination.open('xb') as handle:
            handle.write(raw)
    members = {path.relative_to(out).as_posix(): path.read_bytes() for path in out.rglob('*') if path.is_file()}
    manifest = {name: ident(raw) for name, raw in members.items()}
    save(out / 'manifest.json', manifest)
    members['manifest.json'] = (out / 'manifest.json').read_bytes()
    packet = out / 'SESSION_AUDIT_EVIDENCE.zip'
    with zipfile.ZipFile(packet, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    with zipfile.ZipFile(packet) as archive:
        assert archive.testzip() is None
        assert all(ident(archive.read(name)) == expected for name, expected in manifest.items())
    elapsed = time.monotonic() - start
    status = receipt['status'] if elapsed < 300 else 'FAIL_TOTAL_BUDGET'
    save(out / 'delivery.json', {'status': status, 'packet': str(packet), **ident(packet.read_bytes()),
                               'members': len(manifest), 'total_elapsed_seconds': elapsed})
    print(json.dumps({'status': status, 'output': str(out)}))
    return int(status.startswith('FAIL'))


if __name__ == '__main__':
    sys.exit(main())
