"""Seal only the three P1 new directories; refuse overwrite, never Git/EDA."""
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUFFIX = 'm3_r05_functional_integration_20261015/real_trace_successor_20261016'
DIRECTORIES = [ROOT / 'code/software' / SUFFIX, ROOT / 'code/tb/board' / SUFFIX,
               ROOT / 'code/docs/test' / SUFFIX]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def alphanumeric(value):
    if re.fullmatch(r'[A-Za-z0-9]+', value) is None:
        raise argparse.ArgumentTypeError('ID must contain ASCII letters/digits only')
    return value


def payload_files():
    """Ignore no log files; exclude every SEAL* subtree, even on repeat use."""
    files = []
    for directory in DIRECTORIES:
        for path in directory.rglob('*'):
            relative = path.relative_to(directory)
            if any(part.upper().startswith('SEAL') for part in relative.parts[:-1]):
                continue
            if not path.is_file():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError('PAYLOAD_OUTSIDE_WRITESET:' + str(path))
            # This delivery contains root source/docs and the four original runs.
            if len(relative.parts) > 1 and relative.parts[0] not in {
                    'RUN01', 'RUN02', 'RUN03', 'RUN04'}:
                raise ValueError('UNEXPECTED_PAYLOAD_DIRECTORY:' + str(path))
            files.append(path)
    return sorted(files)


def put(archive, name, raw):
    # Fixed metadata + STORE avoid clock/platform/compressor-dependent ZIP bytes.
    info = zipfile.ZipInfo(name, date_time=(2026, 10, 16, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = zipfile.ZIP_STORED
    archive.writestr(info, raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('seal_id', type=alphanumeric, help='new directory, e.g. SEAL03')
    parser.add_argument('generation', type=alphanumeric, help='archive generation, e.g. R03')
    args = parser.parse_args()
    if not args.seal_id.startswith('SEAL'):
        parser.error('seal_id must start with SEAL')
    out = DIRECTORIES[2] / args.seal_id
    if out.exists():
        parser.error('REFUSE_OVERWRITE:' + str(out))
    files = payload_files()
    script = Path(__file__).resolve()
    script_sha = digest(script.read_bytes())
    out.mkdir(exist_ok=False)
    manifest = {}
    target = out / ('M3_P1_R06_REAL_TRACE_PREPARATION_' + args.generation + '_20261016.zip')
    result = {'argv': list(sys.orig_argv), 'cwd': str(Path.cwd()),
              'python': sys.executable, 'python_version': sys.version,
              'script': str(script), 'script_sha256': script_sha,
              'seal_id': args.seal_id, 'generation': args.generation,
              'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False}
    try:
        with zipfile.ZipFile(target, 'x') as archive:
            for path in files:
                raw = path.read_bytes()
                name = path.relative_to(ROOT).as_posix()
                manifest[name] = {'bytes': len(raw), 'sha256': digest(raw)}
                put(archive, name, raw)
            manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2,
                                         sort_keys=True) + '\n').encode('utf-8')
            put(archive, 'MANIFEST.json', manifest_bytes)
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP_CRC')
            if len(archive.namelist()) != len(manifest) + 1 or set(archive.namelist()) != set(manifest) | {'MANIFEST.json'}:
                raise ValueError('ZIP_MEMBERS')
            if archive.read('MANIFEST.json') != manifest_bytes:
                raise ValueError('ZIP_MANIFEST')
            for name, item in manifest.items():
                raw = archive.read(name)
                if len(raw) != item['bytes'] or digest(raw) != item['sha256']:
                    raise ValueError('ZIP_IDENTITY:' + name)
                if digest((ROOT / name).read_bytes()) != item['sha256']:
                    raise ValueError('SOURCE_CHANGED_DURING_SEAL:' + name)
        if digest(script.read_bytes()) != script_sha:
            raise ValueError('SEAL_SCRIPT_CHANGED')
        (out / 'MANIFEST.json').write_bytes(manifest_bytes)
        result.update(file=str(target), bytes=target.stat().st_size,
                      sha256=digest(target.read_bytes()), payload_members=len(manifest),
                      seal_verify_exit=0, manifest_sha256=digest(manifest_bytes),
                      zip_metadata='fixed 2026-10-16, mode 100644, ZIP_STORED',
                      source_after_matches=True)
    except Exception as exc:
        result.update(seal_verify_exit=1, error=repr(exc), payload_members=len(manifest))
    (out / 'SEAL_RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    return result['seal_verify_exit']


if __name__ == '__main__':
    raise SystemExit(main())
