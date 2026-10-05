"""Evidence integrity audit; a passed audit does NOT override a STA failure."""
import ast
import json
from pathlib import Path
import sys
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assess_clock40 as assess
import clock_trial as trial
import route_trial as route

HERE = trial.HERE


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit():
    tests = (HERE / 'report_selftest.log').read_text(encoding='utf-8')
    assert 'Ran 23 tests' in tests and '\nOK\n' in tests
    for script in HERE.glob('*.py'):
        ast.parse(script.read_text(encoding='utf-8'), filename=str(script))
    verified = []
    for label, filename, route_option in [('G_pll_core40', 'results.json', 1),
                                          ('H_pll_core40_route2', 'H_results.json', 2)]:
        folder = HERE / label
        data = load(HERE / filename)
        result = data['candidate']
        assert all(data['clock_profile_guard_negative_tests'].values())
        pnr = folder / 'impl/pnr'
        assess.EXPECTED_ROUTE = route_option
        actual = assess.profile((pnr / (trial.STEM + '_tr_content.html')).read_text(encoding='utf-8'),
                                (pnr / (trial.STEM + '.rpt.txt')).read_text(encoding='utf-8'),
                                (folder / 'constraints/audio_visual_hold055.sdc').read_text(encoding='utf-8'),
                                (pnr / (trial.STEM + '.pin.html')).read_text(encoding='utf-8'),
                                (pnr / 'cmd.do').read_text(encoding='utf-8'),
                                (pnr / 'device.cfg').read_bytes())
        for key in ['errors', 'global_worst_paths', 'recovery_removal_worst_paths', 'resources',
                    'clocks', 'summary', 'per_clock_TNS', 'offline_report_gate_passed',
                    'CDC_second_stage_slacks', 'CDC_surviving_payload_path_counts',
                    'min_pulse_width_slack_ns']:
            assert actual[key] == result[key], (label, key)
        assert not actual['offline_report_gate_passed']
        assert int(actual['summary']['Numbers of Hold Violated Endpoints']) == (3 if route_option == 1 else 1)
        for name, digest in result['artifact_SHA256'].items():
            assert trial.sha((folder / name).read_bytes()) == digest, name
        receipt = load(folder / 'build_receipt.json')
        assert receipt == result['receipt'] and receipt['state'] == 'finished' and receipt['exit_code'] == 0
        assert receipt['build_log_SHA256'] == trial.sha((folder / 'build.log').read_bytes())
        manifest = load(folder / 'input_manifest.json')
        assert len(manifest['inputs']) == 56 and set(manifest['changes']) == trial.ALLOWED
        differences = []
        for record in manifest['inputs']:
            current = (folder / record['path']).read_bytes()
            original = (trial.BASE / record['path']).read_bytes()
            assert trial.sha(current) == record['candidate_SHA256']
            assert trial.sha(original) == record['baseline_SHA256']
            if current.replace(folder.as_posix().encode(), trial.BASE.as_posix().encode()) != original:
                differences.append(record['path'])
        assert set(differences) == trial.ALLOWED
        review = load(folder / 'functional/functional_review.json')
        evidence = Path(review['actual_evidence_directory'])
        evidence.relative_to(folder)
        assert review == load(evidence / 'functional_review.json') and review['passed']
        for name, digest in review['RTL_SHA256'].items():
            assert trial.sha((folder / 'sources' / name).read_bytes()) == digest, name
        for name, digest in review['testbench_SHA256'].items():
            assert trial.sha((evidence / name).read_bytes()) == digest
            assert trial.sha((HERE / name).read_bytes()) == digest
        vendor = trial.ROOT / 'tools/gowin_1_9_11_03/IDE/simlib/gw5a/prim_sim.v'
        assert trial.sha(vendor.read_bytes()) == review['vendor_primitive_SHA256']
        for name, run in review['runs'].items():
            log = evidence / (name + '.log')
            assert run['log_SHA256'] == trial.sha(log.read_bytes())
            assert (run['exit'] == 0) == run['expected_success']
            if not run['expected_success']:
                assert 'FATAL:' in log.read_text(encoding='utf-8')
        assert len(review['runs']) == 8 and len(review['RTL_SHA256']) == 45
        top_log = (evidence / 'top.log').read_text(encoding='utf-8')
        for marker in ['PASS full clock40 integration checks=1855',
                       'frames=189 commits=189 max_processing_cycles=30 underrun=0',
                       'BCLK avg_period_ns=325.488281']:
            assert marker in top_log
        assert 'core clock period mismatch 20.000000' in (evidence / 'wrong_divider.log').read_text(encoding='utf-8')
        assert 'not2.4576MHz from old NCO step' in (evidence / 'old_step.log').read_text(encoding='utf-8')
        verified.append({'label': label, 'actual_functional_checks': 1855,
                         'full_tool_build_completed': True, 'strict_STA_gate_passed': False,
                         'hold_violated_endpoints': int(actual['summary']['Numbers of Hold Violated Endpoints']),
                         'actual_clock_MHz': {'system': 40, 'pixel': 25, 'serial': 125}})
    G, H = HERE / 'G_pll_core40', HERE / 'H_pll_core40_route2'
    for directory in ['sources', 'constraints', 'rom', 'include']:
        assert {p.name for p in (G / directory).iterdir()} == {p.name for p in (H / directory).iterdir()}
        for p in (G / directory).iterdir():
            assert (H / directory / p.name).read_bytes().replace(H.as_posix().encode(), G.as_posix().encode()) == p.read_bytes()
    h_tcl = (H / 'run.tcl').read_bytes().replace(H.as_posix().encode(), G.as_posix().encode())
    assert h_tcl.count(b'set_option -route_option 2') == 1
    assert h_tcl.replace(b'set_option -route_option 2', b'set_option -route_option 1') == (G / 'run.tcl').read_bytes()
    repair = load(HERE / 'H_functional_index_repair.json')
    assert repair['original_wrapper_exit'] == 1 and repair['all_actual_saved_run_logs_verified']
    assert not repair['RTL_changed'] and not repair['test_rerun_or_fabricated']
    trial.protect()
    route.protect_G()
    trial.write_json(HERE / 'verification_receipt.json', {'evidence_integrity_passed': True,
                     'does_not_override_STA_failure': True, 'candidates': verified,
                     'protected_previous_files': 1263, 'protected_G_files': 172,
                     'formal_repo_written': False, 'programmed': False,
                     'simulation_limitations': ['DVI boundary stub; no TMDS verification',
                                                'Icarus-only include/allocator syntax adapters',
                                                'LOCK loss is injected, not hardware measurement']})
    print('EVIDENCE AUDIT PASS; both clock40 candidates remain STA FAIL', flush=True)


def package():
    audit()
    target = HERE / 'M3_138K_clock40_evidence_20261005.zip'
    assert not target.exists(), 'Never overwrite a delivered archive'
    files = []
    for path in HERE.rglob('*'):
        if not path.is_file() or path == target or path.name == 'archive_receipt.json':
            continue
        relative = path.relative_to(HERE)
        if any(p in ['tmp', 'gwsynthesis', '__pycache__'] for p in relative.parts):
            continue
        if path.suffix.lower() in ['.vvp', '.bin', '.binx', '.fs', '.pr', '.p', '.db', '.exe', '.dll']:
            continue
        files.append(path)
    members = {p.relative_to(HERE).as_posix(): trial.sha(p.read_bytes()) for p in files}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(HERE).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None and set(archive.namelist()) == set(members)
        assert all(trial.sha(archive.read(name)) == digest for name, digest in members.items())
    trial.write_json(HERE / 'archive_receipt.json', {'path': str(target), 'bytes': target.stat().st_size,
                     'SHA256': trial.sha(target.read_bytes()), 'members': members,
                     'CRC_and_member_SHA_passed': True, 'contains_bitstream_or_executable': False})
    print('ZIP CRC/member SHA PASS', target.stat().st_size, 'bytes', flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['audit']:
        audit()
    elif sys.argv[1:] == ['package']:
        package()
    else:
        raise ValueError('Choose audit or package')
