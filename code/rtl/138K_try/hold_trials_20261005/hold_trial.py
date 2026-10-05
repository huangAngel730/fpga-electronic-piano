"""40MHz Hold repair experiments; writes exclusively under this experiment."""
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import types
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
assert ROOT == Path('E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try')
BASE = ROOT / 'clock_trials_20261005/H_pll_core40_route2'
OLD_BASE = 'E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005/H_pll_core40_route2'
STEM = 'audio_visual_coexistence_top'
CAD = ROOT / 'tools/icarus_oss_copy'
LABELS = ['I_hold_locations', 'J_base_encoded', 'K_encoded_guard065', 'L_locations_guard065']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.resolve().relative_to(HERE)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def preserve(start=False):
    # Freeze every pre-existing experiment payload, excluding huge tool trees.
    target = HERE / 'preservation_before.json'
    if start:
        assert not target.exists()
        records = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
                   for name in ['clock_trials_20261005', 'structural_trials_20261005',
                                'pipeline_trials_20261005', 'optimization_20261005',
                                'optimization_followup_20261005']
                   for p in (ROOT / name).rglob('*') if p.is_file()}
        write_json(target, records)
    previous = json.loads(target.read_text(encoding='utf-8'))
    changed = [p for p, digest in previous.items() if not (ROOT / p).is_file()
               or sha((ROOT / p).read_bytes()) != digest]
    write_json(HERE / 'preservation_verification.json',
               {'files': len(previous), 'passed': not changed, 'changed': changed,
                'time': datetime.now().astimezone().isoformat()})
    assert not changed, changed
    success_snapshot = HERE / 'I_preservation_before_L.json'
    if success_snapshot.exists():
        successful = json.loads(success_snapshot.read_text(encoding='utf-8'))
        assert all((HERE / 'I_hold_locations' / p).is_file() and
                   sha((HERE / 'I_hold_locations' / p).read_bytes()) == digest
                   for p, digest in successful.items()), 'Successful I evidence changed'
    print('Protected', len(previous), 'old experiment files PASS', flush=True)


def folder(label):
    assert label in LABELS
    path = HERE / label
    path.resolve().relative_to(HERE)
    return path


def normalize(data, out):
    return data.replace(out.as_posix().encode(), OLD_BASE.encode())


def prepare(label):
    preserve()
    out = folder(label)
    assert not out.exists(), 'Preserve earlier candidate evidence'
    out.mkdir()
    source = BASE
    prefix = OLD_BASE.encode()
    if label == 'L_locations_guard065':
        source = folder('I_hold_locations')
        assert json.loads((source / 'assessment.json').read_text(encoding='utf-8'))['user_acceptance_passed']
        prefix = source.as_posix().encode()
        snapshot = HERE / 'I_preservation_before_L.json'
        assert not snapshot.exists()
        write_json(snapshot, {p.relative_to(source).as_posix(): sha(p.read_bytes())
                              for p in source.rglob('*') if p.is_file()})
    for directory in ['sources', 'constraints', 'rom', 'include']:
        (out / directory).mkdir()
        for path in (source / directory).iterdir():
            assert path.is_file()
            (out / directory / path.name).write_bytes(path.read_bytes().replace(prefix, out.as_posix().encode()))
    for name in [STEM + '.gprj', 'run.tcl']:
        (out / name).write_bytes((source / name).read_bytes().replace(prefix, out.as_posix().encode()))
    (out / 'functional').mkdir()
    print('Prepared relocated +1.522ns baseline', label, flush=True)


def seal(label):
    out = folder(label)
    records, changed = [], []
    expected = {'I_hold_locations': {'constraints/audio_visual.cst', 'constraints/audio_visual_hold055.sdc'},
                'J_base_encoded': {'sources/pitch_mod_fcw_pipeline.sv', 'constraints/audio_visual_hold055.sdc'},
                'K_encoded_guard065': {'sources/pitch_mod_fcw_pipeline.sv', 'constraints/audio_visual_hold055.sdc'},
                'L_locations_guard065': {'constraints/audio_visual.cst', 'constraints/audio_visual_hold055.sdc'}}[label]
    for directory in ['sources', 'constraints', 'rom', 'include']:
        for path in (out / directory).iterdir():
            rel = path.relative_to(out).as_posix()
            actual, original = path.read_bytes(), (BASE / rel).read_bytes()
            if normalize(actual, out) != original:
                changed.append(rel)
            records.append({'path': rel, 'baseline_SHA256': sha(original), 'candidate_SHA256': sha(actual)})
    assert len(records) == 56 and set(changed) == expected, changed
    entries = ET.parse(out / (STEM + '.gprj')).getroot().findall('./FileList/File')
    assert len(entries) == 47
    for item in entries:
        path = Path(item.attrib['path'])
        path.resolve().relative_to(out)
        assert path.is_file()
    assert OLD_BASE not in (out / (STEM + '.gprj')).read_text(encoding='utf-8')
    assert normalize((out / 'run.tcl').read_bytes(), out) == (BASE / 'run.tcl').read_bytes()
    write_json(out / 'input_manifest.json', {'baseline': str(BASE), 'inputs': records,
               'changes': sorted(changed), 'actual_clock_MHz': {'core': 40, 'pixel': 25, 'serial': 125},
               'only_authorized_experiment_folder_written': True, 'programmed': False})
    preserve()


def functional(label):
    out = folder(label)
    verify_inputs(label)
    # Reuse read-only test implementation via explicit configuration injection.
    # The old driver is NOT imported (it has obsolete absolute paths).
    shim = types.ModuleType('clock_trial')
    for name, value in {'HERE': HERE, 'ROOT': ROOT, 'OUT': out, 'CAD': CAD,
                        'STEM': STEM, 'sha': sha, 'write_json': write_json,
                        'protect': preserve}.items():
        setattr(shim, name, value)
    sys.modules['clock_trial'] = shim
    sys.argv = [str(ROOT / 'clock_trials_20261005/run_functional.py'), '--CDC-state-check']
    runpy.run_path(sys.argv[0], run_name='__main__')


def verify_inputs(label):
    out = folder(label)
    manifest = json.loads((out / 'input_manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['inputs']) == 56
    for record in manifest['inputs']:
        assert sha((BASE / record['path']).read_bytes()) == record['baseline_SHA256']
        assert sha((out / record['path']).read_bytes()) == record['candidate_SHA256']
    return manifest


def build(label):
    out = folder(label)
    verify_inputs(label)
    assert json.loads((out / 'functional/functional_review.json').read_text(encoding='utf-8'))['passed']
    if label in ['J_base_encoded', 'K_encoded_guard065']:
        assert json.loads((out / 'miter/review.json').read_text(encoding='utf-8'))['passed']
    receipt, log = out / 'build_receipt.json', out / 'build.log'
    assert not receipt.exists() and not log.exists()
    env = dict(os.environ)
    env['TMP'] = env['TEMP'] = str(out / 'tmp')
    (out / 'tmp').mkdir()
    command = [str(ROOT / 'tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe'), 'run.tcl']
    record = {'state': 'running', 'started': datetime.now().astimezone().isoformat(),
              'command': command, 'cwd': str(out), 'timeout_s': 1800, 'programmed': False}
    preserve()
    try:
        with log.open('wb') as stream:
            process = subprocess.Popen(command, cwd=out, env=env, stdout=stream, stderr=subprocess.STDOUT)
            record['pid'] = process.pid
            write_json(receipt, record)
            print('START', label, record['started'], process.pid, flush=True)
            try:
                process.wait(timeout=1800)
                record['state'] = 'finished'
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=stream, stderr=subprocess.STDOUT)
                process.wait(timeout=30)
                record['state'] = 'time_limit_stopped_not_complete'
        record.update({'exit_code': process.returncode, 'finished': datetime.now().astimezone().isoformat(),
                       'build_log_SHA256': sha(log.read_bytes())})
        write_json(receipt, record)
        print('FINISH', label, record, log.read_text(encoding='utf-8', errors='replace')[-2200:], flush=True)
    finally:
        preserve()


def main():
    if sys.argv[1:] == ['init']:
        preserve(start=True)
        for name in ['tb_pll40.sv', 'tb_clock40_top.sv', 'dvi_sim_stub.v']:
            target = HERE / name
            assert not target.exists()
            target.write_bytes((ROOT / 'clock_trials_20261005' / name).read_bytes())
    elif sys.argv[1:] == ['protect']:
        preserve()
    else:
        action, label = sys.argv[1:]
        {'prepare': prepare, 'seal': seal, 'functional': functional, 'build': build}[action](label)


if __name__ == '__main__':
    main()
