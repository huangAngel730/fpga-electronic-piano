"""Independent continuation of the preserved +0.025 ns 138K baseline."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
assert HERE == Path('E:/FPGA/GAOYUNFPGA/138K_try/optimization_followup_20261005')
OLD = ROOT / 'optimization_20261005'
BASE = OLD / 'C_reset_route1'
REPO = Path('E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano')
SCOPE = REPO / 'code/tb/common/midi_prepared_candidate'
CAD = ROOT / 'tools/icarus_oss_copy'
LABEL = 'A_prepared_selector'
OUT = HERE / LABEL


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def protected_hashes():
    paths = sorted(p for p in OLD.rglob('*') if p.is_file())
    guide = ROOT / 'M2_60K物理优化方法与验收说明_20261005.md'
    if guide.exists():
        paths.append(guide)
    return {str(p): sha(p.read_bytes()) for p in paths}


def preserve_begin():
    receipt = HERE / 'preservation_before.json'
    if receipt.exists():
        raise ValueError('Do not overwrite prior followup evidence')
    write_json(receipt, protected_hashes())


def preserve_check():
    before = json.loads((HERE / 'preservation_before.json').read_text(encoding='utf-8'))
    after = protected_hashes()
    errors = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
    write_json(HERE / 'preservation_verification.json', {
        'time': datetime.now().astimezone().isoformat(), 'files': len(before),
        'changed_added_removed': errors, 'passed': not errors})
    assert not errors, errors
    print('Preserved baseline and old evidence:', len(before), 'files PASS', flush=True)


def prepare():
    if OUT.exists():
        raise ValueError('Preserve every previous trial')
    OUT.mkdir()
    manifest = json.loads((SCOPE / 'manifest.json').read_text(encoding='utf-8'))
    assert sha((BASE / 'sources/midi_event_parser.sv').read_bytes()) == manifest['frozen_parser_SHA']
    candidate = (SCOPE / 'midi_event_parser.sv').read_bytes()
    assert sha(candidate) == manifest['candidate_SHA']
    records = []
    for directory in ['sources', 'constraints', 'rom', 'include']:
        for source in (BASE / directory).iterdir():
            assert source.is_file()
            target = OUT / directory / source.name
            target.parent.mkdir(exist_ok=True)
            original = source.read_bytes()
            body = original.replace(BASE.as_posix().encode(), OUT.as_posix().encode())
            assert body.replace(OUT.as_posix().encode(), BASE.as_posix().encode()) == original
            if source.name == 'midi_event_parser.sv':
                body = candidate
            target.write_bytes(body)
            records.append({'path': target.relative_to(OUT).as_posix(),
                            'baseline_SHA256': sha(original), 'candidate_SHA256': sha(body),
                            'path_only_relocations': original.count(BASE.as_posix().encode()),
                            'RTL_change': source.name == 'midi_event_parser.sv'})
    assert len(records) == 56
    for name in ['audio_visual.cst', 'audio_visual_hold055.sdc']:
        assert (OUT / 'constraints' / name).read_bytes() == (BASE / 'constraints' / name).read_bytes()
    project = ET.fromstring((BASE / 'audio_visual_coexistence_top.gprj').read_bytes())
    for node in project.findall('./FileList/File'):
        node.set('path', node.attrib['path'].replace(BASE.as_posix(), OUT.as_posix()))
    assert len(project.findall('./FileList/File')) == 47
    (OUT / 'audio_visual_coexistence_top.gprj').write_bytes(
        ET.tostring(project, encoding='utf-8', xml_declaration=True))
    tcl = (BASE / 'run.tcl').read_text(encoding='utf-8').replace(BASE.as_posix(), OUT.as_posix())
    assert 'set_option -route_option 1' in tcl and 'set_option -place_option 0' in tcl
    (OUT / 'run.tcl').write_text(tcl, encoding='utf-8')
    write_json(OUT / 'input_manifest.json', {
        'baseline': str(BASE), 'inputs': records, 'candidate_provenance': str(SCOPE),
        'candidate_manifest': manifest, 'changes': ['sources/midi_event_parser.sv'],
        'public_cycle_latency_intended_unchanged': True,
        'SDC_CST_options_unchanged': True, 'original_repo_written': False, 'programmed': False})
    print('Prepared new trial from C_reset_route1: 56 inputs, one RTL replacement', flush=True)


def functional():
    out = OUT / 'functional'
    out.mkdir()
    env = dict(os.environ)
    env['PATH'] = str(CAD / 'bin') + ';' + env['PATH']
    env['TMP'] = env['TEMP'] = str(out / 'tmp')
    (out / 'tmp').mkdir()
    results = {}
    def run(name, command, good=True, marker=None, timeout=240):
        started = time.monotonic()
        log = out / (name + '.log')
        with log.open('wb') as stream:
            process = subprocess.run([str(x) for x in command], cwd=out, env=env,
                                     stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        text = log.read_text(encoding='utf-8', errors='replace')
        results[name] = {'command': [str(x) for x in command], 'exit': process.returncode,
                         'expected_success': good, 'log_SHA256': sha(log.read_bytes()),
                         'elapsed_s': round(time.monotonic() - started, 2)}
        write_json(out / 'run_status.json', results)
        print(name, 'exit', process.returncode, text[-700:], flush=True)
        if (process.returncode == 0) != good or (marker and marker not in text):
            raise ValueError('Unexpected test result: ' + name)
    defs = OUT / 'sources/audio_defs_pkg.sv'
    candidate = OUT / 'sources/midi_event_parser.sv'
    ref = out / 'reference.sv'
    original = (BASE / 'sources/midi_event_parser.sv').read_bytes()
    assert original.count(b'module midi_event_parser #(') == 1
    ref.write_bytes(original.replace(b'module midi_event_parser #(', b'module midi_event_parser_frozen #(', 1))
    original_tb = REPO / 'code/tb/common/midi_scheduler_setup_review/tb_m2_parser_miter.sv'
    bench = original_tb.read_text(encoding='utf-8')
    assert bench.count('i==3?3:8') == 1
    tb = out / 'tb.sv'
    tb.write_text(bench.replace('i==3?3:8', 'i==3?16:8'), encoding='utf-8')
    compiler = [CAD / 'bin/iverilog.exe', '-B', CAD / 'lib/ivl', '-g2012', '-s', 'tb_m2_parser_miter']
    run('positive_compile', compiler + ['-o', out / 'positive.vvp', defs, candidate, ref, tb], timeout=40)
    run('positive', [CAD / 'bin/vvp.exe', out / 'positive.vvp'], marker='PASS M2 full original parser miter lane=3')
    text = candidate.read_text(encoding='utf-8')
    for name, before, after in [
            ('stale_latest', 'parsed_control_rank <= first_prepared_rank', 'parsed_control_rank < first_prepared_rank'),
            ('missing_previous_repair', 'previous_update<=parsed_control;', "previous_update<=1'b0;")]:
        assert before in text
        bad = out / (name + '.sv')
        bad.write_text(text.replace(before, after, 1), encoding='utf-8')
        image = out / (name + '.vvp')
        run(name + '_compile', compiler + ['-o', image, defs, bad, ref, tb], timeout=40)
        run(name, [CAD / 'bin/vvp.exe', image], good=False, marker='full parser')
    # Preserve original directed fixture; alter paths/tool invocation only.
    directed_source = SCOPE / 'run_directed.py'
    body = directed_source.read_text(encoding='utf-8')
    replacements = [
        ("root=Path(__file__).resolve().parents[4]; scope=root/'code/tb/common/midi_prepared_candidate'",
         f"root=Path({OUT.as_posix()!r}); scope=root/'sources'"),
        ("out.relative_to(root/'code/output')", 'out.relative_to(root)'),
        ("Path('D:/Gowin/oss-cad-suite')", f'Path({CAD.as_posix()!r})'),
        ("'-g2012'", "'-B',str(cad/'lib/ivl'),'-g2012'"),
        ("root/'code/rtl/common/audio_defs_pkg.sv'", "root/'sources/audio_defs_pkg.sv'")]
    for before, after in replacements:
        assert body.count(before) == 1, before
        body = body.replace(before, after)
    directed = out / 'run_directed_isolated.py'
    directed.write_text(body, encoding='utf-8')
    run('directed_checker', [sys.executable, '-B', '-X', 'utf8', directed, '--output', out / 'directed'],
        marker='third_fallback_wrong compile 0 run 1', timeout=90)
    write_json(out / 'functional_review.json', {
        'passed': True, 'runs': results, 'candidate_SHA256': sha(candidate.read_bytes()),
        'frozen_reference_SHA256': sha(original), 'original_TB_SHA256': sha(original_tb.read_bytes()),
        'adapted_TB_SHA256': sha(tb.read_bytes()),
        'directed_original_SHA256': sha(directed_source.read_bytes()),
        'directed_adaptations': replacements,
        'coverage': 'All public outputs and scheduler register state each cycle; four configs; burst1/8/16; 33 directed checks; 3 compiled behavioral mutants rejected',
        'formal_repo_written': False})


def build():
    assert json.loads((OUT / 'functional/functional_review.json').read_text(encoding='utf-8'))['passed']
    env = dict(os.environ)
    env['TMP'] = env['TEMP'] = str(OUT / 'tmp')
    (OUT / 'tmp').mkdir()
    command = [str(ROOT / 'tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe'), 'run.tcl']
    log = OUT / 'build.log'
    receipt = OUT / 'build_receipt.json'
    assert not log.exists() and not receipt.exists()
    record = {'started': datetime.now().astimezone().isoformat(), 'command': command,
              'cwd': str(OUT), 'state': 'running', 'timeout_s': 1800, 'programmed': False}
    with log.open('wb') as stream:
        process = subprocess.Popen(command, cwd=OUT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record['pid'] = process.pid
        write_json(receipt, record)
        print('START Gowin', record['started'], 'PID', process.pid, flush=True)
        try:
            code = process.wait(timeout=1800)
            record['state'] = 'finished'
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=stream, stderr=subprocess.STDOUT, check=False)
            process.wait(timeout=30)
            code = process.returncode
            record['state'] = 'time_limit_stopped_not_complete'
    record.update({'finished': datetime.now().astimezone().isoformat(), 'exit_code': code,
                   'build_log_SHA256': sha(log.read_bytes())})
    write_json(receipt, record)
    print('FINISH Gowin', code, record['finished'], log.read_text(encoding='utf-8', errors='replace')[-3000:], flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['start']:
        preserve_begin()
        try:
            prepare()
            functional()
            build()
        finally:
            preserve_check()
    elif sys.argv[1:] == ['preserve-check']:
        preserve_check()
    else:
        raise ValueError('Explicit start or preserve-check required')
