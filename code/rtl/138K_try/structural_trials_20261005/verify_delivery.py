"""Audit actual evidence, then package it. A passed audit is NOT a STA PASS."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('structural_driver_audit', HERE / 'structural_trials.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
sha = driver.shared.sha
write_json = driver.shared.write_json


def audit():
    data = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
    assert data['pending'] == [], 'Do not package unfinished tests as completed'
    assert len(data['results']) == 2
    tests = (HERE / 'report_selftest.log').read_text(encoding='utf-8')
    assert 'Ran 23 tests' in tests and '\nOK\n' in tests
    verified = []
    for result in data['results']:
        label = result['label']
        folder = HERE / label
        review = json.loads((folder / 'functional/functional_review.json').read_text(encoding='utf-8'))
        evidence = Path(review['actual_evidence_directory'])
        evidence.relative_to(folder)
        assert review['passed']
        assert review['candidate_SHA256'] == sha((folder / 'sources/midi_event_parser.sv').read_bytes())
        driver.identity((folder / 'sources/midi_event_parser.sv').read_text(encoding='utf-8'))
        assert driver.assessor.inputs(folder) == []
        assert review == json.loads((evidence / 'functional_review.json').read_text(encoding='utf-8'))
        for name, run in review['runs'].items():
            log = evidence / (name + '.log')
            assert run['log_SHA256'] == sha(log.read_bytes()), name
            assert (run['exit'] == 0) == run['expected_success'], name
            if not run['expected_success']:
                assert 'FATAL:' in log.read_text(encoding='utf-8'), name
        positive = (evidence / 'positive.log').read_text(encoding='utf-8')
        lanes = re.findall(r'PASS M2 full original parser miter lane=(\d) cycles=(\d+)', positive)
        assert lanes == [(str(i), '256205') for i in range(4)]
        assert re.findall(r'PASS directed locked cancellation lane=(\d) cases=(\d+)', positive) == [(str(i), '1') for i in range(4)]
        assert f'oracle cases={review["oracle_cases"]}' in (evidence / 'oracle.log').read_text(encoding='utf-8')
        vector = evidence / ('transition_vectors.txt' if label.startswith('E_') else 'selector_vectors.txt')
        assert review['oracle_vectors_SHA256'] == sha(vector.read_bytes())
        tb = (evidence / 'tb.sv').read_text(encoding='utf-8')
        for marker in ['dut.pending_value[k]!==ref_dut.pending_value[k]',
                       'dut.mod_sent_value[k]!==ref_dut.mod_sent_value[k]',
                       'dut.fifo_mem[k]!==ref_dut.fifo_mem[k]',
                       'dut.running_status,dut.first_data_byte',
                       'dut.selected_valid,dut.grant_control']:
            assert marker in tb, marker
        freshly_checked = driver.assessor.evaluate(label)
        for key in ['errors', 'global_worst_paths', 'recovery_removal_worst_paths', 'resources', 'artifact_SHA256']:
            assert result[key] == freshly_checked[key], key
        verified.append({'label': label, 'functional_passed': True,
                         'STA_gate_passed': result['offline_report_gate_passed'],
                         'new_registers': 0, 'public_latency_cycles_added': 0,
                         'oracle_cases': review['oracle_cases'], 'completed_build_receipt': result['receipt']})
    driver.protect(check=True)
    write_json(HERE / 'verification_receipt.json', {
        'evidence_audit_passed': True, 'all_physical_trials_completed': True,
        'audit_does_not_override_STA_failures': True, 'trials': verified,
        'formal_repo_written': False, 'programmed': False,
        'previous_artifact_hashes_checked': 992,
        'first_two_E_functional_runs_failed_coverage_gate_preserved': True})
    print('EVIDENCE AUDIT PASS; physical pass/fail remains separately recorded', flush=True)


def package():
    audit()
    target = HERE / 'M3_138K_structural_trials_evidence_20261005.zip'
    assert not target.exists(), 'Never replace a delivered archive'
    files = []
    for path in HERE.rglob('*'):
        if not path.is_file() or path == target:
            continue
        relative = path.relative_to(HERE)
        if any(part in ['tmp', 'gwsynthesis'] for part in relative.parts):
            continue
        if path.suffix.lower() in ['.vvp', '.bin', '.binx', '.fs', '.pr', '.p', '.db']:
            continue
        if path.name == 'archive_receipt.json':
            continue
        files.append(path)
    members = {p.relative_to(HERE).as_posix(): sha(p.read_bytes()) for p in files}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for p in sorted(files):
            archive.write(p, p.relative_to(HERE).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(members)
        assert all(sha(archive.read(name)) == digest for name, digest in members.items())
    write_json(HERE / 'archive_receipt.json', {'path': str(target), 'bytes': target.stat().st_size,
                                              'SHA256': sha(target.read_bytes()), 'members': members,
                                              'CRC_and_member_SHA_passed': True,
                                              'contains_bitstream_or_executable': False})
    print('ZIP CRC/member SHA PASS', target.stat().st_size, 'bytes', flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['audit']:
        audit()
    elif sys.argv[1:] == ['package']:
        package()
    else:
        raise ValueError('Choose audit or package')
