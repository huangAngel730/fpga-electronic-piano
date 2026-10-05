"""Collect original and local complete-design evidence separately; do not mask failures."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
assert HERE == ROOT / 'reproduction_20261005'
from full_report_checks import check, pins, expected_138k_electrical_pins

original = ROOT / 'M2_DVI_V0171_originals_20261005/originals/V0171'
stem = 'audio_visual_coexistence_top'
original_pnr = original / 'impl/pnr'
expected_pins = pins((original_pnr / (stem + '.pin.html')).read_text(encoding='utf-8'))
assert expected_pins
original_sdc = (original / 'constraints/audio_visual_hold055.sdc').read_bytes()
results = []
cases = [('M2_original_V0171', original, 'GW5AT-LV60PG484AC1/I0', 'B')]
for label, version in [('60K_control', 'B'), ('138K_B_frozen_constraints', 'B'),
                       ('138K_C_frozen_constraints', 'C'), ('138K_B_pll_migration', 'B'),
                       ('138K_C_pll_migration', 'C'), ('138K_B_electrical_migration', 'B'),
                       ('138K_C_electrical_migration', 'C')]:
    folder = HERE / label
    if (folder / 'build_receipt.json').is_file():
        cases.append((label, folder, 'GW5AT-LV60PG484AC1/I0' if label == '60K_control'
                      else 'GW5AST-LV138PG484AC1/I0', version))
for label, folder, pn, version in cases:
    pnr = folder / 'impl/pnr'
    paths = [pnr / (stem + '_tr_content.html'), pnr / (stem + '.rpt.txt'),
             pnr / (stem + '.pin.html'), pnr / 'cmd.do', pnr / 'device.cfg', folder / 'build.log']
    local = label != 'M2_original_V0171'
    receipt = json.loads((folder / 'build_receipt.json').read_text(encoding='utf-8')) if local else {
        'state': 'historical', 'exit_code': int((folder / 'build_exit.txt').read_text(encoding='utf-8'))}
    if local and receipt['state'] != 'finished':
        results.append({'label': label, 'state': 'running', 'build_receipt': receipt})
        print('RUNNING', label)
        continue
    missing = [str(p.relative_to(folder)) for p in paths if not p.is_file()]
    if missing:
        log_path = folder / 'build.log'
        log_text = log_path.read_text(encoding='utf-8') if log_path.exists() else ''
        results.append({'label': label, 'state': 'build_failed_or_incomplete', 'build_receipt': receipt,
                        'missing_reports': missing, 'offline_report_gate_passed': False,
                        'actual_error_lines': [line for line in log_text.splitlines()
                                               if re.search(r'ERROR\s*\(', line)],
                        'build_log_SHA256': hashlib.sha256(log_path.read_bytes()).hexdigest()
                        if log_path.exists() else None,
                        'PnR_completion_observed': 'Placement and routing completed' in log_text,
                        'STA_completion_observed': 'Timing analysis completed' in log_text,
                        'programmed': False})
        print('INCOMPLETE', label, 'exit=', receipt.get('exit_code'), 'missing=', missing)
        continue
    text = lambda path: path.read_text(encoding='utf-8')
    sdc = folder / 'constraints/audio_visual_hold055.sdc'
    assert sdc.read_bytes() == original_sdc
    expected = {port: dict(row) for port, row in expected_pins.items()}
    if label.endswith('_electrical_migration'):
        # Bank mappings from the already reviewed 138K core schematic, not
        # inferred from the result being checked. No ball or pull/drive change.
        expected = expected_138k_electrical_pins(expected_pins)
    result = check(text(paths[0]), text(paths[1]), text(sdc), text(paths[2]), expected, pn, version,
                   text(paths[3]), text(original_pnr / 'cmd.do'),
                   paths[4].read_bytes(), (original_pnr / 'device.cfg').read_bytes(),
                   allowed_extra_options=('-enable_dsrm 0',) if label.endswith('_electrical_migration') else (),
                   allowed_device_cfg_changes=((b'set vccx = 3.3', b'set vccx = 1.8'),)
                   if label.endswith('_electrical_migration') else ())
    log = text(folder / 'build.log')
    if receipt.get('exit_code') != 0:
        result['errors'].append('build CLI exit is not zero')
    for marker in ['GowinSynthesis finish', 'Placement and routing completed',
                   'Timing analysis completed', 'Bitstream generation completed']:
        if marker not in log:
            result['errors'].append('missing build completion marker: ' + marker)
    result['offline_report_gate_passed'] = not result['errors']
    result['engineering_margin_0p5ns_passed'] = (
        result['offline_report_gate_passed']
        and min(p['slack_ns'] for p in result['global_worst_paths'].values()) >= 0.5)
    result.update({'label': label, 'state': 'finished', 'build_receipt': receipt,
                   'origin': 'local actual run' if local else 'M2 historical run; not local execution',
                   'CST_SDC_unchanged': (folder / 'constraints/audio_visual.cst').read_bytes()
                   == (original / 'constraints/audio_visual.cst').read_bytes(),
                   'artifact_SHA256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                   'programmed': False})
    if label.startswith('138K_'):
        result['not_board_usable_frozen_electrical_constraints'] = not label.endswith('_electrical_migration')
        result['target_bottom_board_and_real_PLL_startup_unverified'] = True
        result['hardware_acceptance'] = False
    results.append(result)
    print('PASS' if result['offline_report_gate_passed'] else 'FAIL', label,
          {**result['global_worst_paths'], **result['recovery_removal_worst_paths']},
          'min_pulse=', result['min_pulse_width_slack_ns'], 'errors=', result['errors'])
report = {'time': datetime.now().astimezone().isoformat(),
          'scope': 'Complete frozen design offline comparison; not hardware or production acceptance',
          'results': results, 'original_repo_written': False, 'programmed': False}
(HERE / 'full_run_results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
