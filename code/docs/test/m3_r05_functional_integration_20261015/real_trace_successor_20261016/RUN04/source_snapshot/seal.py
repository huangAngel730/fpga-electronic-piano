"""Seal only the three P1 new directories; refuse overwrite, never Git/EDA."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUFFIX = 'm3_r05_functional_integration_20261015/real_trace_successor_20261016'
DIRECTORIES = [ROOT / 'code/software' / SUFFIX, ROOT / 'code/tb/board' / SUFFIX,
               ROOT / 'code/docs/test' / SUFFIX]


def main():
    out = DIRECTORIES[2] / 'SEAL01'
    files = sorted(p for directory in DIRECTORIES for p in directory.rglob('*')
                   if p.is_file() and out not in p.parents)
    out.mkdir(exist_ok=False)
    manifest = {}
    target = out / 'M3_P1_R06_REAL_TRACE_PREPARATION_20261016.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            raw = path.read_bytes()
            name = path.relative_to(ROOT).as_posix()
            manifest[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            archive.writestr(name, raw)
        archive.writestr('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(manifest) | {'MANIFEST.json'}
        for name, item in manifest.items():
            raw = archive.read(name)
            assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256']
    result = {'file': str(target), 'bytes': target.stat().st_size,
              'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'payload_members': len(manifest), 'seal_verify_exit': 0,
              'argv': [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).resolve())],
              'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False}
    (out / 'SEAL_RECEIPT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
