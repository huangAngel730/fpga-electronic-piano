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
    command = [sys.executable, '-B', '-X', 'utf8', str(src / 'chat9_replay.py'), '--output', str(out / 'analysis')]
    plan = dict(machine=platform.node(), python=identity(Path(sys.executable)), argv=command,
                cwd=str(ROOT), source_before=before, software_budget_s=90, RTL_calls=0, EDA_calls=0)
    (out / 'PLAN.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    begin = time.monotonic()
    timeout = False
    try:
        p = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=90, check=False)
        stdout, stderr, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code, timeout = exc.stdout or b'', exc.stderr or b'', None, True
    (out / 'stdout.log').write_bytes(stdout)
    (out / 'stderr.log').write_bytes(stderr)
    after = [identity(p) for p in sorted(src.glob('*.py'))]
    elapsed = time.monotonic() - begin
    result = dict(**plan, exit_code=code, timeout=timeout, elapsed_s=elapsed, source_after=after,
                  sources_unchanged=before == after, stdout=identity(out / 'stdout.log'),
                  stderr=identity(out / 'stderr.log'), board_release_allowed=False)
    result['status'] = 'SOFTWARE_REPLAY_PASS' if code == 0 and not timeout and elapsed <= 90 and before == after else 'SOFTWARE_REPLAY_FAIL'
    (out / 'RECEIPT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'exit_code', 'timeout', 'elapsed_s')}))
    return int(result['status'] != 'SOFTWARE_REPLAY_PASS')


if __name__ == '__main__':
    raise SystemExit(main())
