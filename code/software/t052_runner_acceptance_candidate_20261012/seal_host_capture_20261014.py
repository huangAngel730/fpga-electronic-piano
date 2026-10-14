"""Read and seal existing evidence; never launch HDL tools or checker."""
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'code/output'
PLAN = OUT / 'm3_t052_host_capture_plan_20261014_01'
RUN = OUT / 'm3_t052_host_capture_20261014_01'
PARENT = OUT / 'm3_t052_host_capture_parent_20261014_01'
DEST = OUT / 'm3_t052_host_capture_delivery_20261014_01'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def identity(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def verify(path, expected):
    actual = identity(path.read_bytes())
    assert all(actual[k] == expected[k] for k in actual), str(path)


def main():
    receipt = read(RUN / 'receipt.json')
    actual = read(RUN / 'actual_run_receipt.json')
    parent = read(PARENT / 'observation.json')
    verdict = read(RUN / 'check.stdout.bin')
    assert receipt['status'] == 'T052_128_WINDOW_PASS'
    assert verdict['status'] == 'RTL_CONTROL_WINDOW_PASS'
    assert parent['status'] == 'OBSERVED_ZERO_EXIT'
    assert actual['machine'] == 'LAPTOP-KSS1MRR7'
    assert actual['sources_before'] == actual['sources_after']
    assert actual['tools_before'] == actual['tools_after']
    assert len(actual['tools_before']) == 1014
    assert parent['sources_before'] == parent['sources_after']
    assert [s['label'] for s in receipt['steps']] == ['compile', 'run', 'check']
    for step in receipt['steps']:
        assert step['exit_code'] == 0 and not step['timed_out']
        assert step['elapsed_seconds'] < 90
        for stream in ('stdout', 'stderr'):
            verify(RUN / (step['label'] + '.' + stream + '.bin'), step[stream])
    for item in receipt['artifacts'].values():
        verify(Path(item['path']), item)
    for name, item in read(PARENT / 'completion.json')['files'].items():
        path = Path(name)
        if not path.is_absolute():
            path = PARENT / path
        verify(path, item)
    config = identity((PLAN / 'prepared/config.json').read_bytes())
    assert config['sha256'] == receipt['config_sha256']
    consumed = read(PLAN / 'prepared/consumed.json')
    assert consumed['config_sha256'] == config['sha256']
    for marker in ('outer_consumed.json', 'worker_entry_consumed.json'):
        assert (PLAN / marker).is_file()
    files = {}
    for folder in (PLAN, RUN, PARENT):
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name, expected in parent['sources_before'].items():
        path = Path(name)
        verify(path, expected)
        files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    source = Path(__file__).parent
    old = source / 't052_observer_repair_successor_20261014.py'
    new = source / 't052_host_capture_20261014.py'
    diff = ''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True), new.read_text(encoding='utf-8').splitlines(True), fromfile=old.name, tofile=new.name))
    files['HOST_CONTROLLER.diff'] = diff.encode('utf-8')
    for folder, name in (
        ('m3_t052_observer_repair_attempt09_failure_seal_20261014', 'T052_OBSERVER_REPAIR_ATTEMPT09_FAILURE.zip'),
        ('m3_t052_observer_repair_attempt10_failure_seal_20261014', 'T052_OBSERVER_REPAIR_ATTEMPT10_COMPILE_CRASH.zip'),
        ('m3_t052_environment_recovery_diag_plan_20261014_01', 'RESULT.zip'),
    ):
        path = OUT / folder / name
        files['prior_evidence/' + folder + '/' + name] = path.read_bytes()
    summary = {
        'status': 'CAPTURE_AND_CHECKER_PASS_PENDING_M2', 'T052_status': 'PARTIAL',
        'config': config, 'tool_count': len(actual['tools_before']),
        'source_count': len(actual['sources_before']), 'pre_post_sha_equal': True,
        'steps': [{k: s[k] for k in ('label', 'exit_code', 'elapsed_seconds', 'pid')} for s in receipt['steps']],
        'checker': verdict, 'review': 'Implementation window self-review; no reviewer messages sent.',
        'test_context': 'Prior preparation: 5 envelope tests passed against new controller; zero-tool verify passed. No checker rerun during sealing.',
        'boundary': 'No hardware/synthesis/timing validation. Audio math not rerun. No commit/push or shared status changes.',
    }
    files['SUMMARY.json'] = json.dumps(summary, ensure_ascii=False, indent=2).encode('utf-8')
    files['SHA256_INDEX.json'] = json.dumps({n: identity(b) for n, b in files.items()}, indent=2).encode('utf-8')
    DEST.mkdir(exist_ok=False)
    packet = DEST / 'T052_HOST_CAPTURE_EVIDENCE.zip'
    with zipfile.ZipFile(packet, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    with zipfile.ZipFile(packet) as archive:
        assert archive.testzip() is None
        for name, data in files.items():
            assert archive.read(name) == data
    packet_id = identity(packet.read_bytes())
    handoff = (
        'M2：T052 新正式采集已通过，待你复核签收；当前仍保持 PARTIAL。\n'
        '机器 LAPTOP-KSS1MRR7；经正式批准在沙箱外执行，全新 config/输出/三层消费标记。\n'
        '本批 compile / VVP / checker 各调用一次，均退出 0；128 沿 checker=RTL_CONTROL_WINDOW_PASS。\n'
        '7 项输入与 1014 项工具身份前后 SHA 一致；旧失败及 compile-only VVP 均未运行。\n'
        '耗时 compile=0.078s，VVP=0.016s，checker=0.594s；各限90s，外层限300s。\n'
        '四份 capture、原始 stdout/stderr、实际 argv/cwd/环境/退出码、父子收据、SHA 清单及消费标记均在附件。\n'
        '故障对照支持与受限执行环境有关，不证明某个 DLL 是唯一根因；未修改系统或冻结 DUT/ROM/plan。\n'
        '实现窗口已自审，未向审核对话发消息；未提交/推送，未改任务看板或当前状态。\n'
        '请依据附件实际结果决定签收；未进行综合、时序或上板验证。待用户转发，尚未送达。\n'
        f'Config SHA256: {config["sha256"]}\n'
        f'Packet: {packet}\nPacket SHA256: {packet_id["sha256"]}\n'
    )
    (DEST / 'RESULT_AND_M2_HANDOFF.txt').write_text(handoff, encoding='utf-8')
    (DEST / 'SUMMARY.json').write_bytes(files['SUMMARY.json'])
    print(json.dumps({'packet': str(packet), **packet_id, 'status': summary['status']}))


if __name__ == '__main__':
    main()
