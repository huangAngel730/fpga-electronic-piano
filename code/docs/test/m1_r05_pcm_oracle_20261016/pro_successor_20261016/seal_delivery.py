"""Seal this task and exact read-only references; verify every ZIP member."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
MODEL = REPO / 'code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016'
OUTPUT = Path('D:/嵌赛/高云二/拓展/20_M1_Pro四声算法准备_20261016')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    static_path = HERE / 'STATIC_VERIFICATION_R01.json'
    static = json.loads(static_path.read_text(encoding='utf-8'))
    if static['status'] != 'PASS':
        raise ValueError('STATIC_CHECK_NOT_PASS')
    receipt = json.loads((HERE / 'FINAL_RECEIPT.json').read_text(encoding='utf-8'))
    if receipt['publication']['committed'] or receipt['publication']['pushed']:
        raise ValueError('UNEXPECTED_PUBLICATION_CLAIM')
    frozen = json.loads((HERE / 'A0/SOURCE_FREEZE.json').read_text(encoding='utf-8'))
    payload, roles = {}, {}

    def add(path, role):
        relative = path.relative_to(REPO).as_posix()
        name = 'repo/' + relative
        raw = path.read_bytes()
        if name in payload and payload[name] != raw:
            raise ValueError('PAYLOAD_COLLISION:' + name)
        payload[name] = raw
        roles[name] = role

    for row in frozen['files']:
        path = REPO / row['path']
        if sha(path.read_bytes()) != row['sha256']:
            raise ValueError('REFERENCE_CHANGED:' + row['path'])
        add(path, 'READ_ONLY_EXISTING_REFERENCE_NOT_NEW_IMPLEMENTATION')
    new_count = 0
    for folder in (MODEL, HERE):
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                add(path, 'THIS_TASK_AUTHORIZED_NEW_CONTENT')
                new_count += 1
    # Proving link closure is read-only. External web and anchor links do not
    # assert local byte availability; relative artifact links must be present.
    links = 0
    for folder in (MODEL, HERE):
        for path in folder.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' in link or link.startswith('#'):
                    continue
                target = (path.parent / link.split('#', 1)[0]).resolve()
                if not target.is_file() or 'repo/' + target.relative_to(REPO).as_posix() not in payload:
                    raise ValueError('RELATIVE_LINK_NOT_IN_PACKAGE:' + str(path) + ':' + link)
                links += 1
    intro = (
        '# M1 Pro 四声基础：第17批离线软件原件\n\n'
        '入口：repo/code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016/README.md。\n'
        '本包包括本批两个授权子目录和A0所引用73份原件，只读来源按原仓库路径放在repo内，方便离线复核及新软件命令复现；没有把这些旧源另作本批实现。\n'
        '本批未提交/未推送，精确树九项门禁未执行；Pro真实数学仍PENDING_REAL_CAPTURE，board_release_allowed=false。\n'
        '解包后以repo为cwd，参考RUNS收据中的Python argv，将本机解释器和输出目录替换为实际值；已存在输出拒绝覆盖。\n'
        '运行新A1/B0软件即可；不要从本包启动旧专项、ModelSim、Gowin、EDA或板卡。源码冻结的Git blob核验仍需原Git对象，普通解压目录不是Git仓库。\n'
    ).encode('utf-8')
    payload['OPEN_ME.md'] = intro
    roles['OPEN_ME.md'] = 'PACKAGE_ENTRY'
    manifest = {'schema': 'M1_PRO_17_EXACT_MEMBER_MANIFEST_V1',
                'new_task_files': new_count, 'read_only_reference_files': len(frozen['files']),
                'members': [{'path': name, 'bytes': len(raw), 'sha256': sha(raw), 'role': roles[name]}
                            for name, raw in sorted(payload.items())]}
    manifest_raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    archive_path = OUTPUT / 'M1_Pro四声算法准备_20261016.zip'
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr(name, raw)
        archive.writestr('MEMBER_MANIFEST.json', manifest_raw)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None or len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError('ZIP_CRC_OR_DUPLICATE_MEMBER')
        if set(archive.namelist()) != set(payload) | {'MEMBER_MANIFEST.json'}:
            raise ValueError('ZIP_MEMBER_SET')
        for row in manifest['members']:
            raw = archive.read(row['path'])
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                raise ValueError('ZIP_MEMBER_CHANGED:' + row['path'])
        if archive.read('MEMBER_MANIFEST.json') != manifest_raw:
            raise ValueError('ZIP_MANIFEST_CHANGED')
    dump(OUTPUT / 'MEMBER_MANIFEST.json', manifest)
    verification = {'status': 'PASS', 'crc_all_members_readable': True,
                    'every_payload_member_size_and_sha_verified': True,
                    'member_count': len(payload) + 1, 'payload_member_count': len(payload),
                    'new_task_files': new_count, 'read_only_reference_files': len(frozen['files']),
                    'relative_markdown_links_verified': links,
                    'zip_file': archive_path.name, 'zip_bytes': archive_path.stat().st_size,
                    'zip_sha256': sha(archive_path.read_bytes()),
                    'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'new_content_pushed': False}
    dump(OUTPUT / 'ZIP_VERIFICATION.json', verification)
    shutil.copyfile(HERE / 'FINAL_RECEIPT.json', OUTPUT / 'FINAL_RECEIPT.json')
    shutil.copyfile(HERE / '晨间回执_待用户转发.md', OUTPUT / '完成回执与给M2_M3的待转发说明.md')
    dump(OUTPUT / 'PACKAGE_RECEIPT.json', dict(verification,
         status='OFFLINE_PREPARATION_SEALED_REAL_AND_PUBLICATION_PENDING',
         package_path=str(archive_path), notification='待用户转发，尚未送达'))
    print(json.dumps(verification, ensure_ascii=False))


if __name__ == '__main__':
    main()
