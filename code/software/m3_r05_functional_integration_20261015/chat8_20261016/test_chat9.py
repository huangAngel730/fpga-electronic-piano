"""New adapter tests only; mutated recorded PCM copies are SOFTWARE negatives."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

from chat9_replay import closure, read_inputs, golden


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--analysis', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    args.output.mkdir(exist_ok=False)
    source = Path(__file__).with_name('chat9_replay.py')
    actual = json.loads((args.analysis / 'OBSERVED_COMMITS.json').read_text(encoding='utf-8'))
    tests = []
    changes = [('left', 1, 'PCM_LEFT'), ('right', -1, 'PCM_RIGHT'), ('clip', 1, 'PCM_CLIP'),
               ('id', 1, 'PCM_ID'), ('cycle', -1, 'PCM_CYCLE'), ('drop', 0, 'PCM_COMPLETENESS')]
    for field, delta, diagnostic in changes:
        bad = copy.deepcopy(actual)
        if field == 'drop':
            bad.pop(100)
        else:
            bad[100][field] += delta
        path = args.output / (field + '_SOFTWARE_MUTANT.json')
        path.write_text(json.dumps(bad, indent=2), encoding='utf-8')
        cmd = [sys.executable, '-B', '-X', 'utf8', str(source), '--output', str(args.output),
               '--compare-only', str(path), '--golden', str(args.analysis / 'GOLDEN.json')]
        p = subprocess.run(cmd, capture_output=True, timeout=10, check=False)
        (args.output / (field + '.stdout.log')).write_bytes(p.stdout)
        (args.output / (field + '.stderr.log')).write_bytes(p.stderr)
        ok = p.returncode == 1 and diagnostic in p.stderr.decode('utf-8')
        tests.append(dict(name=field, synthetic=True, argv=cmd, exit_code=p.returncode,
                          timeout=False, diagnostic=diagnostic, passed=ok))
    models, _ = closure()
    controls, config, resets, requests, frames, _ = read_inputs()
    # Source-calendar rejection: altered inputs, not new real captures.
    cases = [('cancel', 'UNSUPPORTED_FRAME_OVERLAP'), ('dispatch', 'UNSUPPORTED_DISPATCH_OVERLAP'),
             ('reset', 'UNSUPPORTED_RESET_OVERLAP'), ('control', 'UNSUPPORTED_CONTROL')]
    for case, diagnostic in cases:
        ct, rs, fr = copy.deepcopy(controls), copy.deepcopy(resets), frames.copy()
        if case == 'cancel':
            fr.append(requests[0]['cycle'] + 24)
        elif case == 'dispatch':
            ct[0] = (requests[0]['cycle'] + 1, ct[0][1], ct[0][2])
        elif case == 'reset':
            rs[-1] = (requests[0]['cycle'] + 25, 0)
        else:
            ct[0][1]['event_type'] = 1
        caught = ''
        try:
            golden(models, ct, config, rs, requests, fr)
        except ValueError as exc:
            caught = str(exc)
        tests.append(dict(name=case, synthetic=True, diagnostic=diagnostic,
                          actual_diagnostic=caught, passed=caught.startswith(diagnostic)))
    result = dict(new_tests=len(tests), tests=tests, passed=all(t['passed'] for t in tests),
                  real_RTL_negatives=0, old_tests_rerun=0)
    (args.output / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
