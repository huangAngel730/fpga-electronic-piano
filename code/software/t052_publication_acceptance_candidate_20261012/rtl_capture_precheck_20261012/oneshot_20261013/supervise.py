"""Observe only the incremental static verifier's real exit, never HDL tools."""
import argparse
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location('oneshot_supervised', HERE / 'oneshot.py')
m = importlib.util.module_from_spec(loader)
loader.loader.exec_module(m)
sys.path.insert(0, str(m.RUNNER_DIR))
from supervisor_20261013 import observe_run  # noqa: E402


def sources():
    paths = list(HERE.glob('*.py')) + [m.CHECKER, m.RUNNER_DIR / 'runner.py',
             m.RUNNER_DIR / 'windows_job.py', m.RUNNER_DIR / 'runner_tail_20261013.py',
             m.RUNNER_DIR / 'supervisor_20261013.py']
    return {p.resolve().as_posix(): m.identity(p) for p in paths}


def command(evidence, reuse, suite):
    return [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(HERE / 'qualify.py'),
            '--output', str(Path(evidence).resolve()), '--suite', str(Path(suite).resolve()),
            '--reuse', str(Path(reuse).resolve())]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('output', 'evidence', 'reuse', 'suite'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    result = observe_run(args.output, command(args.evidence, args.reuse, args.suite), m.ROOT,
                         args.evidence.resolve() / 'receipt.json', sources())
    print(result)
    raise SystemExit(result['exit_code'])
