"""Recheck hashes, reject false adoption, and package only non-programmable evidence."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
import experiment
from assess import evaluate, report, BASE


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    experiment.preserve_check()
    baseline = report(BASE)
    assert baseline['offline_report_gate_passed']
    assert baseline['global_worst_paths']['Setup']['slack_ns'] == 0.025
    labels = ['A_prepared_selector', 'B_parallel_pending_mask']
    existing = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
    assert len(existing['results']) == len(labels)
    for label in labels:
        fresh = evaluate(label)
        saved = next(r for r in existing['results'] if r['label'] == label)
        assert fresh == saved, label + ': evidence changed after assessment'
        functional = HERE / label / 'functional'
        record = json.loads((functional / 'functional_review.json').read_text(encoding='utf-8'))
        for name, run in record['runs'].items():
            log = functional / (name + '.log')
            assert sha(log.read_bytes()) == run.get('log_SHA256', run.get('log_SHA')), name
            assert (run['exit'] == 0) == run['expected_success'], name
        assert saved['receipt']['state'] == 'finished' and saved['receipt']['exit_code'] == 0
        assert len(saved['CDC_second_stage_slacks']) == 14
        assert list(saved['CDC_surviving_payload_path_counts'].values()) == [23, 50]
        assert saved['device_cfg_matches_allowed_profile']
        assert saved['normalized_PnR_options'] == baseline['normalized_PnR_options']
    receipt = {'time': datetime.now().astimezone().isoformat(), 'passed': True,
               'trials': labels, 'baseline_preserved': True, 'repository_written': False,
               'new_results_are_not_hardware_acceptance': True,
               'checker_selftest_SHA256': sha((HERE / 'report_selftest.log').read_bytes())}
    (HERE / 'verification_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    archive = HERE / 'M3_138K_followup_evidence_20261005.zip'
    assert not archive.exists(), 'Do not replace an existing delivery'
    paths = []
    for path in HERE.rglob('*'):
        if not path.is_file() or path == archive:
            continue
        parts = path.relative_to(HERE).parts
        if any(part in ['tmp', 'functional_tmp', '__pycache__', 'gwsynthesis'] for part in parts):
            continue
        if path.suffix.lower() in ['.fs', '.bin', '.vvp', '.bak', '.zip']:
            continue
        if 'impl' in parts and path.suffix.lower() not in ['.html', '.txt', '.do', '.cfg']:
            continue
        paths.append(path)
    hashes = {p.relative_to(HERE).as_posix(): sha(p.read_bytes()) for p in paths}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for path in paths:
            output.write(path, path.relative_to(HERE).as_posix())
        output.writestr('ARCHIVE_SHA256.json', json.dumps(hashes, indent=2) + '\n')
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == set(hashes) | {'ARCHIVE_SHA256.json'}
        assert all(sha(package.read(name)) == digest for name, digest in hashes.items())
    (HERE / 'archive_receipt.json').write_text(json.dumps({
        'path': str(archive), 'size': archive.stat().st_size, 'SHA256': sha(archive.read_bytes()),
        'members': len(hashes) + 1, 'CRC_and_member_hashes_passed': True,
        'bitstreams_tools_excluded': True}, indent=2) + '\n', encoding='utf-8')
    print('Verified preserved success, current input/report/test evidence, and ZIP CRC/member SHA PASS', flush=True)


if __name__ == '__main__':
    main()
