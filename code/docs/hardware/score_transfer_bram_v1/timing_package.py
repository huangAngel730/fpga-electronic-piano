"""Seal timing-repair evidence; finalize only an exact gated pushed tree."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
SEALED = DOC/'TIMING_EVIDENCE_20261010'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def verify():
    raw = base64.b64decode((SEALED/'evidence.zip.b64').read_bytes(), validate=True)
    manifest = json.loads((SEALED/'manifest.json').read_text(encoding='utf-8'))
    if sha(raw) != manifest['zip_sha256']:
        raise ValueError('archive identity')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if set(archive.namelist()) != set(manifest['members']) or archive.testzip():
            raise ValueError('member inventory/CRC')
        for name, item in manifest['members'].items():
            data = archive.read(name)
            if sha(data) != item['sha256'] or len(data) != item['bytes']:
                raise ValueError('member identity: '+name)
    return raw, manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('mode', choices=('seal', 'verify', 'finalize'))
    cli.add_argument('--output', type=Path)
    cli.add_argument('--gate', type=Path)
    cli.add_argument('--integrated-remote', help='Exact M2 commit imported by normal merge')
    cli.add_argument('--build', type=Path,
                     default=ROOT/'code/output/m3_score_bram_timing_build_20261010_04')
    args = cli.parse_args()
    if args.mode == 'verify':
        _, manifest = verify()
        print('PASS_TIMING_EVIDENCE', len(manifest['members']))
        return
    out = args.output.resolve()
    out.relative_to(ROOT/'code/output')
    out.mkdir(parents=True, exist_ok=False)
    if args.mode == 'seal':
        sim = ROOT/'code/output/m3_score_bram_timing_sim_20261010_02'
        build = args.build.resolve()
        build.relative_to(ROOT/'code/output')
        simulation = json.loads((sim/'receipt.json').read_text(encoding='utf-8'))
        audit = json.loads((build/'sta_review.json').read_text(encoding='utf-8'))
        if simulation['status'] != 'PASS_MODULE_SIMULATION_ONLY':
            raise ValueError('simulation prerequisite')
        for name, digest in simulation['output_sha256'].items():
            if sha((sim/name).read_bytes()) != digest:
                raise ValueError('simulation artifact changed: '+name)
        if audit['status'] not in ('PASS_ISOLATED_MODULE_40MHZ_STA', 'INCOMPLETE_PHYSICAL_STA'):
            raise ValueError('final physical review prerequisite')
        if sha((build/'receipt.json').read_bytes()) != audit['build_receipt_sha256']:
            raise ValueError('stale physical review receipt')
        if sha((build/'reviewer_snapshot.py').read_bytes()) != audit['reviewer_sha256']:
            raise ValueError('reviewer snapshot changed')
        for label in ('stdout', 'stderr'):
            if sha((build/('review_tests.'+label+'.bin')).read_bytes()) != audit['unit_tests'][label+'_sha256']:
                raise ValueError('audit test log changed: '+label)
        native = json.loads((build/'receipt.json').read_text(encoding='utf-8'))
        for name, digest in native['output_sha256'].items():
            if sha((build/name).read_bytes()) != digest:
                raise ValueError('post-review native artifact changed: '+name)
        for name, digest in audit.get('output_sha256', {}).items():
            if sha((build/name).read_bytes()) != digest:
                raise ValueError('post-review audit artifact changed: '+name)
        selected = {}
        for rel, digest in simulation['input_sha256'].items():
            path = ROOT/rel
            if sha(path.read_bytes()) != digest:
                raise ValueError('post-simulation identity: '+rel)
            selected[rel] = path
        paths = ('code/rtl/input/score_transfer_bram_candidate',
                 'code/tb/input/score_transfer_bram_candidate',
                 'code/software/score_transfer_bram_test_candidate',
                 'code/docs/hardware/score_transfer_bram_v1')
        for rel in paths:
            for path in (ROOT/rel).rglob('*'):
                if (path.is_file() and '__pycache__' not in path.parts
                        and not any(p.startswith(('EVIDENCE_', 'TIMING_EVIDENCE_'))
                                    for p in path.parts)):
                    selected[path.relative_to(ROOT).as_posix()] = path
        # Preserve all attempts, including unsupported mode, timeout/interruption.
        # No simulator database/cache or unreleased programming file is shipped.
        excluded = []
        for suffix in ('sim_20261010_01', 'sim_20261010_02',
                       'build_20261010_01', 'build_20261010_02',
                       'build_20261010_03', 'build_20261010_04'):
            folder = ROOT/('code/output/m3_score_bram_timing_'+suffix)
            for path in folder.rglob('*'):
                if not path.is_file() or 'work' in path.parts:
                    continue
                if path.suffix.lower() in ('.wlf', '.fs', '.bin', '.posp',
                                           '.db', '.p', '.ga', '.rdb'):
                    if path.suffix.lower() not in ('.wlf', '.bin'):
                        excluded.append(dict(path=path.relative_to(ROOT).as_posix(),
                                             bytes=path.stat().st_size,
                                             sha256=sha(path.read_bytes())))
                    # stdout/stderr .bin are original byte logs, not bitstreams.
                    if not path.name.endswith(('.stdout.bin', '.stderr.bin')):
                        continue
                selected[path.relative_to(ROOT).as_posix()] = path
        old = DOC/'EVIDENCE_20261010/manifest.json'
        selected['prior_delivery_manifest.json'] = old
        manifest = dict(status=audit['status'], complete_system=False,
                        hardware_verified=False, excluded_quarantined_outputs=excluded,
                        final_build=build.relative_to(ROOT).as_posix(),
                        final_build_receipt_sha256=sha((build/'receipt.json').read_bytes()),
                        final_sta_review_sha256=sha((build/'sta_review.json').read_bytes()),
                        final_simulation_receipt_sha256=sha((sim/'receipt.json').read_bytes()),
                        old_evidence_manifest_sha256=sha(old.read_bytes()),
                        members={})
        target = out/'TIMING_EVIDENCE.zip'
        with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as archive:
            for name, path in sorted(selected.items()):
                data = path.read_bytes()
                manifest['members'][name] = dict(bytes=len(data), sha256=sha(data))
                archive.writestr(name, data)
        raw = target.read_bytes()
        manifest.update(zip_bytes=len(raw), zip_sha256=sha(raw))
        SEALED.mkdir(exist_ok=False)
        (SEALED/'evidence.zip.b64').write_bytes(base64.b64encode(raw))
        dump(SEALED/'manifest.json', manifest)
        verify()
        dump(out/'receipt.json', manifest)
        print('SEALED', len(manifest['members']), len(raw), sha(raw))
        return
    raw, manifest = verify()
    gate = args.gate.resolve()
    gate.relative_to(ROOT/'code/output')
    receipt = json.loads((gate/'receipt.json').read_text(encoding='utf-8'))
    if receipt['status'] != 'STAGED_TREE_9_GATES_PASS':
        raise ValueError('nine staged-tree gates prerequisite')
    for item in receipt['inputs_after']:
        if sha((ROOT/item['path']).read_bytes()) != item['sha256']:
            raise ValueError('post-gate identity')

    def git(*command):
        return subprocess.check_output(['git', *command], cwd=ROOT,
                                       timeout=60).decode('utf-8').strip()

    head = git('rev-parse', 'HEAD')
    tree = git('rev-parse', 'HEAD^{tree}')
    remote = git('ls-remote', 'origin', 'refs/heads/develop').split()[0]
    if (head != remote or tree != receipt['staged_tree']
            or git('branch', '--show-current') != 'develop'
            or git('status', '--porcelain')):
        raise ValueError('not exact clean gated pushed develop')
    # Historic simulation also froze four shared bookkeeping files. If M2 has
    # published new entries, preserve their old hashes rather than refilling
    # old evidence; accept only exact bytes from the explicitly imported commit.
    shared_status = {'code/docs/'+name+'.md' for name in
                     ('当前状态', '任务看板', '验证记录', '技术决策记录')}
    with zipfile.ZipFile(io.BytesIO(raw)) as evidence:
        simulation = json.loads(evidence.read(
            'code/output/m3_score_bram_timing_sim_20261010_02/receipt.json'))
    sync_changes = {}
    for name, digest in simulation['input_sha256'].items():
        current = sha((ROOT/name).read_bytes())
        if current == digest:
            continue
        if name not in shared_status or not args.integrated_remote:
            raise ValueError('executed source changed after seal: '+name)
        imported = subprocess.check_output(['git', 'show', args.integrated_remote+':'+name],
                                           cwd=ROOT, timeout=30)
        if sha(imported) != current:
            raise ValueError('shared entry differs from exact imported M2 commit: '+name)
        sync_changes[name] = dict(historical_simulation_sha256=digest,
                                  published_M2_sha256=current)
    notice = (DOC/'TIMING_M2_NOTICE_20261010.md').read_text(encoding='utf-8')
    notice = notice.replace('COMMIT_AFTER_PUSH', head[:7])
    (out/'M2_通知_20261010.txt').write_text(notice, encoding='utf-8', newline='\n')
    result = dict(commit=head, remote_develop=remote, tree=tree,
                  status=manifest['status'], gate_receipt_sha256=sha((gate/'receipt.json').read_bytes()),
                  imported_M2_commit=args.integrated_remote,
                  shared_bookkeeping_changes=sync_changes,
                  executed_functional_inputs_unchanged=True,
                  clean=True, M2_notification='待用户转发，尚未送达')
    dump(out/'GIT_DELIVERY.json', result)
    target = out/'M3_曲谱RAM_40MHz独立时序修复_交M2_20261010.zip'
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('TIMING_EVIDENCE_MANIFEST.json',
                         json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
        with zipfile.ZipFile(io.BytesIO(raw)) as evidence:
            for name in evidence.namelist():
                archive.writestr(name, evidence.read(name))
        for path in out.iterdir():
            if path.is_file() and path != target:
                archive.write(path, path.name)
        for path in gate.iterdir():
            if path.is_file():
                archive.write(path, 'publish_gate/'+path.name)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError('forward archive CRC')
    result['archive'] = dict(path=str(target), bytes=target.stat().st_size,
                             sha256=sha(target.read_bytes()))
    dump(out/'receipt.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
