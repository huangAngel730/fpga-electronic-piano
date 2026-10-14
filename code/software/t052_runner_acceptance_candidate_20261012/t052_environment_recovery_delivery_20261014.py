"""Read-only comparison of actual evidence; emit a disabled capture proposal."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'code/output/m3_t052_observer_repair_prepare_20261014_10'
PLAN = ROOT / 'code/output/m3_t052_environment_recovery_diag_plan_20261014_01'
RUN = ROOT / 'code/output/m3_t052_environment_recovery_diag_run_20261014_01'
OUT = ROOT / 'code/output/m3_t052_environment_recovery_handoff_20261014_01'


def read(path):
    return json.loads(path.read_bytes())


def ident(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write(name, value):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def main():
    old = read(OLD / 'prepared/actual_once/receipt.json')
    new = read(RUN / 'receipt.json')
    parent = read(Path(str(RUN) + '_parent') / 'observation.json')
    completion = read(Path(str(RUN) + '_parent') / 'completion.json')
    config = read(PLAN / 'config.json')
    manifest = read(OLD / 'prepared/manifest.json')
    result = read(PLAN / 'RESULT.json')
    assert old['steps'][0]['argv'] == new['steps'][0]['argv']
    assert old['steps'][0]['exit_code'] == 3221225477
    assert new['steps'][0]['exit_code'] == parent['exit_code'] == 0
    assert new['status'] == 'COMPILE_ONLY_PASS_NOT_RUN'
    assert len(new['steps']) == 1 and not new['artifact_executed']
    assert new['tools_before'] == new['tools_after']
    assert len(new['tools_after']) == 1014
    assert new['sources_before'] == new['sources_after']
    assert new['work_inputs_before'] == new['work_inputs_after']
    assert parent['sources_before'] == parent['sources_after']
    for path, expected in completion['files'].items():
        assert ident(Path(path)) == expected, path
    differences = {k: {'old': old['environment'].get(k), 'new': v}
                   for k, v in new['environment'].items()
                   if old['environment'].get(k) != v}
    assert set(differences) == {'TEMP', 'TMP'}
    assert set(old['environment']) == set(new['environment'])
    for name, item in manifest['tools'].items():
        actual = new['tools_after'][name]
        assert all(item[k] == actual[k] for k in ('bytes', 'sha256'))
    assert ident(PLAN / 'RESULT.zip') == result['package_identity']
    with zipfile.ZipFile(PLAN / 'RESULT.zip') as archive:
        assert archive.testzip() is None
        for name, expected in json.loads(archive.read('MANIFEST.json')).items():
            raw = archive.read(name)
            assert {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} == expected
    OUT.mkdir(parents=True, exist_ok=False)
    proposal = {
        'schema': 'T052_CAPTURE_PERMISSION_PROPOSAL_V1', 'approved': False,
        'status': 'DRAFT_REQUIRES_NEW_FORMAL_CAPTURE_PERMISSION',
        'machine': 'LAPTOP-KSS1MRR7',
        'execution_environment': 'exec_command require_escalated; private Job supervision',
        'diagnostic_config_sha256': result['config_sha'],
        'diagnostic_package': result['package_identity'],
        'frozen_manifest': {'path': str(OLD / 'prepared/manifest.json'),
                            **ident(OLD / 'prepared/manifest.json')},
        'sources': manifest['sources'], 'plan': manifest['plan'], 'calendar': manifest['calendar'],
        'tools': manifest['tools'],
        'compile_argv': manifest['compile_argv'], 'run_argv': manifest['run_argv'],
        'calls': {'compile': 1, 'run': 1, 'check': 1, 'gowin': 0},
        'budgets_seconds': {'compile': 90, 'run': 90, 'check': 90, 'outer_total': 300},
        'automatic_retries': 0,
        'new_output': str(ROOT / 'code/output/m3_t052_host_capture_20261014_01'),
        'new_marker': str(ROOT / 'code/output/m3_t052_host_capture_plan_20261014_01/consumed.json'),
        'execution_config': 'must be freshly prepared and frozen in actual host environment before launch',
        'artifact_rule': 'VVP may execute only the new successful compile artifact from this capture; diagnostic and failed VVP prohibited',
        'T052_complete': False,
    }
    write('FORMAL_CAPTURE_PROPOSAL.json', proposal)
    write('COMPARISON.json', {
        'old_compile': old['steps'][0], 'new_compile': new['steps'][0],
        'environment_differences': differences, 'same_argv': True,
        'same_tools': 1014, 'source_and_work_snapshots_stable': True,
        'parent_completion_files_verified': len(completion['files']),
        'diagnostic_package': result, 'formal_capture_executed': False,
        'conclusion': 'Host execution succeeds; evidence supports restricted-environment association, not a unique DLL root cause',
    })
    text = '''T052 环境恢复实际结果（2026-10-14）

同一 T052 _10 输入、Icarus 编译参数及 1014 项工具身份，经正式审批的沙箱外
compile-only 对照通过：compile 0.078 秒退出 0，父监督 1.391 秒退出 0。
原沙箱内 compile 5.141 秒退出 3221225477 / 0xC0000005。
显式环境仅 TEMP/TMP 随全新目录改变，PATH、IVERILOG_ROOT 和系统字段保持。
全部输入、工作副本、工具前后 SHA 相等；父监督 completion 全量文件核验通过。
诊断总工具调用 compile=1，VVP=0，checker=0，Gowin=0。诊断产物未执行。

可行处理方式已验证：T052 后续执行通过 exec_command require_escalated 正式
审批使用沙箱外环境，保留私有 Job 监督、单次消费、失败即停和有界预算。
证据仅支持故障与受限执行环境相关，不证明某 DLL 为唯一根因。
未改业务 RTL、系统设置、服务或安全软件，未重启，旧失败原件保持。

RESULT.zip 位于 ../m3_t052_environment_recovery_diag_plan_20261014_01/。
SHA256: 9ffdad089285d4bd007c32a8da698514c5734e9f9be46400f51992f07e3c0a9d
config SHA256: 8907b1b05a52ad3fcc043902b5dd5ab7b5613c6fe02aae2e4b91649da1d6b277

给 M2 的申请（待用户转发，尚未送达）：
请复核本次 compile-only 对照证据，批准 FORMAL_CAPTURE_PROPOSAL.json 所列
同机同输入同工具的一次全新 compile -> 128沿 VVP -> checker 正式采集。
每步骤90秒、总300秒、失败即停、无重试；仅运行本轮成功编译的新产物。
新实际 config 在正式沙箱外环境准备并冻结；旧失败和诊断 .vvp 不复用。
本草案 approved=false，不是已签许可。T052 保持 PARTIAL，正式 capture 尚缺。

当前改动未提交、未推送。实际验证仅编译诊断；无仿真、综合、STA、上板结论。
'''
    with (OUT / 'RESULT_AND_M2_REQUEST.txt').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
    print(json.dumps({'status': 'DIAGNOSTIC_VERIFIED_CAPTURE_PROPOSAL_DISABLED',
                      'handoff': str(OUT), 'proposal_sha256': ident(OUT / 'FORMAL_CAPTURE_PROPOSAL.json')['sha256']}))


if __name__ == '__main__':
    main()
