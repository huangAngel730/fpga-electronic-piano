"""Record the new A software checks with exact files, commands and raw streams."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    sources.append(Path(sys.executable))
    before = {str(p): sha(p) for p in sources}
    receipt = dict(schema='M1_R06_PCM_SOFTWARE_CHECK_RECEIPT_V1',
                   started_utc=datetime.now(timezone.utc).isoformat(),
                   scope='NEW_M1_A_SOFTWARE_INCREMENT_ONLY', actual_dut_result='PENDING_REAL_CAPTURE',
                   source_before_sha256=before, steps=[], hdl_calls=0, old_suites_rerun=False,
                   automatic_retry=False, total_tool_budget_seconds=240)
    commands = [[sys.executable, '--version'],
                [sys.executable, '-B', '-X', 'utf8', str(HERE / 'test_oracle.py')],
                [sys.executable, '-B', '-X', 'utf8', str(HERE / 'generate_vectors.py'), '--output', str(out / 'vectors')]]
    started = time.monotonic()
    for index, command in enumerate(commands):
        stdout, stderr = out / f'{index}_stdout.bin', out / f'{index}_stderr.bin'
        step_start = time.monotonic()
        timed_out = False
        with stdout.open('xb') as so, stderr.open('xb') as se:
            process = subprocess.Popen(command, cwd=HERE, stdout=so, stderr=se)
            try:
                code = process.wait(timeout=min(120, max(1, 240 - (time.monotonic() - started))))
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                code = process.wait(timeout=5)
        receipt['steps'].append(dict(command=command, cwd=str(HERE), exit_code=code,
                                    timed_out=timed_out, elapsed_seconds=round(time.monotonic() - step_start, 6),
                                    stdout=str(stdout), stderr=str(stderr), stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        if code != 0 or timed_out:
            receipt['first_failure_step'] = index
            break
    receipt['source_after_sha256'] = {str(p): sha(p) for p in sources}
    receipt['source_unchanged'] = before == receipt['source_after_sha256']
    receipt['elapsed_seconds'] = round(time.monotonic() - started, 6)
    receipt['result'] = 'SOFTWARE_INCREMENT_CHECKS_PASS' if len(receipt['steps']) == 3 and all(s['exit_code'] == 0 and not s['timed_out'] for s in receipt['steps']) and receipt['source_unchanged'] else 'FAIL_SOFTWARE_INCREMENT'
    receipt['output_sha256'] = {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    with (out / 'RUN_RECEIPT.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: receipt[k] for k in ('result', 'actual_dut_result', 'elapsed_seconds', 'source_unchanged')}))
    return 0 if receipt['result'] == 'SOFTWARE_INCREMENT_CHECKS_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
