"""Seal desktop source, fresh actual evidence and unchanged real-input package."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from preview_model import ROOT,FROZEN

OLD_SHA='4529de965b76e70b6bbbfba02b33e86eff48afb4a0307a51dd490e6660644eb0'
OLD_ZIP=ROOT/'code/output/score_midi_real_input_delivery_20261015_r01/REAL_MIDI_USER_PATH_DELIVERY.zip'


def identity(path):
    raw=Path(path).read_bytes()
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--history',nargs='*',type=Path,default=[])
    args=parser.parse_args()
    run,output=args.run.resolve(),args.output.resolve()
    for path in (run,output):
        if path.parent!=ROOT/'code/output' or not path.name.startswith('score_midi_desktop_'):
            parser.error('require task-prefixed direct child of code/output')
    histories=[path.resolve() for path in args.history]
    for path in histories:
        if path.parent!=ROOT/'code/output' or not path.name.startswith('score_midi_desktop_') or not path.is_dir():
            parser.error('history must be existing task evidence under code/output')
    receipt=json.loads((run/'receipt.json').read_text(encoding='utf-8'))
    if not receipt.get('passed') or receipt.get('runner_exit')!=0:
        raise ValueError('ACTUAL_DESKTOP_ACCEPTANCE_NOT_PASS')
    for name,before in receipt['before'].items():
        if before!=receipt['after'].get(name) or identity(Path(name))!=before:
            raise ValueError('SOURCE_INPUT_DEPENDENCY_CHANGED: '+name)
    if identity(OLD_ZIP)['sha256']!=OLD_SHA:
        raise ValueError('OLD_REAL_PACKAGE_IDENTITY_CHANGED')
    output.mkdir(exist_ok=False)
    package=output/'DESKTOP_MIDI_DELIVERY.zip'
    members={}
    def add(archive,path,name):
        path=Path(path)
        if path.is_symlink() or not path.is_file():raise ValueError('REGULAR_FILE_REQUIRED: '+str(path))
        if name in members:raise ValueError('DUPLICATE_PACKAGE_MEMBER: '+name)
        members[name]=identity(path)
        archive.write(path,name)
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(HERE.iterdir()):
            if path.is_file() and path.suffix in ('.py','.txt'):
                add(archive,path,'source/'+path.name)
        for path in sorted(run.rglob('*')):
            if path.is_file():add(archive,path,'actual_evidence/'+path.relative_to(run).as_posix())
        for directory in histories:
            for path in sorted(directory.rglob('*')):
                if path.is_file():
                    add(archive,path,'history_evidence/'+directory.name+'/'+path.relative_to(directory).as_posix())
        for path in sorted(FROZEN):add(archive,path,'frozen_dependencies/'+path.relative_to(ROOT).as_posix())
        fixture=ROOT/'code/software/score_midi_import_candidate_20261014/midi_fixtures.py'
        add(archive,fixture,'frozen_dependencies/'+fixture.relative_to(ROOT).as_posix())
        real=ROOT/'code/software/score_midi_real_input_acceptance_20261015'
        for name in ('SOURCE_RIGHTS.txt','inputs/MIDI_sample_2018-03-21.mid','inputs/charge.mid','inputs/beatscribe_README_original.txt'):
            add(archive,real/name,'real_originals/'+name)
        add(archive,OLD_ZIP,'prior_real_delivery/REAL_MIDI_USER_PATH_DELIVERY.zip')
        manifest=dict(schema=1,scope='Desktop offline user-path plus exact prior real CC0 evidence',
                      old_real_zip_sha256=OLD_SHA,members=members,native_picker_tested=False,
                      hardware_pass_claim=False,serial_calls=0,network_calls=0)
        archive.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP_CRC_FAILED')
        for name,expected in members.items():
            raw=archive.read(name)
            if dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())!=expected:
                raise ValueError('SEALED_MEMBER_MISMATCH: '+name)
    summary=dict(package=str(package),identity=identity(package),member_count=len(members)+1,
                 run_receipt=identity(run/'receipt.json'),old_real_zip_sha256=OLD_SHA,
                 status='DESKTOP_OFFLINE_DELIVERY_SEALED',native_picker_tested=False,
                 hardware_pass_claim=False,git_published=False)
    (output/'DELIVERY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    message=('M2：M3本窗口完成本地MIDI桌面离线导入/严格预览/主动确认导出候选。\n'
             '实际结果、正负例、Tk按钮/树行smoke及输入/源码/依赖前后SHA见封存原件。\n'
             '真实GolhaMedia CC0原文件44事件/末384000样本；charge.mid原件meta0x54明确拒收。\n'
             'Type1多轨/变速/取整/容量边界用合成开发夹具，不冒称真实多轨歌曲通过。\n'
             '自动Tk smoke使用注入chooser/confirm，不是人工Windows原生picker验收；不联网/串口/播放，无FPGA ACK或已发声结论。\n'
             '原真实补验ZIP4529de...完整原字节内附，旧失败和新原日志均保留。\n'
             '本包尚未Git发布；发布提交与精确树门禁由主窗口另行补充。请限定复核软件交付，不升级硬件状态。\n'
             '包：'+str(package)+'\nSHA256：'+summary['identity']['sha256']+'\n待用户转发，尚未送达。\n')
    (output/'M2_FORWARD.txt').write_text(message,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
