"""Freeze a self-reviewed diagnostic preparation; never execute HDL tools."""
import argparse
import base64
from datetime import datetime, timezone
import difflib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def seal(prepared, evidence, target):
    prepared, target = Path(prepared).resolve(), Path(target).resolve()
    require(prepared.is_relative_to(ROOT / 'code/output'), 'PREPARED_SCOPE')
    require(target.is_relative_to(HERE) and target != HERE, 'TARGET_SCOPE')
    require(not target.exists(), 'TARGET_EXISTS')
    members, cached = {}, {}

    def add(path, name):
        path = Path(path).resolve()
        require(name not in members, 'DUPLICATE_MEMBER:' + name)
        raw = path.read_bytes()
        members[name] = raw
        cached[path] = raw

    def tree(root, prefix):
        root = Path(root).resolve()
        require(root.is_relative_to(ROOT), 'EVIDENCE_SCOPE')
        require(root.is_dir(), 'MISSING_DIRECTORY:' + str(root))
        for path in sorted(root.rglob('*')):
            if path.is_file() and path.suffix not in ('.pyc', '.vvp'):
                add(path, prefix + '/' + path.relative_to(root).as_posix())

    tree(prepared, 'prepared')
    plan = json.loads(members['prepared/plan.json'])
    config = json.loads(members['prepared/verbose_compile_config.json'])
    require(config['plan'] == identity(members['prepared/plan.json']), 'CONFIG_BINDING')
    launch_raw = members['prepared/verbose_launch.json']
    launch = json.loads(launch_raw)
    require({k: launch['plan'][k] for k in ('bytes', 'sha256')} ==
            identity(members['prepared/plan.json']), 'LAUNCH_PLAN_BINDING')
    require({k: launch['config'][k] for k in ('bytes', 'sha256')} ==
            identity(members['prepared/verbose_compile_config.json']),
            'LAUNCH_CONFIG_BINDING')
    capsule = Path(plan['capsule_root']).resolve()
    actual_members = {p.relative_to(capsule).as_posix()
                      for p in capsule.rglob('*') if p.is_file()}
    require(actual_members == set(plan['capsule_files']), 'CAPSULE_MEMBERS')
    for relative, expected in plan['capsule_files'].items():
        require(identity(members['prepared/capsule/' + relative]) == {
            k: expected[k] for k in ('bytes', 'sha256')}, 'CAPSULE_SHA:' + relative)
    execution = Path(config['execution_output']).resolve()
    outputs = [execution, Path(str(execution) + '_parent'),
               Path(str(execution) + '_parent.entry.json')]
    require(all(not p.exists() for p in outputs), 'ALREADY_EXECUTED')
    for root in evidence:
        tree(root, 'evidence/' + Path(root).name)
    for name in ('a_verbose_compile_plan.py', 'a_verbose_compile_diagnostic.py',
                 'a_verbose_launch.py', 'a_verbose_package.py',
                 'test_verbose_compile_plan_20261014.py',
                 'DIAGNOSIS_AND_REPAIR_20261014.md', 'README_A.md'):
        add(HERE / name, 'source/' + name)
    for path in sorted(HERE.glob('test_verbose*')):
        if path.is_file() and 'source/' + path.name not in members:
            add(path, 'source/' + path.name)
    base = Path(plan['base_plan']['path'])
    add(base, 'baseline/base_plan.json')
    require(identity(members['baseline/base_plan.json']) == {
        k: plan['base_plan'][k] for k in ('bytes', 'sha256')}, 'BASE_SHA')
    old_dir = HERE / 'SEALED_VERBOSE_COMPILE_PLAN_R01'
    old_raw = base64.b64decode((old_dir / 'snapshot.zip.b64').read_bytes(), validate=False)
    old_seal = json.loads((old_dir / 'seal.json').read_bytes())
    require(identity(old_raw) == old_seal['snapshot'], 'OLD_SNAPSHOT_SHA')
    with zipfile.ZipFile(io.BytesIO(old_raw)) as old:
        diffs = []
        for name in ('a_verbose_compile_plan.py', 'a_verbose_compile_diagnostic.py',
                     'test_verbose_compile_plan_20261014.py'):
            old_name = 'workspace/code/software/t061_allocator_reference_candidate_20261013/' + name
            diffs.extend(difflib.unified_diff(
                old.read(old_name).decode('utf-8').splitlines(keepends=True),
                members['source/' + name].decode('utf-8').splitlines(keepends=True),
                fromfile='R01/' + name, tofile='R02/' + name))
        members['changes_from_R01.patch'] = ''.join(diffs).encode('utf-8')
    members['baseline/R01_identity.json'] = encoded(old_seal)
    for command, name in ((['git', 'rev-parse', 'HEAD'], 'head.txt'),
                          (['git', 'status', '--porcelain=v1'], 'status.txt')):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15)
        require(result.returncode == 0, 'GIT_READ_FAILED')
        members['evidence/' + name] = result.stdout
    members['evidence/not_executed.json'] = encoded({
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'outputs': {str(p): p.exists() for p in outputs},
        'scope': 'PREPARATION_ONLY_NO_ICARUS_VVP_EDA',
    })
    for path, raw in cached.items():
        require(path.read_bytes() == raw, 'SEAL_DRIFT:' + str(path))
    manifest = {
        'review_key': target.name,
        'state': 'SELF_CHECKED_PREPARED_NOT_EXECUTED_UNCOMMITTED',
        'authorization': 'User 2026-10-14: self-resolve; no intermediate M2/dual review; prepare only',
        'baseline': members['evidence/head.txt'].decode().strip(),
        'plan': identity(members['prepared/plan.json']),
        'config': identity(members['prepared/verbose_compile_config.json']),
        'launch': identity(launch_raw),
        'files': {name: identity(raw) for name, raw in sorted(members.items())},
    }
    manifest_raw = encoded(manifest)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(members.items()):
            archive.writestr(name, raw)
        archive.writestr('MANIFEST.json', manifest_raw)
    raw = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.testzip() is None, 'ZIP_CRC')
        for name, expected in manifest['files'].items():
            require(identity(archive.read(name)) == expected, 'ZIP_MEMBER_SHA')
    require(all(not p.exists() for p in outputs), 'EXECUTION_APPEARED')
    target.mkdir(exist_ok=False)
    (target / 'snapshot.zip.b64').write_bytes(base64.b64encode(raw) + b'\n')
    (target / 'MANIFEST.json').write_bytes(manifest_raw)
    receipt = {'snapshot': identity(raw), 'manifest': identity(manifest_raw),
               'members': len(members) + 1, 'state': manifest['state'],
               'plan': manifest['plan'], 'config': manifest['config']}
    (target / 'seal.json').write_bytes(encoded(receipt))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, action='append', default=[])
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(seal(args.prepared, args.evidence, args.target)))
