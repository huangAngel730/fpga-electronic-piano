"""Real Gowin primitive PLL simulation plus real RTL whole-top clock-plan checks."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clock_trial as trial

HERE, OUT, CAD = trial.HERE, trial.OUT, trial.CAD
mode = sys.argv[1:]
final_attempt = mode in [['--startup-mute-guard'], ['--CDC-state-check']]
out = OUT / ('functional_v6_CDC_state_check' if mode == ['--CDC-state-check'] else
             'functional_v5_startup_mute_guard' if final_attempt else
             'functional_v4_icarus_syntax_adapter' if mode == ['--icarus-syntax-adapter'] else
             'functional_v3_DVI_boundary_stub' if mode == ['--DVI-boundary-stub'] else
             'functional_v2_include_adapter' if mode == ['--include-adapter'] else 'functional')
assert not out.exists(), 'Preserve all earlier test evidence'
out.mkdir()
(out / 'tmp').mkdir()
env = dict(os.environ)
env['PATH'] = str(CAD / 'bin') + ';' + env['PATH']
env['TMP'] = env['TEMP'] = str(out / 'tmp')
records = {}
for bench in [HERE / 'tb_pll40.sv', HERE / 'tb_clock40_top.sv']:
    (out / bench.name).write_bytes(bench.read_bytes())
compiler = [CAD / 'bin/iverilog.exe', '-B', CAD / 'lib/ivl', '-g2012']
vendor = trial.ROOT / 'tools/gowin_1_9_11_03/IDE/simlib/gw5a/prim_sim.v'
pll = OUT / 'sources/TMDS_PLL_800_600_60.v'


def run(name, command, good=True, marker=None, timeout=600):
    log = out / (name + '.log')
    with log.open('wb') as stream:
        result = subprocess.run([str(x) for x in command], env=env, cwd=out, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout)
    body = log.read_text(encoding='utf-8', errors='replace')
    records[name] = {'command': [str(x) for x in command], 'exit': result.returncode,
                     'expected_success': good, 'log_SHA256': trial.sha(log.read_bytes())}
    trial.write_json(out / 'run_status.json', records)
    print(name, result.returncode, body[-2000:], flush=True)
    assert (result.returncode == 0) == good, name
    assert marker is None or marker in body, name


run('pll_compile', compiler + ['-s', 'tb_pll40', '-o', out / 'pll.vvp', pll, vendor, HERE / 'tb_pll40.sv'], timeout=60)
run('pll', [CAD / 'bin/vvp.exe', out / 'pll.vvp'], marker='PASS vendor PLL model')
# A real wrong divider must fail a measured period check, not a compile error.
bad_pll = out / 'wrong_core_divider.v'
body = pll.read_text(encoding='utf-8')
assert body.count('ODIV2_SEL = 25;') == 1
bad_pll.write_text(body.replace('ODIV2_SEL = 25;', 'ODIV2_SEL = 20;', 1), encoding='utf-8')
run('wrong_divider_compile', compiler + ['-s', 'tb_pll40', '-o', out / 'bad_pll.vvp', bad_pll, vendor, HERE / 'tb_pll40.sv'], timeout=60)
run('wrong_divider', [CAD / 'bin/vvp.exe', out / 'bad_pll.vvp'], good=False, marker='core clock period mismatch')
entries = ET.parse(OUT / (trial.STEM + '.gprj')).getroot().findall('./FileList/File')
sources = [Path(r.attrib['path']) for r in entries if r.attrib['type'] == 'file.verilog']
assert len(sources) == 45
simulation_sources = []
adaptations = []
(out / 'sim_sources').mkdir()
for path in sources:
    body = path.read_text(encoding='utf-8')
    updated = body
    if final_attempt or mode in [['--include-adapter'], ['--DVI-boundary-stub'], ['--icarus-syntax-adapter']]:
        for match in re.finditer(r'`include\s+"([^"]+)"', body):
            actual = Path(match[1])
            assert actual.is_file() and actual.parent == OUT / 'include'
            updated = updated.replace(match[0], '`include "' + actual.name + '"')
            adaptations.append({'file': path.name, 'original_include': match[0], 'simulation_include': actual.name})
    if path.name == 'voice_allocator_4.sv' and (final_attempt or mode == ['--icarus-syntax-adapter']):
        # Icarus asserts on variable-index unpacked packed-struct fields.
        # Mechanical field splitting only; exact original NBA order retained.
        fields = {'note_active': 1, 'in_release': 1, 'source': 4, 'channel': 4, 'note': 8, 'age': 2}
        declaration = '    voice_slot_t slots [0:3];'
        assert updated.count(declaration) == 1
        declarations = '\n'.join('    logic ' + (f'[{width-1}:0] ' if width > 1 else '') +
                                 f'sim_slot_{name} [0:3];' for name, width in fields.items())
        updated = updated.replace(declaration, declarations)
        reset = "                slots[i] <= '0;"
        assert updated.count(reset) == 1
        updated = updated.replace(reset, '\n'.join(f"                sim_slot_{name}[i] <= '0;" for name in fields))
        substitutions = []
        for field in fields:
            pattern = r'slots\[([^\]]+)\]\.' + field + r'\b'
            updated, count = re.subn(pattern, r'sim_slot_' + field + r'[\1]', updated)
            substitutions.append({'field': field, 'width': fields[field], 'references': count})
        assert not re.search(r'\bslots\b', updated)
        adaptations.append({'file': path.name, 'simulation_only_field_split': substitutions,
                            'NBA_order_and_field_widths_retained': True})
    if path.name == 'DVI_TX_Top.v' and (final_attempt or mode in [['--DVI-boundary-stub'], ['--icarus-syntax-adapter']]):
        simulation_sources.append(HERE / 'dvi_sim_stub.v')
        adaptations.append({'file': path.name, 'simulation_only': 'DVI opaque boundary stub; NOT TMDS verification'})
    elif updated != body:
        target = out / 'sim_sources' / path.name
        target.write_text(updated, encoding='utf-8')
        simulation_sources.append(target)
    else:
        simulation_sources.append(path)
trial.write_json(out / 'simulation_include_adaptations.json', adaptations)
args = compiler + ['-s', 'tb_clock40_top', '-I', OUT / 'include', '-o', out / 'top.vvp']
run('top_compile', args + simulation_sources + [vendor, HERE / 'tb_clock40_top.sv'], timeout=90)
run('top', [CAD / 'bin/vvp.exe', out / 'top.vvp'], marker='PASS full clock40 integration')
bad_top = out / 'old_bclk_step.sv'
top = OUT / 'sources/audio_visual_coexistence_top.sv'
body = top.read_text(encoding='utf-8')
assert body.count('.BCLK_PHASE_STEP  (CORE_BCLK_PHASE_STEP)') == 1
bad_top.write_text(body.replace('.BCLK_PHASE_STEP  (CORE_BCLK_PHASE_STEP)',
                                '.BCLK_PHASE_STEP  (I2S_BCLK_PHASE_STEP)', 1), encoding='utf-8')
mutated_sources = [bad_top if p == top else p for p in simulation_sources]
args = compiler + ['-s', 'tb_clock40_top', '-I', OUT / 'include', '-o', out / 'bad_top.vvp']
run('old_step_compile', args + mutated_sources + [vendor, HERE / 'tb_clock40_top.sv'], timeout=90)
run('old_step', [CAD / 'bin/vvp.exe', out / 'bad_top.vvp'], good=False, marker='BCLK3.072MHz average')
review = {'passed': True, 'runs': records,
                 'vendor_primitive_SHA256': trial.sha(vendor.read_bytes()),
                 'testbench_SHA256': {p.name: trial.sha(p.read_bytes()) for p in [HERE / 'tb_pll40.sv', HERE / 'tb_clock40_top.sv']},
                 'RTL_SHA256': {p.name: trial.sha(p.read_bytes()) for p in sources},
                 'uses_real_vendor_PLL_simulation_model': True,
                 'real_clock_periods_measured_ns': {'core': 25, 'pixel': 40, 'serial': 8},
                 'LOCK_loss_injected_test_not_hardware_measurement': True,
                 'audio_MIDI_CDC_and_clock_parameter_checks': True,
                 'compiled_wrong_divider_and_old_BCLK_step_rejected': True,
                 'formal_repo_written': False, 'programmed': False,
                 'actual_evidence_directory': str(out),
                 'simulation_only_include_adaptations': adaptations,
                 'DVI_is_boundary_stub_in_whole_top_simulation': final_attempt or mode in [['--DVI-boundary-stub'], ['--icarus-syntax-adapter']],
                 'encrypted_DVI_IP_not_simulated_or_board_verified': True}
trial.write_json(out / 'functional_review.json', review)
if out.name != 'functional':
    assert not (OUT / 'functional/functional_review.json').exists()
    trial.write_json(OUT / 'functional/functional_review.json', review)
trial.protect()
