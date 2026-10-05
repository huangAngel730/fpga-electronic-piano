"""Isolated 40 MHz core + unchanged 25/125 MHz video from the +.039 baseline."""
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
assert HERE == Path('E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005')
BASE = ROOT / 'structural_trials_20261005/E_fixed_slot_next'
OUT = HERE / 'G_pll_core40'
STEM = 'audio_visual_coexistence_top'
CAD = ROOT / 'tools/icarus_oss_copy'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def imported(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def protected():
    result = {}
    for name in ['optimization_20261005', 'optimization_followup_20261005',
                 'pipeline_trials_20261005', 'structural_trials_20261005']:
        for path in (ROOT / name).rglob('*'):
            if path.is_file():
                result[str(path)] = sha(path.read_bytes())
    guide = ROOT / 'M2_60K物理优化方法与验收说明_20261005.md'
    result[str(guide)] = sha(guide.read_bytes())
    return result


def protect(begin=False):
    receipt = HERE / 'preservation_before.json'
    if begin:
        assert not receipt.exists()
        write_json(receipt, protected())
        return
    before = json.loads(receipt.read_text(encoding='utf-8'))
    after = protected()
    changed = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
    write_json(HERE / 'preservation_verification.json', {'files': len(before), 'passed': not changed,
               'changed_added_removed': changed, 'time': datetime.now().astimezone().isoformat()})
    assert not changed, changed
    print('Protected', len(before), 'old files PASS', flush=True)


def prepare():
    assert not OUT.exists()
    OUT.mkdir()
    for directory in ['sources', 'constraints', 'rom', 'include']:
        (OUT / directory).mkdir()
        for source in (BASE / directory).iterdir():
            assert source.is_file()
            body = source.read_bytes().replace(BASE.as_posix().encode(), OUT.as_posix().encode())
            (OUT / directory / source.name).write_bytes(body)
    project = ET.fromstring((BASE / (STEM + '.gprj')).read_bytes())
    entries = project.findall('./FileList/File')
    assert len(entries) == 47
    for entry in entries:
        entry.set('path', entry.attrib['path'].replace(BASE.as_posix(), OUT.as_posix()))
    (OUT / (STEM + '.gprj')).write_bytes(ET.tostring(project, encoding='utf-8', xml_declaration=True))
    (OUT / 'run.tcl').write_bytes((BASE / 'run.tcl').read_bytes().replace(BASE.as_posix().encode(), OUT.as_posix().encode()))
    print('Copied +.039 baseline, 56 inputs; edit only isolated copies', flush=True)


ALLOWED = {'sources/audio_visual_coexistence_top.sv', 'sources/audio_visual_display_probe.sv',
           'sources/TMDS_PLL_800_600_60.v', 'constraints/audio_visual_hold055.sdc'}


def seal():
    records, changed = [], []
    for directory in ['sources', 'constraints', 'rom', 'include']:
        for path in (OUT / directory).iterdir():
            rel = path.relative_to(OUT).as_posix()
            original = (BASE / rel).read_bytes()
            actual = path.read_bytes()
            normalized = actual.replace(OUT.as_posix().encode(), BASE.as_posix().encode())
            if normalized != original:
                changed.append(rel)
            records.append({'path': rel, 'baseline_SHA256': sha(original), 'candidate_SHA256': sha(actual)})
    assert len(records) == 56 and set(changed) == ALLOWED, changed
    assert (OUT / 'sources/midi_event_parser.sv').read_bytes() == (BASE / 'sources/midi_event_parser.sv').read_bytes()
    assert (OUT / 'constraints/audio_visual.cst').read_bytes() == (BASE / 'constraints/audio_visual.cst').read_bytes()
    write_json(OUT / 'input_manifest.json', {'baseline': str(BASE), 'inputs': records, 'changes': sorted(changed),
               'actual_clock_plan_MHz': {'reference': 50, 'system': 40, 'pixel': 25, 'serial': 125},
               'formal_repo_written': False, 'programmed': False})
    print('Sealed exact authorized clock/parameter change set', sorted(changed), flush=True)


def build():
    functional = json.loads((OUT / 'functional/functional_review.json').read_text(encoding='utf-8'))
    assert functional['passed']
    manifest = json.loads((OUT / 'input_manifest.json').read_text(encoding='utf-8'))
    assert all(sha((OUT / r['path']).read_bytes()) == r['candidate_SHA256'] for r in manifest['inputs'])
    env = dict(os.environ)
    env['TMP'] = env['TEMP'] = str(OUT / 'tmp')
    (OUT / 'tmp').mkdir()
    command = [str(ROOT / 'tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe'), 'run.tcl']
    receipt = OUT / 'build_receipt.json'
    log = OUT / 'build.log'
    assert not receipt.exists() and not log.exists()
    record = {'state': 'running', 'started': datetime.now().astimezone().isoformat(), 'command': command,
              'cwd': str(OUT), 'timeout_s': 1800, 'programmed': False}
    with log.open('wb') as stream:
        process = subprocess.Popen(command, cwd=OUT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record['pid'] = process.pid
        write_json(receipt, record)
        print('START Gowin', record['started'], 'PID', process.pid, flush=True)
        try:
            process.wait(timeout=1800)
            record['state'] = 'finished'
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=stream, stderr=subprocess.STDOUT)
            process.wait(timeout=30)
            record['state'] = 'time_limit_stopped_not_complete'
    record.update({'finished': datetime.now().astimezone().isoformat(), 'exit_code': process.returncode,
                   'build_log_SHA256': sha(log.read_bytes())})
    write_json(receipt, record)
    print('FINISH', record, log.read_text(encoding='utf-8', errors='replace')[-2800:], flush=True)


if __name__ == '__main__':
    action = sys.argv[1:]
    if action == ['prepare']:
        protect(begin=True)
        prepare()
        protect()
    elif action == ['seal']:
        seal()
        protect()
    elif action == ['build']:
        protect()
        try:
            build()
        finally:
            protect()
    elif action == ['protect']:
        protect()
    else:
        raise ValueError('Choose prepare, seal, build, protect')
