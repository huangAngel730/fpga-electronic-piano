"""Freeze this night's read-only inputs and existing tool identities."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/T0'
TASK = Path('E:/FPGA/GAOYUNFPGA/night_task/10.17/M1_M2_M3_Pro夜间任务与并行窗口_20261016')


def identity(path):
    path = Path(path)
    if not path.is_file():
        return {'path': str(path), 'status': 'UNKNOWN_MISSING'}
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size,
            'sha256': digest.hexdigest()}


def execute(label, argv):
    start = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(argv, cwd=ROOT, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=15, check=False)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
        error = None
    except (OSError, subprocess.TimeoutExpired) as exc:
        stdout = getattr(exc, 'stdout', None) or b''
        stderr = getattr(exc, 'stderr', None) or b''
        code, error = None, repr(exc)
    logs = []
    for stream, data in [('stdout', stdout), ('stderr', stderr)]:
        file = OUT / (label + '.' + stream + '.txt')
        file.write_bytes(data)
        logs.append(identity(file))
    return {'argv': argv, 'cwd': str(ROOT), 'start_utc': start,
            'end_utc': datetime.now(timezone.utc).isoformat(),
            'exit_code': code, 'error': error, 'streams': logs}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    inputs = [ROOT / p for p in [
        'AGENTS.md', 'code/AGENTS.md', 'code/rtl/input/AGENTS.md',
        'code/docs/协作入口.md', 'code/docs/任务看板.md', 'code/docs/当前状态.md',
        'code/docs/三人开工任务说明.md', 'code/docs/M3_完赛任务单_2026-10-15.md',
        'code/docs/138K四声部后续集成任务总览_2026-10-15.md',
        'code/docs/模块接口规范.md', 'code/rtl/audio_out/i2s_tx.sv',
        'code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py',
        'code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/NIGHT_PLAN_20261017.md']]
    inputs.extend(TASK / p for p in [
        'MANIFEST.txt', 'M3_夜间五小时_Pro四声基础_2026-10-16.md',
        'M3_并行拓展双滑块窗口_2026-10-16.md', '夜间任务通用执行规范.md'])
    commands = [execute('python_version', [sys.executable, '--version']),
                execute('head', ['git', 'rev-parse', 'HEAD']),
                execute('origin', ['git', 'rev-parse', 'origin/develop']),
                execute('status', ['git', 'status', '--short'])]
    tools = [identity(sys.executable)]
    icarus = Path('E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy/bin')
    for name in ['iverilog', 'vvp']:
        file = icarus / (name + '.exe')
        tools.append(identity(file))
        if file.is_file():
            commands.append(execute(name + '_version', [str(file), '-V']))
    receipt = {'schema': 'M3_PRO_NIGHT_T0_V1', 'utc': datetime.now(timezone.utc).isoformat(),
               'machine': platform.node(), 'platform': platform.platform(),
               'environment_keys': sorted(os.environ), 'inputs': [identity(p) for p in inputs],
               'tools': tools, 'commands': commands, 'python_runtime': sys.version,
               'source_commit': 'ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0',
               'pro_dut_status': 'PENDING_PRO_SOURCE_OR_TRACE',
               'board_release_allowed': False,
               'fetch_attempt': {'command': ['git', 'fetch', 'origin'], 'exit_code': 1,
                                 'stderr': 'Recv failure: Connection was reset',
                                 'origin_not_refreshed': True},
               'quota': {'preflight_only': True, 'new_validation_rounds': 0,
                         'modelsim': 0, 'gowin': 0, 'device': 0}}
    (OUT / 'T0_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'T0_RECORDED', 'receipt': str(OUT / 'T0_RECEIPT.json'),
                      'pro_dut_status': receipt['pro_dut_status'],
                      'tools': tools, 'exits': [r['exit_code'] for r in commands]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
