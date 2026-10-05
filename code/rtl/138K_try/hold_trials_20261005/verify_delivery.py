"""Recompute evidence gate and archive only actual completed experiments."""
import ast
import json
from pathlib import Path
import sys
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hold_trial as trial
import assess_hold as assess


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read(path):
    return path.read_text(encoding='utf-8')


def audit():
    tests = read(trial.HERE / 'report_selftest.log')
    assert 'Ran 23 tests' in tests and '\nOK\n' in tests
    for script in trial.HERE.glob('*.py'):
        ast.parse(read(script), filename=str(script))
    threshold_tests = {}
    for slack, gate, expected in [(.499, True, False), (.5, True, True), (.501, True, True),
                                   (1.279, False, False), (float('nan'), True, False)]:
        value = assess.accept_user({'global_worst_paths': {'Setup': {'slack_ns': slack}}, 'offline_report_gate_passed': gate})
        assert value == expected
        threshold_tests[str((slack, gate))] = True
    verified = []
    for label in ['I_hold_locations', 'L_locations_guard065']:
        out = trial.folder(label)
        result = load(out / 'assessment.json')
        manifest = trial.verify_inputs(label)
        pnr = out / 'impl/pnr'
        timing, usage = read(pnr / (trial.STEM + '_tr_content.html')), read(pnr / (trial.STEM + '.rpt.txt'))
        sdc, pin_report = read(out / 'constraints/audio_visual_hold055.sdc'), read(pnr / (trial.STEM + '.pin.html'))
        command, cfg = read(pnr / 'cmd.do'), (pnr / 'device.cfg').read_bytes()
        fresh = assess.profile(label, timing, usage, sdc, pin_report, command, cfg)
        for key in ['errors', 'user_acceptance_passed', 'global_worst_paths', 'recovery_removal_worst_paths',
                    'resources', 'clocks', 'per_clock_TNS', 'summary', 'internal_location_readback',
                    'diagnostic_original_short_path', 'CDC_second_stage_slacks', 'min_pulse_width_slack_ns']:
            assert fresh[key] == result[key], (label, key)
        assert result['receipt'] == load(out / 'build_receipt.json')
        assert result['receipt']['state'] == 'finished' and result['receipt']['exit_code'] == 0
        for name, digest in result['artifact_SHA256'].items():
            assert trial.sha((out / name).read_bytes()) == digest, name
        # Exact approved CST delta, no changed IO/pin/voltage commands.
        expected_cst = (trial.BASE / 'constraints/audio_visual.cst').read_bytes()
        expected_cst += (f'// Isolated Hold repair: spread existing FFs, no pin/voltage/clock change.\n'
                         f'INS_LOC "{assess.PAIR}base_s1_18_s0" R83C99[1][B];\n'
                         f'INS_LOC "{assess.PAIR}base_s2_18_s0" R87C101[0][A];\n').encode()
        assert (out / 'constraints/audio_visual.cst').read_bytes() == expected_cst
        assert trial.normalize((out / 'run.tcl').read_bytes(), out) == (trial.BASE / 'run.tcl').read_bytes()
        differences = []
        for record in manifest['inputs']:
            path = out / record['path']
            if trial.normalize(path.read_bytes(), out) != (trial.BASE / record['path']).read_bytes():
                differences.append(record['path'])
        assert set(differences) == {'constraints/audio_visual.cst', 'constraints/audio_visual_hold055.sdc'}
        review = load(out / 'functional/functional_review.json')
        evidence = Path(review['actual_evidence_directory'])
        evidence.relative_to(out)
        assert review == load(evidence / 'functional_review.json') and review['passed']
        assert len(review['RTL_SHA256']) == 45 and len(review['runs']) == 8
        for name, digest in review['RTL_SHA256'].items():
            assert trial.sha((out / 'sources' / name).read_bytes()) == digest
        for name, digest in review['testbench_SHA256'].items():
            assert trial.sha((evidence / name).read_bytes()) == digest == trial.sha((trial.HERE / name).read_bytes())
        vendor = trial.ROOT / 'tools/gowin_1_9_11_03/IDE/simlib/gw5a/prim_sim.v'
        assert trial.sha(vendor.read_bytes()) == review['vendor_primitive_SHA256']
        for name, run in review['runs'].items():
            log = evidence / (name + '.log')
            assert trial.sha(log.read_bytes()) == run['log_SHA256']
            assert (run['exit'] == 0) == run['expected_success']
            if not run['expected_success']:
                assert 'FATAL:' in read(log)
        for marker in ['PASS full clock40 integration checks=1855',
                       'frames=189 commits=189 max_processing_cycles=30 underrun=0']:
            assert marker in read(evidence / 'top.log')
        weakened = sdc.replace('set_clock_uncertainty -hold  0.550', 'set_clock_uncertainty -hold  0.500') if label.startswith('I_') else sdc.replace('set_clock_uncertainty -hold  0.650', 'set_clock_uncertainty -hold  0.550')
        rejected = assess.profile(label, timing, usage, weakened, pin_report, command, cfg)
        assert 'SDC differs from exact approved H plan plus reports/explicit stricter guard' in rejected['errors']
        # Wrong physical source clock declarations cannot be accepted.
        wrong = sdc.replace('-multiply_by 4 -divide_by 5', '-multiply_by 1 -divide_by 1')
        rejected = assess.profile(label, timing, usage, wrong, pin_report, command, cfg)
        assert not rejected['user_acceptance_passed']
        if label == 'L_locations_guard065':
            # Source text alone must not satisfy the stricter guard: exercise
            # absent, inactive, weakened and duplicate actual STA commands.
            row = ('<tr>\n<td>TC_CLOCK_UNCERTAINTY</td>\n<td>Actived</td>\n'
                   '<td>set_clock_uncertainty -hold  0.650 '
                   '-from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]</td>\n</tr>')
            assert timing.count(row) == 1
            mutations = {'missing': '', 'inactive': row.replace('Actived', 'Inactived'),
                         'weakened': row.replace('0.650', '0.550'),
                         'duplicate': row + '\n' + row}
            for name, replacement in mutations.items():
                mutated = timing.replace(row, replacement)
                rejected = assess.profile(label, mutated, usage, sdc, pin_report, command, cfg)
                assert 'missing/duplicate/incorrect active approved Hold uncertainty' in rejected['errors'], name
                assert not rejected['user_acceptance_passed'], name
        verified.append({'label': label, 'user_acceptance_passed': result['user_acceptance_passed'],
                         'actual_Setup_ns': result['global_worst_paths']['Setup']['slack_ns'],
                         'actual_Hold_ns': result['global_worst_paths']['Hold']['slack_ns'],
                         'hold_uncertainty_ns': result['hold_uncertainty_ns'],
                         'functional_checks': 1855, 'RTL_changed': False, 'added_pipeline_cycles': 0})
    assert verified[0]['user_acceptance_passed'], 'Preserved I success is the minimum deliverable'
    trial.preserve()
    trial.write_json(trial.HERE / 'verification_receipt.json', {'evidence_audit_passed': True,
                     'candidates': verified, 'setup_floor_tests_passed': threshold_tests,
                     'actual_report_negative_constraint_tests_passed': True,
                     'stricter_guard_active_missing_inactive_weakened_duplicate_tests_passed': True,
                     'prior_experiment_files_preserved': 1566, 'I_success_preserved': True,
                     'only_authorized_experiment_folder_written': True, 'programmed': False})
    print('EVIDENCE AUDIT PASS', verified, flush=True)


def package():
    audit()
    target = trial.HERE / 'M3_138K_Hold修复证据_20261005.zip'
    assert not target.exists(), 'Do not overwrite an existing archive'
    files = []
    for path in trial.HERE.rglob('*'):
        if not path.is_file() or path == target or path.name == 'archive_receipt.json':
            continue
        if any(part in ['tmp', 'gwsynthesis', '__pycache__'] for part in path.relative_to(trial.HERE).parts):
            continue
        if path.suffix.lower() in ['.vvp', '.bin', '.binx', '.fs', '.pr', '.p', '.db', '.exe', '.dll']:
            continue
        files.append(path)
    members = {p.relative_to(trial.HERE).as_posix(): trial.sha(p.read_bytes()) for p in files}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for p in sorted(files):
            archive.write(p, p.relative_to(trial.HERE).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None and set(archive.namelist()) == set(members)
        assert all(trial.sha(archive.read(name)) == digest for name, digest in members.items())
    trial.write_json(trial.HERE / 'archive_receipt.json', {'path': str(target), 'bytes': target.stat().st_size,
                     'SHA256': trial.sha(target.read_bytes()), 'members': members,
                     'CRC_and_member_SHA_passed': True, 'contains_bitstream_or_executable': False})
    print('ZIP CRC/member SHA PASS', target.stat().st_size, 'bytes', flush=True)


if __name__ == '__main__':
    {'audit': audit, 'package': package}[sys.argv[1]]()
