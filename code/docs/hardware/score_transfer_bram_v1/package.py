"""Seal exact RAM evidence and produce a single post-push M2 transfer ZIP."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
NEW_PATHS = ('code/rtl/input/score_transfer_bram_candidate',
             'code/tb/input/score_transfer_bram_candidate',
             'code/software/score_transfer_bram_test_candidate',
             'code/docs/hardware/score_transfer_bram_v1')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('mode', choices=('seal', 'verify', 'finalize'))
    cli.add_argument('--output', type=Path)
    cli.add_argument('--gate', type=Path)
    args = cli.parse_args()
    sealed = DOC / 'EVIDENCE_20261010'
    if args.mode in ('seal', 'verify'):
        if args.mode == 'verify':
            raw = base64.b64decode((sealed/'evidence.zip.b64').read_bytes(), validate=True)
            manifest = json.loads((sealed/'manifest.json').read_text(encoding='utf-8'))
            if sha(raw)!=manifest['zip_sha256']:
                raise ValueError('archive SHA mismatch')
            import io
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if set(z.namelist())!=set(manifest['members']):
                    raise ValueError('member identity')
                for name, item in manifest['members'].items():
                    value=z.read(name)
                    if sha(value)!=item['sha256'] or len(value)!=item['bytes']:
                        raise ValueError('member SHA: '+name)
            print('PASS_SEALED_RAM_EVIDENCE',len(manifest['members'])); return
        output=args.output.resolve()
        output.relative_to(ROOT/'code/output')
        output.mkdir(parents=True,exist_ok=False)
        sim=ROOT/'code/output/m3_score_bram_final_20261010_01'
        syn=ROOT/'code/output/m3_score_bram_syn_20261010_01'
        sr=json.loads((sim/'receipt.json').read_text(encoding='utf-8'))
        if sr['status']!='PASS_MODULE_SIMULATION_ONLY':
            raise ValueError('simulation not passed')
        for rel,digest in sr['input_sha256'].items():
            if sha((ROOT/rel).read_bytes())!=digest:
                raise ValueError('executed source changed: '+rel)
        selected={}
        for relative in NEW_PATHS:
            for path in (ROOT/relative).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts and 'EVIDENCE_20261010' not in path.parts:
                    selected[path.relative_to(ROOT).as_posix()]=path
        path=ROOT/'code/scripts/run_m3_score_transfer_bram_acceptance.py'
        selected[path.relative_to(ROOT).as_posix()]=path
        for relative in sr['input_sha256']:
            path=ROOT/relative
            selected[relative]=path
        # Keep all actual failed development commands/logs and complete captures.
        folders=[sim,syn]+[ROOT/f'code/output/m3_score_bram_dev_20261010_0{i}' for i in (1,2,3)]
        folders+=[ROOT/'code/output/m3_score_bram_reset_dev_20261010_01',
                  ROOT/'code/output/m3_score_bram_review_20261010_02']
        for folder in folders:
            for path in folder.rglob('*'):
                if path.is_file() and 'work' not in path.parts and path.suffix not in ('.wlf',):
                    selected[path.relative_to(ROOT).as_posix()]=path
        intake=Path('E:/FPGA/GAOYUNFPGA/CallBack2')
        inputs=[intake/'M2_M3_阶段收口交接.md',intake/'M3_曲谱存储BSRAM优化_任务单_2026-10-09.md']
        for name in ('M2_T060_A2_96b364a_复核与收口条件_20261009', 'M2_T061_B0_41d2871_复核与B1条件_20261009'):
            inputs+=list((intake/name).glob('*.md'))
        for path in inputs:
            selected['received_callback/'+path.relative_to(intake).as_posix()]=path
        # Existing T060 completion evidence is a reference, not newly executed.
        for name in ('ROUTER_CLOSURE_20261010.md','M2_HANDOFF_ROUTER_20261010.md',
                     'ROUTER_EVIDENCE_MANIFEST_20261010.json'):
            path=ROOT/'code/docs/hardware/audio_math_acceptance_v1'/name
            selected['prior_T060_reference/'+name]=path
        members={name:dict(bytes=path.stat().st_size,sha256=sha(path.read_bytes()))
                 for name,path in sorted(selected.items())}
        target=output/'RAM_EVIDENCE.zip'
        with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
            for name,path in sorted(selected.items()):
                raw=path.read_bytes()
                if sha(raw)!=members[name]['sha256']:
                    raise ValueError('source changed during seal')
                z.writestr(name,raw)
        with zipfile.ZipFile(target) as z:
            if z.testzip():
                raise ValueError('zip CRC')
        raw=target.read_bytes()
        manifest=dict(zip_sha256=sha(raw),zip_bytes=len(raw),members=members,
                      complete_task=False,M2_notification='待用户转发，尚未送达')
        sealed.mkdir(exist_ok=False)
        (sealed/'evidence.zip.b64').write_bytes(base64.b64encode(raw))
        dump(sealed/'manifest.json',manifest)
        dump(output/'receipt.json',manifest)
        print('SEALED',len(members),len(raw),sha(raw)); return
    # Only finalize after exact gate/clean commit/ordinary push have succeeded.
    output=args.output.resolve()
    output.relative_to(ROOT/'code/output')
    output.mkdir(parents=True,exist_ok=False)
    gate=args.gate.resolve()
    gr=json.loads((gate/'receipt.json').read_text(encoding='utf-8'))
    if gr['status']!='STAGED_TREE_9_GATES_PASS':
        raise ValueError('nine gates not passed')
    for item in gr['inputs_after']:
        if sha((ROOT/item['path']).read_bytes())!=item['sha256']:
            raise ValueError('post-gate input changed')
    def git(*command):
        return subprocess.check_output(['git',*command],cwd=ROOT,timeout=30).decode('utf-8').strip()
    head=git('rev-parse','HEAD'); tree=git('rev-parse','HEAD^{tree}')
    remote=git('ls-remote','origin','refs/heads/develop').split()[0]
    if head!=remote or tree!=gr['staged_tree'] or git('branch','--show-current')!='develop' or git('status','--porcelain'):
        raise ValueError('not exact gated clean pushed develop')
    manifest=json.loads((sealed/'manifest.json').read_text(encoding='utf-8'))
    notice=(f'M2，M3已读CallBack2阶段交接。T060路由最小补齐已在5f3c67e，旧B0问题及后续B1/B2a/B2b已交付，'
        f'没有重跑旧RTL/Gowin或自行关闭完整T060/T061。本次按五新路径完成曲谱同步RAM候选并推送develop：{head[:7]}。'
        '原线上协议、公开一拍读、双银行原子发布和非对齐分包保持；真实40MHz/115200 UART 731场景、710响应，'
        '约8905万次公开读、4次COMMIT同沿旧银行读、两项可编译RAM读/银行切换行为反例指定拒收，'
        'COPY/VERIFY/UART READ/发布边沿四项复位后真实上传恢复通过。'
        '唯一一次600秒有界模块综合用时66.78秒、退出0；正文八lane各1个BSRAM，模块总24个DPB、Register3373、LUT等价7211。'
        '但综合估算仅34.739MHz、Slack -3.786ns，request_session到reply[25]路径存在风险，不是40MHz时序通过。'
        '额度已用，不追加综合或擅自改源；请M2确认回包CRC长链分拍的最小修复方案及后续时序权限。'
        '实际层级XML和原生memory推断日志齐套，不以模块总数冒充正文映射。原工具/源/配置/产物SHA、stdout/stderr/exit和开发失败记录已封存，'
        '最终精确暂存树9门禁通过；不改生产/旧证据/共享状态，无PnR、STA、安装、串口、接线或烧录。'
        '请复核独立候选及T060有限收口，并由M2统一登记、决定正式接入与新整机STA；完整T059/T060/T061不自动关闭。'
        '\n\n待用户转发，尚未送达。\n')
    (output/'M2_通知_20261010.txt').write_text(notice,encoding='utf-8')
    result=dict(commit=head,remote_develop=remote,tree=tree,clean=True,
                evidence_zip_sha256=manifest['zip_sha256'],M2_notification='待用户转发，尚未送达')
    dump(output/'GIT_DELIVERY.json',result)
    target=output/'M3_曲谱RAM候选_交M2_20261010.zip'
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
        import io
        raw=base64.b64decode((sealed/'evidence.zip.b64').read_bytes(),validate=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as inner:
            for name in inner.namelist():
                z.writestr(name,inner.read(name))
        for path in output.iterdir():
            if path.is_file() and path!=target:
                z.write(path,path.name)
        for path in gate.iterdir():
            if path.is_file():
                z.write(path,'publish_gate/'+path.name)
    with zipfile.ZipFile(target) as z:
        if z.testzip():
            raise ValueError('final ZIP CRC')
    result['archive']=dict(path=str(target),bytes=target.stat().st_size,sha256=sha(target.read_bytes()))
    dump(output/'receipt.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
