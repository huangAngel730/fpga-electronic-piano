"""Seal only this independent package/run; verify member hashes without executing."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip():
            raise ValueError('SEAL_DUPLICATE_OR_CRC')
        manifest = json.loads(archive.read('MEMBERS.json').decode('utf-8'))
        if set(names) != set(manifest) | {'MEMBERS.json'}:
            raise ValueError('SEAL_MEMBERS')
        for name, expected in manifest.items():
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                raise ValueError('SEAL_UNSAFE_PATH')
            value = archive.read(name)
            if dict(bytes=len(value), sha256=sha(value)) != expected:
                raise ValueError('SEAL_MEMBER_SHA:' + name)
        receipt = json.loads(archive.read('run/receipt.json').decode('utf-8'))
        if receipt['exit_code'] or receipt['status'] != 'N32_FRAME_SOFTWARE_L0_L1_PASS':
            raise ValueError('SEAL_RUN_NOT_PASS')
    return dict(status='SELF_CONTAINED_SEAL_SHA_VERIFIED', sha256=sha(raw),
                bytes=len(raw), members=len(names), executed=False)


def seal(run, output):
    run = run.resolve()
    run.relative_to(ROOT / 'code/output')
    output = output.resolve()
    output.relative_to(ROOT / 'code/docs/hardware/polyphony_frame_acceptance_20261012')
    if output.exists():
        raise ValueError('SEAL_REFUSE_OVERWRITE')
    # Copy the actually executed source/docs/corpus/logs/reference bytes; never
    # substitute later working-tree dependencies into a successful old run.
    files = {('run/' + p.relative_to(run).as_posix()): p.read_bytes()
             for p in run.rglob('*') if p.is_file()}
    manifest = {name: dict(bytes=len(raw), sha256=sha(raw)) for name, raw in files.items()}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
        archive.writestr('MEMBERS.json', json.dumps(manifest, indent=2).encode('utf-8'))
    raw = stream.getvalue()
    result = verify(raw)
    output.mkdir(parents=True)
    (output / 'SOFTWARE_SEAL.zip.b64').write_bytes(base64.encodebytes(raw))
    (output / 'seal_receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('seal', 'verify'))
    parser.add_argument('--run', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--base64', type=Path)
    args = parser.parse_args()
    result = seal(args.run, args.output) if args.mode == 'seal' else verify(base64.decodebytes(args.base64.read_bytes()))
    print(json.dumps(result))
