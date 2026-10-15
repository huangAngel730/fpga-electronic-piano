"""Bounded isolated candidate acceptance; never starts EDA or board tools."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
RTL = ROOT / 'code/rtl/input/m3_dual_slider_138k_candidate_20261015'
TB = ROOT / 'code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015'
TOOLS = Path('D:/Gowin/oss-cad-suite')
ORIGINALS = [
    'code/rtl/common/audio_defs_pkg.sv',
    'code/rtl/common/reset_sync.sv',
    'code/rtl/common/visual_mailbox_cdc.sv',
    'code/rtl/common/visual_control_bridge.sv',
    'code/rtl/common/visual_event_bridge.sv',
    'code/rtl/input/visualizer/visual_live_state.sv',
    'code/rtl/input/visualizer/visual_score_tracker.sv',
    'code/rtl/input/visualizer/visual_scene_renderer.sv',
]
JOB = ROOT / 'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
CREATE_SUSPENDED = 0x00000004  # Windows CreateProcess flag; Python does not export it.


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def identities(paths):
    return [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    # Interrupted launches count conservatively. A known Popen failure with an
    # explicit receipt is the only reservation not counted as a started group.
    previous = []
    for folder in sorted(HERE.glob('run_*')):
        reservation = folder / 'TOOL_CREATE_RESERVED.json'
        if reservation.is_file():
            receipts_found = list(folder.glob('*.receipt.json'))
            known_no_start = receipts_found and all(
                json.loads(p.read_text(encoding='utf-8')).get('process_created') is False
                for p in receipts_found)
            if not known_no_start:
                previous.append(json.loads(reservation.read_text(encoding='utf-8')))
    candidate_identity = {str(path.relative_to(ROOT)): sha(path) for path in (
        RTL / 'dual_slider_candidate.sv', TB / 'tb_dual_slider.sv', Path(__file__).resolve())}
    if len(previous) >= 2:
        parser.error('D two-group nightly bound exhausted; do not reset ledger')
    if any(item['candidate_identity'] == candidate_identity for item in previous):
        parser.error('same-source retry forbidden')
    out = Path(args.output).resolve()
    if out.parent != HERE or not out.name.startswith('run_'):
        parser.error('output must be a new immediate run_* child of this directory')
    out.mkdir(exist_ok=False)
    staged = out / 'stage'
    staged.mkdir()
    sources = [ROOT / p for p in ORIGINALS] + [RTL / 'dual_slider_candidate.sv', TB / 'tb_dual_slider.sv']
    local = sorted([p for d in (RTL, TB, HERE) for p in d.glob('*') if p.is_file()])
    # oss-cad-suite ships runtime DLLs in lib/, not only bin/ or lib/ivl/.
    tool_files = sorted(set([p for folder in (TOOLS / 'bin', TOOLS / 'lib/ivl')
                             for p in folder.rglob('*') if p.is_file()]
                            + [p for p in (TOOLS / 'lib').iterdir() if p.is_file()]))
    inputs = sorted(set(sources + local + [JOB, Path(sys.executable)]))
    before = {'inputs': identities(inputs), 'tools': identities(tool_files)}
    write(out / 'before.json', before)
    write(out / 'PREFLIGHT.json', {
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                             text=True).strip(),
        'candidate_identity': candidate_identity,
        'prior_started_groups': len(previous), 'prior_approval_denials': 2,
        'per_tool_limit_seconds': 90, 'group_tools_total_seconds': 300,
        'nightly_max_groups': 2, 'nightly_simulation_total_limit_seconds': 900,
        'tool_files': len(tool_files), 'board_release_allowed': False})
    command_environment = {key: os.environ[key] for key in (
        'SystemRoot', 'WINDIR', 'COMSPEC', 'OS', 'PROCESSOR_ARCHITECTURE',
        'NUMBER_OF_PROCESSORS', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH') if key in os.environ}
    command_environment.update(PATH=os.pathsep.join((str(TOOLS / 'bin'), str(TOOLS / 'lib'),
                               str(Path(os.environ['SystemRoot']) / 'System32'), os.environ['SystemRoot'])),
                               IVERILOG_ROOT=str(TOOLS / 'lib/ivl'),
                               TEMP=str(out), TMP=str(out))
    write(out / 'environment.json', command_environment)
    spec = importlib.util.spec_from_file_location('owned_windows_job', JOB)
    job_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(job_module)
    source_names = []
    for index, path in enumerate(sources):
        target = staged / ('s%02d.sv' % index)
        shutil.copyfile(path, target)
        if sha(target) != sha(path):
            raise RuntimeError('STAGE_IDENTITY')
        source_names.append(str(target))
    write(out / 'staging.json', identities(sorted(staged.iterdir())))
    receipts = []
    started = time.monotonic()

    def run(label, argv):
        budget = min(90, 300 - (time.monotonic() - started))
        if budget <= 0:
            raise RuntimeError('OUTER_TOTAL_BUDGET')
        receipt = {'argv': argv, 'cwd': str(staged), 'timeout_seconds': budget,
                   'owned_process_tree': True, 'exit_code': None, 'timeout': False,
                   'process_created': False}
        write(out / (label + '.launch.json'), receipt)
        began = time.monotonic()
        job = job_module.WindowsJob()
        try:
            with (out / (label + '.stdout.txt')).open('xb') as stdout, \
                    (out / (label + '.stderr.txt')).open('xb') as stderr:
                if not (out / 'TOOL_CREATE_RESERVED.json').exists():
                    write(out / 'TOOL_CREATE_RESERVED.json', {
                        'candidate_identity': candidate_identity,
                        'group_number': len(previous)+1,
                        'semantics': 'reservation before process create; unknown interrupted creation consumes conservatively'})
                process = subprocess.Popen(argv, cwd=staged, env=command_environment,
                                           stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                           creationflags=CREATE_SUSPENDED)
                receipt['process_created'] = True
                receipt['pid'] = process.pid
                if not (out / 'TOOL_STARTED.json').exists():
                    write(out / 'TOOL_STARTED.json', {
                        'first_pid': process.pid, 'first_label': label,
                        'group_number': len(previous)+1, 'candidate_identity': candidate_identity})
                job.attach_and_resume(process)
                try:
                    receipt['exit_code'] = process.wait(timeout=budget)
                except subprocess.TimeoutExpired:
                    receipt['timeout'] = True
                    job.terminate()
                    receipt['exit_code'] = process.wait(timeout=5)
        finally:
            job.close()
            receipt['elapsed_seconds'] = time.monotonic() - began
            write(out / (label + '.receipt.json'), receipt)
            receipts.append(receipt)
        if receipt['timeout']:
            raise RuntimeError(label + '_TIMEOUT')
        return receipt['exit_code'], (out / (label + '.stdout.txt')).read_text(encoding='utf-8', errors='replace')

    error = None
    results = []
    try:
        binary = staged / 'candidate.vvp'
        for label, tool in [('iverilog_version', 'iverilog.exe'), ('vvp_version', 'vvp.exe')]:
            code, _ = run(label, [str(TOOLS / 'bin' / tool), '-V'])
            if code != 0:
                raise RuntimeError(label + '_NONZERO')
        code, _ = run('compile', [str(TOOLS / 'bin/iverilog.exe'), '-g2012', '-Wall',
                                 '-s', 'tb_dual_slider', '-o', str(binary)] + source_names)
        if code != 0:
            raise RuntimeError('COMPILE_NONZERO_NEVER_RUN_ARTIFACT')
        good, text = run('positive', [str(TOOLS / 'bin/vvp.exe'), str(binary)])
        if good != 0 or 'PASS DUAL_SLIDER_ISOLATED checks=' not in text or 'REJECT' in text:
            raise RuntimeError('POSITIVE_REJECTED')
        results.append({'name': 'positive', 'exit_code': good, 'accepted': True})
        for mutation, diagnostic in [(1, 'MODE_CDC_DELIVERY'), (2, 'MODE_CDC_DELIVERY'),
                                     (3, 'FALLING_FRAME_PROGRESS'), (4, 'AUDIO_UNDERRUN')]:
            label = 'negative_%d' % mutation
            code, text = run(label, [str(TOOLS / 'bin/vvp.exe'), str(binary), '+mutation=%d' % mutation])
            if code == 0 or 'REJECT ' + diagnostic not in text or 'PASS DUAL_SLIDER' in text:
                raise RuntimeError(label + '_NOT_REJECTED_AS_EXPECTED')
            results.append({'name': label, 'exit_code': code, 'accepted': False,
                            'expected_rejection': diagnostic})
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    after = {'inputs': identities(inputs), 'tools': identities(tool_files)}
    write(out / 'after.json', after)
    unchanged = before == after
    outputs = identities(sorted(p for p in out.rglob('*') if p.is_file()))
    write(out / 'products.json', outputs)
    result = {'status': 'PASS' if error is None and unchanged else 'FAIL',
              'error': error, 'identity_unchanged': unchanged, 'results': results,
              'tool_starts': sum(r['process_created'] for r in receipts),
              'elapsed_seconds': time.monotonic()-started,
              'validation_level': ('L2_ISOLATED_CANDIDATE_FIXTURE' if results
                                   else 'L0_NO_SIMULATION_ACCEPTED'),
              'real_audio_chain': False, 'sta_run': False, 'hardware_run': False,
              'original_hit_flash': 'KNOWN_FAIL_DEFERRED_NOT_TESTED',
              'board_release_allowed': False}
    write(out / 'RESULT.json', result)
    write(out / 'NIGHT_RUN_RECEIPT.json', {
        **result, 'candidate_identity': candidate_identity,
        'group_number': len(previous)+1,
        'prior_started_groups': len(previous),
        'calls': receipts, 'prior_approval_denials': 2,
        'consumption_marker': 'TOOL_STARTED.json',
        'reservation_marker': 'TOOL_CREATE_RESERVED.json',
        'prior_static_package_preserved': True})
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
