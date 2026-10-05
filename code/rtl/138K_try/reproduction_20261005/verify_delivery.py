"""Verify final evidence including expected real STA failures; never promotes a failed run."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
assert HERE == ROOT / 'reproduction_20261005'
PACKAGE = ROOT / 'M2_DVI_V0171_originals_20261005'


def safe(path):
    result = Path(path).resolve()
    if not result.is_relative_to(ROOT):
        raise ValueError('Evidence path outside isolated root')
    return result


def sha(path):
    return hashlib.sha256(safe(path).read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


audit = load('input_audit.json')
assert audit['package_original_files_verified'] == 31
assert audit['frozen_project_entries_verified'] == 47
assert len(audit['source_copies']) == 56
for record in audit['package_audit']:
    path = PACKAGE / record['path']
    assert sha(path) == record['sha256'] and path.stat().st_size == record['bytes']
for record in audit['source_copies']:
    assert sha(record['original']) == record['original_SHA256']
    assert sha(record['target']) == record['target_SHA256']
assert sum(len(r['path_replacements']) for r in audit['source_copies']) == 20
for candidate in load('138k_diagnostic_manifest.json'):
    for record in candidate['files']:
        assert sha(record['target']) == record['target_SHA256']
for manifest_name in ['pll_migration_manifest.json', 'electrical_migration_manifest.json']:
    for candidate in load(manifest_name)['candidates']:
        for relative, digest in candidate['file_SHA256'].items():
            assert sha(HERE / candidate['label'] / relative) == digest

model = load('pll_model_test/result.json')
assert model['passed'] and model['compile_exit'] == model['run_exit'] == 0
for path, digest in model['source_SHA256'].items():
    assert sha(path) == digest
assert 'PASS PLL migration vendor model:' in (HERE / 'pll_model_test/run.log').read_text(encoding='utf-8')
selftest = (HERE / 'full_report_selftest_delivery.log').read_text(encoding='utf-8')
assert 'Ran 21 tests' in selftest and selftest.rstrip().endswith('OK')

results = load('full_run_results.json')
assert len(results['results']) == 7
by_label = {r['label']: r for r in results['results']}
assert not any(r['state'] == 'running' for r in by_label.values())
original = by_label['M2_original_V0171']
control = by_label['60K_control']
assert original['offline_report_gate_passed'] and control['offline_report_gate_passed']
for field in ['resources', 'fmax_mhz', 'summary', 'clocks', 'per_clock_TNS',
              'global_worst_paths', 'recovery_removal_worst_paths', 'CDC_second_stage_slacks',
              'CDC_surviving_payload_path_counts', 'min_pulse_width_slack_ns', 'pins']:
    assert control[field] == original[field], field
assert not control['engineering_margin_0p5ns_passed']
expected = {
    '60K_control': [0.017, 0.0, 1.113, 0.869],
    '138K_B_electrical_migration': [-1.412, -0.342, -1.421, -0.158],
    '138K_C_electrical_migration': [-1.356, -0.348, -1.411, -0.152],
}
artifacts = {}
builds = []
original_cst = (PACKAGE / 'originals/V0171/constraints/audio_visual.cst').read_bytes()
original_sdc = (PACKAGE / 'originals/V0171/constraints/audio_visual_hold055.sdc').read_bytes()
for label, slacks in expected.items():
    report = by_label[label]
    actual = [report['global_worst_paths'][kind]['slack_ns'] for kind in ['Setup', 'Hold']]
    actual += [report['recovery_removal_worst_paths'][kind]['slack_ns'] for kind in ['Recovery', 'Removal']]
    assert actual == slacks
    assert report['build_receipt']['state'] == 'finished' and report['build_receipt']['exit_code'] == 0
    if label != '60K_control':
        assert not report['offline_report_gate_passed'] and not report['engineering_margin_0p5ns_passed']
        assert all(v < 0 for v in actual)
        assert len(report['CDC_second_stage_slacks']) == 14
        assert not any('pin electrical/location mismatch' in error or 'configuration changed' in error
                       or 'non-path PnR options changed' in error for error in report['errors'])
        assert report['device_cfg_matches_allowed_profile']
    for path, digest in report['artifact_SHA256'].items():
        assert sha(path) == digest
        artifacts[path] = digest
    folder = HERE / label
    assert (folder / 'constraints/audio_visual_hold055.sdc').read_bytes() == original_sdc
    cst = (folder / 'constraints/audio_visual.cst').read_bytes()
    for directive in [b'IO_LOC', b'INS_LOC']:
        pattern = rb'^' + directive + rb'.*$'
        assert re.findall(pattern, cst, re.M) == re.findall(pattern, original_cst, re.M)
    cst_text = original_cst.decode('utf-8')
    if label != '60K_control':
        lines = cst_text.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if re.match(r'IO_PORT\s+"(?:sys_rst_n|key_n\[0\]|key_n\[1\])"', line):
                lines[index] = line.replace('IO_TYPE=LVCMOS15', 'IO_TYPE=LVCMOS33').replace('BANK_VCCIO=1.5', 'BANK_VCCIO=3.3')
        cst_text = ''.join(lines)
    assert cst == cst_text.encode('utf-8')
    project = ET.fromstring((folder / 'audio_visual_coexistence_top.gprj').read_bytes())
    assert len(project.findall('./FileList/File')) == 47
    for node in project.findall('./FileList/File'):
        assert safe(node.attrib['path']).is_relative_to(folder)
        assert Path(node.attrib['path']).is_file()
    extra = [folder / 'impl/pnr/audio_visual_coexistence_top.fs', folder / 'build_receipt.json',
             folder / 'run.tcl', folder / 'audio_visual_coexistence_top.gprj',
             folder / 'impl/gwsynthesis/audio_visual_coexistence_top.vg', folder / 'DO_NOT_PROGRAM.md']
    for path in extra:
        artifacts[str(path)] = sha(path)
    receipt = json.loads((folder / 'build_receipt.json').read_text(encoding='utf-8'))
    assert receipt['build_log_SHA256'] == sha(folder / 'build.log')
    builds.append({'label': label, 'started': receipt['started'], 'finished': receipt['finished'],
                   'CLI_exit': receipt['exit_code'], 'STA_passed': report['offline_report_gate_passed'],
                   'hardware_acceptance': False})
for label, error_code in [('138K_B_frozen_constraints', 'RP0008'),
                           ('138K_C_frozen_constraints', 'RP0008'), ('138K_B_pll_migration', 'CT1136')]:
    report = by_label[label]
    assert report['state'] == 'build_failed_or_incomplete'
    assert report['build_receipt']['exit_code'] == 1
    assert any(error_code in line for line in report['actual_error_lines'])
    assert sha(HERE / label / 'build.log') == report['build_log_SHA256']
    assert not report['PnR_completion_observed'] and not report['STA_completion_observed']
    artifacts[str(HERE / label / 'build.log')] = report['build_log_SHA256']
    artifacts[str(HERE / label / 'build_receipt.json')] = sha(HERE / label / 'build_receipt.json')
assert not (HERE / '138K_C_pll_migration/build_receipt.json').exists()
for path in HERE.glob('*.py'):
    artifacts[str(path)] = sha(path)
for name in ['README.md', 'M2_完整对比交接.md', 'input_audit.json', '138k_diagnostic_manifest.json',
             'pll_migration_manifest.json', 'electrical_migration_manifest.json', 'full_run_results.json',
             'full_report_selftest_delivery.log', 'collect_full_runs_final.log', 'pll_model_test/result.json']:
    artifacts[str(HERE / name)] = sha(HERE / name)
receipt = {'time': datetime.now().astimezone().isoformat(), 'evidence_integrity_passed': True,
           'scope': 'Delivery integrity and truthful pass/fail states, NOT promotion of failed designs',
           'M2_original_files_reverified': 31, 'project_entries': 47,
           'ROMs': 7, 'headers': 2, 'path_replacements': 20,
           'full_report_checker_tests_passed': 21, 'PLL_vendor_model_passed': True,
           'complete_local_PnR_runs': builds, 'STA_passed_labels': ['60K_control'],
           'STA_failed_labels': ['138K_B_electrical_migration', '138K_C_electrical_migration'],
           'source_and_report_SHA256': artifacts, 'programmed': False,
           'original_repo_written': False, 'M2_originals_modified': False,
           'handoff_state': '待用户转发，尚未送达'}
(HERE / 'delivery_receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('PASS delivery integrity: 31 M2 originals; 47/47 entries + 7 ROMs + 2 headers; source manifests rehashed')
print('PASS control reproduction: original report metrics/pins/CDC match; CLI0; margin0.5ns NOT met')
print('Verified real FAIL: 138K B/C STA negative in all four categories; CLI0/PnR completion is not timing PASS')
print('PASS checker selftests=21; PLL vendor model PASS; no source SDC or fixed-location relaxation')
print('NO PROGRAMMING / NO ORIGINAL-REPO WRITES / HANDOFF NOT SENT')
