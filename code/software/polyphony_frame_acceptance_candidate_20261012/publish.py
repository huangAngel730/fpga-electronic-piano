"""Read-only Git verification and a complete offline handoff after ordinary push."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from deliver import verify

ROOT = HERE.parents[2]
DOC = ROOT / 'code/docs/hardware/polyphony_frame_acceptance_20261012'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out, gate = args.output.resolve(), args.gate.resolve()
    for path in (out, gate):
        path.relative_to(ROOT / 'code/output')
    if out.exists():
        raise ValueError('PUBLISH_REFUSE_OVERWRITE')
    out.mkdir(parents=True)
    steps = []

    def git(label, *arguments):
        argv = ['git'] + list(arguments)
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=60)
        (out / (label + '.stdout.txt')).write_bytes(result.stdout)
        (out / (label + '.stderr.txt')).write_bytes(result.stderr)
        steps.append(dict(label=label, argv=argv, exit_code=result.returncode,
                          stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr)))
        (out / 'progress.json').write_text(json.dumps(steps, indent=2) + '\n', encoding='utf-8', newline='\n')
        if result.returncode:
            raise ValueError('GIT_READ_FAILED:' + label)
        return result.stdout.decode('utf-8').strip()

    try:
        head = git('head', 'rev-parse', 'HEAD')
        tree = git('tree', 'rev-parse', 'HEAD^{tree}')
        branch = git('branch', 'branch', '--show-current')
        remote = git('remote', 'ls-remote', 'origin', 'refs/heads/develop').split()[0]
        clean = git('status', 'status', '--short') == ''
        gated = json.loads((gate / 'receipt.json').read_text(encoding='utf-8'))
        if (head != remote or branch != 'develop' or not clean or gated['tree'] != tree
                or gated['status'] != 'EXACT_INDEX_NINE_GATES_PASS' or gated['exit_code']):
            raise ValueError('NOT_EXACT_CLEAN_GATED_REMOTE')
        seal = verify(base64.decodebytes((DOC / 'EVIDENCE_20261012/SOFTWARE_SEAL.zip.b64').read_bytes()))
        receipt = dict(status='GATED_DEVELOP_PUSH_VERIFIED', commit=head, remote_develop=remote,
                       tree=tree, clean=clean, branch=branch, gate=str(gate), seal=seal,
                       M2_notice='awaiting_user_forward_not_delivered', steps=steps,
                       level='L0/L1_SOFTWARE_ONLY', RTL_verified=False, math_verified=False,
                       physical_verified=False, admission_verified=False, complete=False)
        (out / 'git_delivery.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
        notice = ('M2，N32 接入前帧事务独立软件材料已普通推送 develop：' + head + '。'
            '11 份完整合成正例通过，六份保持原输入/END 的单目标坏观察均退出 1 并命中指定诊断；'
            '手写语义/格式自检及缺文件、拒覆盖通过。源码和输入前后 SHA 不变，'
            '执行快照、全量轨迹、原 stdout/stderr/退出码、300 秒总/90 秒步收据、只读来源及封存齐套；'
            '精确树仓库九门禁通过、远端一致。仅 L0/L1 合成事务软件，PCM 是外部 payload，'
            'clip 为拟议元数据，epoch/接收门为软件注记；不签现有 RTL 或 N32 声音数学、资源准入/STA。'
            '未重跑旧 C/数学阶段，无新 RTL/EDA/设备操作，未改共享表。请复核拟议合同后用于后续隔离适配；'
            '完整 T060/T061 保持 PARTIAL。详见完整离线 ZIP。待用户转发，尚未送达。\n')
        (out / 'M2_NOTICE.txt').write_text(notice, encoding='utf-8', newline='\n')
        paths = list(HERE.glob('*.py')) + [p for p in DOC.rglob('*') if p.is_file()]
        paths += [p for p in gate.glob('*') if p.is_file()]
        paths += [p for p in out.glob('*') if p.is_file()]
        files = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
        manifest = {name: dict(bytes=len(raw), sha256=sha(raw)) for name, raw in files.items()}
        archive_path = out / 'M3_N32_FRAME_SOFTWARE_M2_20261012.zip'
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(files.items()):
                archive.writestr(name, raw)
            archive.writestr('FORWARD_MANIFEST.json', json.dumps(manifest, indent=2).encode('utf-8'))
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() or len(archive.namelist()) != len(files) + 1:
                raise ValueError('FORWARD_CRC_OR_MEMBERS')
            for name, item in manifest.items():
                if sha(archive.read(name)) != item['sha256']:
                    raise ValueError('FORWARD_MEMBER_SHA')
        result = dict(status='OFFLINE_FORWARD_VERIFIED', commit=head, file=str(archive_path),
                      bytes=archive_path.stat().st_size, sha256=sha(archive_path.read_bytes()), members=len(files)+1)
        (out / 'forward_receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(result))
    except Exception as error:
        (out / 'failure.json').write_text(json.dumps(dict(error=str(error), steps=steps), indent=2), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
