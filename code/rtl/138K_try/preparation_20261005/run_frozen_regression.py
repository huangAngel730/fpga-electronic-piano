"""Run selected original benches against SHA-proven frozen DUTs, output-only."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
if HERE != Path('E:/FPGA/GAOYUNFPGA/138K_try/preparation_20261005'):
    raise ValueError('Unexpected output directory')
REPO = Path('E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano')
DUT = HERE / 'relocated_bundle/sources'
OUT = HERE / 'regression'
OUT.mkdir(exist_ok=True)
BENCH = OUT / 'bench_original'
BENCH.mkdir(exist_ok=True)
tool = HERE.parent / 'tools/icarus_oss_copy'
env = dict(os.environ)
env['PATH'] = str(tool / 'bin') + os.pathsep + env.get('PATH', '')
env['TMP'] = env['TEMP'] = str(OUT / 'tmp')
(OUT / 'tmp').mkdir(exist_ok=True)
helper_paths = [
    'code/tb/input/tb_button_debouncer.sv', 'code/tb/common/tb_performance_event_fifo.sv',
    'code/tb/input/tb_midi_cc64.sv', 'code/tb/input/tb_midi_input.sv',
    'code/tb/common/button_tail_select_candidate/tb_button_tail_select.sv',
    'code/tb/input/button_counter_timing/button_reference.sv',
    'code/tb/input/button_counter_timing/fifo_reference.sv',
    'code/tb/input/button_counter_timing/fifo_no_full_bypass.sv',
]
hashes = {}
for relative in helper_paths:
    source = REPO / relative
    target = BENCH / source.name
    data = source.read_bytes()
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Preserve old bench evidence')
    target.write_bytes(data)
    hashes[relative] = hashlib.sha256(data).hexdigest()
defs = DUT / 'audio_defs_pkg.sv'
cases = [
    ('debouncer', 'tb_button_debouncer', [DUT / 'button_debouncer.sv'], 'tb_button_debouncer.sv', [], 'PASS: tb_button_debouncer'),
    ('public_fifo', 'tb_performance_event_fifo', [defs, DUT / 'performance_event_fifo.sv'], 'tb_performance_event_fifo.sv', [], 'PASS tb_performance_event_fifo'),
    ('midi_cc64', 'tb_midi_cc64', [defs, DUT / 'midi_event_parser.sv'], 'tb_midi_cc64.sv', [], 'PASS tb_midi_cc64'),
    ('midi_uart', 'tb_midi_input', [defs, DUT / 'uart_rx.sv', DUT / 'midi_event_parser.sv', DUT / 'midi_input.sv'], 'tb_midi_input.sv', [], 'PASS: tb_midi_input'),
]
for depth, local in [(3, 2), (4, 4), (32, 4)]:
    sources = [defs, BENCH / 'button_reference.sv', BENCH / 'fifo_reference.sv',
               BENCH / 'fifo_no_full_bypass.sv', DUT / 'button_event_converter.sv',
               DUT / 'performance_event_fifo.sv']
    cases.append((f'counter_d{depth}_l{local}', 'tb_button_tail_select', sources,
                  'tb_button_tail_select.sv', ['-P', f'tb_button_tail_select.DEPTH={depth}',
                                              '-P', f'tb_button_tail_select.LOCAL={local}'],
                  'PASS button_counter_timing'))
results = []


def run(command, cwd, logfile, timeout=45):
    try:
        process = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=timeout)
        data = process.stdout + process.stderr
        code = process.returncode
    except subprocess.TimeoutExpired as exc:
        data = (exc.stdout or b'') + (exc.stderr or b'') + b'\nRUNNER_TIMEOUT\n'
        code = 124
    logfile.write_bytes(data)
    return code, data.decode('utf-8', errors='replace')


for name, top, sources, bench, parameters, pass_marker in cases:
    folder = OUT / name
    folder.mkdir(exist_ok=True)
    binary = folder / 'sim.vvp'
    command = [str(tool / 'bin/iverilog.exe'), '-B', str(tool / 'lib/ivl'),
               '-g2012', '-s', top, *parameters, '-o', str(binary),
               *map(str, sources), str(BENCH / bench)]
    compile_code, compile_text = run(command, folder, folder / 'compile.log')
    run_code, text = None, ''
    if compile_code == 0:
        run_code, text = run([str(tool / 'bin/vvp.exe'), str(binary)], folder, folder / 'run.log')
    passed = compile_code == 0 and run_code == 0 and pass_marker in text and not re.search(
        r'FATAL:|\bFAIL\b|\bERROR:|RUNNER_TIMEOUT', text)
    record = {'case': name, 'compile_command': command, 'compile_exit': compile_code,
              'run_exit': run_code, 'passed': passed,
              'pass_lines': [line for line in text.splitlines() if 'PASS' in line],
              'DUT_SHA256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.parent == DUT},
              'log_SHA256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.log')}}
    results.append(record)
    print(('PASS' if passed else 'FAIL'), name, 'compile=', compile_code, 'run=', run_code, flush=True)
    if passed:
        print('\n'.join(record['pass_lines']), flush=True)
    else:
        print((text or compile_text)[-1800:], flush=True)
report = {'time': datetime.now().astimezone().isoformat(),
          'scope': 'Selected frozen DUT functional regression only, NOT whole audio/video or hardware acceptance',
          'bench_source_SHA256': hashes, 'DUT_modified': False, 'bench_modified': False,
          'results': results, 'passed': all(r['passed'] for r in results),
          'original_repo_written': False, 'programmed': False}
(HERE / 'frozen_regression_results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
