"""Seal this completion only. No candidate execution or Git mutation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[6]
SUFFIX = 'm3_pro_fourvoice_trace_20261016'
DOC = ROOT / 'code/docs/test' / SUFFIX / 'pro_basis_r08_20261017/coordinator/task_day4_completion_20261017'
OUT = ROOT / 'code/output/m3_c9_complete_d4_20261017'


def ident(path):
    h, count = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            count += len(block)
            h.update(block)
    return {'bytes': count, 'sha256': h.hexdigest()}


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def main():
    delivery = DOC / 'DELIVERY'
    delivery.mkdir(exist_ok=False)
    selected, direct = set(), set()
    for prefix in ('code/software', 'code/tb/board', 'code/docs/test'):
        base = ROOT / prefix / SUFFIX
        for path in base.rglob('*'):
            if path.is_file() and 'c9_completion_r01' in path.parts and '__pycache__' not in path.parts:
                selected.add(path)
                direct.add(path)
    for path in DOC.rglob('*'):
        if path.is_file() and not path.is_relative_to(delivery) and not any(part.startswith('GATE_') for part in path.parts):
            selected.add(path)
            if not any(part.startswith('FREEZE_') for part in path.parts):
                direct.add(path)
    for path in OUT.rglob('*'):
        if path.is_file():
            selected.add(path)
    assert selected
    for path in Path(__file__).parent.glob('*.py'):
        selected.add(path)
        direct.add(path)
    # Standalone real bytes for inputs read by successful/failing batches and
    # not yet tracked are selected explicitly. Already published dependencies
    # remain in Git and are additionally present in each INPUTS.zip snapshot.
    tracked = set(name.decode('utf-8') for name in subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT).split(b'\0') if name)
    input_reads = {}
    for path in sorted(OUT.glob('*/RECEIPT.json')):
        receipt = json.loads(path.read_text(encoding='utf-8'))
        for name, expected in receipt.get('read_inputs', {}).items():
            file = Path(name)
            if not file.is_absolute():
                file = ROOT / file
            if not file.is_relative_to(ROOT):
                continue
            rel = file.relative_to(ROOT).as_posix()
            # Repairs legitimately supersede earlier failed input bytes; every
            # earlier version stays in its own frozen original archive.
            input_reads[rel] = expected
    for name, expected in input_reads.items():
        file = ROOT / name
        assert ident(file) == expected, 'LATEST_READ_SOURCE_CHANGED:' + name
        if name not in tracked:
            selected.add(file)
            direct.add(file)
    manifest = {path.relative_to(ROOT).as_posix(): ident(path) for path in sorted(selected)}
    save(delivery / 'ORIGINALS_MANIFEST.json', {'schema': 'M3_D4_C9_ORIGINALS_V1',
        'files': manifest, 'external_EXE_DLL_redistributed': False,
        'old_delivery': 'e394790b97d2d974a4d824f65c5fcd4b6a94d623',
        'old_ledgers_modified': False, 'R10_resumed': False})
    archive_path = delivery / 'M3_TASK_DAY4_C9_COMPLETION.zip'
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1,
                         allowZip64=True) as archive:
        archive.write(delivery / 'ORIGINALS_MANIFEST.json', 'ORIGINALS_MANIFEST.json')
        for name, expected in manifest.items():
            archive.write(ROOT / name, name)
            assert ident(ROOT / name) == expected, 'INPUT_CHANGED_DURING_SEAL:' + name
    with zipfile.ZipFile(archive_path) as archive:
        assert len(archive.namelist()) == len(manifest) + 1
        assert len(archive.namelist()) == len(set(archive.namelist()))
        for name, expected in manifest.items():
            h, size = hashlib.sha256(), 0
            with archive.open(name) as member:
                for block in iter(lambda: member.read(1024 * 1024), b''):
                    size += len(block)
                    h.update(block)
            assert {'bytes': size, 'sha256': h.hexdigest()} == expected, 'SEALED_PAYLOAD_CHANGED:' + name
    zipped = ident(archive_path)
    volumes = []
    if zipped['bytes'] <= 24 * 1024 * 1024:
        direct.add(archive_path)
        volumes.append({'path': archive_path.relative_to(ROOT).as_posix(), **zipped})
    else:
        # Raw ordered parts, each <=24MiB. Concatenation restores the verified
        # ZIP byte for byte; the ZIP itself remains local as the simple entry.
        with archive_path.open('rb') as source:
            number = 1
            while block := source.read(24 * 1024 * 1024):
                part = delivery / f'M3_TASK_DAY4_C9_COMPLETION.zip.part{number:03d}'
                with part.open('xb') as sink:
                    sink.write(block)
                direct.add(part)
                volumes.append({'path': part.relative_to(ROOT).as_posix(), **ident(part)})
                number += 1
    save(delivery / 'ARCHIVE_RECEIPT.json', {'schema': 'M3_D4_C9_ARCHIVE_RECEIPT_V1',
        'archive': {'path': archive_path.relative_to(ROOT).as_posix(), **zipped},
        'original_files': len(manifest), 'CRC_SHA_bytes_verified': True,
        'payload_bytes': sum(item['bytes'] for item in manifest.values()),
        'volumes': volumes, 'parts_are_ordered_raw_zip_bytes': len(volumes) > 1,
        'reassembly': 'Concatenate part001, part002, ... into a NEW .zip and verify archive SHA before extraction.',
        'real_verified': False, 'board_release_allowed': False})
    direct.update({delivery / 'ORIGINALS_MANIFEST.json', delivery / 'ARCHIVE_RECEIPT.json'})
    paths = sorted(path.relative_to(ROOT).as_posix() for path in direct)
    save(DOC / 'PUBLICATION_FILES.json', {'paths': paths,
        'scope': 'Only new c9_completion_r01 packages, root completion, used untracked dependencies and sealed original-byte volumes'})
    print(json.dumps({'direct_files': len(paths), 'originals': len(manifest),
        'archive': zipped, 'volumes': len(volumes)}))


if __name__ == '__main__':
    main()
