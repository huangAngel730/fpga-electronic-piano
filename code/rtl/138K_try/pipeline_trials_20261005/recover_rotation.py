"""One same-input recovery after execution-session loss, not a seed search."""
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
import pipeline_trials as task

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / 'D_rotation_pipeline'
RECOVERED = HERE / 'D_rotation_pipeline_recovery1'
RECEIPT = HERE / 'rotation_recovery_receipt.json'


def original_hashes():
    return {p.relative_to(ORIGINAL).as_posix(): task.shared.sha(p.read_bytes())
            for p in ORIGINAL.rglob('*') if p.is_file()}


def verify_original():
    receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
    assert original_hashes() == receipt['original_artifact_SHA256'], 'Do not modify interrupted original'
    task.protect(check=True)


def run():
    assert not RECEIPT.exists() and not RECOVERED.exists(), 'One recovery maximum; keep every attempt'
    task.protect(check=True)
    original_receipt = json.loads((ORIGINAL / 'build_receipt.json').read_text(encoding='utf-8'))
    assert original_receipt['state'] == 'running'
    assert not (ORIGINAL / 'impl/pnr/audio_visual_coexistence_top_tr_content.html').exists()
    hashes = original_hashes()
    task.shared.write_json(RECEIPT, {
        'recorded': datetime.now().astimezone().isoformat(),
        'original_build_receipt': original_receipt, 'original_artifact_SHA256': hashes,
        'observed_original_state': 'execution_session_unavailable_process_exited_no_final_STA',
        'reason': 'Unknown from retained logs; not classified as STA fail or 1800s timeout',
        'process_absence_readonly_checked': True, 'recovery_attempt_limit': 1,
        'candidate_seed_options_constraints_unchanged': True})
    task.shared.LABEL = RECOVERED.name
    task.shared.OUT = RECOVERED
    task.shared.SCOPE = HERE / 'candidates/D_rotation_pipeline'
    task.shared.prepare()
    for directory in ['sources', 'constraints', 'rom', 'include']:
        for source in (ORIGINAL / directory).iterdir():
            new = RECOVERED / directory / source.name
            assert new.read_bytes().replace(RECOVERED.as_posix().encode(), ORIGINAL.as_posix().encode()) == source.read_bytes()
    evidence = json.loads((ORIGINAL / 'functional/functional_review.json').read_text(encoding='utf-8'))
    assert evidence['passed'] and evidence['candidate_SHA256'] == task.shared.sha((RECOVERED / 'sources/midi_event_parser.sv').read_bytes())
    for name, case in evidence['runs'].items():
        log = ORIGINAL / 'functional' / (name + '.log')
        assert task.shared.sha(log.read_bytes()) == case['log_SHA256']
        assert (case['exit'] == 0) == case['expected_success']
    shutil.copytree(ORIGINAL / 'functional', RECOVERED / 'functional')
    task.shared.write_json(RECOVERED / 'functional_prefix_reuse.json', {
        'source': str(ORIGINAL / 'functional'), 'not_a_new_functional_run': True,
        'source_SHA_verified': True, 'original_logs_and_exits_verified': True,
        'copied_SHA256': {p.relative_to(RECOVERED / 'functional').as_posix(): task.shared.sha(p.read_bytes())
                          for p in (RECOVERED / 'functional').rglob('*') if p.is_file()}})
    try:
        task.shared.build()
    finally:
        verify_original()


def collect():
    verify_original()
    paths = [HERE / 'C_payload_buffer', RECOVERED]
    for path in paths:
        receipt = json.loads((path / 'build_receipt.json').read_text(encoding='utf-8'))
        assert receipt['state'] == 'finished', 'Do not assess an unfinished recovery'
    results = [task.assessor.evaluate(path.name) for path in paths]
    task.shared.write_json(HERE / 'final_results.json', {
        'baseline': task.assessor.report(task.shared.BASE), 'results': results,
        'interrupted_attempt': json.loads(RECEIPT.read_text(encoding='utf-8')),
        'two_design_methods': True, 'new_functional_runs': 2,
        'physical_invocations': 3, 'completed_physical_runs': 2,
        'seed_options_or_constraints_changed_for_recovery': False})
    for result in results:
        print(result['label'], 'GATE', result['offline_report_gate_passed'], 'ERRORS', result['errors'],
              'PATHS', result['global_worst_paths'], result['recovery_removal_worst_paths'],
              'RESOURCES', result['resources'], 'SUMMARY', result['summary'], flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['run']:
        run()
    elif sys.argv[1:] == ['verify-original']:
        verify_original()
        print('Interrupted original and older successful artifacts preserved PASS')
    elif sys.argv[1:] == ['collect']:
        collect()
    else:
        raise ValueError('run, collect, or verify-original required')
