"""Seal original night evidence without normalizing any raw stream bytes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[5]
COORD = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator'
OUT = COORD / 'DELIVERY'
SCOPES = ['code/software/m3_pro_fourvoice_trace_20261016',
          'code/tb/board/m3_pro_fourvoice_trace_20261016',
          'code/docs/test/m3_pro_fourvoice_trace_20261016',
          'code/rtl/input/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016',
          'code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016',
          'code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': digest(data)}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify_references(value):
    count = 0
    if isinstance(value, dict):
        if set(('path', 'bytes', 'sha256')) <= set(value):
            path = Path(value['path'])
            if not path.is_file() or path.stat().st_size != value['bytes'] or digest(path.read_bytes()) != value['sha256']:
                raise ValueError('STALE_FINAL_REFERENCE:' + str(path))
            count += 1
        for child in value.values():
            count += verify_references(child)
    elif isinstance(value, list):
        count += sum(verify_references(child) for child in value)
    return count


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    intake = []
    for rel in ['code/docs/test/m3_pro_fourvoice_trace_20261016/C/LATEST_RECEIPT.json',
                'code/docs/test/m3_pro_fourvoice_trace_20261016/D/LATEST_RECEIPT.json']:
        path = ROOT / rel
        value = json.loads(path.read_text(encoding='utf-8'))
        intake.append({'receipt': identity(path), 'verified_references': verify_references(value)})
    slider_path = ROOT / 'code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/DELIVERY.json'
    slider = json.loads(slider_path.read_text(encoding='utf-8'))
    slider_archive = Path(slider['archive'])
    if slider_archive.stat().st_size != slider['bytes'] or digest(slider_archive.read_bytes()) != slider['sha256']:
        raise ValueError('SLIDER_ARCHIVE_IDENTITY')
    intake.append({'receipt': identity(slider_path), 'verified_references': 1})
    paths = []
    for scope in SCOPES:
        base = ROOT / scope
        if base.exists():
            paths.extend(p for p in base.rglob('*') if p.is_file())
    paths = sorted(set(p for p in paths if not p.is_relative_to(OUT)
                       and not p.is_relative_to(COORD / 'PUBLICATION_GATE')
                       and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.vvp', '.vcd')))
    publication = set()
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith('code/software/') or rel.startswith('code/rtl/') or rel.startswith('code/tb/'):
            if path.suffix in ('.py', '.ps1', '.sv', '.md'):
                publication.add(rel)
    for folder in ('C', 'D'):
        base = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016' / folder
        for name in ('RESULT.md', 'NIGHT_RUN_RECEIPT.json', 'LATEST_RECEIPT.json'):
            publication.add((base / name).relative_to(ROOT).as_posix())
    for name in ('CALENDAR.json', 'CALENDAR.jsonl', 'CALENDAR_CONTRACT.json', 'STIMULUS.json'):
        publication.add('code/docs/test/m3_pro_fourvoice_trace_20261016/C/' + name)
    slider_dir = slider_path.parent
    for name in ('RESULT.md', 'NIGHT_RUN_RECEIPT.json', 'DELIVERY.json', 'INTEGRATION_DIFF.md', 'SELF_REVIEW.md',
                 'run.py', 'verify_recorded_geometry.py', 'seal.py'):
        file = slider_dir / name
        if file.is_file():
            publication.add(file.relative_to(ROOT).as_posix())
    for path in COORD.glob('*.md'):
        publication.add(path.relative_to(ROOT).as_posix())
    for name in ('BUDGET_REVISION_20261017.json', 'PUBLICATION_FILES.json'):
        publication.add((COORD / name).relative_to(ROOT).as_posix())
    for name in ('M3_NIGHT_20261017_OFFLINE_ORIGINALS.zip', 'MANIFEST.json', 'DELIVERY.json', 'VERIFICATION.json'):
        publication.add((OUT / name).relative_to(ROOT).as_posix())
    save(COORD / 'PUBLICATION_FILES.json', {'schema': 'M3_NIGHT_PUBLICATION_FILES_V1',
         'paths': sorted(publication), 'raw_stream_policy': 'All original bytes inside the ZIP; no text normalization of evidence'})
    paths.append(COORD / 'PUBLICATION_FILES.json')
    manifest = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                 'sha256': digest(p.read_bytes())} for p in sorted(set(paths))]
    save(OUT / 'MANIFEST.json', {'schema': 'M3_NIGHT_ORIGINALS_V1', 'files': manifest})
    archive = OUT / 'M3_NIGHT_20261017_OFFLINE_ORIGINALS.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as zip_out:
        for entry in manifest:
            zip_out.write(ROOT / entry['path'], entry['path'])
        zip_out.write(OUT / 'MANIFEST.json', 'MANIFEST.json')
    with zipfile.ZipFile(archive) as zip_in:
        if zip_in.testzip() is not None:
            raise ValueError('CRC_FAILURE')
        if set(zip_in.namelist()) != {e['path'] for e in manifest} | {'MANIFEST.json'}:
            raise ValueError('MEMBER_SET')
        for entry in manifest:
            data = zip_in.read(entry['path'])
            if len(data) != entry['bytes'] or digest(data) != entry['sha256']:
                raise ValueError('MEMBER_SHA:' + entry['path'])
    verify = {'status': 'PASS', 'payload_files': len(manifest), 'members': len(manifest) + 1,
              'crc_sizes_sha_all_verified': True, 'final_receipt_intake': intake,
              'archive': identity(archive)}
    save(OUT / 'VERIFICATION.json', verify)
    receipt = {'status': 'DONE_AUTHORIZED_OFFLINE_PACKAGES_PRO_PENDING',
               'utc': datetime.now(timezone.utc).isoformat(), 'archive': identity(archive),
               'manifest': identity(OUT / 'MANIFEST.json'), 'verification': identity(OUT / 'VERIFICATION.json'),
               'payload_files': len(manifest), 'publication_paths': len(publication),
               'C_rounds': 2, 'D_D2_rounds': 3, 'D3_rounds': 2, 'D_shared_rounds': 5, 'slider_rounds': 1,
               'C_D_functional_seconds': 13.093, 'slider_functional_seconds': 100.282,
               'modelsim_gowin_hardware': 0, 'board_release_allowed': False,
               'publication_gate_status': 'PENDING_SEPARATE_RECEIPT', 'git_status': 'NOT_COMMITTED_NOT_PUSHED_AT_SEAL',
               'human_M1_M2_handoff': 'WAITING_FOR_USER_FORWARD_NOT_DELIVERED'}
    save(OUT / 'DELIVERY.json', receipt)
    print(json.dumps({'status': receipt['status'], 'archive': receipt['archive'],
                      'payload_files': len(manifest), 'publication_paths': len(publication)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
