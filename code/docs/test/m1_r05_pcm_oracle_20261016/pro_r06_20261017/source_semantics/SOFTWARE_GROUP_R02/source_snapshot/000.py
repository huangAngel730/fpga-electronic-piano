"""Consume the single R6-1 software group; never invoke an HDL tool."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
MODEL = REPO / 'code/model/m1_r05_pcm_oracle_20261016/pro_r06_20261017/source_semantics'
RTL = REPO / 'code/rtl/audio/m1_pro_observer_r06_20261017'
CONTRACT = HERE / '字段语义_R06.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    out = HERE / 'SOFTWARE_GROUP_R02'
    out.mkdir(exist_ok=False)
    ledger = HERE / 'BUDGET_R6_1_REPAIR_CONSUMED.json'
    write_new(ledger, {'package': 'M1-R6-1', 'group': 'R02_PREPARATION_REPAIR',
                       'state': 'CONSUMED_BEFORE_START', 'limit_seconds': 60,
                       'first_group': 'R01 failed during long-path snapshot preparation; no tests started',
                       'new_hdl_eda_device_calls': 0})
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    files = [REPO / item['path'] for item in contract['sources']]
    files += sorted(MODEL.glob('*.py')) + [CONTRACT, Path(__file__)]
    files = sorted(set(files))
    before = {p.relative_to(REPO).as_posix(): sha(p) for p in files}
    snapshot = out / 'source_snapshot'
    snapshot_map = []
    for index, path in enumerate(files):
        target = snapshot / (str(index).zfill(3) + path.suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        snapshot_map.append({'snapshot': target.name, 'path': path.relative_to(REPO).as_posix(), 'sha256': sha(path)})
    write_new(out / 'SNAPSHOT_MAP.json', snapshot_map)
    commands = [
        [sys.executable, '-B', '-X', 'utf8', '-m', 'unittest', 'discover',
         '-s', str(MODEL), '-p', 'test_semantics_contract.py', '-v'],
        [sys.executable, '-B', '-X', 'utf8', str(MODEL / 'semantics_contract.py'),
         '--contract', str(CONTRACT), '--root', str(REPO),
         '--out', str(out / 'STATIC_CONTRACT_RESULT.json')],
    ]
    plan = {'package': 'M1-R6-1', 'group': 'R02_PREPARATION_REPAIR', 'timeout_seconds': 60,
            'cwd': str(REPO), 'argvs': commands, 'frozen_inputs': before,
            'python': {'path': sys.executable, 'version': sys.version,
                       'sha256': sha(Path(sys.executable))},
            'platform': platform.platform(), 'machine': platform.node(),
            'scope': 'new software schema and explicit source/port checks only',
            'not_executed': ['HDL compilation/simulation', 'EDA', 'device',
                             'old golden suites', 'M3 checker', 'PCM reconstruction']}
    write_new(out / 'PLAN.json', plan)
    started = time.monotonic()
    runs = []
    for index, command in enumerate(commands):
        folder = out / ('command_' + str(index + 1))
        folder.mkdir()
        begin = time.monotonic()
        timed_out = False
        remaining = 60 - (begin - started)
        with (folder / 'stdout.bin').open('xb') as so, (folder / 'stderr.bin').open('xb') as se:
            proc = subprocess.Popen(command, cwd=REPO, stdout=so, stderr=se)
            try:
                code = proc.wait(timeout=max(0.001, remaining))
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                code = proc.wait()
        runs.append({'argv': command, 'cwd': str(REPO), 'exit_code': code,
                     'timeout': timed_out, 'elapsed_seconds': time.monotonic() - begin,
                     'streams': {name: {'bytes': (folder / name).stat().st_size,
                                         'sha256': sha(folder / name)}
                                 for name in ('stdout.bin', 'stderr.bin')}})
        if code or timed_out:
            break
    after = {p.relative_to(REPO).as_posix(): sha(p) for p in files}
    receipt = dict(plan, executions=runs, source_after_sha256=after,
                   source_unchanged=before == after,
                   total_seconds=time.monotonic() - started,
                   passed=len(runs) == 2 and all(not r['exit_code'] and not r['timeout'] for r in runs)
                   and before == after,
                   actual_level='L0_STATIC_CANDIDATE_AND_SOFTWARE_QUALIFICATION',
                   board_release_allowed=False, real_capture='PENDING_REAL_INPUT')
    write_new(out / 'RECEIPT.json', receipt)
    print(json.dumps({key: receipt[key] for key in ('passed', 'source_unchanged', 'total_seconds')},
                     ensure_ascii=False))
    for index in range(len(runs)):
        for name in ('stdout.bin', 'stderr.bin'):
            print('command_' + str(index + 1) + '/' + name)
            print((out / ('command_' + str(index + 1)) / name).read_bytes().decode('utf-8', errors='replace'))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
