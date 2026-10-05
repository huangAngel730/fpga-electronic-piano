"""One isolated route=2 counter-test; preserve the completed route=1 trial."""
from pathlib import Path
import runpy
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clock_trial as trial

G = trial.OUT
H = trial.HERE / 'H_pll_core40_route2'

def protect_G(begin=False):
    import json
    record = trial.HERE / 'G_preservation_before_H.json'
    actual = {p.relative_to(G).as_posix(): trial.sha(p.read_bytes())
              for p in G.rglob('*') if p.is_file()}
    if begin:
        assert not record.exists()
        trial.write_json(record, actual)
        return
    previous = json.loads(record.read_text(encoding='utf-8'))
    assert actual == previous, 'Completed G evidence changed during H experiment'
    trial.write_json(trial.HERE / 'G_preservation_verification.json',
                     {'files': len(actual), 'passed': True})
    print('Completed G evidence protected', len(actual), 'files PASS', flush=True)

if __name__ != '__main__':
    pass
elif sys.argv[1:] == ['prepare']:
    trial.protect()
    original = trial.BASE
    trial.BASE, trial.OUT = G, H
    trial.prepare()
    trial.BASE = original
    trial.seal()
    trial.protect()
elif sys.argv[1:] == ['freeze-G']:
    protect_G(begin=True)
    protect_G()
elif sys.argv[1:] == ['protect-G']:
    protect_G()
elif sys.argv[1:] == ['publish-H-review']:
    # The first H wrapper completed every simulation and saved the review,
    # then failed only because the functional index directory did not exist.
    # Publish from the actual saved evidence, never fabricate/re-run a test.
    import json
    evidence = H / 'functional_v6_CDC_state_check'
    review = json.loads((evidence / 'functional_review.json').read_text(encoding='utf-8'))
    assert review['passed'] and Path(review['actual_evidence_directory']) == evidence
    for name, run in review['runs'].items():
        assert trial.sha((evidence / (name + '.log')).read_bytes()) == run['log_SHA256']
        assert (run['exit'] == 0) == run['expected_success']
    index = H / 'functional'
    assert not index.exists()
    index.mkdir()
    trial.write_json(index / 'functional_review.json', review)
    trial.write_json(trial.HERE / 'H_functional_index_repair.json',
                     {'original_wrapper_exit': 1, 'reason': 'missing index directory after all simulations completed',
                      'all_actual_saved_run_logs_verified': True, 'RTL_changed': False,
                      'test_rerun_or_fabricated': False})
    protect_G()
elif sys.argv[1:] == ['functional']:
    protect_G()
    trial.OUT = H
    sys.argv = [str(trial.HERE / 'run_functional.py'), '--CDC-state-check']
    runpy.run_path(str(trial.HERE / 'run_functional.py'), run_name='__main__')
    protect_G()
elif sys.argv[1:] == ['build']:
    trial.OUT = H
    trial.protect()
    protect_G()
    try:
        trial.build()
    finally:
        trial.protect()
        protect_G()
else:
    raise ValueError('Choose prepare, functional, build')
