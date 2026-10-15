"""Bounded task-B software checks and evidence seal; no RTL, serial, or Git writes."""
import argparse
import ast
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
FROZEN = [ROOT / 'code/software/score_transfer_v1/score_transfer.py',
          ROOT / 'code/docs/hardware/score_transfer_v1/PROTOCOL.md',
          ROOT / 'code/docs/M2_T057曲谱播放接口与仲裁静态核对_2026-10-15.md']


def ident(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def snapshot(paths):
    return {str(path): ident(path.read_bytes()) for path in paths}


def runtime_files():
    prefix = Path(sys.base_prefix)
    files = [Path(sys.executable).resolve(), *prefix.glob('*.dll'),
             *prefix.glob('*.zip'), *prefix.glob('DLLs/*.dll'), *prefix.glob('DLLs/*.pyd')]
    files.extend(path for path in (prefix / 'Lib').rglob('*.py') if 'site-packages' not in path.parts)
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    candidate = sorted(path for path in HERE.rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    sources = candidate + FROZEN
    runtime = runtime_files()
    receipt = {'schema': 1, 'scope': 'TASK_B_LOCAL_SOFTWARE_ONLY', 'status': 'FAIL',
               'machine': platform.node(), 'python_version': sys.version,
               'single_step_limit_seconds': 90, 'total_limit_seconds': 300,
               'serial_calls': 0, 'network_calls': 0, 'rtl_calls': 0, 'eda_calls': 0,
               'git_writes': 0, 'external_review_messages': 0,
               'real_user_midi_acceptance': 'PENDING_NO_VERIFIED_LOCAL_FILE_FOUND',
               'git_published': False, 'M2_final_acceptance': 'PENDING', 'steps': []}
    receipt['sources_before'] = snapshot(sources)
    receipt['runtime_before'] = snapshot(runtime)
    save(out / 'plan.json', {'sources': receipt['sources_before'], 'runtime': receipt['runtime_before'],
                           'expected_steps': ['unit_tests', 'demo_import', 'demo_verify', 'demo_bad_readback'],
                           'expected_exits': [0, 0, 0, 1], 'retries': 0,
                           'maximum_step_seconds': 90, 'maximum_total_seconds': 300})

    def step(label, argv, expected=0):
        remaining = 300 - (time.monotonic() - start)
        if remaining <= 0:
            raise TimeoutError('total budget before ' + label)
        started = time.monotonic()
        item = {'label': label, 'argv': argv, 'cwd': str(ROOT), 'expected_exit': expected,
                'timeout_seconds': min(90, remaining), 'timed_out': False}
        try:
            result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=item['timeout_seconds'])
            stdout, stderr = result.stdout, result.stderr
            item['exit_code'] = result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr = exc.stdout or b'', exc.stderr or b''
            item.update(exit_code=None, timed_out=True)
        item['elapsed_seconds'] = time.monotonic() - started
        for name, raw in (('stdout', stdout), ('stderr', stderr)):
            with (out / f'{label}.{name}.bin').open('xb') as stream:
                stream.write(raw)
            item[name] = ident(raw)
        receipt['steps'].append(item)
        save(out / f'{label}.receipt.json', item)
        if item['timed_out'] or item['exit_code'] != expected:
            raise RuntimeError(f'{label}: unexpected exit or timeout')

    try:
        for path in candidate:
            if path.suffix == '.py':
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        receipt['python_ast_files'] = len([path for path in candidate if path.suffix == '.py'])
        py = [str(Path(sys.executable).resolve()), '-I', '-S', '-B', '-X', 'utf8']
        test_code = (
            'import sys,unittest,json;sys.path.insert(0,sys.argv[1]);'
            'suite=unittest.defaultTestLoader.discover(sys.argv[1],pattern="test_*.py");'
            'r=unittest.TextTestRunner(verbosity=2).run(suite);'
            'print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped))));'
            'raise SystemExit(not r.wasSuccessful())')
        step('unit_tests', py + ['-c', test_code, str(HERE)])
        receipt['unit_test_summary'] = json.loads((out / 'unit_tests.stdout.bin').read_bytes().splitlines()[-1])
        demo = bytes.fromhex('4d546864000000060000000101e04d54726b0000000d00903c648360803c0000ff2f00')
        with (out / 'synthetic_development.mid').open('xb') as stream:
            stream.write(demo)
        save(out / 'demo_source.json', {'kind': 'HANDWRITTEN_SYNTHETIC_DEVELOPMENT_FIXTURE_NOT_REAL_USER_FILE',
                                       'input': ident(demo), 'expected_note_samples': [0, 24000]})
        cli = py + [str(HERE / 'midi_import.py')]
        # Isolated Python omits the script directory, so explicitly add only this candidate.
        bootstrap = 'import sys,runpy;sys.path.insert(0,sys.argv[1]);p=sys.argv[1]+"/midi_import.py";sys.argv=[p,*sys.argv[2:]];runpy.run_path(p,run_name="__main__")'
        cli = py + ['-c', bootstrap, str(HERE)]
        step('demo_import', cli + ['import', '--input', str(out / 'synthetic_development.mid'),
             '--output', str(out / 'imported'), '--source-description', 'Handwritten task-B development fixture',
             '--license-note', 'Synthetic test data; not a downloaded song'])
        expected_records = bytes.fromhex('0000000000003c64c05d000001003c00')
        if (out / 'imported/records.bin').read_bytes() != expected_records:
            raise ValueError('independent demo literal records mismatch')
        common = ['--score', str(out / 'imported/score.json'), '--upload', str(out / 'imported/upload.bin')]
        step('demo_verify', cli + ['verify', *common, '--records', str(out / 'imported/records.bin'), '--output', str(out / 'verified')])
        corrupt = bytearray(expected_records)
        corrupt[6] ^= 1
        with (out / 'corrupted_records.bin').open('xb') as stream:
            stream.write(corrupt)
        step('demo_bad_readback', cli + ['verify', *common, '--records', str(out / 'corrupted_records.bin'), '--output', str(out / 'rejected')], 1)
        rejection = json.loads((out / 'rejected/receipt.json').read_bytes())
        if 'READBACK_RECORD_MISMATCH' not in rejection.get('error', '') or 'readback' in rejection:
            raise ValueError('negative demo did not produce the designated readback rejection')
        receipt['status'] = 'SOFTWARE_ACCEPTANCE_PASS_REAL_USER_FILE_PENDING'
    except Exception as exc:
        receipt['failure'] = f'{type(exc).__name__}: {exc}'
    receipt['sources_after'] = snapshot(sources)
    receipt['runtime_after'] = snapshot(runtime)
    if receipt['sources_before'] != receipt['sources_after'] or receipt['runtime_before'] != receipt['runtime_after']:
        receipt['status'] = 'FAIL'
        receipt['failure'] = 'source/runtime identity changed during acceptance'
    receipt['elapsed_seconds'] = time.monotonic() - start
    if receipt['elapsed_seconds'] >= 300:
        receipt['status'], receipt['failure'] = 'FAIL', 'total budget exceeded'
    save(out / 'receipt.json', receipt)
    snapshot_dir = out / 'source_snapshot'
    snapshot_dir.mkdir()
    for path in sources:
        dest = snapshot_dir / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        if ident(raw) != receipt['sources_after'][str(path)]:
            raise ValueError('source changed before sealing: ' + str(path))
        with dest.open('xb') as stream:
            stream.write(raw)
    members = {path.relative_to(out).as_posix(): path.read_bytes() for path in sorted(out.rglob('*')) if path.is_file()}
    manifest = {name: ident(raw) for name, raw in members.items()}
    save(out / 'manifest.json', manifest)
    members['manifest.json'] = (out / 'manifest.json').read_bytes()
    packet = out / 'TASK_B_EVIDENCE.zip'
    with zipfile.ZipFile(packet, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    with zipfile.ZipFile(packet) as archive:
        assert archive.testzip() is None
        for name, expected in manifest.items():
            assert ident(archive.read(name)) == expected
    sealed_elapsed = time.monotonic() - start
    status = receipt['status'] if sealed_elapsed < 300 else 'FAIL_TOTAL_BUDGET_AT_SEAL'
    save(out / 'delivery.json', {'status': status, 'packet': str(packet),
                               **ident(packet.read_bytes()), 'members': len(manifest),
                               'post_seal_total_seconds': sealed_elapsed})
    print(json.dumps({'status': status, 'output': str(out), 'steps': len(receipt['steps'])}))
    return int(status.startswith('FAIL'))


if __name__ == '__main__':
    sys.exit(main())
