"""Seal local R05 handoff evidence; no functional execution."""
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
BASE = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/D/d3_repair_proposal_20261017'
OUT = BASE / 'HANDOFF_FINAL'


def identity(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def git(*args):
    return subprocess.check_output(['git', *args])


head = git('rev-parse', 'HEAD').decode().strip()
remote = git('rev-parse', 'origin/develop').decode().strip()
tree = git('rev-parse', 'HEAD^{tree}').decode().strip()
assert head == remote == '0cbb4a70dcf6e9c706780e705419fd93274e82e8'
assert not git('status', '--porcelain', '--untracked-files=no')
plan = json.loads((BASE / 'PUBLICATION_FILES.json').read_text(encoding='utf-8'))
snap = json.loads((BASE / 'GATE_R01/INPUTS_BEFORE.json').read_text(encoding='utf-8'))
changed = git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', head).decode().strip('\0').split('\0')
assert set(changed) == set(plan['paths'])
blobs = []
for path in plan['paths']:
    raw = git('show', head + ':' + path)
    assert identity(raw) == snap[path]
    assert raw == (ROOT / path).read_bytes()
    blobs.append({'path': path, **identity(raw)})
receipt = {
    'status': 'PASS', 'verified_utc': datetime.now(timezone.utc).isoformat(),
    'head': head, 'origin_develop_after_fetch': remote, 'tree': tree,
    'baseline': plan['current_baseline'], 'tracked_tree_clean': True,
    'changed_exactly_seven': True, 'committed_blobs_match_gate_inputs': blobs,
    'gate_scope': 'existing checkout, tracked baseline plus seven files; not a separate clean checkout',
    'new_D3_functional_runs': 0, 'new_Pro_or_EDA_runs': 0,
    'board_release_allowed': False, 'model_tokens_and_cost': 'UNKNOWN_NOT_EXPOSED',
    'delivery_to_M2': '待用户转发，尚未送达', 'exit_code': 0,
}
write_json(OUT / 'PUBLICATION_VERIFICATION.json', receipt)
message = f'''M2，你好。M3 五窗口本轮准备材料已汇合、自审，并按最新 R05 重新对齐。待用户转发，尚未送达。

已普通推送 develop：{head}
GitHub：https://github.com/huangAngel730/fpga-electronic-piano/commit/{head}
推送后重新 fetch，HEAD 与 origin/develop 同为该 SHA；树 {tree}，tracked clean。本次只新增 PUBLICATION_FILES.json 列明的七项交接文件，不改 RTL、入口实现、共享状态或任务看板。

当前入口为 R05_RECONCILIATION.md。已接受你在 9fe5779d / V0391 对旧 835 拍超期清理旁路的修复：RETURN/CANCEL/RESET 年龄严格 <833，消费仍为下一实际 833/834 拍 FRAME。M3 核原 ZIP 的 264 载荷 CRC/大小/SHA 一致。原包 SHA 为 2eb6f4182b3c3fff039ba1991bd916f7f8e4ca549ff487e38337c7d48d5272d6；M2 原执行 25 CLI=旧缺陷重现1次+修复后24项（8接受/16拒收），exit0/8.3402246秒，限定 L1。M3 没有重跑，不否定该已修结论。

唯一新增请求：请确认合法取消之后，D3 是否仍必须记录独立计划内直到 END 的每一 FRAME。新静态反例 R05_NEW_COUNTEREXAMPLE.json：req8 在1677请求，1712返回，2509取消（年龄832，满足现合同），省略FRAME2510、END2511；静态控制流可达结构接受。该例 NOT_RUN，不冒称已实测失败，也未判定违反当前限定交易合同。若要求全局帧覆盖，请冻结独立帧计划、最小后继及输入/预算；若不要求，请明确当前只签交易期限及已观察帧间节拍，完整帧覆盖不在签收范围。现 <833 合同不回退，原24项不重跑。

夜间1完成原件核对/汇合/新边界自审；2完成旧合同补丁文本；3完成monitor/B1/B2差异映射；4完成16项静态病例；5完成旧基线到件差额。原R02五窗口材料已原字节封存为 DELIVERY/M3_D3_R02_STATIC_REPAIR_PROPOSAL_20261017.zip（85974字节，42载荷，SHA ac943757a2a3938cf6126c968e04cdde9a89d4680c5daa19d4db730242fabf20）。其中旧未修状态、旧执行请求和旧合法性口径已被R05覆盖，不能直接执行旧补丁。

实际本轮 M3 等级 L0：没有新D3 CLI、Pro仿真、ModelSim、Gowin或设备轮次。仓库发布门禁单独执行 .\\code\\scripts\\check_repo.ps1：9/9 PASS，exit0，130.04699999999866秒；13380项输入前后不变，七项提交blob与门禁输入一致。它在现有checkout执行，并非另建干净checkout；门禁中的T007/T019不算新Pro/D3测试。原始stdout/stderr、调用/工具身份、输入快照和发布回执均在本交接包。

真实 Pro 完整基础仍 PARTIAL。最新来源材料已到件，但61字段中20既有模块口（仅4外层Pro）、9待M2导出、19待M1语义确认、13未实现；P7仍BLOCKED_EXECUTOR_GUARD。真实DUT/TX sidecar/黄金/同源绑定与B0实物电气仍按R04/R05接续；board_release_allowed=false，不启动N32。模型token/费用分项未暴露，记UNKNOWN，不记0。

失败历史原件及初稿纠正保留在历史ZIP；没有删除旧FAIL。请M2登记本次限定静态准备与范围请求，按职责决定上述新边界及后续执行许可；由M2更新共享状态和看板。本包交付不代表完整Pro或整机通过。

附件：M3_D3_R05_RECONCILED_HANDOFF_20261017.zip；其外置RECEIPT.json给出完整SHA和载荷核验结果。提交内R05四文件和历史ZIP与本附件逐字节一致。M2旧修复原ZIP在仓库已有路径，本附件不重复携带，以R05_RECONCILIATION_RECEIPT.json定位核验。
'''
(OUT / 'M2_FORWARD.md').write_text(message, encoding='utf-8', newline='\n')
files = [(ROOT / p, 'published/' + p) for p in plan['paths']]
files += [(p, 'gate/' + p.name) for p in sorted((BASE / 'GATE_R01').iterdir()) if p.is_file()]
for name in ['PRECOMMIT_VERIFICATION.json', 'PUBLICATION_TOOL_RECEIPTS.json', 'PUBLICATION_VERIFICATION.json', 'M2_FORWARD.md']:
    files.append((OUT / name, name))
files.append((BASE / 'coordinator/GATE_INVOCATION.json', 'gate/GATE_INVOCATION.json'))
files.append((Path(__file__), 'seal_handoff.py'))
manifest = {'files': [{'path': arc, **identity(p.read_bytes())} for p, arc in files]}
archive = OUT / 'M3_D3_R05_RECONCILED_HANDOFF_20261017.zip'
assert not archive.exists(), 'Do not overwrite a sealed handoff'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p, arc in files:
        z.write(p, arc)
    z.writestr('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(files) + 1
    for item in manifest['files']:
        assert identity(z.read(item['path'])) == {k: item[k] for k in ['bytes', 'sha256']}
sealed = {'status': 'PASS', 'archive': archive.name, **identity(archive.read_bytes()), 'payloads': len(files), 'crc_size_sha_match': True, 'commit': head, 'exit_code': 0, 'delivery_to_M2': '待用户转发，尚未送达'}
write_json(OUT / 'RECEIPT.json', sealed)
print(json.dumps(sealed, ensure_ascii=False))
