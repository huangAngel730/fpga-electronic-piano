"""Explicit operator freeze, separate from candidate prepare/verify (no tools)."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--tool-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, tools = args.repo.resolve(), args.tool_root.resolve()
    output = args.output.resolve()
    allowed = root / 'code/output'
    if output.parent != allowed or not output.name.startswith('repo_gate_rom_audit_'):
        parser.error('output must be a fresh task-prefixed directory under code/output')
    project = root / 'code/build/electronic_piano.gprj'
    paths = {project, *list((root / 'code/rtl').rglob('*.svh'))}
    for element in ET.parse(project).findall('.//File'):
        if element.get('type') == 'file.verilog' and element.get('enable', '1') == '1':
            path = (project.parent / element.attrib['path']).resolve()
            path.relative_to(root)
            paths.add(path)
    paths.update(root / rel for rel in (
        'code/tb/board/tb_electronic_piano_top.sv',
        'code/tb/board/tb_key_to_tone.sv',
        'code/tb/board/tb_midi_top_integration.sv',
        'code/scripts/check_repo.ps1', 'code/scripts/run_t007_sim.ps1',
        'code/scripts/run_t025_top_stat.py',
        'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py',
        'code/model/generated/sine_wavetable.hex',
        'code/model/generated/triangle_wavetable.hex',
        'code/model/generated/wavetables/velocity_gain_rom.mem',
        'code/model/generated/wavetables/piano_band_4x256_8191.mem'))
    binaries = {tools / 'environment.bat'}
    for relative in ('bin', 'lib/ivl', 'share/yosys'):
        directory = tools / relative
        if not directory.is_dir():
            raise ValueError(f'actual tool directory missing: {directory}')
        binaries.update(p for p in directory.rglob('*') if p.is_file())
    binaries.update(p for p in (tools / 'lib').iterdir() if p.is_file())
    binaries.update(p for p in (tools / 'lib').rglob('*')
                    if p.is_file() and p.suffix.lower() in ('.dll', '.vpi', '.ivl', '.so'))
    for path in paths | binaries:
        if path.is_symlink():
            raise ValueError(f'refuse symlink identity: {path}')
    document = {
        'schema': 'rom-gate-expected-v1',
        'provenance': 'Operator snapshot before candidate prepare; not auto-updated by verifier.',
        'tool_root': str(tools),
        'files': {p.relative_to(root).as_posix(): digest(p) for p in sorted(paths)},
        'tools': {p.relative_to(tools).as_posix(): digest(p) for p in sorted(binaries)},
    }
    output.mkdir(exist_ok=False)
    target = output / 'expected.json'
    target.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'path': str(target), 'sha256': digest(target),
                      'files': len(paths), 'tools': len(binaries)}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, ET.ParseError) as error:
        print(f'FREEZE_REFUSED: {error}', file=sys.stderr)
        raise SystemExit(2)
