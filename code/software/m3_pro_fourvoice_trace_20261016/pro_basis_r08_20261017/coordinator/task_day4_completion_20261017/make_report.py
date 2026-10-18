"""Metadata-only consolidated result and manual M2 handoff text."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
DOC = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/task_day4_completion_20261017'
OUT = ROOT / 'code/output/m3_c9_complete_d4_20261017'


def ident(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    ledger = load(DOC / 'CONSUMPTION.json')
    preflight = load(DOC / 'PREFLIGHT.json')
    for desc in preflight['old_consumption_identities']:
        assert ident(ROOT / desc['path']) == desc, 'OLD_CONSUMPTION_CHANGED'
    matched, failures, receipts = {}, [], []
    for run in ledger['runs']:
        receipt = load(ROOT / run['receipt']['path'])
        receipts.append({**run, 'raw_stdout': ident(ROOT / run['output'] / 'stdout.raw'),
                         'raw_stderr': ident(ROOT / run['output'] / 'stderr.raw')})
        for item in receipt['results']:
            key = item['component'] + ':' + item['id']
            if item['assertion'] == 'MATCHED':
                assert key not in matched, 'PASSED_CASE_RERUN'
                matched[key] = item
            else:
                failures.append({'key': key, 'error': item.get('error'), 'run': run['output']})
    counts = Counter(item['component'] for item in matched.values())
    old = sum(count for key, count in counts.items() if key.startswith('OLD_'))
    new = sum(count for key, count in counts.items() if key.startswith('NEW_'))
    result = {'schema': 'M3_TASK_DAY4_C9_COMPLETION_RESULT_V1',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'baseline': preflight['head'],
        'status': ledger['status'], 'scope': 'OFFLINE_SOFTWARE_COMPLETION_ONLY',
        'matched_old_previously_unrun': old, 'old_original_case_count': 75,
        'matched_new_seams': new, 'matched_total': len(matched), 'by_component': dict(counts),
        'remaining_case_keys': ledger['remaining_case_keys'], 'failure_history': failures,
        'runs': receipts, 'initial_consumed': ledger['initial_consumed'],
        'repair_consumed': ledger['repair_consumed'], 'repair_maximum': 3,
        'total_actual_group_seconds': sum(run['elapsed_s'] for run in ledger['runs']),
        'token_consumption': 'Per-task/member token totals are not exposed by this environment; no account-wide percentage is attributed to this task.',
        'per_case_versions': 'Each matched assertion is bound to its own frozen run version. Unaffected passed cases are not replayed after targeted repairs; no claim of one complete final-version rerun.',
        'old_204_replayed': False, 'old_consumption_verified_unchanged': preflight['old_consumption_identities'],
        'source_loading': 'FROZEN_PY_BYTES_NO_PYC', 'candidate_subprocesses': 0,
        'Pro_HDL_EDA_device_runs': 0, 'N32_new_work': False, 'R10_resumed': False,
        'software_changes': ['C9 72+3=75 same-version application with exact tool/window/argv/output identities',
            'streaming complete74 envelope CSV and explicit61+TX ledger projection',
            'same single R6-5 FRAME_PLAN generator; calendar and C9 TX/serial consumers',
            'streaming >64MiB original A and B companion files',
            'mechanical M1 math input/history bundle; no observed PCM used as golden',
            'capture/source/reset/window/finish provenance and runnable PREPARE/PROCESS_CAPTURE chain'],
        'integration_boundary': 'New end-to-end positive is an explicitly synthetic idle7-row file path; separate serial cases exercise complete stereo words and HOLD/ID0. Neither is a real C9 simulation.',
        'pending_external': {'M1': ['independent accepted/apply plan association', 'supported arithmetic profile and independent PCM24/ID/clip golden results'],
            'M2': ['exact C9 first HDL execution admission and trusted executor/dynamic dependency identity',
                   'audio_stable implementation/policy', 'actual Pro part/PLL/CST/SDC, PnR/STA/recovery/removal/CDC and matching new .fs/recovery'],
            'physical_owner': ['same-board Core/Dock/chip/version and Bank/MIDI/ground/audio electrical originals',
                               'instruments/common timebase and same-session raw digital/analog captures',
                               'precise one-SRAM permission plus safe real hardware conditions']},
        'NoteOn_erratum': 'Already M1 confirmed and M2 accepted L0; E allocation, H first later CTRL_ON&&cmd_ready, C=H+1 absent reset, earliest E+2. No new behavior claim.',
        'overall_Pro_task': 'PARTIAL_PENDING_REAL_EXECUTION_MATH_AND_PHYSICAL_EVIDENCE',
        'M2_delivery': '待用户转发，尚未送达', 'real_verified': False,
        'math_verified': False, 'board_release_allowed': False}
    with (DOC / 'RESULT.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    text = f'''M3 task-day4 旧任务剩余项补齐回执（待用户转发，尚未送达）

基线 {preflight['head']}。本轮仅补齐已列旧任务离线软件差额，R10未恢复，N32未启动，原已签源码/失败原件/消费台账保留。
新 TASK_DAY4_REMAINDER_SW：原未执行 {old}/75 项及本轮新增 {new} 项断言匹配；状态 {ledger['status']}。初组消费 {ledger['initial_consumed']}/1，定向修复 {ledger['repair_consumed']}/3，实际组计时 {result['total_actual_group_seconds']:.6f} 秒。运行逐次命令、退出码、原始stdout/stderr及失败史见 RESULT.json、CONSUMPTION.json 与封存包中的 code/output/m3_c9_complete_d4_20261017。

新增实现：C9 72+driver/observer/TB=75同版申请；完整74字段流式CSV及61+TX显式派生账本；唯一R6-5 FRAME_PLAN到日历/TX/串行；机械M1数学输入/FX/advance/apply全历史；同capture/reset/独立窗口/finish来源校验；PREPARE不要求首次采集前已有trace。真实申请绑定capture/stop/finish/MIDI，合成例的应用窗口另列而不冒充真实准入。

实际等级：限定纯文件软件。整链正例是明确标记的7行合成空闲窗口；串行专例另验完整立体声字、HOLD与ID0。数学黄金仍缺，PCM未当期望；未知/尾段/独立选择策略继续PENDING。新Pro HDL、EDA、设备执行均0，未签DIGITAL_VERIFIED或板测。

请M2按精确新源码/原件复核软件交付并更新状态/看板；对申请中精确C9工具/源/TB/driver/observer/输入/窗口/argv/cwd/env/预算/输出决定首次HDL准入与可信执行器，不能恢复旧消费或把纯Pythonguard当HDL许可。M1仍需独立数学profile/plan关联/黄金输出，M2仍需audio_stable及同版STA/物理交付；实物/仪器/一次SRAM条件见RESULT.json精确清单。NoteOn文字已由既有M1/M2回执限定关闭，不重复申请。

发布提交、九项门禁与远端核同追加于 PUBLICATION.json；封存原件入口 DELIVERY/ARCHIVE_RECEIPT.json。所有路径/bytes/SHA与CRC逐件核对，不能只凭摘要签真实通过。
'''
    (DOC / 'FORWARD_TO_M2.txt').write_text(text, encoding='utf-8', newline='\n')
    (DOC / 'RESULT.md').write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'status': ledger['status'], 'old': old, 'new': new,
                      'remaining': len(ledger['remaining_case_keys']), 'failures_preserved': len(failures)}))


if __name__ == '__main__':
    main()
