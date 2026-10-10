"""Wait for one isolated unlimited PnR; no retries, no device operations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--build', required=True, type=Path)
    cli.add_argument('--control', required=True, type=Path)
    cli.add_argument('--reference', required=True, type=Path)
    args = cli.parse_args()
    build, control = args.build.resolve(), args.control.resolve()
    for directory in (build, control):
        directory.relative_to(ROOT/'code/output')
    control.mkdir(parents=True, exist_ok=False)
    reference = args.reference.resolve()
    reference.relative_to(ROOT/'code/output')
    old = json.loads((reference/'receipt.json').read_text(encoding='utf-8'))
    new = json.loads((build/'receipt.json').read_text(encoding='utf-8'))
    for key in ('source_sha256', 'tool', 'part', 'device_version', 'period_ns'):
        if old[key] != new[key]:
            raise ValueError('same configuration required: '+key)
    if old['configuration_sha256']['module.sdc'] != new['configuration_sha256']['module.sdc']:
        raise ValueError('SDC changed')
    old_tcl = (reference/'synth.tcl').read_text(encoding='ascii')
    if old_tcl.replace(reference.as_posix(), build.as_posix()) != (
            build/'synth.tcl').read_text(encoding='ascii'):
        raise ValueError('synthesis or implementation options changed')
    runner = Path(__file__).with_name('timing_build.py')
    shutil.copyfile(Path(__file__), control/'background_runner.py')
    command = [sys.executable, '-B', '-X', 'utf8', str(runner), 'pnr',
               '--output', str(build), '--unlimited-pnr',
               '--allow-isolated-unreleased-bitstream']
    job = dict(status='STARTED', supervisor_pid=os.getpid(), command=command,
               started_utc=datetime.now(timezone.utc).isoformat(),
               timeout_seconds=None, auto_retry=False, do_not_program=True,
               same_source_tool_configuration=True,
               reference_receipt_sha256=hashlib.sha256(
                   (reference/'receipt.json').read_bytes()).hexdigest(),
               runner_sha256=hashlib.sha256(runner.read_bytes()).hexdigest())
    with (control/'runner.stdout.bin').open('xb') as stdout, (
            control/'runner.stderr.bin').open('xb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        job['runner_pid'] = process.pid
        dump(control/'started.json', job)
        # Deliberately no timeout. Only this child's natural termination ends wait.
        result = process.wait()
    job.update(status='PROCESS_EXITED_REVIEW_REQUIRED', exit_code=result,
               finished_utc=datetime.now(timezone.utc).isoformat())
    receipt = build/'receipt.json'
    job['build_receipt_sha256'] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    job['build_status'] = json.loads(receipt.read_text(encoding='utf-8'))['status']
    job['native_sta_passed'] = False
    dump(control/'completion.json', job)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
