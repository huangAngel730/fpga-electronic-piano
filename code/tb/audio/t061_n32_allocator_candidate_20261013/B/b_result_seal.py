"""Seal the reviewed N32-B split execution, including its full capture."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def digest(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def add_tree(members, prefix, root, exclude=()):
    root = Path(root).resolve()
    for path in sorted(root.rglob('*')):
        if (path.is_file() and '__pycache__' not in path.parts and
                path.suffix.lower() not in exclude):
            members[prefix + '/' + path.relative_to(root).as_posix()] = path.read_bytes()


def seal(prepared, base, continuation, historical, target):
    prepared, base = Path(prepared).resolve(), Path(base).resolve()
    continuation = Path(continuation).resolve()
    historical, target = Path(historical).resolve(), Path(target).resolve()
    output_root = (ROOT / 'code/output').resolve()
    if not all(path.is_relative_to(output_root)
               for path in (prepared, base, continuation, historical)):
        raise ValueError('EVIDENCE_OUTSIDE_OUTPUT')
    if target.parent != HERE or target.exists():
        raise ValueError('TARGET_SCOPE_OR_EXISTS')
    members = {}
    for path in sorted(HERE.iterdir()):
        if (path.is_file() and path.suffix != '.pyc'):
            members['authored/' + path.name] = path.read_bytes()
    members['prepared/plan.json'] = (prepared / 'plan.json').read_bytes()
    add_tree(members, 'prepared/snapshot', prepared / 'snapshot')
    add_tree(members, 'evidence/base', base, exclude=('.vvp', '.pyc'))
    add_tree(members, 'evidence/continuation', continuation,
             exclude=('.vvp', '.pyc'))
    members['evidence/historical_300s_timeout_receipt.json'] = (
        historical / 'receipt.json').read_bytes()
    manifest = {
        'schema': 'T061_N32_B_SEALED_RESULT_V1',
        'review_key': 'T061-N32-B-RESULT-20261014-R01',
        'status': 'N32_B_R1_EVENT_AUDIO_AND_MUTANTS_PASS_T061_PARTIAL',
        'files': {name: digest(raw) for name, raw in sorted(members.items())},
        'contains_full_capture': True,
        'excluded_suffixes': ['.vvp', '.pyc'],
        'automatic_retries': 0, 'EDA_calls': 0, 'T061_complete': False,
        'physical_STA': 'NOT_RUN',
    }
    manifest_raw = (json.dumps(manifest, ensure_ascii=False, indent=2,
                               sort_keys=True) + '\n').encode('utf-8')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, raw in sorted(members.items()):
            bundle.writestr(name, raw)
        bundle.writestr('MANIFEST.json', manifest_raw)
    archive = stream.getvalue()
    target.mkdir()
    (target / 'snapshot.zip.b64').write_bytes(base64.b64encode(archive) + b'\n')
    (target / 'MANIFEST.json').write_bytes(manifest_raw)
    result = {
        'review_key': manifest['review_key'], 'status': manifest['status'],
        'snapshot': digest(archive), 'manifest': digest(manifest_raw),
        'members': len(members) + 1, 'T061_complete': False,
    }
    (target / 'seal.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8', newline='\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', required=True, type=Path)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--continuation', required=True, type=Path)
    parser.add_argument('--historical', required=True, type=Path)
    parser.add_argument('--target', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(seal(args.prepared, args.base, args.continuation,
                          args.historical, args.target), sort_keys=True))
