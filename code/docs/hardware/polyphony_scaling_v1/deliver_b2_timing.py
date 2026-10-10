"""Seal checker-only replay, gate exact index snapshot, package verified push.

Never commits/pushes, runs B2 RTL/Gowin, or touches a device. Existing repository
gates include their mandatory short T007/T019 simulations. Dirty RAM work stays
outside the index snapshot and is neither stashed nor changed.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
STATUS = 'PASS_B2_TIMING_CHECKER_REPAIR_T061_PARTIAL'
DOCUMENTS = ('B2_TIMING_REPAIR_20261010.md', 'M2_HANDOFF_B2_TIMING_REPAIR_20261010.md',
             'deliver_b2_timing.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def verify(package):
    manifest = json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    carrier = (package/'evidence.zip.b64').read_bytes()
    raw = base64.b64decode(carrier, validate=True)
    if sha(carrier) != manifest['carrier_sha256'] or sha(raw) != manifest['zip_sha256']:
        raise ValueError('ARCHIVE_SHA')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() or len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError('ZIP_CRC_OR_DUPLICATE')
        if set(archive.namelist()) != set(manifest['members']):
            raise ValueError('MEMBER_SET')
        for name, item in manifest['members'].items():
            data = archive.read(name)
            if len(data) != item['bytes'] or sha(data) != item['sha256']:
                raise ValueError('MEMBER_SHA:'+name)
        receipt = json.loads(archive.read(manifest['qualified_receipt']))
        if (receipt['status'] != STATUS or receipt['exit_code'] != 0
                or receipt['source_sha256'] != receipt['source_after']
                or receipt['protected_before'] != receipt['protected_after']):
            raise ValueError('UNQUALIFIED_REPLAY')
        for step in receipt['steps']:
            if step['exit_code'] != step['expected_exit'] or step['timed_out']:
                raise ValueError('UNQUALIFIED_STEP')
        # Bind receipt-referenced bytes to actual members, not only a new list.
        bound = dict(receipt['source_sha256'], **receipt['outputs'])
        bound.update(receipt['original_captures'])
        for path, digest in bound.items():
            name = Path(path).relative_to(ROOT).as_posix()
            if sha(archive.read(name)) != digest:
                raise ValueError('RECEIPT_MEMBER_SHA:'+name)
    return {'status': 'B2_TIMING_SEAL_VERIFIED_T061_PARTIAL', 'members': len(manifest['members']),
            'zip_sha256': sha(raw), 'zip_bytes': len(raw), 'task_complete': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('seal', 'verify', 'gate', 'finalize'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--feedback', type=Path)
    parser.add_argument('--package', type=Path, default=DOC/'B2_TIMING_REPAIR_20261010_02')
    parser.add_argument('--gate', type=Path)
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
        if receipt['status'] != STATUS:
            raise ValueError('UNQUALIFIED_RUN')
        paths = {p for p in run.rglob('*') if p.is_file()}
        paths.update(Path(p) for p in receipt['source_sha256'])
        paths.update(Path(p) for p in receipt['original_captures'])
        paths.update(Path(p) for item in receipt['original_behavior_audit'] for p in item['logs'])
        paths.update(DOC/name for name in DOCUMENTS)
        # Keep source calendar anchors, original seals and read-only ROMs.
        paths.update(p for p in (ROOT/'code/rtl/common/polyphony_scaling_candidate').glob('*.sv'))
        paths.update(p for p in (ROOT/'code/tb/common/polyphony_scaling_candidate').glob('*.sv'))
        for folder in ('B2A_20261010', 'B2B_20261010'):
            paths.add(DOC/folder/'manifest.json')
        frozen = ROOT/'code/rtl/138K_try/hold_trials_20261005/L_locations_guard065'
        paths.add(frozen/'input_manifest.json')
        paths.update((frozen/'rom').glob('*.mem'))
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
        feedback = args.feedback.resolve()
        payload.update({'M2_feedback/'+p.relative_to(feedback).as_posix(): p.read_bytes()
                        for p in feedback.rglob('*') if p.is_file()})
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
        raw = stream.getvalue()
        carrier = base64.b64encode(raw)
        manifest = dict(stage='B2_TIMING_CHECKER_REPAIR', task_complete=False,
                        qualified_receipt=(run/'receipt.json').relative_to(ROOT).as_posix(),
                        zip_sha256=sha(raw), carrier_sha256=sha(carrier), zip_bytes=len(raw),
                        members={n: dict(bytes=len(d), sha256=sha(d)) for n, d in sorted(payload.items())})
        package.mkdir(parents=True, exist_ok=False)
        dump(package/'manifest.json', manifest)
        (package/'evidence.zip.b64').write_bytes(carrier)
        result = verify(package)
        dump(package/'seal_receipt.json', dict(command=[sys.executable, *sys.argv], exit_code=0,
                                             sealer_sha256=sha(Path(__file__).read_bytes()), result=result))
        print(json.dumps(result))
        return
    out = args.output.resolve()
    out.relative_to(ROOT/'code/output')
    out.mkdir(parents=True, exist_ok=False)
    steps = []

    def command(label, argv, env=None, cwd=ROOT):
        begin = time.monotonic()
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=900)
        for name, data in (('stdout', result.stdout), ('stderr', result.stderr)):
            (out/(label+'.'+name+'.bin')).write_bytes(data)
        steps.append(dict(label=label, command=argv, cwd=str(cwd), exit_code=result.returncode,
                          elapsed_seconds=time.monotonic()-begin,
                          stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr)))
        dump(out/'progress.json', steps)
        if result.returncode:
            dump(out/'receipt.json', dict(status='FAIL', phase=label,
                                         exit_code=result.returncode, steps=steps))
            raise ValueError('COMMAND_FAIL:'+label)
        return result.stdout

    if args.mode == 'gate':
        tree = command('staged_tree', ['git', 'write-tree']).decode().strip()
        snapshot = out/'snapshot'
        snapshot.mkdir()
        command('export_index', ['git', '-c', 'core.longpaths=true', 'checkout-index',
                                '--all', '--prefix', str(snapshot)+'/' ])
        index = command('index_path', ['git', 'rev-parse', '--git-path', 'index']).decode().strip()
        env = os.environ.copy()
        env.update(GIT_DIR=str(ROOT/'.git'), GIT_WORK_TREE=str(snapshot),
                   GIT_INDEX_FILE=str((ROOT/index).resolve()), PYTHONDONTWRITEBYTECODE='1',
                   PYTHONUTF8='1', GIT_CONFIG_COUNT='1',
                   GIT_CONFIG_KEY_0='core.longpaths', GIT_CONFIG_VALUE_0='true')
        env['PATH'] = str(Path(sys.executable).parent)+os.pathsep+env['PATH']
        raw = command('repo_gates', [shutil.which('pwsh') or shutil.which('powershell'),
                      '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                      str(snapshot/'code/scripts/check_repo.ps1')], env, snapshot)
        if raw.count(b'[PASS]') != 9 or b'All repository checks passed.' not in raw:
            raise ValueError('NOT_NINE_REAL_GATES')
        after = command('index_after', ['git', 'write-tree']).decode().strip()
        if after != tree:
            raise ValueError('INDEX_CHANGED_DURING_GATE')
        dump(out/'receipt.json', dict(status='EXACT_INDEX_SNAPSHOT_9_GATES_PASS', exit_code=0,
              staged_tree=tree, snapshot=str(snapshot), steps=steps,
              dirty_RAM_excluded=True, B2_RTL_rerun=False, Gowin_run=False))
        print('EXACT_INDEX_SNAPSHOT_9_GATES_PASS:'+tree)
        return
    gate = args.gate.resolve()
    gate.relative_to(ROOT/'code/output')
    gated = json.loads((gate/'receipt.json').read_text(encoding='utf-8'))
    head = command('head', ['git', 'rev-parse', 'HEAD']).decode().strip()
    tree = command('tree', ['git', 'rev-parse', 'HEAD^{tree}']).decode().strip()
    branch = command('branch', ['git', 'branch', '--show-current']).decode().strip()
    remote = command('remote', ['git', 'ls-remote', 'origin', 'refs/heads/develop']).decode().split()[0]
    dirty = command('remaining_work', ['git', 'status', '--short']).decode('utf-8')
    if (gated['status'] != 'EXACT_INDEX_SNAPSHOT_9_GATES_PASS' or head != remote
            or tree != gated['staged_tree'] or branch != 'develop'):
        raise ValueError('NOT_EXACT_GATED_PUSH')
    result = dict(commit=head, remote_develop=remote, tree=tree, branch=branch,
                  M2_notification='待用户转发，尚未送达', task_complete=False,
                  remaining_uncommitted_work=dirty, seal=verify(package),
                  gate_receipt_sha256=sha((gate/'receipt.json').read_bytes()), steps=steps)
    dump(out/'GIT_DELIVERY.json', result)
    for name in DOCUMENTS[:2]:
        shutil.copyfile(DOC/name, out/name)
    manifest = json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    (out/'B2_timing_evidence.zip').write_bytes(base64.b64decode((package/'evidence.zip.b64').read_bytes(), validate=True))
    for name in ('manifest.json', 'seal_receipt.json'):
        shutil.copyfile(package/name, out/name)
    notice = (f'M2，B2a/B2b时间checker最小返修已推送develop：{head[:7]}。\n'
              +(DOC/DOCUMENTS[1]).read_text(encoding='utf-8'))
    (out/'M2_通知.txt').write_text(notice, encoding='utf-8', newline='\n')
    target = out/'M3_T061_B2时间checker返修_交M2_20261010.zip'
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.iterdir()):
            if path.is_file() and path != target:
                archive.write(path, path.name)
        for path in sorted(gate.iterdir()):
            if path.is_file():
                archive.write(path, 'publish_gate/'+path.name)
        prior = ROOT/'code/output/m3_t061_b2_timing_publish_gate_20261010_01'
        if prior.is_dir():
            for path in sorted(prior.iterdir()):
                if path.is_file():
                    archive.write(path, 'prior_export_failure_not_gate_PASS/'+path.name)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError('FORWARD_CRC')
    dump(out/'receipt.json', dict(status='PUSH_VERIFIED_FORWARD_READY', commit=head,
                                 archive=str(target), archive_sha256=sha(target.read_bytes()),
                                 archive_bytes=target.stat().st_size, task_complete=False))
    print(json.dumps(dict(commit=head, archive=str(target), zip_sha256=manifest['zip_sha256']), ensure_ascii=False))


if __name__ == '__main__':
    main()
