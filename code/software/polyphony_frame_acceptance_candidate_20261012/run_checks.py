"""One bounded isolated stdlib-only software run, no HDL or tool discovery."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOC = ROOT / 'code/docs/hardware/polyphony_frame_acceptance_20261012'
STDLIB = {'argparse', 'ast', 'base64', 'copy', 'hashlib', 'io', 'json', 'os',
          'pathlib', 'shutil', 'subprocess', 'sys', 'tempfile', 'time', 'unittest', 'zipfile'}
LEAVES = {'frame_reference.py', 'trace_check.py', 'vectors.py', 'test_frame.py'}
REFERENCES = [
    ROOT / 'code/docs/M2_已混音PCM帧适配独立候选_2026-10-12.md',
    ROOT / 'code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv',
    Path('E:/FPGA/GAOYUNFPGA/Callback3/M3_T060预检状态及N32帧事务独立代码任务_2026-10-12.md'),
    Path('E:/FPGA/GAOYUNFPGA/Callback3/M3_T060放行条件及N32帧事务新代码任务_20261012/M2_N32R1整机接入差异与833拍合同_2026-10-11.md')]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def identity(paths):
    return {str(p.resolve()): dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes())) for p in paths}


def audit(paths):
    """Deny dependencies outside this new package/stdlib and leaf child launch."""
    local = {p.stem for p in paths}
    imports = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split('.')[0] for a in node.names)
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    raise ValueError('DEPENDENCY_RELATIVE_IMPORT')
                names.add((node.module or '').split('.')[0])
            if isinstance(node, ast.Call):
                called = ast.unparse(node.func)
                if called in ('eval', 'exec', '__import__', 'importlib.import_module', 'os.system', 'os.popen'):
                    raise ValueError('DEPENDENCY_DYNAMIC_EXEC:' + called)
        if names - STDLIB - local:
            raise ValueError('DEPENDENCY_OUTSIDE_CLOSURE:' + str(names - STDLIB - local))
        if path.name in LEAVES and names & {'subprocess', 'os'}:
            raise ValueError('LEAF_PROCESS_LAUNCH_NOT_ALLOWED')
        imports[path.name] = sorted(names)
    return imports


def run(out):
    out = out.resolve()
    out.relative_to(ROOT / 'code/output')
    if out.exists():
        raise ValueError('RUN_REFUSE_OVERWRITE')
    out.mkdir(parents=True)
    start = time.monotonic()
    steps, before, observed = [], {}, []
    failure = None
    try:
        sources = sorted(HERE.glob('*.py'))
        docs = sorted(DOC.glob('*.md'))
        observed = sources + docs + REFERENCES + [Path(sys.executable)]
        before = identity(observed)
        dump(out / 'source_input_before.json', before)
        dump(out / 'closure.json', audit(sources))
        snapshot = out / 'snapshot'
        snapshot.mkdir()
        for path in sources:
            shutil.copyfile(path, snapshot / path.name)
        reference_dir = out / 'readonly_references'
        reference_dir.mkdir()
        for index, path in enumerate(REFERENCES):
            shutil.copyfile(path, reference_dir / (str(index) + '_' + path.name))
        docs_dir = out / 'docs'
        docs_dir.mkdir()
        for path in docs:
            shutil.copyfile(path, docs_dir / path.name)
        dump(out / 'executed_snapshot_before.json', identity(sorted(snapshot.glob('*.py'))))
        dump(out / 'execution_closure.json', audit(sorted(snapshot.glob('*.py'))))

        def command(label, script, args, expected=0, diagnostic=None):
            remaining = 300 - (time.monotonic() - start)
            if remaining <= 0:
                raise ValueError('TOTAL_BUDGET_EXHAUSTED')
            bound = min(90, remaining)
            argv = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(snapshot / script)] + args
            begin = time.monotonic()
            env = os.environ.copy()
            env.pop('PYTHONPATH', None)
            env.pop('PYTHONHOME', None)
            try:
                proc = subprocess.run(argv, cwd=snapshot, env=env, capture_output=True, timeout=bound)
                stdout, stderr, code, timed_out = proc.stdout, proc.stderr, proc.returncode, False
            except subprocess.TimeoutExpired as error:
                stdout, stderr, code, timed_out = error.stdout or b'', error.stderr or b'', -1, True
            (out / (label + '.stdout.txt')).write_bytes(stdout)
            (out / (label + '.stderr.txt')).write_bytes(stderr)
            step = dict(label=label, argv=argv, cwd=str(snapshot), limit_seconds=bound,
                        elapsed_seconds=time.monotonic()-begin, exit_code=code,
                        expected_exit=expected, timed_out=timed_out, diagnostic=diagnostic,
                        stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
            steps.append(step)
            dump(out / 'progress.json', steps)
            print(label + ': exit ' + str(code), flush=True)
            if timed_out or code != expected or (diagnostic and diagnostic.encode() not in stderr):
                raise ValueError('STEP_FAILED:' + label)
            if time.monotonic() - start > 300:
                raise ValueError('TOTAL_BUDGET_EXCEEDED')

        command('01_semantic_and_parser_tests', 'test_frame.py', [])
        corpus = out / 'corpus'
        command('02_generate_complete_traces', 'vectors.py', ['--output', str(corpus)])
        inputs_before = identity(sorted(corpus.glob('*')))
        dump(out / 'trace_input_before.json', inputs_before)
        manifest = json.loads((corpus / 'manifest.json').read_text(encoding='utf-8'))
        for kind, code in (('positives', 0), ('negatives', 1)):
            for name, item in manifest[kind].items():
                command(kind + '_' + name, 'trace_check.py', ['--trace', str(corpus / item['file'])],
                        expected=code, diagnostic=item.get('diagnostic'))
        command('missing_file_refused', 'trace_check.py', ['--trace', str(corpus / 'MISSING.jsonl')], expected=1)
        command('overwrite_refused', 'vectors.py', ['--output', str(corpus)], expected=1,
                diagnostic='VECTORS_REFUSE_OVERWRITE')
        inputs_after = identity(sorted(corpus.glob('*')))
        dump(out / 'trace_input_after.json', inputs_after)
        if inputs_before != inputs_after:
            raise ValueError('TRACE_INPUT_CHANGED')
        snap_after = identity(sorted(snapshot.glob('*.py')))
        dump(out / 'executed_snapshot_after.json', snap_after)
        if json.loads((out / 'executed_snapshot_before.json').read_text(encoding='utf-8')) != snap_after:
            raise ValueError('EXECUTED_SOURCE_CHANGED')
    except Exception as error:
        failure = str(error)
    after = identity(observed) if observed else {}
    dump(out / 'source_input_after.json', after)
    if before != after and failure is None:
        failure = 'SOURCE_OR_READONLY_INPUT_CHANGED'
    elapsed = time.monotonic() - start
    if elapsed > 300 and failure is None:
        failure = 'TOTAL_BUDGET_EXCEEDED'
    receipt = dict(status='FAIL' if failure else 'N32_FRAME_SOFTWARE_L0_L1_PASS',
        exit_code=int(failure is not None), error=failure, steps=steps,
        elapsed_seconds=elapsed, total_limit_seconds=300, per_step_limit_seconds=90,
        source_and_inputs_unchanged=before == after, no_retry=True,
        origin='SYNTHETIC_SOFTWARE_TEST', level='L0/L1', voices_context_only=32,
        positive_cases=11, complete_behavior_negatives=6,
        RTL_run=False, EDA_run=False, math_verified=False, physical_verified=False,
        admission_verified=False, t060_complete=False, t061_complete=False,
        gate_not_in_this_software_budget=True,
        M2_notice='awaiting_user_forward_not_delivered')
    dump(out / 'receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return receipt['exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
