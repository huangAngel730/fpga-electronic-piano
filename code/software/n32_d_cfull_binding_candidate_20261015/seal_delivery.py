"""Small static-binding handoff; large immutable originals stay external."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from run_acceptance import ROOT,ABCD,CFULL,RECEIPT,info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--history',action='append',default=[],type=Path,
                        help='Existing task-prefixed attempt to preserve unchanged (repeatable)')
    args=parser.parse_args();run,output=args.run.resolve(),args.output.resolve()
    for path in (run,output):
        if path.parent!=ROOT/'code/output' or not path.name.startswith('n32_d_cfull_binding_'):
            parser.error('require direct task-prefixed code/output path')
    histories=[]
    for value in args.history:
        path=value.resolve()
        if path.parent!=ROOT/'code/output' or not path.name.startswith('n32_d_cfull_binding_') or not path.is_dir():
            parser.error('history must be an existing task-prefixed direct child of code/output')
        if path in (run,output) or path in histories:
            parser.error('history must be distinct from run/output and other histories')
        histories.append(path)
    receipt=json.loads((run/'receipt.json').read_text(encoding='utf-8'))
    if receipt.get('passed') is not True or receipt.get('runner_exit')!=0:
        raise ValueError('STATIC_ACCEPTANCE_NOT_PASS')
    for path,before in receipt['before'].items():
        if receipt['after'].get(path)!=before or info(Path(path))!=before:
            raise ValueError('DELIVERY_SOURCE_IDENTITY_CHANGED: '+path)
    fixed={ABCD:'ba9e4f42d9aa5bb60c6d5122ae271fc58b3b9e7d27cca4caa48fd9740d85aa36',CFULL:'eac6e9371a96e91447a75d869d7e7a6dc76252fd89d6c8b621953a396a42c726'}
    attachments=[]
    for path,expected in fixed.items():
        actual=info(path)
        if actual['sha256']!=expected:raise ValueError('ORIGINAL_PACKAGE_CHANGED: '+str(path))
        attachments.append(dict(path=str(path),identity=actual,body_in_small_package=False,
                                required_for_independent_verify=True,transfer='User attaches ORIGINAL file body separately; SHA alone is insufficient'))
    output.mkdir(exist_ok=False);package=output/'N32_D_CFULL_STATIC_BINDING_DELIVERY.zip';members={}
    def add(archive,path,name):
        if name in members or path.is_symlink():raise ValueError('UNSAFE_OR_DUPLICATE_MEMBER: '+name)
        members[name]=info(path);archive.write(path,name)
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(HERE.iterdir()):
            if path.is_file() and path.suffix in ('.py','.json','.txt'):add(archive,path,'source/'+path.name)
        for path in sorted(run.rglob('*')):
            if path.is_file():add(archive,path,'actual_evidence/'+path.relative_to(run).as_posix())
        for index,history in enumerate(histories):
            for path in sorted(history.rglob('*')):
                if path.is_file():add(archive,path,'failure_history/'+str(index)+'_'+history.name+'/'+path.relative_to(history).as_posix())
        for path in (RECEIPT,RECEIPT.with_name('M2_REVIEW.md')):add(archive,path,'independent_anchors/'+path.name)
        handoff=ROOT/'code/build/138k_polyphony_resource/m3_n32_allocator_candidate_20261013/D_N32_R1_EXACT_HANDOFF_20261015.md'
        add(archive,handoff,'independent_anchors/'+handoff.name)
        archive.writestr('ORIGINAL_ATTACHMENTS.json',json.dumps(attachments,indent=2)+'\n')
        archive.writestr('MANIFEST.json',json.dumps(dict(schema=1,members=members,
            external_originals=attachments,historical_attempts=[str(path) for path in histories],scope='STATIC_BINDING_ONLY',resources='UNKNOWN',STA='NOT_RUN',
            T061_complete=False,EDA_calls=0,RTL_calls=0,device_calls=0),indent=2)+'\n')
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP_CRC_FAILED')
        for name,expected in members.items():
            raw=archive.read(name)
            if dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())!=expected:
                raise ValueError('SEALED_MEMBER_CHANGED: '+name)
    summary=dict(package=str(package),identity=info(package),members=len(members)+2,
                 external_originals=attachments,historical_attempts=[str(path) for path in histories],scope='STATIC_BINDING_ONLY',resources='UNKNOWN',STA='NOT_RUN',
                 T061_complete=False,EDA_calls=0,RTL_calls=0,device_calls=0,git_published=False)
    (output/'DELIVERY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    (output/'ORIGINAL_ATTACHMENTS.json').write_text(json.dumps(attachments,indent=2)+'\n',encoding='utf-8')
    text=('M2：M3本窗口完成独立D/C_FULL静态关联后继，原D/R02和C_FULL证据原件未改。\n'
          '四层ZIP CRC/成员/长度/SHA、D45项、25业务/include/ROM来源映射、独立top/wrapper及连续/reuse边界由新工具静态核对。\n'
          '正负例、实际prepare/verify双流/退出码及输入/源码/运行时前后SHA见小封存包；未执行任何包内脚本、checker、RTL或EDA。\n'
          '只申请静态关联限定复核；原D仍L0/L1准备、资源UNKNOWN/STA NOT_RUN，未自动重签原D、未授权综合，不升级生产N32/T061。\n'
          '本小包不重复塞入37MB/7.7MB原ZIP，用户须另附下列两个原文件本体，不能只发SHA：\n'
          + '\n'.join(a['path']+'\nSHA256 '+a['identity']['sha256'] for a in attachments)
          + '\n新包：'+str(package)+'\nSHA256 '+summary['identity']['sha256']
          + '\nGit提交/精确树门禁由主窗口发布后补充；本包本身未声明已推送。待用户转发，尚未送达。\n')
    (output/'M2_FORWARD.txt').write_text(text,encoding='utf-8')
    print(json.dumps(summary,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
