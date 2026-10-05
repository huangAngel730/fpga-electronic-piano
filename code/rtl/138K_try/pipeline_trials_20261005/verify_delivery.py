"""Evidence integrity is separate from a candidate's physical timing pass."""
from datetime import datetime
import json
from pathlib import Path
import sys
import zipfile

sys.dont_write_bytecode = True
import pipeline_trials as task
import recover_rotation as rotation

HERE = Path(__file__).resolve().parent


def main():
    task.protect(check=True)
    rotation.verify_original()
    labels = ['C_payload_buffer', 'D_rotation_pipeline_recovery1']
    data = json.loads((HERE / 'final_results.json').read_text(encoding='utf-8'))
    assert data['baseline']['offline_report_gate_passed']
    assert data['baseline']['global_worst_paths']['Setup']['slack_ns'] == 0.025
    assert len(data['results']) == len(labels)
    original = (task.shared.BASE / 'sources/midi_event_parser.sv').read_text(encoding='utf-8')
    for label in labels:
        project = HERE / label
        actual = task.assessor.evaluate(label)
        saved = next(r for r in data['results'] if r['label'] == label)
        assert saved == actual, 'Reports/input/evidence changed after collection: ' + label
        source = (project / 'sources/midi_event_parser.sv').read_text(encoding='utf-8')
        # Public ports/parameters, byte parser, event output, FIFO bypass and
        # counters, and all original scheduler-state updates remain literal.
        assert source[source.index('module midi_event_parser'):source.index('    import audio_defs_pkg::*;')] == original[original.index('module midi_event_parser'):original.index('    import audio_defs_pkg::*;')]
        start = '    integer comb_fifo_index;'
        end = '    // Apply the current byte before arbitration.'
        assert source[source.index(start):source.index(end)] == original[original.index(start):original.index(end)]
        end = '    // At most one locked control event;'
        assert source[source.index(end):] == original[original.index(end):]
        functional = project / 'functional'
        evidence = json.loads((functional / 'functional_review.json').read_text(encoding='utf-8'))
        assert evidence['passed']
        for name, run in evidence['runs'].items():
            assert task.shared.sha((functional / (name + '.log')).read_bytes()) == run['log_SHA256']
            assert (run['exit'] == 0) == run['expected_success']
        positive = (functional / 'positive.log').read_text(encoding='utf-8')
        for lane in range(4):
            assert f'PASS M2 full original parser miter lane={lane} cycles=256193' in positive
        assert 'PASS prepared corner checks=33' in (functional / 'directed/positive.log').read_text(encoding='utf-8')
        assert 'two consecutive cancellations mismatch' in (functional / 'directed/third_fallback_wrong.log').read_text(encoding='utf-8')
        assert evidence['runs']['stale_payload']['exit'] != 0
        if label.startswith('D_'):
            assert evidence['runs']['wrong_next_rr']['exit'] != 0
            assert '`define CHECK_LOOKAHEAD' in (functional / 'tb.sv').read_text(encoding='utf-8')
            prefix = json.loads((project / 'functional_prefix_reuse.json').read_text(encoding='utf-8'))
            assert prefix['not_a_new_functional_run']
            for path, expected in prefix['copied_SHA256'].items():
                assert task.shared.sha((functional / path).read_bytes()) == expected
        assert len(actual['CDC_second_stage_slacks']) == 14
        assert list(actual['CDC_surviving_payload_path_counts'].values()) == [23, 50]
        assert actual['normalized_PnR_options'] == data['baseline']['normalized_PnR_options']
        assert actual['device_cfg_matches_allowed_profile']
    tests = (HERE / 'report_selftest.log').read_text(encoding='utf-8')
    assert 'Ran 23 tests' in tests and tests.rstrip().endswith('OK')
    receipt = {'time': datetime.now().astimezone().isoformat(), 'evidence_integrity_passed': True,
               'baseline_and_prior_documents_preserved': True, 'original_repo_written': False,
               'labels': labels, 'hardware_acceptance': False,
               'interrupted_original_preserved': True, 'physical_invocations': 3,
               'new_functional_runs': 2, 'recovery_reuses_measured_identical_source_functional_prefix': True,
               'physical_results': {r['label']: r['offline_report_gate_passed'] for r in data['results']}}
    task.shared.write_json(HERE / 'verification_receipt.json', receipt)
    archive = HERE / 'M3_138K_pipeline_trials_evidence_20261005.zip'
    assert not archive.exists(), 'Never overwrite a delivery'
    paths = []
    for path in HERE.rglob('*'):
        if not path.is_file() or path == archive:
            continue
        parts = path.relative_to(HERE).parts
        if any(p in ['tmp', '__pycache__', 'gwsynthesis'] for p in parts):
            continue
        if path.suffix.lower() in ['.fs', '.bin', '.vvp', '.bak', '.zip']:
            continue
        if 'impl' in parts and path.suffix.lower() not in ['.html', '.txt', '.do', '.cfg']:
            continue
        paths.append(path)
    hashes = {p.relative_to(HERE).as_posix(): task.shared.sha(p.read_bytes()) for p in paths}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for path in paths:
            output.write(path, path.relative_to(HERE).as_posix())
        output.writestr('ARCHIVE_SHA256.json', json.dumps(hashes, indent=2) + '\n')
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == set(hashes) | {'ARCHIVE_SHA256.json'}
        assert all(task.shared.sha(package.read(n)) == digest for n, digest in hashes.items())
    task.shared.write_json(HERE / 'archive_receipt.json', {
        'path': str(archive), 'size': archive.stat().st_size, 'SHA256': task.shared.sha(archive.read_bytes()),
        'members': len(hashes) + 1, 'CRC_member_SHA_passed': True, 'bitstreams_tools_excluded': True})
    print('Protected older files; literal public/FIFO/counter/state blocks; tests/reports/input hashes; ZIP CRC/SHA PASS', flush=True)


if __name__ == '__main__':
    main()
