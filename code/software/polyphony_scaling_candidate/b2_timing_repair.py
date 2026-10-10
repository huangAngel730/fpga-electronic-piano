"""Replay existing B2 captures only; no RTL tool, synthesis, or device calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from inventory import FROZEN, ROOT

HERE = Path(__file__).resolve().parent
DOC = ROOT/'code/docs/hardware/polyphony_scaling_v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def identities(paths):
    return {str(p): sha(p) for p in sorted(set(paths)) if p.is_file()}


def mutate(raw, tag, operation, field=1):
    """Preserve complete fixture and truthful END counts; change one property."""
    lines = raw.decode('ascii').splitlines()
    if '$finish called at ' in lines[-1]:
        lines.pop()
    rows = [line.split() for line in lines[1:]]
    index = next(i for i, row in enumerate(rows) if row[0] == tag)
    if operation in (-1, 1, 2):
        rows[index][field] = str(int(rows[index][field])+operation)
    elif operation == 'missing':
        rows.pop(index)
        # F deletion changes END's F count, so rejection cannot rely on counts.
        rows[-1][13] = str(int(rows[-1][13])-1)
    elif operation == 'duplicate':
        rows.insert(index+1, list(rows[index]))
        rows[-1][13] = str(int(rows[-1][13])+1)
    rows.sort(key=lambda row: int(row[1]))
    return ('\n'.join([lines[0]]+[' '.join(row) for row in rows])+'\n').encode('ascii')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--feedback', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    out = args.output.resolve()
    out.relative_to(ROOT/'code/output')
    out.mkdir(parents=True, exist_ok=False)
    feedback = args.feedback.resolve()
    protected = list(FROZEN.rglob('*'))
    protected += list((ROOT/'code/rtl/common/polyphony_scaling_candidate').glob('*.sv'))
    protected += list((ROOT/'code/tb/common/polyphony_scaling_candidate').glob('*.sv'))
    protected += list(feedback.rglob('*'))
    protected += [ROOT/'code/docs'/f'{name}.md' for name in
                  ('当前状态', '任务看板', '验证记录', '技术决策记录', '模块接口规范')]
    protected += [ROOT/'code/rtl/board/electronic_piano_top.sv',
                  ROOT/'code/rtl/common/audio_defs_pkg.sv', ROOT/'code/constraints/electronic_piano.cst']
    for folder in ('B0_20261009', 'B1_20261010', 'B2A_20261010', 'B2B_20261010'):
        protected += list((DOC/folder).rglob('*'))
    source_paths = list(HERE.glob('*.py'))
    source_paths += list((ROOT/'code/software/audio_math_acceptance_candidate').glob('*.py'))
    receipt = dict(status='STARTED', started_utc=datetime.now(timezone.utc).isoformat(),
                   argv=sys.argv, cwd=str(ROOT), python=sys.executable,
                   verification='L1 checker tests / existing RTL capture offline L3 replay only',
                   RTL_executed=False, Gowin_executed=False, hardware_operated=False,
                   task_complete=False, steps=[],
                   source_sha256=identities(source_paths), protected_before=identities(protected))
    dump(out/'started.json', receipt)
    started = time.monotonic()

    def command(label, argv, expected=0, diagnostic=None, limit=300):
        begin = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=limit)
            stdout, stderr, code, expired = result.stdout, result.stderr, result.returncode, False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code, expired = error.stdout or b'', error.stderr or b'', None, True
        std, err = out/(label+'.stdout.bin'), out/(label+'.stderr.bin')
        std.write_bytes(stdout)
        err.write_bytes(stderr)
        step = dict(label=label, command=argv, expected_exit=expected, exit_code=code,
                    timed_out=expired, timeout_seconds=limit,
                    elapsed_seconds=time.monotonic()-begin,
                    stdout=str(std), stdout_sha256=sha(std), stderr=str(err), stderr_sha256=sha(err))
        if diagnostic:
            step['expected_diagnostic'] = diagnostic
            step['diagnostic'] = json.loads(stdout)['reason']
        receipt['steps'].append(step)
        dump(out/'progress.json', receipt)
        if expired or code != expected or diagnostic and not step['diagnostic'].startswith(diagnostic):
            raise ValueError('UNEXPECTED_COMMAND_RESULT:'+label)
        print(label+':PASS', flush=True)

    def replay(stage, path, label, diagnostic=None):
        command(label, [sys.executable, '-B', '-X', 'utf8', str(HERE/(
            'b2_check.py' if stage == 'B2a' else 'b2b_check.py')),
            '--input', str(path)], expected=int(diagnostic is not None), diagnostic=diagnostic)

    try:
        # Bind the M2 feedback as received, not by mutable filenames alone.
        manifest = json.loads((feedback/'M2_PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
        for rel, item in manifest.items():
            path = feedback/rel
            if not path.is_file() or path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
                raise ValueError('M2_PACKAGE_IDENTITY:'+rel)
        receipt['feedback_manifest_sha256'] = sha(feedback/'M2_PACKAGE_MANIFEST.json')
        capture_inputs = []
        for stage, folder in (('B2a', 'B2A_20261010'), ('B2b', 'B2B_20261010')):
            sealed = json.loads((DOC/folder/'manifest.json').read_text(encoding='utf-8'))
            bound = {item['member']: item for item in sealed['members']}
            run = ROOT/Path(sealed['qualified_receipt']).parent
            captures = sorted(run.glob('*_N*_simulate.stdout.bin'))
            if len(captures) != (6 if stage == 'B2a' else 2):
                raise ValueError('ORIGINAL_PROFILE_COUNT:'+stage)
            for i, path in enumerate(captures):
                rel = path.relative_to(ROOT).as_posix()
                if sha(path) != bound[rel]['sha256'] or path.stat().st_size != bound[rel]['bytes']:
                    raise ValueError('ORIGINAL_CAPTURE_IDENTITY:'+rel)
                capture_inputs.append(path)
                replay(stage, path, f'{stage}_original_{i}')
        receipt['original_captures'] = identities(capture_inputs)
        for stage in ('B2a', 'B2b'):
            path = feedback/stage/'original_short_positive.capture'
            replay(stage, path, stage+'_M2_original')
            for path in sorted((feedback/stage/'complete_timing_counterexamples').glob('*.capture')):
                name = path.stem
                diagnostic = ('ADVANCE_CLOCK' if stage == 'B2a' and 'advance' in name else
                              'OUTPUT_HANDSHAKE_CLOCK_FIXTURE' if stage == 'B2a' else
                              'ADVANCE_EDGE_OR_MISSING' if '_A_' in name else
                              'LANE_CLOCK_OR_MISSING' if '_L_' in name else 'FIRST_VALID_CLOCK_OR_MISSING')
                replay(stage, path, stage+'_M2_'+name, diagnostic)
        generated = out/'counterexamples'
        generated.mkdir()
        for stage, cases in (
            ('B2a', [('A', -1, 'ADVANCE_CLOCK'), ('A', 1, 'ADVANCE_CLOCK'),
                     ('L', -1, 'LANE_CLOCK'), ('L', 1, 'LANE_CLOCK'),
                     ('O', -1, 'OUTPUT_HANDSHAKE_CLOCK_FIXTURE'),
                     ('O', 1, 'OUTPUT_HANDSHAKE_CLOCK_FIXTURE')]),
            ('B2b', [('A', -1, 'ADVANCE_EDGE_OR_MISSING'), ('A', 1, 'ADVANCE_EDGE_OR_MISSING'),
                     ('L', -1, 'LANE_CLOCK_OR_MISSING'), ('L', 1, 'LANE_CLOCK_OR_MISSING'),
                     ('F', -1, 'FIRST_VALID_CLOCK_OR_MISSING'), ('F', 1, 'FIRST_VALID_CLOCK_OR_MISSING'),
                     ('F', 'missing', 'FIRST_VALID_CLOCK_OR_MISSING'),
                     ('F', 'duplicate', 'DUPLICATE_TAG_AT_EDGE')])):
            raw = (feedback/stage/'original_short_positive.capture').read_bytes()
            for tag, op, diagnostic in cases:
                label = stage+'_'+tag+'_'+str(op)
                path = generated/(label+'.capture')
                path.write_bytes(mutate(raw, tag, op))
                replay(stage, path, label, diagnostic)
        raw = (feedback/'B2b/original_short_positive.capture').read_bytes()
        delayed = generated/'B2b_delayed_P_positive.capture'
        delayed.write_bytes(mutate(raw, 'P', 2))
        replay('B2b', delayed, 'B2b_delayed_P_positive')
        for stage, tag, field, diagnostic in (
            ('B2a', 'O', 6, 'DEADLINE_FLAG'), ('B2b', 'F', 5, 'PCM_OR_DEADLINE'),
            ('B2b', 'P', 5, 'OUTPUT_BACKPRESSURE_STABILITY')):
            path = generated/(stage+'_'+tag+'_bad_deadline.capture')
            raw = (feedback/stage/'original_short_positive.capture').read_bytes()
            path.write_bytes(mutate(raw, tag, 1, field))
            replay(stage, path, path.stem, diagnostic)
        command('B2a_semantic_nine', [sys.executable, '-B', '-X', 'utf8', str(HERE/'b2_negatives.py'),
                '--input', str(feedback/'B2a/original_short_positive.capture'),
                '--output', str(out/'semantic_B2a')])
        command('B2b_semantic_six', [sys.executable, '-B', '-X', 'utf8', str(HERE/'b2b_negatives.py'),
                '--input', str(feedback/'B2b/original_short_positive.capture'),
                '--output', str(out/'semantic_B2b')])
        semantic_reasons = json.loads((out/'semantic_B2b/receipt.json').read_text(encoding='utf-8'))
        for item in semantic_reasons:
            replay('B2b', out/'semantic_B2b'/(item['name']+'.capture'),
                   'B2b_semantic_cli_'+item['name'], item['reason'])
        # Retain the actual previously executed RTL behavior counterexamples.
        # Check their sealed log identities and designated fatal diagnostics;
        # do NOT execute the compiler or simulator again.
        behavior = []
        for stage, folder, cases in (
            ('B2a', 'B2A_20261010', (
                ('B2_mutant_GAIN_ZERO_simulate', 'CHECK_GAIN_FROZEN'),
                ('B2_mutant_SKIP_LAST_simulate', 'CHECK_ALL_VOICES'))),
            ('B2b', 'B2B_20261010', (
                ('B1_MUTANT_IGNORE_GENERATION_simulate', 'B2B_STALE_GENERATION_ACCEPTED'),
                ('B2_MUTANT_GAIN_ZERO_simulate', None)))):
            seal = json.loads((DOC/folder/'manifest.json').read_text(encoding='utf-8'))
            members = {item['member']: item for item in seal['members']}
            old = json.loads((ROOT/seal['qualified_receipt']).read_text(encoding='utf-8'))
            for label, reason in cases:
                step = next(s for s in old['steps'] if s['label'] == label)
                logs = {}
                for stream in ('stdout', 'stderr'):
                    path = ROOT/step[stream]['path']
                    bound = members[path.relative_to(ROOT).as_posix()]
                    if sha(path) != bound['sha256'] or path.stat().st_size != bound['bytes']:
                        raise ValueError('BEHAVIOR_LOG_IDENTITY:'+label)
                    logs[str(path)] = sha(path)
                if (step['timed_out'] or step['exit_code'] != step['expected_exit']
                        or reason and reason not in (ROOT/step['stdout']['path']).read_text(encoding='utf-8')):
                    raise ValueError('ORIGINAL_BEHAVIOR_DIAGNOSTIC:'+label)
                behavior.append(dict(stage=stage, label=label, original_exit=step['exit_code'],
                                     designated_fatal=reason, logs=logs, RTL_rerun=False))
                if reason is None:
                    replay(stage, ROOT/step['stdout']['path'],
                           'B2b_original_gain_behavior', 'MATH_GAIN_PCM')
        receipt['original_behavior_audit'] = behavior
        for pattern in ('test_b2_timing.py', 'test_b2_checker.py', 'test_candidate.py'):
            command(pattern[:-3], [sys.executable, '-B', '-X', 'utf8', '-m', 'unittest', 'discover',
                    '-s', str(HERE), '-p', pattern, '-v'])
        receipt['status'] = 'PASS_B2_TIMING_CHECKER_REPAIR_T061_PARTIAL'
    except Exception as error:
        receipt.update(status='FAIL', error=type(error).__name__+':'+str(error))
    receipt['source_after'] = identities(source_paths)
    receipt['protected_after'] = identities(protected)
    if receipt['source_after'] != receipt['source_sha256'] or receipt['protected_after'] != receipt['protected_before']:
        receipt.update(status='FAIL', error='INPUT_CHANGED')
    receipt['elapsed_seconds'] = time.monotonic()-started
    receipt['exit_code'] = int(receipt['status'] == 'FAIL')
    receipt['outputs'] = identities(p for p in out.rglob('*') if p.name != 'receipt.json')
    dump(out/'receipt.json', receipt)
    print(receipt['status'], flush=True)
    return receipt['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
