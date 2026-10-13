"""Seal existing P0 static/software evidence. Never starts HDL/EDA tools."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
TB = ROOT / 'code/tb/audio/t052_publication_acceptance_candidate_20261012'
SW = ROOT / 'code/software/t052_publication_acceptance_candidate_20261012'
DOCS = HERE.parent


def identity(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def dump(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gate', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT / 'code/output'):
        raise ValueError('OUTPUT_SCOPE_OR_EXISTS')
    out.mkdir(parents=True)
    package = out / 'package'
    files = set()
    for directory in (TB / 'successor_20261013',
                      SW / 'rtl_capture_precheck_20261012/successor_20261013',
                      DOCS / 'P0_1_DRIVER_20261013',
                      DOCS / 'P0_2_CHECKER_20261013', HERE):
        files.update(p for p in directory.rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts)
    readonly = [TB / name for name in (
        'controls_128.hex', 'tb_t052_publication_control_128.sv',
        't052_public_observer.sv')]
    readonly += [SW / 'publication.py', DOCS / 'source_manifest.json',
                 SW / 'rtl_capture_precheck_20261012/render_control_mem.py',
                 ROOT / 'code/docs/test/t052_publication_acceptance_20261012/M2_CONTROL_PLAN_20261012/controls_proposed.jsonl',
                 ROOT / 'code/docs/evidence/m2_new_deliveries_review_20261012/RAW_EVIDENCE.zip',
                 ROOT / 'code/docs/evidence/m2_new_deliveries_review_20261012/READONLY_T052_DEPENDENCIES.zip',
                 ROOT / 'code/docs/evidence/m2_ab_failure_t052_static_review_20261013/RAW_EVIDENCE.zip']
    unchanged = {}
    for path in readonly:
        relative = path.relative_to(ROOT).as_posix()
        original = subprocess.run(['git', 'show', 'HEAD:' + relative], cwd=ROOT,
                                  capture_output=True, check=True).stdout
        if original != path.read_bytes():
            raise ValueError('OLD_SOURCE_CHANGED:' + relative)
        unchanged[relative] = identity(path)
    files.update(readonly)
    for name in ('m3_t052_p0_1_20261013_01', 'm3_t052_p0_1_20261013_02',
                 'm3_t052_p0_2_20261013_01', 'm3_t052_p0_2_20261013_02',
                 'm3_t052_p0_2_20261013_03', 'm3_t052_p0_2_20261013_04'):
        directory = ROOT / 'code/output' / name
        files.update(p for p in directory.rglob('*') if p.is_file())
    if args.gate:
        files.update(p for p in args.gate.resolve().rglob('*') if p.is_file())
    for path in sorted(files):
        relative = path.relative_to(ROOT)
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    manifest = {p.relative_to(package).as_posix(): identity(p)
                for p in sorted(package.rglob('*')) if p.is_file()}
    dump(package / 'MEMBERS.json', manifest)
    dump(package / 'OLD_SOURCE_UNCHANGED.json', unchanged)
    archive_path = out / 'M3_T052_P0_STATIC_COMBINATION_20261013.zip'
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(package).as_posix())
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP_CRC')
        for name, expected in manifest.items():
            raw = archive.read(name)
            if {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} != expected:
                raise ValueError('ZIP_MEMBER:' + name)
    git_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    receipt = {'status': 'SEALED_EXISTING_STATIC_SOFTWARE_EVIDENCE', 'git_head': git_head,
               'zip': {'path': str(archive_path), **identity(archive_path)},
               'member_count': len(manifest) + 2,
               'old_source_git_byte_checks': len(unchanged),
               'P0_1_final': 'code/output/m3_t052_p0_1_20261013_02',
               'P0_2_final': 'code/output/m3_t052_p0_2_20261013_04',
               'new_candidate_HDL_runs': 0, 'T052_complete': False,
               'notice': '待用户转发，尚未送达'}
    dump(out / 'delivery_receipt.json', receipt)
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
