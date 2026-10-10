"""Read-only bounded PnR progress sampling. CPU activity is not convergence."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]


def snapshot(build, pid):
    command = ('Get-CimInstance Win32_Process -Filter "ProcessId = '+str(pid)+'" | '
               'Select-Object ProcessId,ParentProcessId,CommandLine,CreationDate,'
               'KernelModeTime,UserModeTime,ReadOperationCount,WriteOperationCount,'
               'ReadTransferCount,WriteTransferCount | ConvertTo-Json -Compress')
    query = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
                           capture_output=True, timeout=20)
    if query.returncode:
        raise ValueError('process query failed: '+query.stderr.decode(errors='replace'))
    process = json.loads(query.stdout.decode('utf-8')) if query.stdout.strip() else None
    if process and str(build/'pnr.tcl').lower() not in process['CommandLine'].lower():
        raise ValueError('PID does not belong to this exact isolated build')
    raw = (build/'pnr.stdout.bin').read_bytes()
    text = raw.decode('utf-8', errors='replace')
    phases = re.findall(r'^.*(?:Phase \d+ completed|routing completed|analysis completed).*$',
                        text, re.MULTILINE)
    folder = build/'project/score_ram/impl/pnr'
    return dict(observed_at=datetime.now().astimezone().isoformat(), process=process,
                process_query=dict(command=command, exit_code=query.returncode),
                reported_phases=phases, stdout_bytes=len(raw),
                stdout_sha256=hashlib.sha256(raw).hexdigest(),
                files={p.name: dict(bytes=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns)
                       for p in folder.iterdir() if p.is_file()})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('build', type=Path)
    cli.add_argument('--pid', type=int, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    build = args.build.resolve()
    build.relative_to(ROOT/'code/output')
    out = args.output.resolve()
    out.relative_to(ROOT/'code/output')
    out.mkdir(parents=True, exist_ok=False)
    first = snapshot(build, args.pid)
    time.sleep(40)
    second = snapshot(build, args.pid)
    cpu_delta = None
    if first['process'] and second['process']:
        cpu_delta = sum(int(second['process'][k])-int(first['process'][k])
                        for k in ('KernelModeTime', 'UserModeTime'))/1e7
    new_phases = [p for p in second['reported_phases'] if p not in first['reported_phases']]
    changed = [name for name, item in second['files'].items()
               if first['files'].get(name) != item]
    result = dict(first=first, second=second, cpu_seconds_delta=cpu_delta,
                  new_reported_phases=new_phases, updated_native_files=changed,
                  classification=('NEW_REPORTED_PHASE' if new_phases else
                                  'CPU_ACTIVE_NO_NEW_REPORTED_PHASE' if cpu_delta and cpu_delta > 0 else
                                  'NO_OBSERVED_CPU_ACTIVITY_OR_PROCESS_ENDED'),
                  cannot_infer_deadlock_or_convergence_from_cpu_alone=True,
                  physical_sta_passed=False, read_only_monitor=True,
                  monitor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                                   encoding='utf-8', newline='\n')
    (out/'monitor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k: result[k] for k in ('classification', 'cpu_seconds_delta',
                                           'new_reported_phases', 'updated_native_files')}))


if __name__ == '__main__':
    main()
