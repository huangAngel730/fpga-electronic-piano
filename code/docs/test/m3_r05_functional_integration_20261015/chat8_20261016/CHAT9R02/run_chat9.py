"""Bounded software replay, never starts RTL or EDA; unique output per run."""
import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from analyze_existing import ROOT, identity


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--run-id', required=True)
    args = cli.parse_args()
    if not args.run_id.isalnum():
        raise ValueError('RUN_ID')
    out = ROOT / 'code/docs/test/m3_r05_functional_integration_20261015/chat8_20261016' / args.run_id
    out.mkdir(exist_ok=False)
    src = Path(__file__).parent
    before = [identity(p) for p in sorted(src.glob('*.py'))]
    for item in before:
        (out / Path(item['path']).name).write_bytes(Path(item['path']).read_bytes())
    commands = [
        [sys.executable, '-B', '-X', 'utf8', str(src / 'chat9_replay.py'), '--output', str(out / 'analysis')],
        [sys.executable, '-B', '-X', 'utf8', str(src / 'test_chat9.py'), '--analysis', str(out / 'analysis'),
         '--output', str(out / 'negatives')],
    ]
    plan = dict(machine=platform.node(), python=identity(Path(sys.executable)), argv=commands,
                cwd=str(ROOT), source_before=before, step_budget_s=90,
                software_budget_s=180, RTL_calls=0, EDA_calls=0)
    (out / 'PLAN.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    begin = time.monotonic()
    timeout, calls = False, []
    for index, command in enumerate(commands):
        try:
            p = subprocess.run(command, cwd=ROOT, capture_output=True,
                               timeout=min(90, max(0.001, 180 - (time.monotonic() - begin))), check=False)
            stdout, stderr, code = p.stdout, p.stderr, p.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code, timeout = exc.stdout or b'', exc.stderr or b'', None, True
        stdout_path, stderr_path = out / f'{index}.stdout.log', out / f'{index}.stderr.log'
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        calls.append(dict(argv=command, exit_code=code, timeout=timeout,
                          stdout=identity(stdout_path), stderr=identity(stderr_path)))
        if code != 0 or timeout:
            break
    after = [identity(p) for p in sorted(src.glob('*.py'))]
    elapsed = time.monotonic() - begin
    result = dict(**plan, exit_code=code, timeout=timeout, elapsed_s=elapsed, source_after=after,
                  sources_unchanged=before == after, calls=calls, board_release_allowed=False)
    result['status'] = 'SOFTWARE_REPLAY_PASS' if len(calls) == 2 and code == 0 and not timeout and elapsed <= 180 and before == after else 'SOFTWARE_REPLAY_FAIL'
    (out / 'RECEIPT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'exit_code', 'timeout', 'elapsed_s')}))
    return int(result['status'] != 'SOFTWARE_REPLAY_PASS')


if __name__ == '__main__':
    raise SystemExit(main())
