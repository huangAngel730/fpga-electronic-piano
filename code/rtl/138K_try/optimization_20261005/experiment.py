"""Bounded physical-only 138K experiments; never touch production or prior evidence."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
HERE = Path(__file__).resolve().parent
assert HERE == ROOT / 'optimization_20261005'
BASE = ROOT / 'reproduction_20261005/138K_C_electrical_migration'
PROFILES = {'C_place2_route1': (2, 1), 'C_place2_route2': (2, 2),
            'C_reset_location': (0, 0), 'C_reset_route1': (0, 1)}
RESET_LABEL = 'C_reset_location'
RESET_LABELS = {RESET_LABEL, 'C_reset_route1'}


def expected_cst(label, original):
    if label not in RESET_LABELS:
        return original
    for suffix in ['A', 'B']:
        before = f'R49C101[1][{suffix}]'.encode()
        after = f'R44C168[1][{suffix}]'.encode()
        assert original.count(before) == 1
        original = original.replace(before, after)
    return original


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(label):
    place, route = PROFILES[label]
    out = HERE / label
    if out.exists():
        raise ValueError('Preserve every previous attempt')
    out.mkdir()
    records = []
    for directory in ['sources', 'constraints', 'rom', 'include']:
        for source in (BASE / directory).iterdir():
            assert source.is_file()
            target = out / directory / source.name
            target.parent.mkdir(exist_ok=True)
            original = source.read_bytes()
            relocated = original.replace(BASE.as_posix().encode(), out.as_posix().encode())
            assert relocated.replace(out.as_posix().encode(), BASE.as_posix().encode()) == original
            if source.name == 'audio_visual.cst':
                relocated = expected_cst(label, relocated)
            target.write_bytes(relocated)
            records.append({'path': str(target.relative_to(out)), 'baseline_SHA256': sha(original),
                            'candidate_SHA256': sha(relocated),
                            'path_only_relocations': original.count(BASE.as_posix().encode())})
    assert len(records) == 56
    for name in ['audio_visual.cst', 'audio_visual_hold055.sdc']:
        expected = (BASE / 'constraints' / name).read_bytes()
        if name.endswith('.cst'):
            expected = expected_cst(label, expected)
        assert (out / 'constraints' / name).read_bytes() == expected
    project = ET.fromstring((BASE / 'audio_visual_coexistence_top.gprj').read_bytes())
    for node in project.findall('./FileList/File'):
        node.set('path', node.attrib['path'].replace(BASE.as_posix(), out.as_posix()))
    assert len(project.findall('./FileList/File')) == 47
    (out / 'audio_visual_coexistence_top.gprj').write_bytes(
        ET.tostring(project, encoding='utf-8', xml_declaration=True))
    tcl = (BASE / 'run.tcl').read_text(encoding='utf-8').replace(BASE.as_posix(), out.as_posix())
    assert tcl.count('set_option -place_option 0') == tcl.count('set_option -route_option 0') == 1
    tcl = tcl.replace('set_option -place_option 0', f'set_option -place_option {place}')
    tcl = tcl.replace('set_option -route_option 0', f'set_option -route_option {route}')
    (out / 'run.tcl').write_text(tcl, encoding='utf-8')
    manifest = {'label': label, 'baseline': str(BASE), 'inputs': records,
                'changes': {'place_option': [0, place], 'route_option': [0, route]},
                'scope': 'Complete four-voice V0171 audio+HDMI physical experiment only',
                'RTL_functional_change': False, 'SDC_byte_identical': True,
                'CST_byte_identical': label not in RESET_LABELS,
                'original_repo_written': False, 'programmed': False}
    if label in RESET_LABELS:
        evidence = BASE / 'impl/pnr/audio_visual_coexistence_top_tr_content.html'
        text = evidence.read_text(encoding='utf-8')
        for suffix, register in [('A', 'dout_6_s0'), ('B', 'dout_0_s0')]:
            assert f'<td>R44C168[1][{suffix}]</td>' in text
            assert f'TMDS8b10b_inst_g/{register}/CLK' in text
        manifest['changes']['serial_reset_fixed_locations'] = {
            'before': ['R49C101[1][A]', 'R49C101[1][B]'],
            'after': ['R44C168[1][A]', 'R44C168[1][B]'],
            'basis': 'Actual 138K C DVI encoder FF locations, nearer encoder cluster; hypothesis not guaranteed timing gain',
            'source_report': str(evidence), 'source_report_SHA256': sha(evidence.read_bytes()),
            'old_worst_reset_route_ns': 4.502}
    (out / 'input_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('PREPARED', label, '56 files, 47 project inputs; no RTL/SDC changes', flush=True)
    return out


def run(label):
    out = prepare(label)
    log = out / 'build.log'
    receipt = out / 'build_receipt.json'
    tool = ROOT / 'tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe'
    env = dict(os.environ)
    env['TMP'] = env['TEMP'] = str(out / 'tmp')
    (out / 'tmp').mkdir()
    command = [str(tool), 'run.tcl']
    record = {'label': label, 'started': datetime.now().astimezone().isoformat(),
              'command': command, 'cwd': str(out), 'state': 'running', 'timeout_s': 1800,
              'original_repo_written': False, 'programmed': False}
    with log.open('wb') as output:
        process = subprocess.Popen(command, cwd=out, env=env, stdout=output, stderr=subprocess.STDOUT)
        record['pid'] = process.pid
        receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print('START', label, record['started'], 'PID', process.pid, flush=True)
        try:
            code = process.wait(timeout=1800)
            record['state'] = 'finished'
        except subprocess.TimeoutExpired:
            # Kill only the child tree started above, never other Gowin processes.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], check=False,
                           stdout=output, stderr=subprocess.STDOUT)
            process.wait(timeout=30)
            code = process.returncode
            record['state'] = 'time_limit_stopped_not_complete'
    record.update({'finished': datetime.now().astimezone().isoformat(), 'exit_code': code,
                   'build_log_SHA256': sha(log.read_bytes())})
    receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print('FINISH', label, record['state'], 'CLI', code, record['finished'], flush=True)
    print(log.read_text(encoding='utf-8', errors='replace')[-2500:], flush=True)
    return code


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in PROFILES:
        raise ValueError('Choose one explicitly authorized physical profile')
    raise SystemExit(run(sys.argv[1]))
