"""Seal only the chat8 software delta; old large traces remain referenced."""
import json
import zipfile
from pathlib import Path

from analyze_existing import C, PINS, ROOT, identity

DOC = ROOT / 'code/docs/test/m3_r05_functional_integration_20261015/chat8_20261016'
SRC = Path(__file__).parent


def main():
    output = DOC / 'SEAL_R01'
    output.mkdir(exist_ok=False)
    receipt = json.loads((DOC / 'R01/RUN_RECEIPT.json').read_text(encoding='utf-8'))
    members = {}
    for old in receipt['source_before']:
        path = Path(old['path'])
        if identity(path) != old:
            raise ValueError('EXECUTED_SOURCE_CHANGED:' + str(path))
        members['executed_sources/' + path.name] = path
    for folder in (SRC, DOC):
        for path in sorted(folder.rglob('*')):
            if path.is_file() and output not in path.parents and '__pycache__' not in path.parts:
                members[path.relative_to(ROOT).as_posix()] = path
    for path in (C / 'EVENT_CALENDAR.json', C / 'DIGITAL_SUMMARY.json'):
        if identity(path)['sha256'] != PINS[path]:
            raise ValueError('REUSED_SOURCE_CHANGED')
        members['REUSED/' + path.name] = path
    md = next(p for p in PINS if p.name == '给M3_R05冻结算法与PCM声音判据.md')
    if identity(md)['sha256'] != PINS[md]:
        raise ValueError('M1_MD_CHANGED')
    members['read_only_inputs/' + md.name] = md
    manifest = {'status': 'SOFTWARE_DELTA_ONLY_MATH_PARTIAL',
                'large_original_traces_included': False,
                'large_original_traces': [identity(p) for p in PINS if p.suffix == '.jsonl'],
                'members': {name: identity(p) for name, p in members.items()},
                'board_release_allowed': False, 'Git_writes': 0, 'EDA_RTL_calls': 0}
    archive = output / 'M3_CHAT8_A_C_MATH_SCOPE_DELTA_20261016.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, path in members.items():
            z.write(path, name)
        z.writestr('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    import hashlib
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('ARCHIVE_CRC')
        for name, item in manifest['members'].items():
            data = z.read(name)
            if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError('ARCHIVE_MEMBER:' + name)
    seal = {'archive': identity(archive), 'payload_members': len(members),
            'CRC_and_all_member_SHA_verified': True,
            'status': manifest['status'], 'new_RTL_calls': 0, 'Git_writes': 0}
    (output / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'SEAL_RECEIPT.json').write_text(json.dumps(seal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(seal, ensure_ascii=False))


if __name__ == '__main__':
    main()
