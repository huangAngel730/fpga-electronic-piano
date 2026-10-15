"""Seal source, frozen inputs, logs and receipts; never ship executable VVP."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXCLUDED = {'.vvp', '.exe', '.dll', '.pyc', '.vcd', '.fst', '.fs', '.bit'}


def stamp(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, nargs='+', required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != ROOT / 'code/output' or not output.name.startswith('repo_gate_rom_audit_'):
        parser.error('fresh task-prefixed code/output directory required')
    if output.exists():
        parser.error('refuse existing output')
    members, sources = {}, {}

    def add(name, path):
        path = path.resolve()
        if name in members:
            raise ValueError(f'duplicate archive member {name}')
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'not a regular input {path}')
        raw = path.read_bytes()
        if len(raw) > 64 * 1024 * 1024:
            raise ValueError(f'oversized evidence {path}')
        members[name] = raw
        sources[str(path)] = stamp(raw)

    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.suffix.lower() not in EXCLUDED and '__pycache__' not in path.parts:
            add('source/' + path.relative_to(HERE).as_posix(), path)
    expected_path = args.expected.resolve()
    document = json.loads(expected_path.read_text(encoding='utf-8'))
    add('inputs/expected.json', expected_path)
    for relative, expected in document['files'].items():
        path = (ROOT / relative).resolve()
        path.relative_to(ROOT)
        add('inputs/' + relative, path)
        if sources[str(path)]['sha256'] != expected:
            raise ValueError(f'frozen input changed: {relative}')
    history = ROOT / ('code/software/score_midi_import_candidate_20261014/'
                      'PUBLICATION_20261015_R01/REPOSITORY_GATE_R02_LOGS.zip')
    add('inputs/HISTORICAL_FALSE_GREEN_LOGS.zip', history)
    omitted = []
    for directory in args.evidence:
        directory = directory.resolve()
        if directory.parent != ROOT / 'code/output' or not directory.name.startswith('repo_gate_rom_audit_'):
            raise ValueError(f'evidence outside task scope: {directory}')
        for path in sorted(directory.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(directory).as_posix()
            if path.suffix.lower() in EXCLUDED or '__pycache__' in path.parts:
                omitted.append(directory.name + '/' + relative)
                continue
            add('evidence/' + directory.name + '/' + relative, path)
    for name, identity in sources.items():
        if stamp(Path(name).read_bytes()) != identity:
            raise ValueError(f'input drift while sealing: {name}')
    manifest = {'schema': 1, 'scope': 'ISOLATED_ROM_GATE_DELIVERY',
                'files': {name: stamp(raw) for name, raw in sorted(members.items())},
                'omitted_executable_or_waveform_artifacts': omitted,
                'tool_bytes_included': False, 'tool_identities': document['tools'],
                'M2_acceptance': 'PENDING', 'formal_gate_integration': 'NOT_PERFORMED'}
    members['MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    output.mkdir(exist_ok=False)
    target = output / 'ROM_GATE_DELIVERY.zip'
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(members.items()):
            archive.writestr(name, raw)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(members):
            raise ValueError('archive CRC/member-set mismatch')
        for name, raw in members.items():
            if stamp(archive.read(name)) != stamp(raw):
                raise ValueError(f'archive byte mismatch {name}')
    receipt = {'archive': str(target), **stamp(target.read_bytes()),
               'members': len(members), 'crc_and_all_members': 'PASS',
               'input_sources_before_after_equal': True, 'omitted': omitted}
    (output / 'SEAL_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f'SEAL_REFUSED: {error}', file=sys.stderr)
        raise SystemExit(2)
