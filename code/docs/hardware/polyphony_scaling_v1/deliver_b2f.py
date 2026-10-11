"""Seal actual N8 identity successor evidence; gate delegated to existing exact-index tool.

Never builds, commits, pushes or accesses devices. Old packages stay unchanged.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
STATUS = 'B2F_N8_IDENTITY_SUCCESSOR_PASS_T061_PARTIAL'
DOCS = ('B2F_IMPLEMENTATION_20261011.md', 'B2F_DELIVERY_20261011.md',
        'M2_HANDOFF_B2F_20261011.md', 'deliver_b2f.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def qualified(receipt):
    if (receipt['b2f']['directed_cases'] != 13 or receipt['b2f']['directed_public_bank_reads'] != 104):
        raise ValueError('DIRECTED_COVERAGE')
    if (receipt['status'] != STATUS or receipt['exit_code'] != 0
            or receipt['candidate_sources_before'] != receipt['candidate_sources_after']
            or receipt['frozen_inputs_before'] != receipt['frozen_inputs_after']
            or receipt['old_seal_and_shared_before'] != receipt['old_seal_and_shared_after']
            or receipt['actual_RTL_capture_reuse'] or receipt['elapsed_seconds'] > 1800):
        raise ValueError('UNQUALIFIED_RUN_OR_IDENTITY')
    for step in receipt['steps']:
        if (step['exit_code'] != step['expected_exit'] or step['timed_out']
                or step.get('elapsed_limit_exceeded')):
            raise ValueError('UNQUALIFIED_STEP:'+step['label'])


def bound(receipt):
    items = receipt['candidate_sources_after'] + receipt['frozen_inputs_after'] + receipt['outputs']
    for step in receipt['steps']:
        items += [step['stdout'], step['stderr']]
    return items


def verify(package):
    manifest = json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    carrier = (package/'evidence.zip.b64').read_bytes()
    raw = base64.b64decode(carrier, validate=True)
    if sha(raw) != manifest['zip_sha256'] or sha(carrier) != manifest['carrier_sha256']:
        raise ValueError('ARCHIVE_SHA')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if (archive.testzip() or len(set(names)) != len(names)
                or set(names) != set(manifest['members'])):
            raise ValueError('ZIP_CRC_DUPLICATE_OR_MEMBERS')
        for name, item in manifest['members'].items():
            data = archive.read(name)
            if len(data) != item['bytes'] or sha(data) != item['sha256']:
                raise ValueError('MEMBER_SHA:'+name)
        receipt = json.loads(archive.read(manifest['qualified_receipt']))
        qualified(receipt)
        for item in bound(receipt):
            data = archive.read(item['path'])
            if len(data) != item['bytes'] or sha(data) != item['sha256']:
                raise ValueError('RECEIPT_BOUND_BYTES:'+item['path'])
        run = str(Path(manifest['qualified_receipt']).parent).replace('\\', '/')
        for response, long_case in ((3, 0), (64, 0), (1, 1)):
            report = json.loads(archive.read(f'{run}/B2F_N8_R{response}_long{long_case}.json'))
            if (report['status'] != STATUS or report['N'] != 8
                    or report['response'] != response or report['long_case'] != bool(long_case)
                    or not report['sample_deadline_qualified']):
                raise ValueError('PROFILE_OR_LIMITATION')
        negatives = json.loads(archive.read(run+'/checker_tests/report.json'))
        if (negatives['exit_code'] or negatives['unit_tests'] != 4
                or len(negatives['complete_N8_negatives']) != 11
                or any(x['expected'] != x['actual'] for x in negatives['complete_N8_negatives'])):
            raise ValueError('CHECKER_TESTS')
        labels = {step['label']: step for step in receipt['steps']}
        step = labels['identity_control_normal_simulate']
        if step['exit_code'] or b'B2F_IDENTITY_CONTROL_PASS cases=13 bank_reads=104' not in archive.read(step['stdout']['path']):
            raise ValueError('DIRECTED_PUBLIC_BANK_TEST')
        for response, long_case in ((3, 0), (64, 0), (1, 1)):
            for suffix in ('compile', 'simulate', 'replay'):
                if labels[f'B2F_N8_R{response}_long{long_case}_{suffix}']['exit_code']:
                    raise ValueError('MISSING_REAL_POSITIVE')
        for label, reason in (('identity_control_old_mask_simulate', b'B2F_BANK_CONTROL_CLOBBER'),
                              ('B1_MUTANT_IGNORE_GENERATION_simulate', b'B2B_STALE_GENERATION_ACCEPTED'),
                              ('B2_MUTANT_GAIN_ZERO_replay', b'MATH_GAIN_PCM')):
            step = labels[label]
            if step['exit_code'] != 1 or reason not in archive.read(step['stdout']['path']):
                raise ValueError('BEHAVIOR_MUTANT_NOT_REJECTED')
    return dict(status='B2F_N8_IDENTITY_SEAL_VERIFIED_T061_PARTIAL', zip_sha256=sha(raw),
                zip_bytes=len(raw), members=len(names), task_complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('seal', 'verify', 'forward'))
    parser.add_argument('--run', type=Path)
    parser.add_argument('--package', type=Path, default=DOC/'B2F_20261011')
    parser.add_argument('--gate', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    package.relative_to(DOC)
    if args.mode == 'verify':
        print(json.dumps(verify(package)))
        return
    if args.mode == 'seal':
        run = args.run.resolve()
        run.relative_to(ROOT/'code/output')
        receipt = json.loads((run/'receipt.json').read_text(encoding='utf-8'))
        qualified(receipt)
        paths = {p for p in run.rglob('*') if p.is_file()}
        paths.update(ROOT/item['path'] for item in bound(receipt))
        paths.update(DOC/name for name in DOCS)
        paths.add(ROOT/'code/software/polyphony_scaling_candidate/inventory.py')
        paths.add(ROOT/'code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/input_manifest.json')
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
        feedback = Path('E:/FPGA/GAOYUNFPGA/Callback2/M2_夜间整机与两项复核回执_给M3_2026-10-11.md')
        if feedback.is_file():
            payload['M2_feedback/'+feedback.name] = feedback.read_bytes()
        for item in bound(receipt):
            if sha(payload[item['path']]) != item['sha256']:
                raise ValueError('SOURCE_CHANGED:'+item['path'])
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
        raw = stream.getvalue()
        carrier = base64.b64encode(raw)
        package.mkdir(parents=True, exist_ok=False)
        dump(package/'manifest.json', dict(stage='B2F_N8_IDENTITY_SUCCESSOR', task_complete=False,
             qualified_receipt=(run/'receipt.json').relative_to(ROOT).as_posix(),
             zip_sha256=sha(raw), carrier_sha256=sha(carrier), zip_bytes=len(raw),
             members={n: dict(bytes=len(d), sha256=sha(d)) for n, d in sorted(payload.items())}))
        (package/'evidence.zip.b64').write_bytes(carrier)
        result = verify(package)
        dump(package/'seal_receipt.json', dict(command=[sys.executable, *sys.argv], exit_code=0,
             sealer_sha256=sha(Path(__file__).read_bytes()), result=result))
        print(json.dumps(result))
        return
    gate = args.gate.resolve()
    gate.relative_to(ROOT/'code/output')
    gated = json.loads((gate/'receipt.json').read_text(encoding='utf-8'))
    out = args.output.resolve()
    out.relative_to(ROOT/'code/output')
    out.mkdir(parents=True, exist_ok=False)
    steps = []

    def git(label, argv):
        result = subprocess.run(['git', *argv], cwd=ROOT, capture_output=True, timeout=90)
        for suffix, data in (('stdout', result.stdout), ('stderr', result.stderr)):
            (out/(label+'.'+suffix+'.bin')).write_bytes(data)
        steps.append(dict(command=['git', *argv], exit_code=result.returncode,
                          stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr)))
        if result.returncode:
            raise ValueError('GIT_COMMAND:'+label)
        return result.stdout.decode('utf-8').strip()

    head = git('head', ['rev-parse', 'HEAD'])
    tree = git('tree', ['rev-parse', 'HEAD^{tree}'])
    branch = git('branch', ['branch', '--show-current'])
    remote = git('remote', ['-c', 'http.version=HTTP/1.1', '-c', 'http.lowSpeedLimit=1', '-c', 'http.lowSpeedTime=30',
                            'ls-remote', 'origin', 'refs/heads/develop']).split()[0]
    if (gated['status'] != 'EXACT_INDEX_SNAPSHOT_9_GATES_PASS' or gated['exit_code']
            or gated['staged_tree'] != tree or branch != 'develop' or head != remote):
        raise ValueError('NOT_EXACT_GATED_PUSH')
    dump(out/'GIT_DELIVERY.json', dict(status='PUSH_VERIFIED', commit=head, tree=tree,
         remote_develop=remote, branch=branch, seal=verify(package), task_complete=False,
         gate_receipt_sha256=sha((gate/'receipt.json').read_bytes()), steps=steps,
         M2_notification='待用户转发，尚未送达'))
    for name in DOCS[:3]:
        shutil.copyfile(DOC/name, out/name)
    for name in ('manifest.json', 'seal_receipt.json'):
        shutil.copyfile(package/name, out/name)
    (out/'B2F_evidence.zip').write_bytes(base64.b64decode(
        (package/'evidence.zip.b64').read_bytes(), validate=True))
    (out/'M2_通知.txt').write_text(f'develop 已推送并核验：{head}\n\n'+
        (DOC/DOCS[2]).read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
    target = out/'M3_T061_N8身份控制返修_交M2_20261011.zip'
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.iterdir()):
            if path.is_file() and path != target:
                archive.write(path, path.name)
        for path in sorted(gate.iterdir()):
            if path.is_file():
                archive.write(path, 'publish_gate/'+path.name)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError('FORWARD_CRC')
    result = dict(status='PUSH_VERIFIED_FORWARD_READY', commit=head, archive=str(target),
                  archive_bytes=target.stat().st_size, archive_sha256=sha(target.read_bytes()),
                  task_complete=False)
    dump(out/'receipt.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
