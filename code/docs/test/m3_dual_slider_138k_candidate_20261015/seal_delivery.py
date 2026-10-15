"""Seal existing D evidence only. Starts no compiler, simulator, EDA or subprocess."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RTL = ROOT / 'code/rtl/input/m3_dual_slider_138k_candidate_20261015'
TB = ROOT / 'code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': digest(raw)}


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    destination = HERE / 'delivery_night_r02'
    destination.mkdir(exist_ok=False)
    runs, calls = [], []
    for number in range(1, 4):
        folder = HERE / ('run_night_%02d' % number)
        night = json.loads((folder / 'NIGHT_RUN_RECEIPT.json').read_text(encoding='utf-8'))
        before = json.loads((folder / 'before.json').read_text(encoding='utf-8'))
        after = json.loads((folder / 'after.json').read_text(encoding='utf-8'))
        step_records = []
        for path in sorted(folder.glob('*.receipt.json')):
            receipt = json.loads(path.read_text(encoding='utf-8'))
            label = path.name[:-len('.receipt.json')]
            step = {'label': label, **receipt,
                    'receipt': identity(path),
                    'stdout': identity(folder / (label + '.stdout.txt')),
                    'stderr': identity(folder / (label + '.stderr.txt'))}
            step_records.append(step)
            if receipt['process_created']:
                calls.append(step)
        runs.append({'directory': folder.name,
                     'candidate_identity': night['candidate_identity'],
                     'tools_files': len(before['tools']),
                     'tool_snapshot_before': identity(folder / 'before.json'),
                     'tool_snapshot_after': identity(folder / 'after.json'),
                     'source_and_tools_unchanged_during_run': before == after,
                     'result': night['error'], 'steps': step_records,
                     'tool_starts': night['tool_starts'],
                     'group_consumed': any(step['process_created'] for step in step_records)})
    if sum(run['group_consumed'] for run in runs) != 2 or len(calls) != 6:
        raise RuntimeError('UNEXPECTED_LEDGER_STOP')
    current = {str(path.relative_to(ROOT)): identity(path) for path in (
        RTL / 'dual_slider_candidate.sv', TB / 'tb_dual_slider.sv', HERE / 'run_candidate.py')}
    save(HERE / 'CURRENT_IDENTITIES.json', {
        'source': current, 'current_rtl_compiled': False,
        'executed_rtl_sha256': '42e3b795b80183e629746d16ac61e1883ee4eb30dc5530b0c72ab34ccce2cbfa',
        'executed_binary': identity(HERE / 'run_night_03/stage/candidate.vvp'),
        'frozen_old_sources_modified': False})
    save(HERE / 'NIGHT_RUN_RECEIPT.json', {
        'status': 'PARTIAL_STOPPED_TWO_GROUPS_CONSUMED',
        'validation': 'L1_EXECUTED_OLD_SHA_COMPILE_PASS_L2_SIM_FAIL_CURRENT_STATIC_FIX_UNTESTED',
        'git_head_at_preflight': '8b64a352464932a28df565038cafc8d623dea5c9',
        'prior_platform_denials': 2, 'zero_tool_precheck_failures': 1,
        'real_groups_consumed': 2, 'max_groups': 2,
        'tool_starts': 6, 'iverilog_version_calls': 2, 'vvp_version_calls': 2,
        'compile_calls': 1, 'artifact_vvp_calls': 1,
        'negative_runs': 0, 'positive_passes': 0,
        'eda_calls': 0, 'hardware_calls': 0, 'git_write_calls': 0,
        'actual_tool_elapsed_seconds': sum(step['elapsed_seconds'] for step in calls),
        'actual_artifact_simulation_seconds': sum(step['elapsed_seconds'] for step in calls if step['label'] == 'positive'),
        'per_tool_limit_seconds': 90, 'group_limit_seconds': 300,
        'current_source': current, 'runs': runs,
        'old_run_night_01_fixed_L2_label_is_not_valid_evidence': True,
        'hit_flash': 'KNOWN_FAIL_DEFERRED_NOT_REPAIRED',
        'real_audio_chain': False, 'formal_integration': False,
        'board_release_allowed': False, 'forwarding_status': 'PENDING_USER_FORWARD_NOT_DELIVERED'})
    # Reconstruct historical runner bytes into a NEW location only. Each must
    # match the contemporaneous before.json SHA; do not silently substitute a
    # newer runner or claim these copies were captured at execution time.
    current_runner = (HERE / 'run_candidate.py').read_bytes()
    modern_tools = b'''    # oss-cad-suite ships runtime DLLs in lib/, not only bin/ or lib/ivl/.
    tool_files = sorted(set([p for folder in (TOOLS / 'bin', TOOLS / 'lib/ivl')
                             for p in folder.rglob('*') if p.is_file()]
                            + [p for p in (TOOLS / 'lib').iterdir() if p.is_file()]))'''
    old_tools = b'''    tool_files = sorted(p for folder in (TOOLS / 'bin', TOOLS / 'lib/ivl')
                        for p in folder.rglob('*') if p.is_file())'''
    modern_path = b'''    command_environment.update(PATH=os.pathsep.join((str(TOOLS / 'bin'), str(TOOLS / 'lib'),
                               str(Path(os.environ['SystemRoot']) / 'System32'), os.environ['SystemRoot'])),'''
    old_path = b'''    command_environment.update(PATH=str(TOOLS / 'bin') + os.pathsep + os.environ['PATH'],'''
    if modern_tools not in current_runner or modern_path not in current_runner:
        raise RuntimeError('RECONSTRUCTION_PATTERN_MISSING')
    second = current_runner.replace(modern_tools, old_tools).replace(modern_path, old_path)
    first = second.replace(b'CREATE_SUSPENDED = 0x00000004  # Windows CreateProcess flag; Python does not export it.\n', b'')
    first = first.replace(b'creationflags=CREATE_SUSPENDED)', b'creationflags=subprocess.CREATE_SUSPENDED)')
    first = re.sub(rb"'validation_level': \('L2_ISOLATED_CANDIDATE_FIXTURE' if results\n\s+else 'L0_NO_SIMULATION_ACCEPTED'\),",
                   b"'validation_level': 'L2_ISOLATED_CANDIDATE_FIXTURE',", first)
    reconstruction = destination / 'reconstructed_exact_runner_sources'
    reconstruction.mkdir()
    reconstructed = []
    for run, raw in zip(runs, [first, second, current_runner]):
        expected = next(value for key, value in run['candidate_identity'].items() if key.endswith('run_candidate.py'))
        if digest(raw) != expected:
            raise RuntimeError('RECONSTRUCTED_RUNNER_SHA_MISMATCH:' + run['directory'])
        path = reconstruction / (run['directory'] + '_runner.py')
        with path.open('xb') as stream:
            stream.write(raw)
        reconstructed.append({'run': run['directory'], 'sha256': expected,
                              'contemporaneous_snapshot': False,
                              'reconstructed_exact_original_bytes_verified_by_before_sha': True})
    save(reconstruction / 'RECONSTRUCTION_RECEIPT.json', reconstructed)
    files = {}
    for directory in (RTL, TB, HERE):
        for path in directory.rglob('*'):
            if path.is_file() and destination not in path.parents and path != destination:
                files[str(path.relative_to(ROOT)).replace('\\', '/')] = path.read_bytes()
    for path in reconstruction.rglob('*'):
        if path.is_file():
            files['reconstructed_exact_runner_sources/' + path.name] = path.read_bytes()
    dependencies = json.loads((HERE / 'run_night_03/before.json').read_text(encoding='utf-8'))['inputs']
    for item in dependencies:
        path = Path(item['path'])
        if path.is_relative_to(ROOT) and not path.is_relative_to(HERE) and not path.is_relative_to(RTL) and not path.is_relative_to(TB):
            raw = path.read_bytes()
            if digest(raw) != item['sha256']:
                raise RuntimeError('ORIGINAL_DEPENDENCY_CHANGED:' + str(path))
            files['readonly_dependencies/' + path.relative_to(ROOT).as_posix()] = raw
    manifest = {name: {'bytes': len(raw), 'sha256': digest(raw)} for name, raw in sorted(files.items())}
    files['SEALED_MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    archive = destination / 'DUAL_SLIDER_NIGHT_PARTIAL_20261016.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as package:
        for name, raw in sorted(files.items()):
            package.writestr(name, raw)
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise RuntimeError('ARCHIVE_CRC')
        for name, expected in manifest.items():
            raw = package.read(name)
            if {'bytes': len(raw), 'sha256': digest(raw)} != expected:
                raise RuntimeError('ARCHIVE_MANIFEST_IDENTITY:' + name)
    delivery = {'archive': archive.name, **identity(archive), 'members': len(files),
                'crc_verified': True, 'all_member_sha_verified': True,
                'status': 'PARTIAL_TWO_GROUPS_EXHAUSTED', 'published': False,
                'compile_calls': 1, 'artifact_vvp_calls': 1, 'positive_passes': 0,
                'negative_runs': 0, 'eda_calls': 0, 'hardware_calls': 0,
                'current_source_uncompiled': True, 'board_release_allowed': False}
    save(destination / 'DELIVERY.json', delivery)
    print(json.dumps(delivery))


if __name__ == '__main__':
    main()
