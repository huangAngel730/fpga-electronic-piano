"""Seal static preparation and original evidence; never execute tool chains."""
import argparse
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location('oneshot_seal', HERE / 'oneshot.py')
m = importlib.util.module_from_spec(loader)
loader.loader.exec_module(m)
sys.path.insert(0, str(m.RUNNER_DIR))
from supervisor_20261013 import require_supervisor  # noqa: E402
guard_loader = importlib.util.spec_from_file_location('oneshot_supervisor', HERE / 'supervise.py')
guard = importlib.util.module_from_spec(guard_loader)
guard_loader.loader.exec_module(guard)


def seal(evidence, failure, target, supervisor, reuse, suite):
    evidence, failure, target = (Path(p).resolve() for p in (evidence, failure, target))
    m.need(target.parent == m.DOC / 'CONTROL_PREPARATION_20261012', 'SEAL_OUTPUT_SCOPE')
    m.need(not target.exists(), 'TARGET_EXISTS')
    verified = require_supervisor(evidence, supervisor, guard.command(evidence, reuse, suite),
                                  guard.sources(), expected_cwd=m.ROOT,
                                  expected_total=300, expected_step=90)
    # Archive the exact bytes checked here, not a later read of a live path.
    cached = {Path(path).resolve(): raw for path, raw in verified['files'].items()}

    def cached_bytes(path):
        path = Path(path).resolve()
        if path not in cached:
            cached[path] = path.read_bytes()
        return cached[path]

    def raw_identity(data):
        return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def checked(item):
        data = cached_bytes(item['path'])
        m.need(raw_identity(data) == {k: item[k] for k in ('bytes', 'sha256')},
               'SEALED_INPUT_DRIFT:' + item['path'])
        return data

    receipt = json.loads(cached_bytes(evidence / 'receipt.json'))
    m.need(receipt['status'] == 'PREPARATION_SOFTWARE_PASS' and
           receipt['exit_code'] == 0 and receipt['HDL_calls'] == 0, 'NOT_PREPARED')
    reuse = Path(reuse).resolve()
    m.need(Path(receipt['REUSED']['receipt']['path']).resolve() == reuse / 'receipt.json',
           'REUSED_RECEIPT_PATH')
    reused_receipt = json.loads(checked(receipt['REUSED']['receipt']))
    config_path = Path(receipt['config']['path']).resolve()
    m.need(config_path == reuse / 'prepared/config.json' and
           receipt['config'] == reused_receipt['config'], 'REUSED_CONFIG_BINDING')
    config = json.loads(checked(receipt['config']))
    checked(config['manifest'])
    for name, expected in config['software'].items():
        checked({'path': name, **expected})
    members = {}
    for directory, prefix, record in ((evidence, 'software_preparation', receipt),
                                       (reuse, 'reused_preparation', reused_receipt)):
        members[prefix + '/receipt.json'] = cached_bytes(directory / 'receipt.json')
        for name, item in record['artifacts'].items():
            m.need(Path(item['path']).resolve() == directory / name and
                   (directory / name).resolve().is_relative_to(directory), 'ARTIFACT_PATH')
            members[prefix + '/' + name] = checked(item)
    for path in sorted(failure.rglob('*')):
        if path.is_file():
            members['first_failure/' + path.relative_to(failure).as_posix()] = cached_bytes(path)
    parent = Path(supervisor).resolve().parent
    for name, data in verified['files'].items():
        path = Path(name).resolve()
        if path.is_relative_to(parent):
            members['external_supervisor/' + path.relative_to(parent).as_posix()] = data
        elif path.is_relative_to(m.ROOT) and path.suffix == '.py':
            members['source/' + path.relative_to(m.ROOT).as_posix()] = data
    for name in config['software']:
        path = Path(name)
        members['source/' + path.relative_to(m.ROOT).as_posix()] = cached_bytes(path)
    members['signed_manifest.json'] = checked(config['signed_manifest'])
    m.need(raw_identity(members['signed_manifest.json'])['sha256'] == m.OLD_SHA,
           'SIGNED_MANIFEST_PIN')
    original = json.loads(members['signed_manifest.json'])
    for role, item in {'plan': original['plan'], 'calendar': original['calendar'],
                       **original['sources']}.items():
        members['frozen_inputs/' + role + '/' + Path(item.get('member', item['path'])).name] = m.source_bytes(item)
    inventory = {name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                 for name, raw in members.items()}
    members['member_inventory.json'] = (json.dumps(inventory, indent=2) + '\n').encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(members.items()):
            archive.writestr(name, raw)
    raw_zip = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        m.need(archive.testzip() is None and len(archive.namelist()) == len(members), 'ZIP_VERIFY')
        for name, raw in members.items():
            m.need(archive.read(name) == raw, 'ZIP_MEMBER:' + name)
    target.mkdir(parents=True)
    (target / 'evidence.zip.b64').write_text(base64.b64encode(raw_zip).decode() + '\n', encoding='ascii')
    for name in ('config.json', 'manifest.json'):
        (target / name).write_bytes(cached_bytes(config_path.parent / name))
    result = {'status': 'SEALED_PREPARATION_ONLY', 'zip_bytes': len(raw_zip),
              'zip_sha256': hashlib.sha256(raw_zip).hexdigest(), 'members': len(members),
              'config': raw_identity(cached_bytes(config_path)), 'source': inventory,
              'execution_authorized': False, 'HDL_calls': 0,
              'external_supervisor': {'path': Path(supervisor).resolve().as_posix(),
                                      **raw_identity(cached_bytes(supervisor))},
              'tool_binary_distribution': False,
              'first_failure_note': 'Original logs retained; current qualify adds workspace TEMP. No claim current qualify was first-failure source.',
              'T052_complete': False}
    m.write(target / 'seal.json', result)
    return {key: result[key] for key in ('status', 'zip_bytes', 'zip_sha256', 'members', 'config')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('evidence', 'failure', 'target', 'supervisor', 'reuse', 'suite'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(seal(args.evidence, args.failure, args.target,
                          args.supervisor, args.reuse, args.suite)))
