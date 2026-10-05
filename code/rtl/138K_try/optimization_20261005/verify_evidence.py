"""Verify evidence integrity separately from the explicitly failed design timing gate."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from experiment import BASE, PROFILES, expected_cst


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    result = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
    assert len(result['results']) == len(PROFILES) == 4
    old = json.loads((ROOT / 'reproduction_20261005/full_run_results.json').read_text(encoding='utf-8'))
    prior_count = 0
    for case in old['results']:
        for name, expected in case.get('artifact_SHA256', {}).items():
            assert digest(Path(name)) == expected, name
            prior_count += 1
    counts = {}
    for case in result['results']:
        label = case['label']
        out = HERE / label
        assert case['state'] == 'finished' and case['receipt']['exit_code'] == 0
        assert case['resources']['DSP']['used'] == 46 and case['resources']['BSRAM']['used'] == 20
        assert not case['hardware_acceptance'] and not case['programmed']
        expected_pass = label == 'C_reset_route1'
        assert case['offline_report_gate_passed'] == expected_pass
        if expected_pass:
            assert case['errors'] == []
            assert case['summary']['Numbers of Setup Violated Endpoints'] == '0'
            assert case['summary']['Numbers of Hold Violated Endpoints'] == '0'
            assert case['global_worst_paths']['Setup']['slack_ns'] == 0.025
            assert case['global_worst_paths']['Hold']['slack_ns'] == 0.0
            assert case['recovery_removal_worst_paths']['Recovery']['slack_ns'] == 0.873
            assert case['recovery_removal_worst_paths']['Removal']['slack_ns'] == 0.008
            assert not case['engineering_margin_0p5ns_passed']
        assert case['PnR_option_differences']['added'] == case['PnR_option_differences']['removed'] == []
        assert case['device_cfg_matches_allowed_profile']
        for name, expected in case['artifact_SHA256'].items():
            assert digest(out / name) == expected
        manifest = json.loads((out / 'input_manifest.json').read_text(encoding='utf-8'))
        assert len(manifest['inputs']) == 56
        for item in manifest['inputs']:
            path = item['path']
            assert digest(out / path) == item['candidate_SHA256']
            baseline = (BASE / path).read_bytes()
            assert hashlib.sha256(baseline).hexdigest() == item['baseline_SHA256']
            if Path(path).name == 'audio_visual.cst':
                baseline = expected_cst(label, baseline)
            assert (out / path).read_bytes().replace(out.as_posix().encode(), BASE.as_posix().encode()) == baseline
        assert all(r['observed'] == [r['expected']] for r in case['serial_reset_fixed_location_readback'].values())
        counts[label] = {'inputs_verified': 56, 'artifacts_verified': len(case['artifact_SHA256']),
                         'design_timing_passed': expected_pass}
    regression = json.loads((HERE / 'frozen_regression_results.json').read_text(encoding='utf-8'))
    assert regression['passed'] and len(regression['results']) == 7
    assert all(r['passed'] and r['compile_exit'] == r['run_exit'] == 0 for r in regression['results'])
    for case in regression['results']:
        for name, expected in case['DUT_SHA256'].items():
            assert digest(HERE / 'C_reset_route1/sources' / name) == expected
        for name, expected in case['log_SHA256'].items():
            assert digest(HERE / 'regression' / case['case'] / name) == expected
    selftest = (HERE / 'report_selftest.log').read_text(encoding='utf-8')
    assert 'Ran 25 tests' in selftest and selftest.rstrip().endswith('OK')
    receipt = {'time': datetime.now().astimezone().isoformat(), 'evidence_verification_passed': True,
               'design_timing_passed': True, 'accepted_offline_profile': 'C_reset_route1',
               'engineering_margin_0p5ns_passed': False,
               'cases': counts, 'prior_raw_artifacts_still_matching': prior_count,
               'functional_regression_groups': 7, 'report_selftests': 25,
               'original_repo_written': False, 'programmed': False}
    (HERE / 'verification_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    verify()
